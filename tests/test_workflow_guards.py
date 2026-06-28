import tempfile
import unittest
from pathlib import Path

from code_engine.workflow.orchestrator import run_workflow


class WorkflowGuardTests(unittest.TestCase):
    def test_execute_does_not_imply_external_access(self):
        with tempfile.TemporaryDirectory() as tmp:
            state = run_workflow("ketamine depression", run_dir=Path(tmp), until="acquisition", execute=True)
            self.assertEqual((state.api_calls_made, state.network_calls_made), (0, 0))

    def test_external_flags_without_execute_warn(self):
        with tempfile.TemporaryDirectory() as tmp:
            state = run_workflow("ketamine depression", run_dir=Path(tmp), until="search", api=True, network=True)
            self.assertTrue(any("execute=false" in item for item in state.warnings))
            self.assertEqual((state.api_calls_made, state.network_calls_made), (0, 0))


if __name__ == "__main__":
    unittest.main()
