import tempfile,unittest,json
from pathlib import Path
from tests.l2_layered_helpers import run_case

class MechanismRetentionTests(unittest.TestCase):
    def test_mechanism_retained_outside_core(self):
        with tempfile.TemporaryDirectory() as tmp:
            run=Path(tmp);run_case(run);item=json.loads((run/"artifacts/l2_mechanism_observations.jsonl").read_text().splitlines()[0]);self.assertTrue(item["retained"]);self.assertFalse(item["canonical_graph_eligible"])

if __name__=="__main__":unittest.main()
