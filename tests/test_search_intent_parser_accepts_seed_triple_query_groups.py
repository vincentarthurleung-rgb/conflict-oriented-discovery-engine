import unittest
from code_engine.search.semantic_search_intent import validate_search_intent_json
from tests.search_intent_helpers import PAYLOAD

class SearchParserAcceptTests(unittest.TestCase):
    def test_valid_task_schema(self):
        value=validate_search_intent_json(PAYLOAD);self.assertEqual(value.seed_triple.subject.name,"metformin");self.assertTrue(value.search_intent_schema_valid)

if __name__=="__main__":unittest.main()
