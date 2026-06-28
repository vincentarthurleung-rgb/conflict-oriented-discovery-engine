import tempfile
import unittest
from pathlib import Path

from code_engine.workflow.orchestrator import run_workflow


class WorkflowPartialReportTests(unittest.TestCase):
    def test_missing_data_still_produces_report(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            state = run_workflow("ketamine depression", run_dir=directory)
            report = (directory / "run_report.md").read_text(encoding="utf-8")
            self.assertEqual(state.steps["payload"].status, "blocked")
            self.assertIn("Next recommended command", report)
            self.assertTrue((directory / "final_report.md").exists())


if __name__ == "__main__":
    unittest.main()
