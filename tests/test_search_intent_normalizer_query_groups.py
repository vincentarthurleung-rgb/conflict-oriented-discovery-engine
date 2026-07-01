import unittest

from code_engine.search.semantic_search_intent import normalize_search_intent_response


class QueryGroupNormalizerTests(unittest.TestCase):
    def test_missing_groups_object_and_string_items(self):
        result = normalize_search_intent_response({"query_groups": {"direct_relation": "metformin AND AMPK"}})
        self.assertEqual(result.normalized["query_groups"]["direct_relation"][0]["query"], "metformin AND AMPK")
        self.assertEqual(result.normalized["query_groups"]["validation_only"], [])

    def test_queries_recovery_is_seed_aware(self):
        payload = {"seed_triple": {"subject": {"name": "metformin"}, "object": {"name": "AMPK"}},
                   "queries": ["metformin AND AMPK", "AMPK"]}
        result = normalize_search_intent_response(payload)
        self.assertEqual(len(result.normalized["query_groups"]["direct_relation"]), 1)
        self.assertEqual(len(result.normalized["query_groups"]["broad_recall"]), 1)


if __name__ == "__main__": unittest.main()
