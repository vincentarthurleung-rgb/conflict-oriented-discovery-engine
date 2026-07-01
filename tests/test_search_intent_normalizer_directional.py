import unittest

from code_engine.search.semantic_search_intent import normalize_search_intent_response


class DirectionalNormalizerTests(unittest.TestCase):
    def test_directional_string_and_relation_default(self):
        for raw, expected in (("subject>object", True), ("metformin → AMPK", True), ("no", False), ("both", True)):
            payload = {"seed_triple": {"relation": {"name": "activates", "directional": raw}}}
            result = normalize_search_intent_response(payload)
            self.assertIs(result.normalized["seed_triple"]["relation"]["directional"], expected)
            self.assertTrue(result.repairs)

    def test_unknown_direction_defaults_from_relation(self):
        result = normalize_search_intent_response({"seed_triple": {"relation": {"name": "activates", "directional": "maybe"}}})
        self.assertTrue(result.normalized["seed_triple"]["relation"]["directional"])
        self.assertIn("search_intent_directional_defaulted_from_relation_family", result.warnings)


if __name__ == "__main__": unittest.main()
