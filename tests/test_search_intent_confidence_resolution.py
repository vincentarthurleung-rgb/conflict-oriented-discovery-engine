import unittest

from code_engine.search.semantic_search_intent import resolve_search_intent_confidence


class SearchIntentConfidenceResolutionTests(unittest.TestCase):
    def test_semantic_intake_fallback(self):
        value = resolve_search_intent_confidence(None, .6, .5, schema_valid=True,
                                                 llm_search_intent_used=True, allowed_l1_query_count=6)
        self.assertEqual(value, (.6, "semantic_intake_confidence"))

    def test_guarded_default(self):
        value = resolve_search_intent_confidence(None, None, None, schema_valid=True,
                                                 llm_search_intent_used=True, allowed_l1_query_count=1)
        self.assertEqual(value, (.6, "schema_valid_guarded_default"))

    def test_failed_planner_stays_zero(self):
        value = resolve_search_intent_confidence(.9, .8, .7, schema_valid=False,
                                                 llm_search_intent_used=False, allowed_l1_query_count=0)
        self.assertEqual(value, (0.0, "failed_zero"))

    def test_llm_value_is_clipped(self):
        value = resolve_search_intent_confidence(1.4, .6, .5, schema_valid=True,
                                                 llm_search_intent_used=True, allowed_l1_query_count=1)
        self.assertEqual(value, (1.0, "llm_response_confidence"))


if __name__ == "__main__": unittest.main()
