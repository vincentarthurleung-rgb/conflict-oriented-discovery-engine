import unittest

from code_engine.extraction.l1_extractor import build_l1_dry_run_plan


class DomainSpecificPromptSelectionTests(unittest.TestCase):
    def plan(self, text):
        return build_l1_dry_run_plan(text, auto_domain=True, cache_path="missing-cache.json")

    def test_domain_specific_profiles_are_selected(self):
        cases = (
            ("domain: neuropharmacology mechanism", "neuropharmacology_l1_v2"),
            ("esketamine clinical trial efficacy", "clinical_outcome_l1_v2"),
            ("ketamine NMDA receptor binding affinity", "drug_target_binding_l1_v2"),
        )
        for text, expected in cases:
            with self.subTest(text=text):
                self.assertEqual(self.plan(text)["prompt_profile_id"], expected)

    def test_pilot_terms_do_not_select_a_profile_implicitly(self):
        self.assertEqual(self.plan("ketamine depression mechanism")["prompt_profile_id"], "general_biomedical_l1_v2")

    def test_prompt_profile_changes_fingerprint(self):
        general = build_l1_dry_run_plan("neutral text", domain="general_biomedical", cache_path="missing-cache.json")
        pathway = build_l1_dry_run_plan("neutral text", domain="pathway_biology", cache_path="missing-cache.json")
        self.assertNotEqual(general["prompt_fingerprint"]["fingerprint_hash"], pathway["prompt_fingerprint"]["fingerprint_hash"])
        self.assertNotEqual(general["compiled_prompt_hash"], pathway["compiled_prompt_hash"])


if __name__ == "__main__":
    unittest.main()
