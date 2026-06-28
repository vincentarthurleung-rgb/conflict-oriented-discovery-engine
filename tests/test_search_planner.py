import json
import unittest
from pathlib import Path

from code_engine.query.intent import parse_research_intent
from code_engine.query.search_planner import build_literature_search_plan


FIXTURE = json.loads((Path(__file__).parent / "fixtures/intake_minimal.json").read_text())


class SearchPlannerTests(unittest.TestCase):
    def test_mechanism_overview_has_molecular_behavioral_clinical_queries(self):
        plan = build_literature_search_plan(parse_research_intent(FIXTURE["natural_language_queries"][0]))
        queries = [item.query_string for item in plan.primary_queries + plan.secondary_queries + plan.mechanism_queries + plan.clinical_queries]
        self.assertIn("ketamine BDNF depression", queries)
        self.assertTrue(any("behavioral" in query for query in queries))
        self.assertTrue(any("clinical" in query for query in queries))

    def test_comparison_has_pairwise_query(self):
        plan = build_literature_search_plan(parse_research_intent(FIXTURE["natural_language_queries"][2]))
        queries = [item.query_string for item in plan.primary_queries]
        self.assertIn("esketamine ketamine depression comparison", queries)


if __name__ == "__main__": unittest.main()
