import tempfile
import unittest

from code_engine.acquisition.literature_search import execute_acquisition_plan
from code_engine.query.intent import parse_research_intent
from code_engine.query.search_planner import build_literature_search_plan
from code_engine.temporal.paper_year_filter import PaperYearFilter


class WindowClient:
    def __init__(self): self.windows = []
    def search(self, query, source, max_results, year_from=None, year_to=None):
        self.windows.append((year_from, year_to)); return []
    def fetch(self, *args): raise AssertionError


class DateWindowDiagnosticsTests(unittest.TestCase):
    def test_broad_window_attempts_every_query_with_explicit_window(self):
        plan = build_literature_search_plan(parse_research_intent("metformin AMPK cancer"),
                                            paper_year_filter=PaperYearFilter(2000, 2020, "discovery"))
        client = WindowClient()
        with tempfile.TemporaryDirectory() as tmp:
            report = execute_acquisition_plan(plan, repository_root=tmp, execute=True, network=True,
                                              max_papers=100, client=client, year_from=2000, year_to=2020)
        self.assertEqual(client.windows, [(2000, 2020)] * len(plan.pubmed_queries))
        self.assertEqual(len(report["query_diagnostics"]), len(plan.pubmed_queries))


if __name__ == "__main__": unittest.main()
