import unittest

from code_engine.system_b.evaluation.metric_engine import case_cluster_bootstrap, paired_case_cluster_bootstrap


class AtlasClusterBootstrapTests(unittest.TestCase):
    def test_case_cluster_bootstrap_samples_cases(self):
        result = case_cluster_bootstrap({"case1": ["i1", "i2"], "case2": ["i3"]}, {"i1": 1.0, "i2": 0.0, "i3": 1.0}, repetitions=100, seed=7)
        self.assertEqual(result["status"], "ready")
        self.assertEqual(result["included_case_ids"], ["case1", "case2"])
        self.assertIn("ci_low", result)

    def test_paired_bootstrap_rejects_mismatched_items(self):
        result = paired_case_cluster_bootstrap({"case1": ["i1"]}, {"i1": 1.0}, {"i2": 0.0})
        self.assertEqual(result["status"], "configuration_mismatch")


if __name__ == "__main__":
    unittest.main()
