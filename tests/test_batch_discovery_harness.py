import json
import tempfile
import unittest
from pathlib import Path

from code_engine.evaluation.batch_discovery.batch_runner import run_batch_discovery
from code_engine.evaluation.batch_discovery.metrics import compute_batch_metrics
from code_engine.evaluation.batch_discovery.prompt_bank import load_prompt_bank


FIXTURE=Path(__file__).parent/"fixtures/prompt_bank_small.jsonl"


class BatchDiscoveryHarnessTests(unittest.TestCase):
    def test_offline_batch_outputs_and_metrics(self):
        self.assertEqual(len(load_prompt_bank(FIXTURE)),2)
        with tempfile.TemporaryDirectory() as tmp:
            result=run_batch_discovery(FIXTURE,run_dir=tmp,max_prompts=10,sample_conflict_count=5)
            root=Path(tmp)
            self.assertEqual(result["manifest"]["api_calls_made"],0)
            self.assertEqual(result["manifest"]["network_calls_made"],0)
            self.assertEqual(result["metrics"]["abstract_conflict_candidate_count"],1)
            for name in ("batch_run_manifest.json","conflict_annotation_schema.json","conflict_annotation_sample.jsonl","batch_metrics_summary.json","batch_discovery_report.md"):
                self.assertTrue((root/name).exists())

    def test_annotation_metrics(self):
        metrics=compute_batch_metrics(prompts=[{"prompt_id":"P"}],candidates=[{"candidate_id":"C"}],annotations=[{"annotation_label":"valid_direct_conflict"}])
        self.assertEqual(metrics["valid_conflict_rate"],1.0)
        self.assertEqual(metrics["primary_evaluation_goal"],"automated_problem_discovery")


if __name__ == "__main__": unittest.main()
