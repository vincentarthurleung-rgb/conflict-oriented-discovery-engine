import unittest

from code_engine.temporal.hypothesis_comparison import compare_hypothesis_to_later_evidence


class ComparisonTests(unittest.TestCase):
    def test_partial_overlap_keeps_review(self):
        result = compare_hypothesis_to_later_evidence({"hypothesis_id":"h","direction":"increase","linked_mechanism_edge_ids":["m"]}, [{"direction":"increase"}], "increase")
        self.assertIn(result["comparison_to_later_evidence"], {"extends_later_evidence", "partially_covered_by_later_evidence"})
        self.assertTrue(result["still_requires_validation"])
        self.assertTrue(result["human_review_question"])


if __name__ == "__main__": unittest.main()
