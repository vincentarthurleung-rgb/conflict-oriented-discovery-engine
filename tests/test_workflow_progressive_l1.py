import tempfile
import unittest
from pathlib import Path

from code_engine.workflow.orchestrator import run_workflow


class WorkflowProgressiveL1Tests(unittest.TestCase):
    def test_abstract_and_progressive_dry_runs(self):
        with tempfile.TemporaryDirectory() as tmp:
            state=run_workflow("sirolimus mTOR signaling",run_dir=Path(tmp),until="abstract_conflict_screening",l1_mode="abstract_screening")
            self.assertEqual(state.api_calls_made,0)
            self.assertEqual(state.network_calls_made,0)
            self.assertIn(state.steps["abstract_l1"].status,{"planned","completed"})
            self.assertIn("abstract_conflict_candidates",state.artifacts)
            self.assertGreaterEqual(state.l1_estimated_cost_usd,0)
        with tempfile.TemporaryDirectory() as tmp:
            state=run_workflow("sirolimus mTOR signaling",run_dir=Path(tmp),until="fulltext_conflict_confirmation",l1_mode="progressive_fulltext",enable_fulltext_escalation=True,l1_budget_usd=5)
            self.assertEqual((state.api_calls_made,state.network_calls_made),(0,0))
            self.assertEqual(state.steps["fulltext_escalation"].status,"planned")
            self.assertTrue((Path(tmp)/"artifacts/fulltext_escalation_plan.json").exists())
            self.assertTrue((Path(tmp)/"artifacts/fulltext_conflict_summary.json").exists())


if __name__ == "__main__": unittest.main()
