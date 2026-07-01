import tempfile
import unittest
from pathlib import Path

from code_engine.extraction.progressive_l1 import run_fulltext_evidence_l1


class FirstTimeoutClient:
    def __init__(self): self.calls = 0
    def extract_json(self, prompt, **_):
        self.calls += 1
        if self.calls == 1: raise TimeoutError("read timed out")
        return {"claims": []}


class FulltextTimeoutTests(unittest.TestCase):
    def test_fulltext_timeout_records_error_and_continues(self):
        spans = [{"span_id": str(i), "paper_id": f"P{i}", "source_scope": "full_text", "text": "A."} for i in (1, 2)]
        with tempfile.TemporaryDirectory() as tmp:
            result = run_fulltext_evidence_l1(spans, [], {}, Path(tmp), execute=True, api_enabled=True, llm_client=FirstTimeoutClient())
            self.assertEqual(result["summary"]["timeout_count"], 1)
            self.assertEqual(result["summary"]["successful_l1_papers"], 1)
            self.assertTrue((Path(tmp) / "fulltext_l1_errors.jsonl").exists())


if __name__ == "__main__": unittest.main()
