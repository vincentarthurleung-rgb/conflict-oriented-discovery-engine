import json, tempfile, unittest
from tests.rebuild_test_support import make_rebuild

class RebuiltRunIdTests(unittest.TestCase):
    def test_summary_identifies_source_and_rebuilt_runs(self):
        with tempfile.TemporaryDirectory() as tmp:
            source, output = make_rebuild(tmp)
            summary = json.loads((output / "artifacts/merged_evidence_graph_summary.json").read_text())
        self.assertEqual(summary["run_id"], output.name)
        self.assertEqual(summary["source_run_id"], source.name)
        self.assertEqual(summary["rebuilt_run_id"], output.name)
        self.assertEqual(summary["artifact_run_id_semantics"], "run_id_is_current_rebuilt_run")

if __name__ == "__main__": unittest.main()
