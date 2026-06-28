import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from code_engine.extraction.l1_extractor import execute_l1_extraction


class FakeDeepSeek:
    def __init__(self): self.calls = 0
    def extract_json(self, prompt, **kwargs):
        self.calls += 1
        return {"claims": [{"subject_raw": "ketamine", "relation_raw": "increased", "direct_relation_sign": "positive", "object_raw": "BDNF", "evidence_sentence": "Ketamine increased BDNF.", "statement_type": "direct_experimental_result", "evidence_type": "animal_model", "confidence": 0.9}]}


class L1ExecutableExtractionTests(unittest.TestCase):
    def test_gating_and_fake_execute_outputs(self):
        chunk = [{"paper_id": "P1", "chunk_id": "c1", "content": "Ketamine increased BDNF."}]
        with tempfile.TemporaryDirectory() as tmp:
            fake = FakeDeepSeek()
            dry = execute_l1_extraction(chunk, repository_root=tmp, client=fake)
            no_api = execute_l1_extraction(chunk, repository_root=tmp, execute=True, api=False, client=fake)
            self.assertEqual(fake.calls, 0)
            self.assertTrue(dry["extraction_needed"] and no_api["extraction_needed"])
            done = execute_l1_extraction(chunk, repository_root=tmp, execute=True, api=True, client=fake)
            self.assertEqual(fake.calls, 1)
            self.assertEqual(done["api_calls_made"], 1)
            claim = json.loads((Path(tmp) / "data/processed/l1_v2/P1_c1_claim.json").read_text())
            self.assertEqual(claim["paper_id"], "P1")
            legacy = json.loads((Path(tmp) / "data/processed/l1/P1_extracted.json").read_text())
            self.assertIn("chunks_extracted", legacy)

    def test_missing_api_key_is_clear(self):
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {}, clear=True):
            with self.assertRaisesRegex(ValueError, "DEEPSEEK_API_KEY"):
                execute_l1_extraction([], repository_root=tmp, execute=True, api=True)


if __name__ == "__main__": unittest.main()
