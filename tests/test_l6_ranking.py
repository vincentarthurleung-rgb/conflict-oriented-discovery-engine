import unittest

from src.reporting.ranking import compute_ranking_score, rank_hypotheses


class L6RankingTests(unittest.TestCase):
    def test_score_formula_is_stable(self):
        hyp = {"metrics_breakdown": {"consistency": 0.5, "identifiability": 0.7, "complexity": 0.2}}
        self.assertEqual(compute_ranking_score(hyp), 1.07)

    def test_ranking_is_deterministic_with_tie_break(self):
        items = [
            {"hypothesis_id": "B", "objective_loss_score": 0.2, "metrics_breakdown": {"consistency": 1.0}},
            {"hypothesis_id": "A", "objective_loss_score": 0.2, "metrics_breakdown": {"consistency": 1.0}},
        ]
        first = rank_hypotheses(items)
        second = rank_hypotheses(items)
        self.assertEqual([h["hypothesis_id"] for h in first], ["A", "B"])
        self.assertEqual(first, second)


if __name__ == "__main__":
    unittest.main()
