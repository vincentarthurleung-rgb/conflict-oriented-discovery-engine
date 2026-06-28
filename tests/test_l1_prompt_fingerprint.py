import unittest

from code_engine.query.prompt_compatibility import (
    build_l1_prompt_fingerprint,
    compute_l1_cache_key,
)


class L1PromptFingerprintTests(unittest.TestCase):
    def setUp(self):
        self.base = {
            "paper_id": "P1", "chunk_id": "c1", "chunk_hash": "h1",
            "domain_id": "neuropharmacology", "prompt_profile_id": "neuropharmacology",
            "prompt_version": "2.0", "output_schema_version": "l1_v2_evidence_mechanism_schema",
            "extraction_policy_version": "evidence_grounded_v2",
            "model_name": "deepseek-v4-pro", "model_family": "deepseek",
        }

    def assert_change_changes_key(self, field, value):
        first = compute_l1_cache_key(build_l1_prompt_fingerprint(**self.base))
        changed = compute_l1_cache_key(build_l1_prompt_fingerprint(**{**self.base, field: value}))
        self.assertNotEqual(first, changed, field)

    def test_all_identity_fields_affect_cache_key(self):
        changes = {
            "domain_id": "general_biomedical",
            "prompt_profile_id": "general_biomedical",
            "prompt_version": "2.1",
            "output_schema_version": "schema_v3",
            "extraction_policy_version": "policy_v3",
            "chunk_hash": "h2",
            "model_name": "other-model",
            "model_family": "other-family",
            "paper_id": "P2",
            "chunk_id": "c2",
        }
        for field, value in changes.items():
            with self.subTest(field=field):
                self.assert_change_changes_key(field, value)

    def test_fingerprint_contains_complete_metadata(self):
        payload = build_l1_prompt_fingerprint(**self.base).model_dump()
        self.assertTrue(set(self.base).issubset(payload))
        self.assertTrue(payload["fingerprint_hash"])


if __name__ == "__main__":
    unittest.main()
