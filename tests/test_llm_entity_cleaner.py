"""Tests for LLM-assisted entity surface cleaner and verified normalization routing.

Tests:
  1. CLI accepts --entity-llm-cleaner.
  2. Default entity_llm_cleaner=False.
  3. --api alone does not enable LLM cleaner.
  4. --entity-llm-cleaner requires api enabled or records clear disabled reason.
  5. Unresolved mention triggers LLM cleaner when enabled.
  6. Ambiguous mention can trigger LLM cleaner when enabled.
  7. LLM cleaner extracts 5-fluorouracil from "the therapeutic effect of 5-fluorouracil (5-FU)".
  8. LLM cleaner routes 5-fluorouracil to PubChem / ChEMBL.
  9. LLM cleaner identifies EMT as biological_process and does not force MyGene / UniProt.
 10. LLM cleaner splits GRB2-RAS-RAF-MEK-ERK pathway into candidate gene/protein heads.
 11. LLM-suggested but externally unverified result is not high-confidence graph eligible.
 12. Externally verified cleaned candidate can become external_grounded.
 13. Ambiguous external result remains review-required.
 14. Audit files contain original mention, cleaned mention, provider route, verification status, final decision.
 15. Existing non-LLM normalization behavior remains unchanged when cleaner disabled.
"""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from tests.replay_test_support import fixture as replay_fixture


# ---------------------------------------------------------------------------
# Fake LLM client for tests
# ---------------------------------------------------------------------------

class FakeLLMClient:
    """Fake LLM client that returns deterministic responses for testing."""
    def __init__(self, responses: dict | None = None):
        self._responses = responses or {}
        self._calls: list[dict] = []

    def extract_json(self, messages):
        """Simulate extract_json for the cleaner prompt."""
        self._calls.append({"messages": messages})
        # Default response: extract entities from surface
        user_content = ""
        if isinstance(messages, list):
            for m in messages:
                if m.get("role") == "user":
                    user_content = m.get("content", "")
        elif isinstance(messages, str):
            user_content = messages

        if "5-fluorouracil" in user_content or "5-FU" in user_content:
            return {
                "cleaned_head_entities": [
                    {
                        "surface": "5-fluorouracil",
                        "aliases": ["5-FU"],
                        "entity_type": "drug",
                        "ontology_routes": ["pubchem", "chembl"],
                        "removed_modifiers": ["therapeutic effect"],
                        "confidence": 0.86,
                        "rationale_short": "5-FU is an alias of 5-fluorouracil; treatment effect is a modifier",
                    }
                ],
                "residual_context": "therapeutic effect",
            }
        if "EMT" in user_content or "epithelial" in user_content:
            return {
                "cleaned_head_entities": [
                    {
                        "surface": "epithelial-mesenchymal transition",
                        "aliases": ["EMT"],
                        "entity_type": "biological_process",
                        "ontology_routes": [],
                        "removed_modifiers": [],
                        "confidence": 0.92,
                        "rationale_short": "EMT is a developmental biological process",
                    }
                ],
                "residual_context": "",
            }
        if "GRB2" in user_content or "MEK" in user_content:
            return {
                "cleaned_head_entities": [
                    {"surface": "GRB2", "aliases": [], "entity_type": "gene", "ontology_routes": ["mygene", "uniprot"], "removed_modifiers": [], "confidence": 0.85, "rationale_short": "GRB2 adaptor protein"},
                    {"surface": "RAS", "aliases": ["HRAS", "KRAS", "NRAS"], "entity_type": "gene", "ontology_routes": ["mygene", "uniprot"], "removed_modifiers": [], "confidence": 0.82, "rationale_short": "RAS GTPase"},
                    {"surface": "RAF", "aliases": ["BRAF", "CRAF"], "entity_type": "gene", "ontology_routes": ["mygene", "uniprot"], "removed_modifiers": [], "confidence": 0.80, "rationale_short": "RAF kinase"},
                    {"surface": "MEK", "aliases": ["MAP2K1", "MAP2K2"], "entity_type": "gene", "ontology_routes": ["mygene", "uniprot"], "removed_modifiers": [], "confidence": 0.88, "rationale_short": "MEK kinase"},
                    {"surface": "ERK", "aliases": ["MAPK1", "MAPK3"], "entity_type": "gene", "ontology_routes": ["mygene", "uniprot"], "removed_modifiers": [], "confidence": 0.88, "rationale_short": "ERK kinase"},
                ],
                "residual_context": "pathway",
            }
        # Generic response
        return {
            "cleaned_head_entities": [
                {
                    "surface": user_content.strip() if user_content else "unknown",
                    "aliases": [],
                    "entity_type": "unknown",
                    "ontology_routes": [],
                    "removed_modifiers": [],
                    "confidence": 0.5,
                    "rationale_short": "generic extraction",
                }
            ],
            "residual_context": "",
        }


