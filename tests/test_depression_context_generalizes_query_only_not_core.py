import unittest

from code_engine.normalization.layered_grounding import compute_context_compatibility


class DepressionContextTests(unittest.TestCase):
    def test_query_only_and_strong_title_are_distinct(self):
        seed = {"context": {"terms": ["depression"]}}
        weak = compute_context_compatibility({"evidence_sentence": "Ketamine increased BDNF in cultured neurons."}, seed,
                                             query_record={"query": "ketamine BDNF depression"},
                                             paper_metadata={"title": "Ketamine increases BDNF in cultured neurons"})
        strong = compute_context_compatibility({"evidence_sentence": "Ketamine increased BDNF."}, seed,
                                               query_record={"query": "ketamine BDNF depression"},
                                               paper_metadata={"title": "Ketamine increases BDNF in a mouse model of depression"})
        self.assertEqual(weak.status, "context_query_only"); self.assertFalse(weak.core_context_eligible)
        self.assertEqual(strong.status, "context_matched"); self.assertTrue(strong.core_context_eligible)


if __name__ == "__main__": unittest.main()
