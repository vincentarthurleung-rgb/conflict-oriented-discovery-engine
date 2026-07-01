import unittest

from code_engine.normalization.layered_grounding import compute_context_compatibility


class ContextMissingTests(unittest.TestCase):
    def test_missing_context_is_not_core_eligible(self):
        result = compute_context_compatibility({"evidence_sentence": "Metformin activates AMPK."}, {"context": {"terms": ["cancer"]}})
        self.assertEqual(result.status, "context_missing")
        self.assertFalse(result.core_context_eligible)


if __name__ == "__main__": unittest.main()
