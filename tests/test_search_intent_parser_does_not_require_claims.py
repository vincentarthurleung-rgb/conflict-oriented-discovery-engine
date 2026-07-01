import unittest
from code_engine.search.semantic_search_intent import validate_search_intent_json
from tests.search_intent_helpers import PAYLOAD

class NoClaimsRequirementTests(unittest.TestCase):
    def test_valid_without_claims(self):
        self.assertNotIn("claims",PAYLOAD);self.assertTrue(validate_search_intent_json(PAYLOAD).query_groups)

if __name__=="__main__":unittest.main()
