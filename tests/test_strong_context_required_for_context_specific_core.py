import unittest

from code_engine.normalization.layered_grounding import compute_context_compatibility


class StrongContextRequiredTests(unittest.TestCase):
    def test_title_is_strong_source(self):
        result = compute_context_compatibility(
            {"evidence_sentence": "Metformin-induced AMPK activation was inhibited."},
            {"context": {"terms": ["cancer"]}},
            query_record={"query": "metformin AMPK cancer"},
            paper_metadata={"title": "AMPK activation and tumor suppression in triple negative breast cancer"})
        self.assertEqual(result.status, "context_matched")
        self.assertTrue(result.strong_context_match)
        self.assertTrue(result.core_context_eligible)
        self.assertIn("cancer", result.title_context_terms)


if __name__ == "__main__": unittest.main()
