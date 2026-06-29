import tempfile
import unittest
from pathlib import Path
from code_engine.evaluation.batch_discovery.batch_runner import run_batch_discovery


class BatchGlobalCorpusTests(unittest.TestCase):
    def test_overlapping_prompts_reuse_paper_and_task(self):
        fixture = Path(__file__).parent / "fixtures/prompt_bank_overlap_small.jsonl"
        with tempfile.TemporaryDirectory() as tmp:
            result = run_batch_discovery(fixture, run_dir=Path(tmp) / "run", global_corpus_dir=Path(tmp) / "corpus")
            metrics = result["metrics"]
            self.assertLess(metrics["unique_paper_count"], 2)
            self.assertGreater(metrics["duplicate_paper_hit_count"], 0)
            self.assertGreater(metrics["abstract_l1_cache_hit_count"], 0)
            self.assertGreater(metrics["estimated_api_calls_saved_by_cache"], 0)


if __name__ == "__main__": unittest.main()
