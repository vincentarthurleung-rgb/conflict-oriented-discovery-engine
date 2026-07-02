import tempfile,unittest
from tests.test_lincs_score_provenance import validated
class GuardTests(unittest.TestCase):
 def test_guard_records_no_case_specific_tuning(self):
  with tempfile.TemporaryDirectory() as tmp: summary,_=validated(tmp)
  guard=summary["anti_overfitting_guard"]; self.assertFalse(guard["case_specific_threshold_tuning"]); self.assertFalse(guard["case_specific_gene_set_expansion"]); self.assertFalse(guard["interpretation_forced_to_supportive"]); self.assertEqual(summary["interpretation_distribution"]["supportive"],0)
if __name__=="__main__": unittest.main()
