import json, tempfile, unittest
from pathlib import Path
from code_engine.tools.rebuild_graph_hypothesis import rebuild_graph_hypothesis
from tests.full_pipeline_test_support import make_pipeline

class FullRebuildTests(unittest.TestCase):
 def test_rebuild_generates_l4_l7_without_calls(self):
  with tempfile.TemporaryDirectory() as tmp:
   source=make_pipeline(Path(tmp)/"source"); (source/"run_state.json").write_text(json.dumps({"run_id":"source","query":"q","api_calls_made":4,"network_calls_made":3,"summary":{}})); (source/"artifacts/runtime_provenance_report.json").write_text("{}")
   output=rebuild_graph_hypothesis(source,output_suffix="full",stages=("l4","l5","l6","l7")); state=json.loads((output/"run_state.json").read_text()); plan_exists=(output/"artifacts/l7_validation_plan.json").exists()
  self.assertEqual(state["api_calls_made"],0); self.assertEqual(state["network_calls_made"],0); self.assertTrue(plan_exists)
if __name__=="__main__": unittest.main()
