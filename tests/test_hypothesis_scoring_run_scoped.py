import unittest
from code_engine.hypothesis.scoring import score_hypothesis_candidate


class HypothesisScoringTests(unittest.TestCase):
    def test_grounding_penalties_and_determinism(self):
        full = {"candidate_type": "mechanism_conflict_hypothesis", "source_scope": "full_text", "fulltext_entropy": 1, "linked_evidence_ids": ["E"], "validation_requirements": [{}]}
        abstract = {**full, "source_scope": "abstract", "requires_manual_review": True}
        coverage = {**abstract, "candidate_type": "coverage_gap_hypothesis"}
        one = score_hypothesis_candidate(full)
        self.assertEqual(one, score_hypothesis_candidate(full))
        self.assertGreater(one["overall_score"], score_hypothesis_candidate(abstract)["overall_score"])
        self.assertLess(score_hypothesis_candidate(coverage)["overall_score"], score_hypothesis_candidate(abstract)["overall_score"])
        self.assertIn("manual_review_penalty", score_hypothesis_candidate(abstract)["score_components"])


if __name__ == "__main__": unittest.main()
