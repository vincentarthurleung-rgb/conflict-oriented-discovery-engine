import os,unittest
from unittest.mock import patch
from code_engine.validation.readiness import check_case_readiness
class ValidatorReadinessTests(unittest.TestCase):
 @patch.dict(os.environ,{"L1_PROVIDER":"deepseek","MODEL_NAME":"test","DEEPSEEK_API_KEY":"test"})
 def test_network_selects_production_v1(self):
  value=check_case_readiness("configs/case_profiles/autophagy_cancer_chemoresistance.case_profile.json","configs/search_plans/autophagy_cancer_chemoresistance_2000_2020.llm_v1.frozen.json",network_allowed=True)
  self.assertTrue(value["ready"]);self.assertEqual(["pubmed_post_cutoff","reactome","enrichr"],value["routing"]["selected_validators"]);self.assertEqual(["chembl","opentargets"],value["routing"]["recommended_but_unavailable"])
if __name__=="__main__":unittest.main()
