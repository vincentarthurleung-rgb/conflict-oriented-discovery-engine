import json, tempfile, unittest
from pathlib import Path
from code_engine.evidence_graph.builders import build_merged_evidence_graph_from_run_artifacts

class NoConflictTimelineWarningTests(unittest.TestCase):
    def test_no_conflict_timeline_is_not_reported_as_mismatch(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); art=root/"artifacts"; art.mkdir()
            (art/"l2_abstract_observations.json").write_text("[]")
            (art/"conflict_evidence_timelines.jsonl").write_text(json.dumps({"conflict_id":"OLD"})+"\n")
            value=build_merged_evidence_graph_from_run_artifacts(root)["summary"]
        self.assertEqual(value["timeline_conflict_attachment_status"], "not_applicable_no_true_graph_conflicts")
        self.assertNotIn("timelines_without_conflict_match", value["export_warnings"])

if __name__ == "__main__": unittest.main()
