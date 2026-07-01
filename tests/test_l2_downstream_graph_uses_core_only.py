import inspect,unittest
from code_engine.workflow.steps import run_abstract_conflict_screening_step

class DownstreamCoreOnlyTests(unittest.TestCase):
    def test_conflict_step_reads_core_artifact(self):
        self.assertIn("l2_core_graph_observations.jsonl",inspect.getsource(run_abstract_conflict_screening_step))

if __name__=="__main__":unittest.main()
