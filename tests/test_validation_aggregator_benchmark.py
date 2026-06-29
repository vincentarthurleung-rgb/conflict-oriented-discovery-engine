import tempfile
import unittest
from pathlib import Path

from code_engine.validation.benchmarks.runner import run_aggregator_benchmark


class ValidationAggregatorBenchmarkTests(unittest.TestCase):
    def test_all_deterministic_cases_match(self):
        cases = Path(__file__).parent / "fixtures/validation_benchmark/benchmark_cases.jsonl"
        with tempfile.TemporaryDirectory() as tmp:
            metrics = run_aggregator_benchmark(cases, Path(tmp) / "report.json")
        self.assertEqual(metrics["case_count"], 10)
        self.assertEqual(metrics["status_accuracy"], 1.0)


if __name__ == "__main__": unittest.main()
