import unittest

from code_engine.extraction.converters import (
    l1_claim_to_evidence_record,
    l1_claim_to_legacy_tuple,
    legacy_tuple_to_l1_claim,
)
from code_engine.schemas.l1_extraction import L1ExtractedClaim


def claim_payload():
    return {
        "claim_id": "claim-1", "paper_id": "P1", "chunk_id": "c1", "chunk_hash": "h1",
        "domain_id": "neuropharmacology", "prompt_profile_id": "neuropharmacology",
        "prompt_version": "2.0", "output_schema_version": "l1_v2_evidence_mechanism_schema",
        "extraction_policy_version": "evidence_grounded_v2", "model_name": "model",
        "model_family": "family", "compiled_prompt_hash": "prompt-hash",
        "subject_raw": "ketamine", "subject_type": "compound", "relation_raw": "increased",
        "relation_family": "causal", "direct_relation_sign": "positive", "object_raw": "BDNF",
        "object_type": "gene", "evidence_sentence": "Ketamine increased BDNF in mice.",
        "evidence_quote": "Ketamine increased BDNF", "section": "Results",
        "statement_type": "direct_experimental_result", "evidence_type": "animal_model",
        "confidence": 0.9, "subject_span": "ketamine", "relation_span": "increased",
        "object_span": "BDNF", "species": "mouse", "treatment": "ketamine",
    }


class L1V2SchemaConverterTests(unittest.TestCase):
    def test_claim_validates_and_caps_ungrounded_confidence(self):
        claim = L1ExtractedClaim(**claim_payload())
        self.assertEqual(claim.direct_relation_sign, "positive")
        self.assertEqual(claim.prompt_fingerprint["chunk_hash"], "h1")
        self.assertTrue(claim.prompt_fingerprint["fingerprint_hash"])
        ungrounded = L1ExtractedClaim(**{**claim_payload(), "evidence_sentence": "", "confidence": 0.95})
        self.assertEqual(ungrounded.confidence, 0.6)
        self.assertIn("confidence_capped_missing_evidence_sentence", ungrounded.extraction_warnings)

    def test_speculative_direct_result_is_reclassified(self):
        claim = L1ExtractedClaim(**{**claim_payload(), "speculative": True})
        self.assertEqual(claim.statement_type, "speculation")

    def test_converts_to_evidence_record_with_fingerprint(self):
        evidence = l1_claim_to_evidence_record(L1ExtractedClaim(**claim_payload()))
        self.assertEqual(evidence.paper_id, "P1")
        self.assertEqual(evidence.chunk_id, "c1")
        self.assertEqual(evidence.sentence, "Ketamine increased BDNF in mice.")
        self.assertEqual(evidence.subject_span, "ketamine")
        self.assertEqual(evidence.prompt_version, "2.0")
        self.assertTrue(evidence.prompt_fingerprint)

    def test_converts_to_legacy_tuple(self):
        legacy = l1_claim_to_legacy_tuple(L1ExtractedClaim(**claim_payload()))
        self.assertEqual(legacy["subject"], "ketamine")
        self.assertEqual(legacy["relation_sign"], 1)
        self.assertEqual(legacy["context"]["species"], "mouse")

    def test_legacy_tuple_conversion_is_warned(self):
        claim = legacy_tuple_to_l1_claim(
            {"subject": "ketamine", "relation_sign": 1, "object": "BDNF", "evidence_sentence": "Ketamine increased BDNF."},
            {"paper_id": "P1", "chunk_id": "c1"},
        )
        self.assertEqual(claim.direct_relation_sign, "positive")
        self.assertIn("converted_from_legacy_tuple_missing_native_l1_v2_provenance", claim.extraction_warnings)


if __name__ == "__main__":
    unittest.main()
