import json
import tempfile
import unittest
from pathlib import Path

from code_engine.extraction.abstract_screening import run_abstract_l1_screening


class FirstTimeoutClient:
    def __init__(self): self.calls = 0
    def extract_json(self, prompt, **_):
        self.calls += 1
        if self.calls == 1: raise TimeoutError("read operation timed out")
        return {"claims": []}


class AbstractTimeoutContinueTests(unittest.TestCase):
    def test_timeout_records_error_and_continues(self):
        papers = [{"paper_id": "P1", "abstract": "A."}, {"paper_id": "P2", "abstract": "B."}]
        with tempfile.TemporaryDirectory() as tmp:
            result = run_abstract_l1_screening(papers, {}, Path(tmp), execute=True, api_enabled=True, llm_client=FirstTimeoutClient())
            summary = result["summary"]
            self.assertEqual((summary["attempted_l1_papers"], summary["successful_l1_papers"], summary["failed_l1_papers"]), (2, 1, 1))
            self.assertEqual(summary["timeout_count"], 1)
            self.assertIsNone(summary["blocked_reason"])
            error = json.loads((Path(tmp) / "abstract_l1_errors.jsonl").read_text())
            self.assertTrue(error["continued"])
            self.assertNotIn("api_key", json.dumps(error).lower())


if __name__ == "__main__": unittest.main()
