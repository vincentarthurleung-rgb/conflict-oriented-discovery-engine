import tempfile, unittest
from pathlib import Path
from code_engine.reporting.full_abstract_pipeline import build_l7_validation_stub
from tests.full_pipeline_test_support import make_pipeline

class L7Tests(unittest.TestCase):
 def test_missing_index_generates_complete_plan_outcome(self):
  with tempfile.TemporaryDirectory() as tmp: value=build_l7_validation_stub(make_pipeline(Path(tmp)))
  self.assertEqual(value["status"],"not_run_config_missing"); self.assertTrue(value["validation_plan_generated"]); self.assertFalse(value["validation_executed"]); self.assertEqual(value["api_calls"],0)
if __name__=="__main__": unittest.main()
