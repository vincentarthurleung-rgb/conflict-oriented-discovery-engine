import unittest
from code_engine.query.intent import parse_research_intent
from code_engine.query.search_planner import build_literature_search_plan
from code_engine.temporal.paper_year_filter import PaperYearFilter

class PubMedYearQueryTests(unittest.TestCase):
    def test_runtime_range_is_applied_to_every_pubmed_query(self):
        value = PaperYearFilter(2016, 2020, "discovery", "cli_argument")
        plan = build_literature_search_plan(parse_research_intent("ketamine depression"), paper_year_filter=value)
        self.assertTrue(plan.pubmed_queries)
        for query in plan.pubmed_queries:
            self.assertIn('"2016"[Date - Publication]', query.query_string)
            self.assertIn('"2020"[Date - Publication]', query.query_string)
            self.assertTrue(query.year_filter_applied_to_query)
            self.assertEqual(query.temporal_role, "discovery")

if __name__ == "__main__": unittest.main()
