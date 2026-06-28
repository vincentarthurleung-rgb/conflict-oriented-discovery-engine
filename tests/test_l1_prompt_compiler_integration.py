import unittest

from code_engine.extraction.l1_extractor import build_l1_dry_run_plan


class L1PromptCompilerIntegrationTests(unittest.TestCase):
    def test_neuropharmacology_selected_for_ketamine_depression(self):
        plan = build_l1_dry_run_plan(
            "Ketamine reduced depression-like behavior in mice.",
            auto_domain=True,
            cache_path="definitely_missing_cache.json",
        )
        self.assertEqual(plan["domain_id"], "neuropharmacology")
        self.assertEqual(plan["prompt_profile_id"], "neuropharmacology_l1_v2")
        self.assertIn("behavioral_assay", plan["context_slots"])
        self.assertIn("oxygen_condition", plan["context_slots"])

    def test_general_biomedical_is_default(self):
        plan = build_l1_dry_run_plan("A generic biomedical statement.", cache_path="missing.json")
        self.assertEqual(plan["domain_id"], "general_biomedical")
        self.assertEqual(plan["prompt_profile_id"], "general_biomedical_l1_v2")

    def test_compiled_prompt_hash_is_stable(self):
        kwargs = {"paper_id": "P", "chunk_id": "c", "cache_path": "missing.json"}
        first = build_l1_dry_run_plan("same text", **kwargs)
        second = build_l1_dry_run_plan("same text", **kwargs)
        self.assertEqual(first["compiled_prompt_hash"], second["compiled_prompt_hash"])
        self.assertEqual(first["prompt_fingerprint"], second["prompt_fingerprint"])
        self.assertEqual(first["api_calls_made"], 0)


if __name__ == "__main__":
    unittest.main()
