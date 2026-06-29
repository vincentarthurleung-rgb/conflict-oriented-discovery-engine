import json
import tempfile
import unittest
from pathlib import Path
from code_engine.evaluation.batch_discovery.batch_runner import run_batch_discovery


class BatchHypothesisGenerationTests(unittest.TestCase):
    def test_batch_conflict_generates_traceable_hypothesis_metrics(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); bank = root / "bank.jsonl"
            prompt = {"prompt_id": "P", "query": "s affects o", "abstract_claims": [{"claim_id": "1", "paper_id": "A", "source_scope": "abstract", "subject_raw": "s", "object_raw": "o", "subject_canonical_id": "S", "object_canonical_id": "O", "allow_high_confidence_graph_use": True, "direction": "activate"}, {"claim_id": "2", "paper_id": "B", "source_scope": "abstract", "subject_raw": "s", "object_raw": "o", "subject_canonical_id": "S", "object_canonical_id": "O", "allow_high_confidence_graph_use": True, "direction": "inhibit"}], "normalized_observations": []}
            bank.write_text(json.dumps(prompt) + "\n")
            result = run_batch_discovery(bank, run_dir=root / "run", min_evidence_count=1, min_entropy=0)
            self.assertGreater(result["metrics"]["hypothesis_count"], 0)
            self.assertNotIn("hypothesis_accuracy", result["metrics"])
            for name in ("batch_hypothesis_candidates.jsonl", "batch_hypothesis_hyperedges.jsonl", "batch_hypothesis_summary.json"):
                self.assertTrue((root / "run" / name).exists())


if __name__ == "__main__": unittest.main()
