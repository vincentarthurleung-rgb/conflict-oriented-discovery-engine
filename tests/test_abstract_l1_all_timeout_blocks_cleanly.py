import tempfile
import unittest
from pathlib import Path

from code_engine.extraction.abstract_screening import run_abstract_l1_screening


class TimeoutClient:
    def extract_json(self, prompt, **_): raise TimeoutError("read timeout")


class AbstractAllTimeoutTests(unittest.TestCase):
    def test_all_timeout_blocks_cleanly(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = run_abstract_l1_screening([{"paper_id": "P", "abstract": "A."}], {}, Path(tmp), execute=True, api_enabled=True, llm_client=TimeoutClient())
            self.assertEqual(result["summary"]["blocked_reason"], "all_l1_extractions_failed")
            self.assertEqual(result["summary"]["timeout_count"], 1)


if __name__ == "__main__": unittest.main()