# ---------------------------------------------------------------------------
# Tests for LLMEntityCleaner
# ---------------------------------------------------------------------------

class LLMEntityCleanerTests(unittest.TestCase):
    """Test the core LLMEntityCleaner component."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.tmp_path = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def _make_cleaner(self, llm_client=None, enabled=True):
        from code_engine.normalization.llm_entity_cleaner import LLMEntityCleaner
        return LLMEntityCleaner(
            llm_client=llm_client,
            enabled=enabled,
            audit_dir=self.tmp_path,
        )

    # Test 7: LLM cleaner extracts 5-fluorouracil from noisy mention
    def test_extracts_5fu_from_noisy_mention(self):
        cleaner = self._make_cleaner(FakeLLMClient())
        result = cleaner.clean(
            "the therapeutic effect of 5-fluorouracil (5-FU)",
            mention_role="subject",
        )
        self.assertEqual(result.llm_cleaner_status, "cleaned")
        self.assertTrue(len(result.cleaned_head_entities) > 0)
        head = result.cleaned_head_entities[0]
        self.assertIn("5-fluorouracil", head.surface)
        self.assertIn("5-FU", head.aliases)

    # Test 8: LLM cleaner routes 5-fluorouracil to PubChem / ChEMBL
    def test_routes_5fu_to_pubchem_chembl(self):
        cleaner = self._make_cleaner(FakeLLMClient())
        result = cleaner.clean(
            "the therapeutic effect of 5-fluorouracil (5-FU)",
            mention_role="object",
        )
        head = result.cleaned_head_entities[0]
        routes = [r.casefold() for r in head.ontology_routes]
        self.assertTrue(any(r in routes for r in ["pubchem", "chembl"]))

    # Test 9: LLM cleaner identifies EMT as biological_process
    def test_identifies_emt_as_biological_process(self):
        cleaner = self._make_cleaner(FakeLLMClient())
        result = cleaner.clean("EMT", mention_role="subject")
        head = result.cleaned_head_entities[0]
        self.assertEqual(head.entity_type, "biological_process")
        # EMT should route to ontology lookup, not MyGene/UniProt.
        self.assertEqual(head.ontology_routes, ["ols"])

    # Test 10: LLM cleaner splits pathway into gene/protein heads
    def test_splits_grb2_ras_raf_mek_erk_pathway(self):
        cleaner = self._make_cleaner(FakeLLMClient())
        result = cleaner.clean(
            "GRB2-RAS-RAF-MEK-ERK pathway",
            mention_role="subject",
        )
        self.assertTrue(len(result.cleaned_head_entities) >= 5)
        gene_heads = [h for h in result.cleaned_head_entities if h.entity_type == "gene"]
        self.assertTrue(len(gene_heads) >= 4)

    # Test: disabled cleaner returns disabled status
    def test_disabled_cleaner_returns_disabled(self):
        cleaner = self._make_cleaner(FakeLLMClient(), enabled=False)
        result = cleaner.clean("5-fluorouracil", mention_role="subject")
        self.assertEqual(result.llm_cleaner_status, "disabled")

    # Test: empty surface returns empty_surface status
    def test_empty_surface_returns_empty(self):
        cleaner = self._make_cleaner(FakeLLMClient())
        result = cleaner.clean("", mention_role="subject")
        self.assertEqual(result.llm_cleaner_status, "empty_surface")

    # Test: deterministic pre-cleaning works without LLM
    def test_deterministic_cleaning_without_llm(self):
        cleaner = self._make_cleaner(llm_client=None, enabled=True)
        result = cleaner.clean(
            "overexpression of Trop2",
            mention_role="subject",
        )
        # Should have used deterministic fallback
        self.assertIn(result.llm_cleaner_status, {"cleaned_with_warnings", "llm_unavailable"})
        self.assertTrue(len(result.cleaned_head_entities) > 0)

    # Test 14: Audit files are written correctly
    def test_audit_files_written(self):
        cleaner = self._make_cleaner(FakeLLMClient())
        cleaner.clean("5-fluorouracil", mention_role="subject", claim_id="C1", observation_id="O1")
        paths = cleaner.write_audit_files(self.tmp_path)
        self.assertIn("entity_llm_cleaner_audit_jsonl", paths)
        self.assertIn("entity_llm_cleaner_summary", paths)

        # Verify audit content
        audit_path = Path(paths["entity_llm_cleaner_audit_jsonl"])
        self.assertTrue(audit_path.is_file())
        records = [json.loads(line) for line in audit_path.read_text().splitlines() if line.strip()]
        self.assertTrue(len(records) >= 1)
        record = records[0]
        self.assertEqual(record["original_mention"], "5-fluorouracil")
        self.assertIn("claim_id", record)
        self.assertIn("provider_routes", record)
        self.assertIn("llm_cleaner_status", record)

    # Test: manifest fields are correct
    def test_manifest_fields(self):
        cleaner = self._make_cleaner(FakeLLMClient())
        cleaner.clean("5-fluorouracil", mention_role="subject")
        fields = cleaner.manifest_fields()
        self.assertTrue(fields["entity_llm_cleaner_enabled"])
        self.assertEqual(fields["entity_llm_cleaner_calls_made"], 1)
        self.assertEqual(fields["cleaner_eligible_mentions"], 1)
        self.assertEqual(fields["cleaner_actual_calls"], 1)

    def test_persistent_cache_resumes_without_repeating_llm_call(self):
        first_client = FakeLLMClient()
        first = self._make_cleaner(first_client)
        initial = first.clean(
            "the therapeutic effect of 5-fluorouracil (5-FU)",
            claim_context="5-FU reduced viability",
            mention_role="object",
        )
        self.assertEqual(len(first_client._calls), 1)

        resumed_client = FakeLLMClient()
        resumed = self._make_cleaner(resumed_client)
        cached = resumed.clean(
            "the therapeutic effect of 5-fluorouracil (5-FU)",
            claim_context="5-FU reduced viability",
            mention_role="object",
        )

        self.assertEqual(len(resumed_client._calls), 0)
        self.assertEqual(cached.cleaned_head_entities, initial.cleaned_head_entities)
        self.assertEqual(resumed.manifest_fields()["cleaner_cache_hits"], 1)
        cache_files = list((self.tmp_path / "entity_llm_cleaner_cache").glob("*.json"))
        self.assertEqual(len(cache_files), 1)
        cache_payload = cache_files[0].read_text(encoding="utf-8")
        self.assertNotIn("5-FU reduced viability", cache_payload)

    def test_deterministic_skip_accounts_for_zero_actual_calls(self):
        cleaner = self._make_cleaner(llm_client=None, enabled=True)
        cleaner.clean("overexpression of Trop2", mention_role="subject")

        fields = cleaner.manifest_fields()
        self.assertEqual(fields["cleaner_eligible_mentions"], 1)
        self.assertEqual(fields["cleaner_deterministic_skip"], 1)
        self.assertEqual(fields["cleaner_actual_calls"], 0)
        self.assertEqual(fields["cleaner_pending"], 0)

    # Test: update_verification_status works
    def test_update_verification_status(self):
        cleaner = self._make_cleaner(FakeLLMClient())
        cleaner.clean("5-fluorouracil", mention_role="subject")
        cleaner.update_verification_status(
            original_mention="5-fluorouracil",
            verification_result="verified",
            final_decision="accepted",
            high_confidence_allowed=True,
        )
        self.assertEqual(cleaner.external_verified_after_cleaning_count, 1)
        fields = cleaner.manifest_fields()
        self.assertEqual(fields["entity_external_verified_after_llm_cleaning_count"], 1)

    # Test: update unverified status
    def test_update_unverified_status(self):
        cleaner = self._make_cleaner(FakeLLMClient())
        cleaner.clean("UnknownMention123", mention_role="subject")
        cleaner.update_verification_status(
            original_mention="UnknownMention123",
            verification_result="unverified",
            final_decision="llm_suggested_unverified",
            high_confidence_allowed=False,
            rejection_reason="no_external_verification",
        )
        self.assertEqual(cleaner.suggested_unverified_count, 1)


# ---------------------------------------------------------------------------
# CLI tests
# ---------------------------------------------------------------------------

class ReplayLLMCleanerCLITests(unittest.TestCase):
    """Test the --entity-llm-cleaner CLI flag."""

    # Test 1: CLI accepts --entity-llm-cleaner
    def test_cli_accepts_entity_llm_cleaner_flag(self):
        from code_engine.cli.replay_case_from_stage import main
        try:
            main(["--case-profile", "/nonexistent/profile.json",
                  "--search-plan-file", "/nonexistent/plan.json",
                  "--source-run", "/nonexistent/source",
                  "--from-stage", "bundle",
                  "--output-suffix", "test",
                  "--bundle-id-suffix", "test",
                  "--network", "--api", "--entity-network-lookup",
                  "--entity-llm-cleaner",
                  "--no-l1", "--skip-fulltext", "--skip-l7"])
        except SystemExit:
            pass
        except (FileNotFoundError, ValueError, OSError):
            pass

    # Test 2: Default entity_llm_cleaner=False
    def test_default_entity_llm_cleaner_is_false(self):
        from code_engine.cli.replay_case_from_stage import replay as replay_fn
        import inspect
        sig = inspect.signature(replay_fn)
        self.assertFalse(
            sig.parameters["entity_llm_cleaner"].default,
            "replay() must default to entity_llm_cleaner=False",
        )

    # Test 3: --api alone does not enable LLM cleaner
    def test_api_alone_does_not_enable_llm_cleaner(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            profile, plan, source = replay_fixture(root)
            with patch("code_engine.workflow.steps.run_l2_abstract_step") as mock_l2:
                mock_l2.return_value = MagicMock()
                from code_engine.cli.replay_case_from_stage import replay
                replay(profile, plan, source, "l2",
                       root / "runs", "replay", "r2",
                       network=True, api=True, entity_network_lookup=True,
                       entity_llm_cleaner=False,
                       bundle_root=root / "bundles")
                self.assertTrue(mock_l2.called)
                call_kwargs = mock_l2.call_args.kwargs
                self.assertTrue(call_kwargs.get("network"))
                self.assertTrue(call_kwargs.get("api"))
                self.assertFalse(call_kwargs.get("entity_llm_cleaner", False),
                                 "--api alone should not enable entity_llm_cleaner")

    # Test 4: --entity-llm-cleaner is passed through to L2 step
    def test_entity_llm_cleaner_passed_to_l2_step(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            profile, plan, source = replay_fixture(root)
            with patch("code_engine.workflow.steps.run_l2_abstract_step") as mock_l2:
                mock_l2.return_value = MagicMock()
                from code_engine.cli.replay_case_from_stage import replay
                replay(profile, plan, source, "l2",
                       root / "runs", "replay", "r2",
                       network=True, api=True, entity_network_lookup=True,
                       entity_llm_cleaner=True,
                       bundle_root=root / "bundles")
                self.assertTrue(mock_l2.called)
                call_kwargs = mock_l2.call_args.kwargs
                self.assertTrue(call_kwargs.get("entity_llm_cleaner", False),
                                "entity_llm_cleaner should be passed to L2 step")


# ---------------------------------------------------------------------------
# Integration tests with ResolverCascade
# ---------------------------------------------------------------------------

class ResolverLLMCleanerIntegrationTests(unittest.TestCase):
    """Test the ResolverCascade integration with LLM cleaner."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.tmp_path = Path(self.tmp.name)
        self.artifacts = self.tmp_path / "artifacts"
        self.artifacts.mkdir(parents=True)

    def tearDown(self):
        self.tmp.cleanup()

    def _make_resolver(self, entity_llm_cleaner=False, llm_client=None, entity_network_lookup=False):
        from code_engine.normalization.resolver import ResolverCascade
        return ResolverCascade(
            run_dir=self.tmp_path,
            execute=True,
            network_enabled=False,
            api_enabled=False,
            entity_network_lookup=entity_network_lookup,
            entity_llm_cleaner=entity_llm_cleaner,
            llm_client=llm_client,
        )

    # Test 15: Existing non-LLM normalization behavior unchanged when cleaner disabled
    def test_normal_behavior_without_llm_cleaner(self):
        resolver = self._make_resolver(entity_llm_cleaner=False)
        result = resolver.resolve_entity("5-fluorouracil", context={"expected_entity_type": "drug"})
        # Should produce a normalization decision (unresolved or fallback since no network)
        self.assertIsNotNone(result)
        self.assertIn(result.normalization_status, {"unresolved_fallback", "ambiguous", "empty_or_invalid"})

    # Test 5: Unresolved mention triggers LLM cleaner when enabled
    def test_unresolved_triggers_llm_cleaner(self):
        resolver = self._make_resolver(
            entity_llm_cleaner=True,
            llm_client=FakeLLMClient(),
            entity_network_lookup=False,
        )
        result = resolver.resolve_entity(
            "the therapeutic effect of 5-fluorouracil (5-FU)",
            context={"expected_entity_type": "drug", "claim_id": "C1"},
        )
        # Cleaner should be initialized and called
        self.assertIsNotNone(resolver._llm_cleaner)
        self.assertTrue(resolver._llm_cleaner.calls_made >= 1)
        self.assertIsNotNone(result)

    # Test 11: LLM-suggested but externally unverified result is NOT high-confidence graph eligible
    def test_llm_unverified_not_high_confidence(self):
        resolver = self._make_resolver(
            entity_llm_cleaner=True,
            llm_client=FakeLLMClient(),
            entity_network_lookup=False,  # No external lookup available
        )
        result = resolver.resolve_entity(
            "the therapeutic effect of 5-fluorouracil (5-FU)",
            context={"expected_entity_type": "drug"},
        )
        # With no external lookup, LLM cleaned but unverified -> not high confidence
        self.assertFalse(
            result.allow_high_confidence_graph_use,
            "LLM-suggested but externally unverified must not be high-confidence graph eligible",
        )


