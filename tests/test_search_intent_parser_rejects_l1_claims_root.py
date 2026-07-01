import unittest
from code_engine.search.semantic_search_intent import SearchIntentValidationError,validate_search_intent_json

class WrongTaskSchemaTests(unittest.TestCase):
    def test_claims_root_rejected_without_l1_error_message(self):
        with self.assertRaises(SearchIntentValidationError) as caught:validate_search_intent_json({"claims":[]})
        self.assertEqual(caught.exception.error_type,"search_intent_schema_validation_failed");self.assertNotIn("L1 response object must contain claims",str(caught.exception))

if __name__=="__main__":unittest.main()
