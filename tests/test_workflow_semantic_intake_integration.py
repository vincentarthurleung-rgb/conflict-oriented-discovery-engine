import tempfile
import unittest
from pathlib import Path

from code_engine.workflow.orchestrator import run_workflow
from tests.test_semantic_intake_llm_first import FakeLLM, payload


class WorkflowSemanticIntakeTests(unittest.TestCase):
    def test_dry_run_records_degraded_mode(self):
        with tempfile.TemporaryDirectory() as tmp:
            state = run_workflow("氯胺酮与抑郁症", run_dir=Path(tmp), until="search")
            self.assertEqual(state.semantic_mode, "deterministic_degraded")
            self.assertEqual(state.api_calls_made, 0)

    def test_fake_llm_records_semantic_mode(self):
        with tempfile.TemporaryDirectory() as tmp:
            state = run_workflow("query", run_dir=Path(tmp), until="search", execute=True, api=True, semantic_llm_client=FakeLLM(payload()))
            self.assertEqual(state.semantic_mode, "llm_semantic")
            self.assertEqual(state.api_calls_made, 0)

    def test_uncertain_execute_blocks_unless_allowed(self):
        with tempfile.TemporaryDirectory() as tmp:
            blocked = run_workflow("unknown topic", run_dir=Path(tmp), until="search", execute=True)
            self.assertEqual(blocked.steps["intake"].status, "blocked")
        with tempfile.TemporaryDirectory() as tmp:
            allowed = run_workflow("unknown topic", run_dir=Path(tmp), until="search", execute=True, allow_uncertain_intake=True)
            self.assertEqual(allowed.steps["search"].status, "completed")


if __name__ == "__main__": unittest.main()
