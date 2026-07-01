import unittest

from code_engine.normalization.layered_grounding import compute_context_compatibility


class HypoxiaContextTests(unittest.TestCase):
    def test_hypoxia_requires_strong_source(self):
        seed = {"context": {"terms": ["hypoxia"]}}
        weak = compute_context_compatibility({"evidence_sentence": "HIF1A increased in tumor cells."}, seed,
                                             query_record={"query": "hypoxia HIF1A tumor cells"})
        strong = compute_context_compatibility({"evidence_sentence": "Hypoxia increased HIF1A in tumor cells."}, seed,
                                               query_record={"query": "hypoxia HIF1A tumor cells"})
        self.assertEqual(weak.status, "context_query_only"); self.assertFalse(weak.core_context_eligible)
        self.assertEqual(strong.status, "context_matched"); self.assertTrue(strong.core_context_eligible)


if __name__ == "__main__": unittest.main()
