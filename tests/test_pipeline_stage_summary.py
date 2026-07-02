import tempfile, unittest
from pathlib import Path
from code_engine.reporting.full_abstract_pipeline import generate_full_abstract_pipeline
from tests.full_pipeline_test_support import make_pipeline

class PipelineSummaryTests(unittest.TestCase):
 def test_abstract_pipeline_is_complete(self):
  with tempfile.TemporaryDirectory() as tmp: value=generate_full_abstract_pipeline(make_pipeline(Path(tmp)))["pipeline"]
  self.assertTrue(value["pipeline_complete_for_abstract_mode"]); self.assertFalse(value["pipeline_complete_for_fulltext_mode"]); self.assertEqual(value["blocking_errors"],[])
if __name__=="__main__": unittest.main()
