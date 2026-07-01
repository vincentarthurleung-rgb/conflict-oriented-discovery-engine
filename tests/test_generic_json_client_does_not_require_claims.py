import unittest
from unittest.mock import patch
from code_engine.extraction.deepseek_client import DeepSeekClient

class Response:
    def raise_for_status(self): pass
    def json(self): return {"choices":[{"message":{"content":'{"seed_triple": {}, "query_groups": {}}'}}]}

class GenericClientTests(unittest.TestCase):
    def test_deepseek_generic_json_has_no_claims_contract(self):
        with patch("httpx.post",return_value=Response()):
            value=DeepSeekClient("fake",max_retries=0).extract_json("prompt")
        self.assertIn("seed_triple",value);self.assertNotIn("claims",value)

if __name__=="__main__":unittest.main()
