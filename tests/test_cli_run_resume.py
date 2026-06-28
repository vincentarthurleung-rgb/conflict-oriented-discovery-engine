import tempfile
import unittest
from pathlib import Path

from code_engine.workflow.orchestrator import run_workflow


class WorkflowResumeTests(unittest.TestCase):
    def test_resume_continues_and_resets_external_permissions(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            run_workflow("ketamine depression", run_dir=directory, until="search", api=True, network=True)
            resumed = run_workflow(resume=directory, until="acquisition")
            self.assertEqual(resumed.steps["acquisition"].status, "planned")
            self.assertFalse(resumed.api_enabled)
            self.assertFalse(resumed.network_enabled)
            self.assertEqual((resumed.api_calls_made, resumed.network_calls_made), (0, 0))


if __name__ == "__main__":
    unittest.main()
