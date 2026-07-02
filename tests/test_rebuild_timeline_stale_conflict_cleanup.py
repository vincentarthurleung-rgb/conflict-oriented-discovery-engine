import json, tempfile, unittest
from tests.rebuild_test_support import make_rebuild

class RebuildTimelineTests(unittest.TestCase):
    def test_stale_timeline_is_not_conflict_attached(self):
        with tempfile.TemporaryDirectory() as tmp:
            _, output = make_rebuild(tmp)
            summary = json.loads((output / "artifacts/merged_evidence_graph_summary.json").read_text())
            timeline = (output / "artifacts/conflict_evidence_timelines.jsonl").read_text()
        self.assertEqual(summary["graph_conflict_candidates_used_by_timeline"], 0)
        self.assertEqual(summary["timeline_rebuild_status"], "skipped_due_to_no_true_graph_conflicts")
        self.assertTrue(summary["stale_source_timeline_artifacts_ignored"])
        self.assertEqual(timeline, "")

if __name__ == "__main__": unittest.main()
