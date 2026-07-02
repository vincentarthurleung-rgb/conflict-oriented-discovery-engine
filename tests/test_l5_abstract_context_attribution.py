import tempfile, unittest
from pathlib import Path
from code_engine.reporting.full_abstract_pipeline import build_l5_context_attribution
from tests.full_pipeline_test_support import make_pipeline

class L5Tests(unittest.TestCase):
 def test_abstract_attribution_explains_core_and_downgrades(self):
  with tempfile.TemporaryDirectory() as tmp: value=build_l5_context_attribution(make_pipeline(Path(tmp)))
  self.assertEqual(value["status"],"completed"); self.assertEqual(value["core_canonical_observation_count"],5)
if __name__=="__main__": unittest.main()
