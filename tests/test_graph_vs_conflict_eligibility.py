import unittest
from code_engine.normalization.graph_eligibility import apply_graph_eligibility
class EligibilityTests(unittest.TestCase):
 def test_local_graph_entry_is_not_conflict_input(self):
  value=apply_graph_eligibility({"subject_raw":"Specific process A","subject_type":"biological_process","object_raw":"Specific response B","object_type":"phenotype","relation_raw":"increased","relation_family":"activation","evidence_sentence":"Specific process A increased Specific response B.","paper_id":"P1"})
  self.assertTrue(value["graph_observation_eligible"]);self.assertFalse(value["conflict_reasoning_eligible"]);self.assertIn("local_canonical_id_requires_review",value["conflict_ineligibility_reasons"])
 def test_external_strong_entry_can_be_conflict_input(self):
  value=apply_graph_eligibility({"subject_canonical_id":"X:1","object_canonical_id":"X:2","relation_raw":"increased","relation_family":"activation","evidence_sentence":"A increased B.","paper_id":"P1"},existing_conflict_eligible=True)
  self.assertTrue(value["conflict_reasoning_eligible"])
if __name__=="__main__":unittest.main()
