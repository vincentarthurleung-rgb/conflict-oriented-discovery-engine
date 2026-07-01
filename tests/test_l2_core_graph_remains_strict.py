import tempfile,unittest,json
from pathlib import Path
from tests.l2_layered_helpers import run_case

class CoreStrictTests(unittest.TestCase):
    def test_core_file_only_contains_eligible(self):
        with tempfile.TemporaryDirectory() as tmp:
            run=Path(tmp);run_case(run);items=[json.loads(x) for x in (run/"artifacts/l2_core_graph_observations.jsonl").read_text().splitlines()];self.assertTrue(items);self.assertTrue(all(x["canonical_graph_eligible"] and x["graph_layer"]=="core_canonical_graph" for x in items))

if __name__=="__main__":unittest.main()
