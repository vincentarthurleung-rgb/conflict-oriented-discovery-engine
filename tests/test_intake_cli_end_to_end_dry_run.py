import tempfile
import unittest

from code_engine.cli.intake import run_intake_workflow


class IntakeCLIDryRunTests(unittest.TestCase):
    def test_natural_language_to_plans_without_calls(self):
        with tempfile.TemporaryDirectory() as tmp:
            report = run_intake_workflow("我想了解一下当前氯胺酮在抑郁症中的作用", repository_root=tmp)
        self.assertTrue(report["parsed_intent"])
        self.assertTrue(report["search_queries"])
        self.assertTrue(all(not item["is_evidence"] for item in report["seed_triples"]))
        self.assertEqual(report["api_calls_made"], 0)
        self.assertEqual(report["network_calls_made"], 0)


if __name__ == "__main__": unittest.main()
