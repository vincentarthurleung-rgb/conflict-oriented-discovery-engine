import unittest

from code_engine.search.semantic_search_intent import normalize_search_intent_response


class ContextAliasesNormalizerTests(unittest.TestCase):
    def test_alias_string_and_context_terms(self):
        payload = {"seed_triple": {"subject": {"name": "metformin", "aliases": "Glucophage"},
                   "object": {"name": "AMPK"}, "context": {"context_terms": ["cancer"]}}}
        seed = normalize_search_intent_response(payload).normalized["seed_triple"]
        self.assertEqual(seed["subject"]["aliases"], ["Glucophage"])
        self.assertEqual(seed["object"]["aliases"], [])
        self.assertEqual(seed["context"]["terms"], ["cancer"])

    def test_context_list(self):
        payload = {"seed_triple": {"context": ["cancer", "metabolism"]}}
        context = normalize_search_intent_response(payload).normalized["seed_triple"]["context"]
        self.assertEqual(context["terms"], ["cancer", "metabolism"])


if __name__ == "__main__": unittest.main()