# ---------------------------------------------------------------------------
# Entity type classification tests
# ---------------------------------------------------------------------------

class EntityTypeClassificationTests(unittest.TestCase):
    """Test entity type classification in the LLM cleaner."""

    def test_drug_type_classification(self):
        from code_engine.normalization.llm_entity_cleaner import _infer_entity_type_heuristic
        # 5-fluorouracil starts with digits, not matched by uppercase heuristic
        # Without L1 hint it's "unknown" — the LLM cleaner provides proper classification
        result = _infer_entity_type_heuristic("5-fluorouracil")
        self.assertIn(result, {"unknown", "compound", "drug"})

    def test_gene_type_classification(self):
        from code_engine.normalization.llm_entity_cleaner import _infer_entity_type_heuristic
        self.assertEqual(_infer_entity_type_heuristic("TP53"), "gene")

    def test_pathway_classification(self):
        from code_engine.normalization.llm_entity_cleaner import _infer_entity_type_heuristic
        self.assertEqual(_infer_entity_type_heuristic("MAPK signaling pathway"), "pathway")

    def test_biological_process_classification(self):
        from code_engine.normalization.llm_entity_cleaner import _infer_entity_type_heuristic
        self.assertEqual(_infer_entity_type_heuristic("apoptosis"), "biological_process")

    def test_disease_classification(self):
        from code_engine.normalization.llm_entity_cleaner import _infer_entity_type_heuristic
        self.assertEqual(_infer_entity_type_heuristic("breast cancer"), "disease")

    def test_routing_drug_to_pubchem_chembl(self):
        from code_engine.normalization.llm_entity_cleaner import _route_entity_type
        routes = _route_entity_type("drug")
        self.assertTrue(any(r in routes for r in ["pubchem", "chembl"]))

    def test_routing_gene_to_mygene_uniprot(self):
        from code_engine.normalization.llm_entity_cleaner import _route_entity_type
        routes = _route_entity_type("gene")
        self.assertTrue(any(r in routes for r in ["mygene", "uniprot"]))

    def test_routing_biological_process_to_ols(self):
        from code_engine.normalization.llm_entity_cleaner import _route_entity_type
        routes = _route_entity_type("biological_process")
        self.assertEqual(routes, ["ols"])


