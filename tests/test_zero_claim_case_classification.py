import unittest
from code_engine.system_b.case_card import CaseCardBuilder
class ZeroClaimClassificationTests(unittest.TestCase):
 def test_execution_passed_is_not_scientific_success(self):
  bundle={"case_id":"x","manifest":{"case_type":"conflict_enriched","case_execution_outcome":"execution_passed","scientific_output_class":"no_core_observations","is_zero_claim_case":True,"zero_claim_reason":"gate","core_observation_count":0},"pipeline":{},"external_validation":{}}
  card=CaseCardBuilder().build(bundle);self.assertEqual("execution_passed",card["case_execution_outcome"]);self.assertEqual("no_core_observations",card["scientific_output_class"]);self.assertTrue(card["is_zero_claim_case"])
if __name__=="__main__":unittest.main()
