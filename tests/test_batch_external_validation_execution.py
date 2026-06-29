import tempfile
import unittest
from pathlib import Path

from code_engine.evaluation.batch_discovery.validation import run_batch_external_validation


CANDIDATE = {"candidate_id":"C1","prompt_id":"P1","subject_canonical_id":"CHEM:SIROLIMUS","object_canonical_id":"GENE:MTOR","subject_name":"sirolimus","object_name":"MTOR","relation_family":"drug_target","polarity_type":"mechanistic"}


class BatchExternalValidationTests(unittest.TestCase):
    def test_planned_and_local_execution_artifacts(self):
        indexes = Path(__file__).parent / "fixtures/validation_indexes"
        with tempfile.TemporaryDirectory() as tmp:
            planned = run_batch_external_validation([CANDIDATE], tmp, query_mode="local_index", index_dir=str(indexes))
            self.assertEqual(planned["execution"].network_calls_made, 0)
            for name in ("batch_validation_anchors.jsonl", "batch_validation_query_plans.jsonl", "batch_external_validation_evidence.jsonl", "batch_external_validation_signals.jsonl", "batch_validation_metrics.json"):
                self.assertTrue((Path(tmp) / name).exists())
            executed = run_batch_external_validation([CANDIDATE], tmp, execute=True, query_mode="local_index", index_dir=str(indexes))
            self.assertGreaterEqual(executed["metrics"]["validation_evidence_count"], 1)
            self.assertEqual(executed["execution"].network_calls_made, 0)
            self.assertIn("validation_external_index_not_configured_count", executed["metrics"])


if __name__ == "__main__": unittest.main()