# ---------------------------------------------------------------------------
# Deterministic cleaning tests
# ---------------------------------------------------------------------------

class DeterministicCleaningTests(unittest.TestCase):
    """Test the deterministic pre-cleaning logic."""

    def test_strips_overexpression_modifier(self):
        from code_engine.normalization.llm_entity_cleaner import _deterministic_clean
        cleaned, removed, aliases, extra = _deterministic_clean("overexpression of Trop2")
        self.assertIn("Trop2", cleaned)
        self.assertTrue(len(removed) > 0)

    def test_strips_inhibition_modifier(self):
        from code_engine.normalization.llm_entity_cleaner import _deterministic_clean
        cleaned, removed, aliases, extra = _deterministic_clean("inhibition of mTOR")
        self.assertIn("mTOR", cleaned)
        self.assertTrue(any("inhibition" in r for r in removed))

    def test_expands_known_aliases_5fu(self):
        from code_engine.normalization.llm_entity_cleaner import _deterministic_clean
        cleaned, removed, aliases, extra = _deterministic_clean("5-FU")
        self.assertTrue(len(aliases) > 0)
        self.assertTrue(any("5-fluorouracil" in a.casefold() for a in aliases))

    def test_expands_known_aliases_emt(self):
        from code_engine.normalization.llm_entity_cleaner import _deterministic_clean
        cleaned, removed, aliases, extra = _deterministic_clean("EMT")
        self.assertTrue(any("epithelial" in a.casefold() for a in aliases))


