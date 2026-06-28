import tempfile
import unittest
from pathlib import Path

from code_engine.workflow.run_state import create_run_state, load_run_state, mark_run_completed, mark_run_failed, record_artifact, save_run_state, update_step_status


class WorkflowRunStateTests(unittest.TestCase):
    def test_state_round_trip_and_mutations(self):
        with tempfile.TemporaryDirectory() as tmp:
            state = create_run_state("ketamine depression", until="search")
            update_step_status(state, "intake", "completed", summary={"ok": True})
            record_artifact(state, "intake", Path(tmp) / "artifacts/intake.json")
            save_run_state(state, tmp)
            loaded = load_run_state(tmp)
            self.assertEqual(loaded.steps["intake"].status, "completed")
            self.assertIn("intake", loaded.artifacts)
            mark_run_failed(loaded, "search", "test error")
            self.assertEqual(loaded.failed_step, "search")
            mark_run_completed(loaded)
            self.assertEqual(loaded.final_status, "planned")


if __name__ == "__main__":
    unittest.main()
