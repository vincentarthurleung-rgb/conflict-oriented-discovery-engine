import json
import tempfile
import unittest
from pathlib import Path

from code_engine.domain.prompt_compiler import compile_l1_prompt
from code_engine.domain.prompt_registry import default_prompt_registry
from code_engine.extraction.l1_extractor import build_l1_dry_run_plan, execute_l1_extraction
from code_engine.extraction.l1_refiner import refine_l1_claims
from code_engine.schemas.l1_extraction import L1ExtractedClaim


class FakeExtendedContextClient:
    def extract_json(self, prompt, **kwargs):
        return {"claims": [{
            "subject": "Drug X", "subject_type": "drug", "relation_raw": "increased",
            "relation_family": "expression_regulation", "direct_relation_sign": 1,
            "therapeutic_direction": "not_applicable", "object": "Gene Y expression",
            "object_type": "assay_readout", "context": {
                "species": "", "brain_region": "hippocampus", "drug_form": "Drug X",
                "receptor_target": "NMDA receptor", "pathway": "mTOR signaling",
                "molecular_readout": "Gene Y expression",
            },
            "negated": False, "null_or_no_effect": False, "speculative": False,
            "evidence_sentence": "Drug X increased Gene Y expression in the hippocampus.",
            "confidence": 0.95,
        }]}


class PromptRegistryRuntimeSemanticsTests(unittest.TestCase):
    def compile(self, profile_id):
        profile = default_prompt_registry().get_profile(profile_id)
        return compile_l1_prompt(profile, "Compound X changed a molecular readout.")

    def test_default_prompts_are_domain_neutral_and_pilot_is_explicit(self):
        banned = ("ketamine", "bdnf", "depression", "esketamine", "arketamine", "norketamine", "hydroxynorketamine")
        for profile_id in ("general_biomedical_l1_v2", "neuropharmacology_l1_v2"):
            text = self.compile(profile_id).text.lower()
            self.assertFalse(any(term in text for term in banned), profile_id)
        pilot = self.compile("neuropharmacology_ketamine_l1_v2_1").text.lower()
        self.assertIn("ketamine", pilot)
        self.assertIn("bdnf", pilot)

    def test_enum_missing_policy_version_alias_and_size(self):
        registry = default_prompt_registry()
        for profile_id, budget in (("general_biomedical_l1_v2", 9000), ("neuropharmacology_l1_v2", 9000), ("neuropharmacology_ketamine_l1_v2_1", 11000)):
            compiled = self.compile(profile_id)
            self.assertEqual(compiled.prompt_version, "2.1")
            self.assertLessEqual(compiled.compiled_prompt_char_count, budget)
            self.assertIn("beneficial, adverse, mixed, not_applicable, or unknown", compiled.text)
            self.assertIn('output ""', compiled.text)
            self.assertNotIn('use "unspecified" if', compiled.text.lower())
        alias = registry.get_profile("general_biomedical")
        self.assertEqual(alias.version, "2.1")
        self.assertTrue(registry.resolution_metadata("general_biomedical")["deprecated_alias"])

    def test_explicit_pilot_plan_and_prompt_metadata(self):
        plan = build_l1_dry_run_plan(
            "neutral chunk", domain="neuropharmacology", pilot_profile="ketamine",
            cache_path="missing-cache.json",
        )
        self.assertEqual(plan["prompt_profile_id"], "neuropharmacology_ketamine_l1_v2_1")
        self.assertEqual(plan["prompt_version"], "2.1")
        self.assertIn("receptor_target", plan["context_slots_used"])
        self.assertGreater(plan["compiled_prompt_char_count"], 0)

    def test_missing_sentinels_are_missing_and_dynamic_context_survives_l2_adapter(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = execute_l1_extraction(
                [{"paper_id": "P1", "chunk_id": "c1", "content": "Drug X increased Gene Y expression in the hippocampus."}],
                repository_root=tmp, execute=True, api=True, client=FakeExtendedContextClient(),
                domain="neuropharmacology", auto_domain=False,
            )
            self.assertFalse(result["errors"])
            payload = json.loads((Path(tmp) / "data/processed/l1_v2/P1_c1_claim.json").read_text())
            claim = L1ExtractedClaim.model_validate(payload)
            self.assertEqual(claim.context["receptor_target"], "NMDA receptor")
            self.assertEqual(claim.context["pathway"], "mTOR signaling")
            self.assertIn("species", claim.missing_required_context_slots)
            refined = refine_l1_claims([claim])
            self.assertEqual(refined["refined_claims"][0]["refined_context"]["molecular_readout"], "Gene Y expression")
            l2_input_context = refined["chunks_extracted"][0]["raw_samples"][0]["causal_tuples"][0]["context"]
            self.assertEqual(l2_input_context["receptor_target"], "NMDA receptor")

        base = payload | {"claim_id": "sentinel", "context": {"species": "unspecified"}}
        sentinel = L1ExtractedClaim.model_validate(base)
        self.assertIn("species", sentinel.missing_required_context_slots)


if __name__ == "__main__":
    unittest.main()
