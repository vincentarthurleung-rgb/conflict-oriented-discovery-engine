import json
import tempfile
import unittest
from pathlib import Path

from code_engine.workflow.orchestrator import run_workflow


class WorkflowExternalValidationTests(unittest.TestCase):
    def test_dry_run_artifacts_state_and_report(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            state=run_workflow("sirolimus affects mTOR signaling",run_dir=root,until="validation",l1_mode="abstract_screening",external_validation=True,validation_query_mode="auto")
            self.assertEqual((state.api_calls_made,state.network_calls_made),(0,0))
            for name in ("validation_anchors.jsonl","validation_questions.jsonl","validation_routes.jsonl","validation_query_plan.jsonl","external_validation_execution_summary.json","external_validation_aggregate_summary.json"):
                self.assertTrue((root/"artifacts"/name).exists(),name)
            self.assertGreater(state.validation_anchor_count,0)
            self.assertGreater(state.validation_question_count,0)
            self.assertEqual(state.validation_actual_evidence_count,0)
            self.assertIn("Resource-aware external validation",(root/"run_report.md").read_text())

    def test_cache_only_and_local_index_are_planned_offline(self):
        fixture_indexes=Path(__file__).parent/"fixtures/validation_indexes"
        for mode,extra in (("cache_only",{"validation_cache_dir":"missing-cache"}),("local_index",{"validation_index_dir":str(fixture_indexes)})):
            with self.subTest(mode=mode), tempfile.TemporaryDirectory() as tmp:
                state=run_workflow("sirolimus affects mTOR signaling",run_dir=Path(tmp),until="validation",l1_mode="abstract_screening",external_validation=True,validation_query_mode=mode,**extra)
                self.assertEqual((state.api_calls_made,state.network_calls_made),(0,0))
                self.assertGreater(state.validation_query_plan_count,0)


if __name__ == "__main__": unittest.main()
