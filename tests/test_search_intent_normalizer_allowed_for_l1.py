import unittest

from code_engine.search.semantic_search_intent import normalize_search_intent_response


class AllowedForL1NormalizerTests(unittest.TestCase):
    def test_boolean_coercion_and_group_defaults(self):
        groups = {"direct_relation": [{"query": "a", "allowed_for_l1_acquisition": "yes"}],
                  "mechanism": [{"query": "b", "allowed_for_l1_acquisition": 1}],
                  "context_only": [{"query": "c"}]}
        normalized = normalize_search_intent_response({"query_groups": groups}).normalized["query_groups"]
        self.assertTrue(normalized["direct_relation"][0]["allowed_for_l1_acquisition"])
        self.assertTrue(normalized["mechanism"][0]["allowed_for_l1_acquisition"])
        self.assertFalse(normalized["context_only"][0]["allowed_for_l1_acquisition"])


if __name__ == "__main__": unittest.main()
