import unittest

from code_engine.query.intake import parse_research_intake


class FakeIntakeClient:
    def extract_json(self, prompt, **kwargs):
        return {
            "research_intent": {"research_goal": "compare mechanisms", "needs_comparison": True},
            "seed_triples": [{"triple_id": "s1", "subject": "ketamine", "relation": "affects", "object": "depression", "source": "bad", "is_evidence": True}],
            "search_concepts": ["ketamine", "depression"],
        }


class LLMResearchIntakeTests(unittest.TestCase):
    def test_fake_llm_intake_forces_seed_non_evidence(self):
        result = parse_research_intake("ketamine depression", llm_client=FakeIntakeClient(), use_api=True)
        self.assertEqual(result.parser_mode, "llm_assisted")
        self.assertFalse(result.seed_triples[0].is_evidence)
        self.assertEqual(result.seed_triples[0].source, "llm_semantic_intake")

    def test_no_api_uses_deterministic_fallback(self):
        result = parse_research_intake("我想了解一下当前氯胺酮在抑郁症中的作用")
        self.assertEqual(result.api_calls_made, 0)
        self.assertEqual(result.semantic_mode, "deterministic_degraded")
        self.assertTrue(result.requires_manual_review)
        self.assertTrue(all(not item.is_evidence for item in result.seed_triples))


if __name__ == "__main__": unittest.main()
