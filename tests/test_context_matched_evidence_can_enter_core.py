import unittest

from code_engine.normalization.layered_grounding import compute_context_compatibility


class ContextMatchedTests(unittest.TestCase):
    def test_cancer_sentence_is_context_eligible(self):
        result = compute_context_compatibility(
            {"evidence_sentence": "Metformin increases sensitivity through AMPK activation in liver cancer cells."},
            {"context": {"terms": ["cancer"]}})
        self.assertEqual(result.status, "context_matched")
        self.assertTrue(result.core_context_eligible)


if __name__ == "__main__": unittest.main()
