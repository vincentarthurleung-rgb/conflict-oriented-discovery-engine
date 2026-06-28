import json
import tempfile
import unittest
from pathlib import Path

from code_engine.extraction.l1_refiner import load_l1_claims, refine_l1_claims
from tests.test_l1_v2_schema_converters import claim_payload


class Stage3L1V2CompatibilityTests(unittest.TestCase):
    def test_v2_and_legacy_inputs_preserve_metadata(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            v2 = root / "v2.json"
            v2.write_text(json.dumps(claim_payload()), encoding="utf-8")
            v2_result = refine_l1_claims(load_l1_claims(v2))
            self.assertEqual(v2_result["refined_claims"][0]["fingerprint"]["chunk_hash"], "h1")
            legacy = root / "legacy.json"
            legacy.write_text(json.dumps({"asset_id": "P2", "chunks_extracted": [{"chunk_index": 0, "raw_samples": [{"causal_tuples": [{"subject": "ketamine", "relation_sign": 1, "object": "BDNF", "evidence_sentence": "Ketamine increased BDNF."}]}]}]}), encoding="utf-8")
            claims = load_l1_claims(legacy)
            self.assertEqual(claims[0].paper_id, "P2")
            self.assertIn("converted_from_legacy_tuple", " ".join(claims[0].extraction_warnings))


if __name__ == "__main__": unittest.main()
