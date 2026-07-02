import tempfile
import unittest

from code_engine.acquisition.literature_search import execute_acquisition_plan
from code_engine.query.intent import parse_research_intent
from code_engine.query.search_planner import build_literature_search_plan


class ZeroClient:
    def search(self, *args, **kwargs): return []
    def fetch(self, *args, **kwargs): raise AssertionError("fetch must not run")


class NoSilentZeroTests(unittest.TestCase):
    def test_all_zero_has_explicit_reason(self):
        plan = build_literature_search_plan(parse_research_intent("metformin AMPK cancer"))
        with tempfile.TemporaryDirectory() as tmp:
            report = execute_acquisition_plan(plan, repository_root=tmp, execute=True, network=True, max_papers=100, client=ZeroClient())
        self.assertEqual(report["downloaded_papers"], [])
        self.assertEqual(report["pubmed_query_zero_result_count"], len(plan.pubmed_queries))
        self.assertEqual(report["reason"], "all_queries_zero_results")


if __name__ == "__main__": unittest.main()
