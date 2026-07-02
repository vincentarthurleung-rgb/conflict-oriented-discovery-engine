import tempfile
import unittest

from code_engine.acquisition.literature_search import execute_acquisition_plan
from code_engine.query.intent import parse_research_intent
from code_engine.query.search_planner import build_literature_search_plan


class ErrorClient:
    def search(self, *args, **kwargs): raise TimeoutError("mock timeout")
    def fetch(self, *args, **kwargs): raise AssertionError("fetch must not run")


class AcquisitionDiagnosticsTests(unittest.TestCase):
    def test_query_failures_are_not_silent(self):
        plan = build_literature_search_plan(parse_research_intent("metformin AMPK cancer"))
        with tempfile.TemporaryDirectory() as tmp:
            report = execute_acquisition_plan(plan, repository_root=tmp, execute=True, network=True, max_papers=100, client=ErrorClient())
        self.assertEqual(report["pubmed_query_error_count"], len(plan.pubmed_queries))
        self.assertEqual(report["reason"], "all_queries_failed")
        self.assertEqual(report["network_calls_made"], len(plan.pubmed_queries))
        self.assertTrue(all(item["error_type"] == "TimeoutError" for item in report["query_diagnostics"]))


if __name__ == "__main__": unittest.main()
