import tempfile,unittest,json
from pathlib import Path
from tests.l2_layered_helpers import run_case

class ContextRetentionTests(unittest.TestCase):
    def test_context_not_core(self):
        with tempfile.TemporaryDirectory() as tmp:
            run=Path(tmp);run_case(run);item=json.loads((run/"artifacts/l2_context_observations.jsonl").read_text().splitlines()[0]);self.assertTrue(item["retained"]);self.assertFalse(item["canonical_graph_eligible"])

if __name__=="__main__":unittest.main()
