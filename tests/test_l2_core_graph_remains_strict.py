import tempfile,unittest,json
from pathlib import Path
from tests.l2_layered_helpers import run_case

class CoreStrictTests(unittest.TestCase):
    def test_core_file_only_contains_eligible(self):
        with tempfile.TemporaryDirectory() as tmp:
            run=Path(tmp);run_case(run);items=[json.loads(x) for x in (run/"artifacts/l2_core_graph_observations.jsonl").read_text().splitlines() if x.strip()]
            self.assertTrue(all(x["canonical_graph_eligible"] and x["graph_layer"]=="core_canonical_graph" for x in items))
            self.assertTrue(all(not str(x.get("subject_canonical_id","")).startswith("RUN:") and not str(x.get("object_canonical_id","")).startswith("RUN:") for x in items))
            retained=[json.loads(x) for x in (run/"artifacts/l2_retained_observations.jsonl").read_text().splitlines() if x.strip()]
            self.assertTrue(retained)
            self.assertTrue(any(x.get("scientific_edge_layer")=="causal_reviewable" for x in retained))

if __name__=="__main__":unittest.main()
