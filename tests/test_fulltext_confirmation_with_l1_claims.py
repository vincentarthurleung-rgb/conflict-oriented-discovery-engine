import unittest
from code_engine.fulltext.conflict_confirmation import confirm_fulltext_conflicts
class L1ConfirmationTests(unittest.TestCase):
 def test_opposing_mock_l1_claims_support(self):
  claims=[{"claim_id":"1","polarity":"positive","relation_family":"r","linked_conflict_candidate_ids":["c"]},{"claim_id":"2","polarity":"negative","relation_family":"r","linked_conflict_candidate_ids":["c"]}]
  result=confirm_fulltext_conflicts([{"candidate_id":"c","paper_ids":["p"]}],claims,[])
  self.assertEqual(result["confirmations"][0]["full_text_confirmation_status"],"full_text_supported")
