import unittest

from code_engine.query.intent import parse_research_intent
from code_engine.query.search_planner import build_literature_search_plan


class FakeSearchLLM:
    def extract_json(self, prompt, **kwargs):
        return {"queries": ["ketamine plasticity", "https://bad.example", "ketamine; depression"]}


class LiteratureSearchPlannerLLMTests(unittest.TestCase):
    def test_llm_queries_are_sanitized(self):
        plan = build_literature_search_plan(parse_research_intent("ketamine depression"), llm_client=FakeSearchLLM(), use_llm=True)
        texts = [item.query_string for item in plan.secondary_queries]
        self.assertIn("ketamine plasticity", texts)
        self.assertNotIn("https://bad.example", texts)
        self.assertIn("query_sanitized", plan.warnings)

    def test_ketamine_and_comparison_queries(self):
        plan = build_literature_search_plan(parse_research_intent("氯胺酮抗抑郁机制在抑郁症中的作用"))
        texts = {item.query_string for item in plan.primary_queries + plan.secondary_queries + plan.mechanism_queries}
        self.assertIn("ketamine depression", texts)
        self.assertIn("ketamine mTOR BDNF depression", texts)
        comparison = build_literature_search_plan(parse_research_intent("compare ketamine and esketamine in depression"))
        compare_texts = {item.query_string for item in comparison.comparison_queries}
        self.assertIn("ketamine esketamine depression mechanism", compare_texts)


if __name__ == "__main__": unittest.main()
