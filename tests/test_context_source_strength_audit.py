import unittest

from code_engine.normalization.layered_grounding import compute_context_compatibility


class ContextSourceAuditTests(unittest.TestCase):
    def test_audit_records_source_strength(self):
        result = compute_context_compatibility({"evidence_sentence": "Metformin activates AMPK."},
                                               {"context": {"terms": ["cancer"]}},
                                               query_record={"query": "metformin AMPK cancer"})
        payload = result.to_dict()
        self.assertEqual(payload["strong_context_terms_matched"], [])
        self.assertEqual(payload["weak_context_terms_matched"], ["cancer"])
        self.assertEqual(payload["context_sources"][0]["source"], "retrieval_query")
        self.assertEqual(payload["context_sources"][0]["strength"], "weak")


if __name__ == "__main__": unittest.main()
