import tempfile,unittest,json
from pathlib import Path
from tests.l2_layered_helpers import run_case

class NonBinaryRetentionTests(unittest.TestCase):
    def test_non_core_observations_are_retained(self):
        with tempfile.TemporaryDirectory() as tmp:
            run=Path(tmp);run_case(run);items=[json.loads(x) for x in (run/"artifacts/l2_retained_observations.jsonl").read_text().splitlines()]
            self.assertTrue(any(x["retained"] and not x["allow_high_confidence_graph_use"] for x in items))

if __name__=="__main__":unittest.main()
