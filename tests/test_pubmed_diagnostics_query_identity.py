import tempfile
import unittest

from code_engine.acquisition.literature_search import execute_acquisition_plan
from code_engine.query.intent import parse_research_intent
from code_engine.query.search_planner import build_literature_search_plan


class EmptyClient:
    def search(self, *args, **kwargs): return []
    def fetch(self, *args, **kwargs): raise AssertionError


class PubmedDiagnosticsIdentityTests(unittest.TestCase):
    def test_query_and_intent_id_are_distinct_fields(self):
        plan = build_literature_search_plan(parse_research_intent("metformin AMPK cancer"))
        with tempfile.TemporaryDirectory() as tmp:
            report = execute_acquisition_plan(plan, repository_root=tmp, execute=True, network=True,
                                              max_papers=10, client=EmptyClient())
        rows = report["query_diagnostics"]
        self.assertEqual([row["query_id"] for row in rows], [query.query_id for query in plan.pubmed_queries])
        self.assertTrue(all(row["pubmed_query_id"] == row["query_id"] for row in rows))
        self.assertTrue(all(row["intent_id"] == plan.intent_id for row in rows))


if __name__ == "__main__": unittest.main()
