import tempfile
import unittest
from pathlib import Path

from code_engine.workflow.orchestrator import run_workflow


class WorkflowDryRunTests(unittest.TestCase):
    def test_until_search_is_local_and_persisted(self):
        with tempfile.TemporaryDirectory() as tmp:
            state = run_workflow("我想了解一下当前氯胺酮在抑郁症中的作用", run_dir=Path(tmp), until="search")
            self.assertEqual(state.steps["search"].status, "completed")
            self.assertEqual(state.steps["acquisition"].status, "pending")
            self.assertEqual((state.api_calls_made, state.network_calls_made), (0, 0))
            self.assertTrue((Path(tmp) / "run_state.json").exists())
            self.assertTrue((Path(tmp) / "run_report.md").exists())

    def test_validation_plan_is_reached_without_runtime_inputs(self):
        with tempfile.TemporaryDirectory() as tmp:
            state = run_workflow("ketamine depression mechanism", run_dir=Path(tmp), until="validation")
            self.assertEqual(state.steps["validation"].status, "planned")
            self.assertTrue((Path(tmp) / "artifacts/validation_plan.json").exists())


if __name__ == "__main__":
    unittest.main()
