import unittest
from code_engine.validation.readiness import check_case_readiness
class ResourceTests(unittest.TestCase):
    def test_skeletons_are_explicitly_unavailable(self):
        r=check_case_readiness("configs/case_profiles/metformin_ampk_cancer.case_profile.json","configs/search_plans/metformin_ampk_cancer_2000_2020.llm_v1.frozen.json")
        self.assertIn("lincs_l1000",r["routing"]["selected_validators"]); self.assertIn("reactome",r["routing"]["recommended_but_unavailable"])
