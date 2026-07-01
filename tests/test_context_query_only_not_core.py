import unittest

from code_engine.normalization.layered_grounding import compute_context_compatibility


class QueryOnlyContextTests(unittest.TestCase):
    def test_retrieval_query_is_weak_context(self):
        result = compute_context_compatibility(
            {"evidence_sentence": "Therapeutic activation of AMPK by metformin could inhibit cyst enlargement."},
            {"context": {"terms": ["cancer"]}},
            query_record={"query": "metformin AMPK cancer", "context_strict": True},
            paper_metadata={"title": "Baseline Characteristics of ADPKD Patients in TAME-PKD."})
        self.assertEqual(result.status, "context_query_only")
        self.assertFalse(result.strong_context_match)
        self.assertTrue(result.weak_context_match)
        self.assertTrue(result.query_context_only)
        self.assertFalse(result.core_context_eligible)


if __name__ == "__main__": unittest.main()
