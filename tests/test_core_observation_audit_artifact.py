import json, tempfile, unittest
from pathlib import Path
from tests.whitebox_test_support import make_whitebox

class CoreObservationAuditTests(unittest.TestCase):
    def test_only_core_canonical_graph_rows_are_exported(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); make_whitebox(root, 5, 100)
            rows=[json.loads(x) for x in (root/"artifacts/core_observations.jsonl").read_text().splitlines()]
        self.assertEqual(len(rows), 5)
        self.assertTrue(all(row["graph_layer"] == "core_canonical_graph" for row in rows))

if __name__ == "__main__": unittest.main()
