import unittest

from code_engine.query.intent import parse_research_intent
from code_engine.query.search_planner import build_literature_search_plan


class DomainNeutralQueryPlannerTests(unittest.TestCase):
    def query_texts(self, query):
        plan = build_literature_search_plan(parse_research_intent(query))
        return {item.query_string.casefold() for item in plan.pubmed_queries}

    def test_non_pilot_queries_never_gain_ketamine_terms(self):
        for query in ("metformin AMPK cancer", "aspirin COX inflammation"):
            with self.subTest(query=query):
                self.assertFalse(any("ketamine" in text for text in self.query_texts(query)))

    def test_user_supplied_ketamine_is_preserved_without_extra_expansion(self):
        texts = self.query_texts("ketamine BDNF depression")
        self.assertTrue(any("ketamine" in text for text in texts))
        self.assertNotIn("ketamine nmda receptor antidepressant", texts)


if __name__ == "__main__": unittest.main()