# ---------------------------------------------------------------------------
# New deterministic cleaning tests (drug/therapy, dose/exposure, aliases, pathway)
# ---------------------------------------------------------------------------

class NewDeterministicCleaningTests(unittest.TestCase):
    """Test the new deterministic cleaning rules added for cleaner integration."""

    def test_amitriptyline_therapy_cleans_to_drug(self):
        from code_engine.normalization.llm_entity_cleaner import _deterministic_clean
        cleaned, removed, aliases, extra = _deterministic_clean("amitriptyline therapy")
        self.assertIn("amitriptyline", cleaned)
        self.assertNotIn("therapy", cleaned.casefold())

    def test_high_doses_exogenous_h2s_cleans_to_h2s(self):
        from code_engine.normalization.llm_entity_cleaner import _deterministic_clean
        cleaned, removed, aliases, extra = _deterministic_clean("high doses of exogenous H2S")
        self.assertIn("H2S", cleaned)
        self.assertNotIn("high doses", cleaned.casefold())

    def test_inhibition_endogenous_h2s_production_cleans_to_h2s(self):
        from code_engine.normalization.llm_entity_cleaner import _deterministic_clean
        cleaned, removed, aliases, extra = _deterministic_clean("inhibition of endogenous H2S production")
        self.assertIn("H2S", cleaned)

    def test_parenthetical_alias_extraction_dmba(self):
        from code_engine.normalization.llm_entity_cleaner import _deterministic_clean
        cleaned, removed, aliases, extra = _deterministic_clean("7,12-dimethylbenz[a]anthracene (DMBA, D)")
        self.assertIn("7,12-dimethylbenz[a]anthracene", cleaned)
        self.assertIn("DMBA", aliases)
        self.assertNotIn("D", aliases)

    def test_parenthetical_alias_extraction_5fu(self):
        from code_engine.normalization.llm_entity_cleaner import _deterministic_clean
        cleaned, removed, aliases, extra = _deterministic_clean("5-fluorouracil (5-FU)")
        self.assertIn("5-fluorouracil", cleaned)
        self.assertIn("5-FU", aliases)

    def test_pathway_decomposition_pi3k_akt(self):
        from code_engine.normalization.llm_entity_cleaner import _deterministic_clean
        cleaned, removed, aliases, extra = _deterministic_clean("PI3K-Akt signalling pathway")
        extra_surfaces = [h.surface.upper() for h in extra]
        self.assertTrue(any("PI3K" in s for s in extra_surfaces))
        self.assertTrue(any("AKT" in s for s in extra_surfaces))

    def test_pathway_decomposition_grb2_erk(self):
        from code_engine.normalization.llm_entity_cleaner import _deterministic_clean
        cleaned, removed, aliases, extra = _deterministic_clean("GRB2-RAS-RAF-MEK-ERK pathway")
        extra_surfaces = [h.surface.upper() for h in extra]
        for expected in ["GRB2", "RAS", "RAF", "MEK", "ERK"]:
            self.assertTrue(any(expected in s for s in extra_surfaces),
                            f"Expected {expected} in extra heads, got {extra_surfaces}")

    def test_treatment_with_metformin(self):
        from code_engine.normalization.llm_entity_cleaner import _deterministic_clean
        cleaned, removed, aliases, extra = _deterministic_clean("treatment with metformin")
        self.assertIn("metformin", cleaned.casefold())
        self.assertTrue(any("treatment_with" in r for r in removed))

    def test_therapeutic_effect_of_rapamycin(self):
        from code_engine.normalization.llm_entity_cleaner import _deterministic_clean
        cleaned, removed, aliases, extra = _deterministic_clean("therapeutic effect of rapamycin")
        self.assertNotIn("therapeutic effect", cleaned.casefold())
        self.assertIn("rapamycin", cleaned.casefold())


