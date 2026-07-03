import unittest

from code_engine.system_b.dashboard import DashboardAPI


class DashboardAPITests(unittest.TestCase):
    def setUp(self): self.api = DashboardAPI("system_b_outputs", "system_b_outputs/kg")

    def test_dashboard_endpoints(self):
        status, summary = self.api.dispatch("/api/dashboard/summary")
        self.assertEqual(status, 200); self.assertGreaterEqual(summary["case_count"], 2)
        _, cases = self.api.dispatch("/api/dashboard/cases")
        self.assertTrue(any(x["case_id"]=="metformin_ampk_cancer" for x in cases["cases"]))
        _, card = self.api.dispatch("/api/dashboard/case/metformin_ampk_cancer/card")
        self.assertEqual(card["quality_class"], "CASE_READY_FOR_ARCHIVE")

    def test_comparison_coverage_and_recommendations(self):
        _, comparison = self.api.dispatch("/api/dashboard/comparison")
        self.assertTrue(comparison["cases"])
        _, coverage = self.api.dispatch("/api/dashboard/validator-coverage")
        row=next(x for x in coverage["cases"] if x["case_id"]=="metformin_ampk_cancer");self.assertEqual(row["lincs_l1000"], "executed")
        _, recommendation = self.api.dispatch("/api/dashboard/recommendations")
        self.assertIn(recommendation["suggested_case_type"], {"conflict_enriched","under_covered_domain"})


if __name__ == "__main__": unittest.main()
