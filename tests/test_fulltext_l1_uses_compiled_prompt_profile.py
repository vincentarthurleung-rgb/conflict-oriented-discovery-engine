import tempfile
import unittest
from pathlib import Path

from code_engine.extraction.progressive_l1 import run_fulltext_evidence_l1


class CapturingClient:
    def __init__(self): self.prompt = ""
    def extract_json(self, prompt, **_):
        self.prompt = prompt
        return '```json\n{"claims": []}\n```'


class FulltextCompiledPromptTests(unittest.TestCase):
    def test_fulltext_l1_uses_compiled_prompt_profile(self):
        span = {"span_id": "S", "paper_id": "P", "source_scope": "full_text", "text": "A changed B."}
        client = CapturingClient()
        with tempfile.TemporaryDirectory() as tmp:
            result = run_fulltext_evidence_l1([span], [], {"prompt_profile_id": "general_biomedical_l1_v2"}, Path(tmp), execute=True, api_enabled=True, llm_client=client)
            self.assertIn('Root object: {"claims": [...]}', client.prompt)
            self.assertIn("version 2.1", client.prompt)
            self.assertIn("l1_response_markdown_fence_stripped", result["summary"]["warnings"])


if __name__ == "__main__":
    unittest.main()