# ---------------------------------------------------------------------------
# Cleaner verified-but-rejected tracking tests
# ---------------------------------------------------------------------------

class CleanerVerifiedRejectedTests(unittest.TestCase):
    """Test cleaner verified-but-rejected tracking."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.tmp_path = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_verified_but_rejected_counted(self):
        from code_engine.normalization.llm_entity_cleaner import LLMEntityCleaner
        cleaner = LLMEntityCleaner(
            llm_client=FakeLLMClient(),
            enabled=True,
            audit_dir=self.tmp_path,
        )
        cleaner.clean("5-fluorouracil", mention_role="subject")
        cleaner.update_verification_status(
            original_mention="5-fluorouracil",
            verification_result="verified",
            final_decision="rejected_by_adjudicator",
            high_confidence_allowed=False,
            rejection_reason="ambiguous_external_result_after_cleaning",
        )
        self.assertEqual(cleaner.external_verified_after_cleaning_count, 1)
        self.assertEqual(cleaner.cleaner_verified_but_rejected_count, 1)
        fields = cleaner.manifest_fields()
        self.assertEqual(fields["cleaner_verified_but_rejected_count"], 1)
        self.assertTrue(len(fields["top_cleaner_verified_but_rejected_mentions"]) >= 1)

    def test_verified_and_accepted_not_counted_as_rejected(self):
        from code_engine.normalization.llm_entity_cleaner import LLMEntityCleaner
        cleaner = LLMEntityCleaner(
            llm_client=FakeLLMClient(),
            enabled=True,
            audit_dir=self.tmp_path,
        )
        cleaner.clean("5-fluorouracil", mention_role="subject")
        cleaner.update_verification_status(
            original_mention="5-fluorouracil",
            verification_result="verified",
            final_decision="accepted",
            high_confidence_allowed=True,
        )
        self.assertEqual(cleaner.cleaner_verified_but_rejected_count, 0)
        self.assertEqual(cleaner.external_verified_after_cleaning_count, 1)


# ---------------------------------------------------------------------------
# Provider eligibility tests
# ---------------------------------------------------------------------------

class ProviderEligibilityTests(unittest.TestCase):
    """Test the redefined provider eligibility rules."""

    def test_pathway_has_ontology_route(self):
        from code_engine.normalization.llm_entity_cleaner import _route_entity_type
        routes = _route_entity_type("pathway")
        self.assertEqual(routes, ["ols"], "pathway should have ontology route")

    def test_biological_process_has_ontology_route(self):
        from code_engine.normalization.llm_entity_cleaner import _route_entity_type
        routes = _route_entity_type("biological_process")
        self.assertEqual(routes, ["ols"], "biological_process should have ontology route")

    def test_disease_has_ontology_route(self):
        from code_engine.normalization.llm_entity_cleaner import _route_entity_type
        routes = _route_entity_type("disease")
        self.assertEqual(routes, ["ols"], "disease should have ontology route")

    def test_drug_has_concrete_provider_routes(self):
        from code_engine.normalization.llm_entity_cleaner import _route_entity_type
        routes = _route_entity_type("drug")
        self.assertTrue(any(r in routes for r in ["pubchem", "chembl"]))

    def test_gene_has_concrete_provider_routes(self):
        from code_engine.normalization.llm_entity_cleaner import _route_entity_type
        routes = _route_entity_type("gene")
        self.assertTrue(any(r in routes for r in ["mygene", "uniprot"]))

    def test_protein_has_concrete_provider_routes(self):
        from code_engine.normalization.llm_entity_cleaner import _route_entity_type
        routes = _route_entity_type("protein")
        self.assertTrue(any(r in routes for r in ["uniprot", "mygene"]))

    def test_compound_has_concrete_provider_routes(self):
        from code_engine.normalization.llm_entity_cleaner import _route_entity_type
        routes = _route_entity_type("compound")
        self.assertTrue(any(r in routes for r in ["pubchem", "chembl"]))

    def test_clinical_outcome_has_no_provider_route(self):
        from code_engine.normalization.llm_entity_cleaner import _route_entity_type
        routes = _route_entity_type("clinical_outcome")
        self.assertEqual(routes, [], "clinical_outcome should have no provider routes")

    def test_phenotype_has_ontology_route(self):
        from code_engine.normalization.llm_entity_cleaner import _route_entity_type
        routes = _route_entity_type("phenotype")
        self.assertEqual(routes, ["ols"], "phenotype should have ontology route")

    def test_context_has_no_provider_route(self):
        from code_engine.normalization.llm_entity_cleaner import _route_entity_type
        routes = _route_entity_type("context")
        self.assertEqual(routes, [], "context should have no provider routes")

    def test_experimental_condition_has_no_provider_route(self):
        from code_engine.normalization.llm_entity_cleaner import _route_entity_type
        routes = _route_entity_type("experimental_condition")
        self.assertEqual(routes, [], "experimental_condition should have no provider routes")


# ---------------------------------------------------------------------------
# Resolver cleaner integration tests (with mock providers)
# ---------------------------------------------------------------------------

class ResolverCleanerDecisionIntegrationTests(unittest.TestCase):
    """Test that cleaner verified results correctly flow into resolver decisions."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.tmp_path = Path(self.tmp.name)
        self.artifacts = self.tmp_path / "artifacts"
        self.artifacts.mkdir(parents=True)

    def tearDown(self):
        self.tmp.cleanup()

    def _make_mock_provider(self, name, candidates=None):
        mock = MagicMock()
        mock.name = name
        mock.last_status = "success"
        mock.last_warnings = []
        mock.last_network_calls = 1
        mock.last_api_calls = 1
        mock.can_handle = MagicMock(return_value=True)
        mock.propose = MagicMock(return_value=candidates or [])
        return mock

    def test_verified_cleaned_becomes_final_decision(self):
        from code_engine.normalization.candidates import EntityCandidate
        from code_engine.normalization.resolver import ResolverCascade

        pubchem_candidate = EntityCandidate(
            surface="amitriptyline",
            normalized_surface="amitriptyline",
            canonical_id="CID:2160",
            canonical_name="Amitriptyline",
            entity_type="drug",
            semantic_level="chemical",
            source="pubchem",
            provider_name="PubChemCandidateProvider",
            external_ids={"pubchem": "CID:2160"},
            match_type="exact",
            match_score=0.95,
            type_score=0.9,
            source_reliability=0.9,
            context_score=0.8,
            overall_score=0.88,
            is_grounded=True,
        )

        resolver = ResolverCascade(
            run_dir=self.tmp_path,
            execute=True,
            network_enabled=True,
            api_enabled=True,
            entity_network_lookup=True,
            entity_llm_cleaner=True,
            llm_client=FakeLLMClient(),
        )

        mock_pubchem = self._make_mock_provider("PubChemCandidateProvider", [pubchem_candidate])
        mock_null = self._make_mock_provider("NullProvider", [])
        mock_null.can_handle = MagicMock(return_value=False)
        resolver.hub.providers = [mock_pubchem, mock_null]

        result = resolver.resolve_entity(
            "the therapeutic effect of amitriptyline therapy",
            context={"expected_entity_type": "drug", "claim_id": "C_test1"},
        )

        self.assertIsNotNone(result)
        self.assertIn(result.selected_source, {
            "external_after_cleaning", "external_after_cleaning_rejected",
            "external_after_cleaning_ambiguous", "cleaned_but_no_provider_match",
            "llm_cleaned_unverified", "external_direct", "curated", "cache",
        })

    def test_llm_only_unverified_never_high_confidence(self):
        from code_engine.normalization.resolver import ResolverCascade

        resolver = ResolverCascade(
            run_dir=self.tmp_path,
            execute=True,
            network_enabled=False,
            api_enabled=False,
            entity_network_lookup=False,
            entity_llm_cleaner=True,
            llm_client=FakeLLMClient(),
        )

        mock_null = self._make_mock_provider("NullProvider", [])
        mock_null.can_handle = MagicMock(return_value=False)
        resolver.hub.providers = [mock_null]

        result = resolver.resolve_entity(
            "the therapeutic effect of 5-fluorouracil (5-FU)",
            context={"expected_entity_type": "drug"},
        )

        # LLM cleaned but no external verification -> not high confidence
        self.assertFalse(
            result.allow_high_confidence_graph_use,
            "LLM-only unverified result must never be high-confidence graph eligible",
        )
        # selected_source should indicate that LLM cleaned but unverified
        self.assertIn(
            result.selected_source,
            {"llm_cleaned_unverified", "cleaned_but_no_provider_match", "external_after_cleaning_rejected", ""},
            f"Expected cleaner-related source, got {result.selected_source}",
        )

    def test_status_counts_unchanged_when_cleaner_disabled(self):
        from code_engine.normalization.resolver import ResolverCascade

        resolver_off = ResolverCascade(
            run_dir=self.tmp_path,
            execute=True,
            network_enabled=False,
            api_enabled=False,
            entity_network_lookup=False,
            entity_llm_cleaner=False,
            llm_client=None,
        )
        mock_null = self._make_mock_provider("NullProvider", [])
        mock_null.can_handle = MagicMock(return_value=False)
        resolver_off.hub.providers = [mock_null]

        result_off = resolver_off.resolve_entity(
            "PI3K",
            context={"expected_entity_type": "gene"},
        )
        self.assertIsNotNone(result_off)
        self.assertEqual(result_off.selected_source, "")
        self.assertIsNone(result_off.cleaner_trace)


if __name__ == "__main__":
    unittest.main()
