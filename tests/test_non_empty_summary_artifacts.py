import unittest
from code_engine.cli.export_case_bundle import REQUIRED
class NonEmptySummaryTests(unittest.TestCase):
 def test_required_summaries_include_pipeline_and_selection(self):
  self.assertIn("pipeline_stage_summary.json",REQUIRED);self.assertIn("validator_selection_report.json",REQUIRED)
if __name__=="__main__":unittest.main()
