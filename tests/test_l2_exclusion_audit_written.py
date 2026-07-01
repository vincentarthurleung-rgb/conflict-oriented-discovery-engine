import tempfile,unittest,json
from pathlib import Path
from tests.l2_layered_helpers import run_case

class ExclusionAuditTests(unittest.TestCase):
    def test_every_non_core_has_reason(self):
        with tempfile.TemporaryDirectory() as tmp:
            run=Path(tmp);run_case(run);items=[json.loads(x) for x in (run/"artifacts/l2_exclusion_audit.jsonl").read_text().splitlines()];self.assertTrue(items);self.assertTrue(all(x["excluded_from_core_reason"] for x in items))

if __name__=="__main__":unittest.main()
