import unittest

from code_engine.hypothesis.scoring import score_hypothesis_candidate
from code_engine.reporting.ranking import rank_hypotheses


class HypothesisBeliefWeightTests(unittest.TestCase):
    def test_belief_weight_not_used_for_hypothesis_or_report_ranking(self):
        candidate = {"candidate_id": "C", "source_scope": "abstract", "abstract_entropy": 0.8}
        self.assertEqual(score_hypothesis_candidate({**candidate, "belief_weight": 0.1})["overall_score"],
                         score_hypothesis_candidate({**candidate, "belief_weight": 0.99})["overall_score"])
        hypotheses = [{"hypothesis_id": "A", "metrics_breakdown": {"consistency": 0.5}, "journal_weight": 0.1},
                      {"hypothesis_id": "B", "metrics_breakdown": {"consistency": 0.5}, "journal_weight": 0.99}]
        self.assertEqual([item["hypothesis_id"] for item in rank_hypotheses(hypotheses)], ["A", "B"])


if __name__ == "__main__": unittest.main()
