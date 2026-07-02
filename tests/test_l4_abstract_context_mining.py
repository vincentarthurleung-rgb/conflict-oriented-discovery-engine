import tempfile, unittest
from pathlib import Path
from code_engine.reporting.full_abstract_pipeline import build_l4_context_mining
from tests.full_pipeline_test_support import make_pipeline

class L4Tests(unittest.TestCase):
 def test_abstract_context_mining_completes(self):
  with tempfile.TemporaryDirectory() as tmp: value=build_l4_context_mining(make_pipeline(Path(tmp)))
  self.assertEqual(value["status"],"completed"); self.assertEqual(value["mode"],"abstract_context_mining"); self.assertFalse(value["fulltext_required"])
if __name__=="__main__": unittest.main()
