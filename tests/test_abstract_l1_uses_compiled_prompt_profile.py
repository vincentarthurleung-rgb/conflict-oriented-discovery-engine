import tempfile
import unittest
from pathlib import Path

from code_engine.extraction.abstract_screening import run_abstract_l1_screening


class CapturingClient:
    def __init__(self, response=None):
        self.prompt = ""
        self.response = response if response is not None else {"claims": []}

    def extract_json(self, prompt, **_):
        self.prompt = prompt
        return self.response


class AbstractCompiledPromptTests(unittest.TestCase):
    def test_abstract_l1_uses_compiled_prompt_profile_version_21(self):
        client = CapturingClient([])
        with tempfile.TemporaryDirectory() as tmp:
            result = run_abstract_l1_screening(
                [{"paper_id": "P1", "abstract": "Ketamine increased BDNF."}],
                {"domain_id": "neuropharmacology", "prompt_profile_id": "neuropharmacology_l1_v2"},
                Path(tmp), execute=True, api_enabled=True, llm_client=client, pilot_profile="ketamine")
            self.assertIn('Root object: {"claims": [...]}', client.prompt)
            self.assertIn("version 2.1", client.prompt)
            self.assertIn("therapeutic_direction", client.prompt)
            self.assertIn('output ""', client.prompt)
            self.assertNotIn("Extract grounded biomedical claims from this abstract", client.prompt)
            self.assertIn("l1_response_wrapped_list_as_claims", result["summary"]["warnings"])
            self.assertEqual(result["summary"]["prompt_calls"][0]["pilot_profile"], "ketamine")


if __name__ == "__main__":
    unittest.main()
