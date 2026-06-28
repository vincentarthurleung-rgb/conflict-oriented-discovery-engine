import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path

from code_engine.cli.normalize import main as normalize_main
from code_engine.config.validation import validate_entity_registry
from code_engine.normalization.llm_candidate_proposer import LLMCandidateProposer
from code_engine.normalization.lexical import normalize_lexical_surface
from code_engine.normalization.registry import LocalBiomedicalRegistry
from code_engine.normalization.resolver import ResolverCascade
from code_engine.graph.ontology_alignment import clean_semantic_token


class NormalizationResolverCascadeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.resolver = ResolverCascade()

    def assert_relation(self, decision, predicate, object_id):
        self.assertIn((predicate, object_id), [(item.predicate, item.object) for item in decision.relations])

    def test_bdnf_name_and_alias(self):
        for term in ("BDNF", "brain-derived neurotrophic factor"):
            decision = self.resolver.resolve_entity(term)
            self.assertEqual(decision.canonical_id, "GENE:BDNF")
            self.assertEqual(decision.normalization_status, "resolved")

    def test_glua1_is_gene_subunit_not_ampa_complex(self):
        decision = self.resolver.resolve_entity("GluA1")
        self.assertEqual(decision.canonical_id, "GENE:GRIA1")
        self.assert_relation(decision, "subunit_of", "COMPLEX:AMPA_RECEPTOR")
        self.assertNotEqual(decision.canonical_id, self.resolver.resolve_entity("AMPA receptor").canonical_id)

    def test_ampa_receptor_is_complex(self):
        decision = self.resolver.resolve_entity("AMPA receptor")
        self.assertEqual(decision.canonical_id, "COMPLEX:AMPA_RECEPTOR")
        self.assertEqual(decision.entity_type, "receptor_complex")

    def test_glun2b_and_nmda_remain_distinct(self):
        subunit = self.resolver.resolve_entity("GluN2B")
        complex_entity = self.resolver.resolve_entity("NMDA receptor")
        self.assertEqual(subunit.canonical_id, "GENE:GRIN2B")
        self.assert_relation(subunit, "subunit_of", "COMPLEX:NMDA_RECEPTOR")
        self.assertEqual(complex_entity.canonical_id, "COMPLEX:NMDA_RECEPTOR")
        self.assertNotEqual(subunit.canonical_id, complex_entity.canonical_id)

    def test_salt_and_metabolites_preserve_relations(self):
        salt = self.resolver.resolve_entity("ketamine hydrochloride")
        nor = self.resolver.resolve_entity("norketamine")
        hydroxy = self.resolver.resolve_entity("hydroxynorketamine")
        self.assertEqual(salt.canonical_id, "CHEM:KETAMINE_HCL")
        self.assert_relation(salt, "salt_form_of", "CHEM:KETAMINE")
        self.assert_relation(nor, "metabolite_of", "CHEM:KETAMINE")
        self.assertNotEqual(hydroxy.canonical_id, "CHEM:KETAMINE")

    def test_phenotype_and_assay_types(self):
        outcome = self.resolver.resolve_entity("antidepressant response")
        assay = self.resolver.resolve_entity("forced swim test")
        self.assertEqual(outcome.entity_type, "phenotype")
        self.assertEqual(assay.entity_type, "behavioral_assay")
        self.assert_relation(assay, "measures", "PHENOTYPE:DEPRESSION_LIKE_BEHAVIOR")

    def test_unknown_is_low_confidence_unresolved(self):
        decision = self.resolver.resolve_entity("unknown kinase X")
        self.assertEqual(decision.normalization_status, "unresolved_fallback")
        self.assertLessEqual(decision.confidence, 0.35)
        self.assertFalse(decision.allow_high_confidence_graph_use)
        self.assertIn("uppercase_fallback_low_confidence", decision.warnings)

    def test_empty_and_failed_placeholders(self):
        for term in ("", "unspecified", "failed_parse", "n/a"):
            self.assertEqual(self.resolver.resolve_entity(term).normalization_status, "empty_or_invalid")

    def test_duplicate_alias_validation_and_resolution_ambiguity(self):
        payload = {
            "version": "test",
            "entities": [
                {"canonical_id": "X:1", "canonical_name": "one", "entity_type": "gene", "semantic_level": "gene", "aliases": ["shared"], "relations": []},
                {"canonical_id": "X:2", "canonical_name": "two", "entity_type": "protein", "semantic_level": "protein", "aliases": ["shared"], "relations": []}
            ]
        }
        warnings = validate_entity_registry(payload)
        self.assertTrue(warnings)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "registry.json"
            path.write_text(json.dumps(payload), encoding="utf-8")
            decision = ResolverCascade(LocalBiomedicalRegistry(path)).resolve_entity("shared")
        self.assertEqual(decision.normalization_status, "ambiguous")
        self.assertFalse(decision.allow_high_confidence_graph_use)

    def test_missing_registry_is_strict_by_default(self):
        with self.assertRaises(FileNotFoundError):
            LocalBiomedicalRegistry("definitely_missing_registry.json")

    def test_explicit_registry_fallback_is_audited(self):
        registry = LocalBiomedicalRegistry("definitely_missing_registry.json", allow_fallback=True)
        self.assertIn("registry_missing_builtin_demo_fallback_used", registry.warnings)
        self.assertEqual(ResolverCascade(registry).resolve_entity("ketamine").canonical_id, "CHEM:KETAMINE")

    def test_lexical_receptor_and_greek_normalization(self):
        self.assertEqual(normalize_lexical_surface("NMDAR").normalized_surface, "nmda receptor")
        self.assertEqual(normalize_lexical_surface("AMPAR").normalized_surface, "ampa receptor")
        self.assertIn("beta", normalize_lexical_surface("CaMKII-β").normalized_surface)

    def test_ontology_adapter_retains_new_audit_fields(self):
        resolved = clean_semantic_token("GluA1")
        unknown = clean_semantic_token("unknown kinase X")
        self.assertEqual(resolved.canonical_id, "GENE:GRIA1")
        self.assertTrue(resolved.allow_high_confidence_graph_use)
        self.assertEqual(unknown.normalization_status, "unresolved_fallback")
        self.assertLessEqual(unknown.confidence, 0.35)
        self.assertFalse(unknown.allow_high_confidence_graph_use)

    def test_llm_proposer_is_disabled_and_unvalidated(self):
        proposer = LLMCandidateProposer()
        self.assertEqual(proposer.propose("novel entity"), [])
        proposer.enabled = True
        candidate = proposer.propose("novel entity")[0]
        self.assertEqual(candidate.match_type, "llm_suggestion_unvalidated")
        self.assertIn("requires_deterministic_validation", candidate.warnings)

    def test_cli_smoke(self):
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            status = normalize_main(["--term", "GluA1", "--json", "--show-candidates"])
        payload = json.loads(output.getvalue())
        self.assertEqual(status, 0)
        self.assertEqual(payload["canonical_id"], "GENE:GRIA1")


if __name__ == "__main__":
    unittest.main()
