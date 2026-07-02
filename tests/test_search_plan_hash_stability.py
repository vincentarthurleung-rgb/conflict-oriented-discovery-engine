import unittest

from code_engine.query.intent import parse_research_intent
from code_engine.query.search_planner import build_literature_search_plan
from code_engine.search.search_plan_replay import executable_query_hash


class SearchPlanHashTests(unittest.TestCase):
    def test_hash_ignores_unrelated_metadata_and_detects_query_change(self):
        plan = build_literature_search_plan(parse_research_intent("metformin AMPK cancer"))
        first = executable_query_hash(plan)
        plan.warnings.append("volatile")
        self.assertEqual(first, executable_query_hash(plan))
        plan.pubmed_queries[0].query_string += " AND test"
        self.assertNotEqual(first, executable_query_hash(plan))


if __name__ == "__main__": unittest.main()
