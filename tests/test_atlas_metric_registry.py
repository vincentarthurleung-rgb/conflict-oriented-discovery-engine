import unittest

from code_engine.system_b.evaluation.metric_engine import METRIC_REGISTRY, exact_match, jaccard, ranking_metrics


class AtlasMetricRegistryTests(unittest.TestCase):
    def test_registry_contains_required_first_batch(self):
        for metric_id in ("precision", "recall", "f1", "macro_f1", "weighted_f1", "exact_match", "jaccard", "precision_at_k", "recall_at_k", "mrr", "cohen_kappa", "fleiss_kappa", "krippendorff_alpha", "weighted_kappa", "icc"):
            self.assertIn(metric_id, METRIC_REGISTRY)

    def test_exact_jaccard_and_ranking(self):
        self.assertEqual(exact_match({"a": "X"}, {"a": "X"})["value"], 1.0)
        self.assertAlmostEqual(jaccard({"a": {"x", "y"}}, {"a": {"y", "z"}})["value"], 1 / 3)
        ranked = ranking_metrics({"case": {"gold"}}, {"case": ["bad", "gold"]}, k=2)
        self.assertEqual(ranked["mrr"]["value"], 0.5)


if __name__ == "__main__":
    unittest.main()
