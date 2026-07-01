import unittest

from code_engine.search.semantic_search_intent import normalize_search_intent_response


class PurposeNormalizerTests(unittest.TestCase):
    def test_prose_and_missing_purpose_are_derived_from_group(self):
        groups = {"direct_relation": [{"query": "a", "purpose": "Find direct evidence"}],
                  "mechanism": [{"query": "b"}]}
        result = normalize_search_intent_response({"query_groups": groups})
        self.assertEqual(result.normalized["query_groups"]["direct_relation"][0]["purpose"], "direct_relation")
        self.assertEqual(result.normalized["query_groups"]["mechanism"][0]["purpose"], "mechanism")


if __name__ == "__main__": unittest.main()
