import copy
import json
import unittest
from pathlib import Path

from code_engine.query.intent import parse_research_intent
from code_engine.query.prompt_compatibility import (
    ChunkProcessingRecord, build_prompt_fingerprint, build_required_fingerprint_for_intent,
    compare_prompt_compatibility,
)


FIXTURE = json.loads((Path(__file__).parent / "fixtures/intake_minimal.json").read_text())


class PromptCompatibilityTests(unittest.TestCase):
    def setUp(self):
        self.required = build_required_fingerprint_for_intent(parse_research_intent("domain: neuropharmacology ketamine depression mechanism"))
        self.base = copy.deepcopy(FIXTURE["inventory"]["papers"][0]["chunks"][0]["l1_record"])

    def decision(self, changes=None, chunk_hash="hash1", **kwargs):
        record = {**self.base, **(changes or {})}
        return compare_prompt_compatibility(record, self.required, required_chunk_hash=chunk_hash, **kwargs)

    def test_identical_reuses(self):
        self.assertEqual(self.decision().reason, "compatible_existing_l1")

    def test_prompt_version_reextracts(self):
        self.assertEqual(self.decision({"prompt_version": "1.0"}).reason, "prompt_version_changed")

    def test_schema_version_reextracts(self):
        self.assertEqual(self.decision({"output_schema_version": "v1"}).reason, "schema_version_changed")

    def test_domain_reextracts(self):
        self.assertEqual(self.decision({"domain_id": "oncology"}).reason, "domain_changed")

    def test_chunk_hash_reextracts(self):
        self.assertEqual(self.decision(chunk_hash="changed").reason, "chunk_hash_changed")

    def test_missing_l1_reextracts(self):
        self.assertEqual(compare_prompt_compatibility(None, self.required).reason, "missing_l1_output")

    def test_model_family_reuse_requires_flag(self):
        required = build_prompt_fingerprint(
            domain_id=self.required.domain_id, prompt_profile_id=self.required.prompt_profile_id,
            prompt_version=self.required.prompt_version, output_schema_version=self.required.output_schema_version,
            extraction_policy_version=self.required.extraction_policy_version,
            model_name="deepseek-compatible-new", model_family="deepseek",
        )
        denied = compare_prompt_compatibility(self.base, required, required_chunk_hash="hash1")
        allowed = compare_prompt_compatibility(self.base, required, required_chunk_hash="hash1", allow_model_family_reuse=True)
        self.assertFalse(denied.can_reuse)
        self.assertTrue(allowed.can_reuse)


if __name__ == "__main__": unittest.main()
