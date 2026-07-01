import tempfile,unittest,json
from pathlib import Path
from tests.l2_layered_helpers import run_case

class OffSeedTests(unittest.TestCase):
    def test_off_seed_reason(self):
        with tempfile.TemporaryDirectory() as tmp:
            run=Path(tmp);run_case(run);item=json.loads((run/"artifacts/l2_excluded_observations.jsonl").read_text().splitlines()[0]);self.assertEqual(item["excluded_from_retention_reason"],"off_seed_relation")

if __name__=="__main__":unittest.main()
