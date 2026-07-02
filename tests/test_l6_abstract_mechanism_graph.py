import tempfile, unittest
from pathlib import Path
from code_engine.reporting.full_abstract_pipeline import build_l6_mechanism_graph
from tests.full_pipeline_test_support import make_pipeline

class L6GraphTests(unittest.TestCase):
 def test_abstract_mechanism_graph_has_nodes_and_edges(self):
  with tempfile.TemporaryDirectory() as tmp: value=build_l6_mechanism_graph(make_pipeline(Path(tmp)))
  self.assertEqual(value["status"],"completed"); self.assertGreater(value["node_count"],0); self.assertGreater(value["edge_count"],0); self.assertEqual(value["evidence_level"],"abstract")
if __name__=="__main__": unittest.main()
