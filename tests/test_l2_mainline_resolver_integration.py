import json
import tempfile
import unittest
from pathlib import Path

from code_engine.graph.conflict_discovery import build_conflict_graph, group_observations
from code_engine.graph.ontology_alignment import (
    extract_normalized_observations,
    write_normalization_audit,
)
from code_engine.normalization.registry import LocalBiomedicalRegistry
from code_engine.normalization.resolver import ResolverCascade
from src.pipelines.stage5_shannon_matrix import build_arg_parser


class L2MainlineResolverIntegrationTests(unittest.TestCase):
    def test_orchestrator_flags_default_to_resolver_and_exclusion(self):
        defaults = build_arg_parser().parse_args([])
        self.assertTrue(defaults.resolver_cascade)
        self.assertFalse(defaults.legacy_synonym_only)
        self.assertFalse(defaults.include_low_confidence)
        legacy = build_arg_parser().parse_args(["--legacy-synonym-only"])
        self.assertTrue(legacy.legacy_synonym_only)

    def _extract(self, root: Path, *, legacy_synonym_only: bool = False):
        input_dir = root / "l1_5"
        input_dir.mkdir()
        payload = {
            "asset_id": "P1",
            "belief_weight": 0.8,
            "chunks_extracted": [{
                "chunk_index": 0,
                "raw_samples": [{
                    "causal_tuples": [
                        {
                            "subject": "GluA1",
                            "object": "AMPA receptor",
                            "relation_sign": 1,
                            "evidence_sentence": "GluA1 contributes to AMPA receptor function.",
                        },
                        {
                            "subject": "norketamine",
                            "object": "ketamine",
                            "relation_sign": -1,
                            "evidence_sentence": "Norketamine is distinct from ketamine.",
                        },
                        {
                            "subject": "unknown kinase X",
                            "object": "BDNF",
                            "relation_sign": 1,
                            "evidence_sentence": "Unknown kinase X may affect BDNF.",
                        },
                        {
                            "subject": "",
                            "object": "BDNF",
                            "relation_sign": 1,
                            "evidence_sentence": "Invalid empty subject.",
                        },
                    ]
                }],
            }],
        }
        (input_dir / "P1_refined.json").write_text(json.dumps(payload), encoding="utf-8")
        return extract_normalized_observations(
            str(input_dir),
            synonym_map={"glua1": "LEGACY_GLUA1"},
            forbidden_keywords=[],
            legacy_synonym_only=legacy_synonym_only,
        )

    def test_resolver_cascade_is_default_and_preserves_distinct_identities(self):
        with tempfile.TemporaryDirectory() as tmp:
            observations, _ = self._extract(Path(tmp))

        glua1 = observations[0]
        norketamine = observations[1]
        self.assertEqual(glua1["subject_canonical_id"], "GENE:GRIA1")
        self.assertEqual(glua1["object_canonical_id"], "COMPLEX:AMPA_RECEPTOR")
        self.assertNotEqual(glua1["subject_canonical_id"], glua1["object_canonical_id"])
        self.assertEqual(glua1["subject_resolver"], "resolver_cascade_v1")
        self.assertIn(
            ("subunit_of", "COMPLEX:AMPA_RECEPTOR"),
            [(relation["predicate"], relation["object"]) for relation in glua1["subject_relations"]],
        )
        self.assertEqual(norketamine["subject_canonical_id"], "CHEM:NORKETAMINE")
        self.assertEqual(norketamine["object_canonical_id"], "CHEM:KETAMINE")
        self.assertNotEqual(norketamine["subject_canonical_id"], norketamine["object_canonical_id"])

    def test_unknown_is_retained_but_excluded_from_default_conflict_graph(self):
        with tempfile.TemporaryDirectory() as tmp:
            observations, _ = self._extract(Path(tmp))

        unknown = observations[2]
        self.assertEqual(unknown["subject_normalization_status"], "unresolved_fallback")
        self.assertLessEqual(unknown["subject_confidence"], 0.35)
        self.assertEqual(unknown["normalization_quality"], "low_confidence")
        self.assertTrue(unknown["exclude_from_high_confidence_conflict"])

        graph, edges, _, report = build_conflict_graph(observations, latent_pool=[])
        self.assertEqual(len(graph), 2)
        self.assertEqual(report["skipped_low_confidence_observation_count"], 1)
        self.assertNotIn("UNKNOWN KINASE X", {edge["source"] for edge in edges})

    def test_l3_pair_key_prefers_canonical_id_and_keeps_legacy_names(self):
        with tempfile.TemporaryDirectory() as tmp:
            observations, _ = self._extract(Path(tmp))

        grouped = group_observations(observations)
        self.assertIn(("GENE:GRIA1", "COMPLEX:AMPA_RECEPTOR"), grouped)
        _, edges, _, _ = build_conflict_graph(observations, latent_pool=[])
        edge = next(item for item in edges if item["subject_canonical_id"] == "GENE:GRIA1")
        self.assertEqual(edge["edge_id"], "GENE:GRIA1->COMPLEX:AMPA_RECEPTOR")
        self.assertEqual(edge["source"], "GRIA1")
        self.assertEqual(edge["target"], "AMPA RECEPTOR")
        self.assertEqual(edge["subject_entity_type"], "gene")
        self.assertEqual(edge["skipped_low_confidence_observation_count"], 0)

    def test_include_low_confidence_is_explicit(self):
        with tempfile.TemporaryDirectory() as tmp:
            observations, _ = self._extract(Path(tmp))
        graph, _, _, report = build_conflict_graph(
            observations, latent_pool=[], include_low_confidence=True
        )
        self.assertEqual(len(graph), 3)
        self.assertEqual(report["skipped_low_confidence_observation_count"], 0)

    def test_ambiguous_observation_is_retained_for_audit_but_excluded(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            registry_path = root / "registry.json"
            registry_path.write_text(json.dumps({
                "version": "test",
                "entities": [
                    {"canonical_id": "X:1", "canonical_name": "one", "entity_type": "gene", "semantic_level": "gene", "aliases": ["shared"], "relations": []},
                    {"canonical_id": "X:2", "canonical_name": "two", "entity_type": "protein", "semantic_level": "protein", "aliases": ["shared"], "relations": []},
                    {"canonical_id": "X:3", "canonical_name": "target", "entity_type": "gene", "semantic_level": "gene", "aliases": ["target"], "relations": []},
                ],
            }), encoding="utf-8")
            input_dir = root / "input"
            input_dir.mkdir()
            (input_dir / "P_refined.json").write_text(json.dumps({
                "asset_id": "P",
                "chunks_extracted": [{"chunk_index": 0, "raw_samples": [{"causal_tuples": [{
                    "subject": "shared", "object": "target", "relation_sign": 1,
                    "evidence_sentence": "Shared affects target.",
                }]}]}],
            }), encoding="utf-8")
            resolver = ResolverCascade(LocalBiomedicalRegistry(registry_path))
            observations, _ = extract_normalized_observations(
                str(input_dir), {}, [], resolver=resolver
            )

        self.assertEqual(len(observations), 1)
        self.assertEqual(observations[0]["subject_normalization_status"], "ambiguous")
        self.assertEqual(observations[0]["subject"], "SHARED")
        self.assertTrue(observations[0]["exclude_from_high_confidence_conflict"])

    def test_legacy_synonym_only_mode_requires_explicit_selection(self):
        with tempfile.TemporaryDirectory() as tmp:
            observations, _ = self._extract(Path(tmp), legacy_synonym_only=True)
        self.assertEqual(observations[0]["subject"], "LEGACY_GLUA1")
        self.assertEqual(observations[0]["subject_canonical_id"], "")
        self.assertEqual(observations[0]["subject_resolver"], "legacy_synonym_only")

    def test_normalization_audit_contains_summary_and_reference_examples(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _, audit = self._extract(root)
            json_path = root / "entity_normalization_audit.json"
            markdown_path = root / "entity_normalization_audit.md"
            write_normalization_audit(audit, str(json_path), str(markdown_path))
            payload = json.loads(json_path.read_text(encoding="utf-8"))

        self.assertEqual(payload["summary"]["total_raw_terms"], 8)
        self.assertEqual(payload["summary"]["unresolved_fallback_count"], 1)
        self.assertEqual(payload["summary"]["empty_or_invalid_count"], 1)
        self.assertEqual(payload["summary"]["low_confidence_excluded_count"], 2)
        examples = {item["raw_term"]: item for item in payload["reference_examples"]}
        self.assertEqual(examples["GluA1"]["canonical_id"], "GENE:GRIA1")
        self.assertEqual(examples["AMPA receptor"]["canonical_id"], "COMPLEX:AMPA_RECEPTOR")
        self.assertEqual(examples["norketamine"]["canonical_id"], "CHEM:NORKETAMINE")
        self.assertEqual(examples["forced swim test"]["canonical_id"], "ASSAY:FORCED_SWIM_TEST")


if __name__ == "__main__":
    unittest.main()
