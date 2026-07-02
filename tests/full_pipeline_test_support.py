import json
from pathlib import Path
from tests.whitebox_test_support import make_whitebox

def make_pipeline(root: Path):
    make_whitebox(root, 5, 10); art=root/"artifacts"
    rows=json.loads((art/"l2_abstract_observations.json").read_text())
    (art/"l2_retained_observations.jsonl").write_text("".join(json.dumps(row)+"\n" for row in rows))
    return root
