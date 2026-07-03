import inspect,unittest
from code_engine.workflow import steps
class SalvageLaneTests(unittest.TestCase):
 def test_l2_writes_separate_graph_lane(self):self.assertIn("l2_graph_observations",inspect.getsource(steps.run_l2_abstract_step))
if __name__=="__main__":unittest.main()
