import json
import tempfile
import unittest
from pathlib import Path

from code_engine.extraction.l1_response import (
    L1ResponseError, normalize_l1_json_response, write_l1_diagnostic,
)


class L1ResponseNormalizationTests(unittest.TestCase):
    def test_l1_response_normalizes_list_root(self):
        value, warnings = normalize_l1_json_response([{"subject": "Ketamine"}])
        self.assertEqual(value["claims"][0]["subject"], "Ketamine")
        self.assertIn("l1_response_wrapped_list_as_claims", warnings)

    def test_l1_response_normalizes_legacy_causal_tuples(self):
        value, warnings = normalize_l1_json_response({"causal_tuples": []})
        self.assertEqual(value, {"claims": []})
        self.assertIn("legacy_causal_tuples_converted_to_claims", warnings)

    def test_l1_response_strips_markdown_fence(self):
        value, warnings = normalize_l1_json_response('```json\n{"claims": []}\n```')
        self.assertEqual(value, {"claims": []})
        self.assertIn("l1_response_markdown_fence_stripped", warnings)

    def test_l1_response_unrecognized_object_blocks(self):
        with self.assertRaises(L1ResponseError) as caught:
            normalize_l1_json_response({"result": []})
        self.assertEqual(caught.exception.error_type, "l1_response_missing_claims_root")

    def test_l1_parse_error_diagnostics_written_and_secrets_redacted(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp)
            write_l1_diagnostic(output, stage="abstract_l1", paper_id="P1", pmid="1",
                prompt_metadata={"prompt_profile_id": "p", "prompt_version": "2.1", "compiled_prompt_hash": "a" * 64},
                raw_response='api_key="secret-value" Authorization: Bearer token-value sk-abcdefghijk',
                error_type="json_parse_failed", parsed_json_type="string", recoverable=False,
                recovery_action="blocked_no_claims_emitted")
            record = json.loads((output / "l1_parse_errors.jsonl").read_text())
            raw = Path(record["raw_response_path"]).read_text()
            self.assertNotIn("secret-value", raw)
            self.assertNotIn("token-value", raw)
            self.assertNotIn("sk-abcdefghijk", raw)


if __name__ == "__main__":
    unittest.main()
