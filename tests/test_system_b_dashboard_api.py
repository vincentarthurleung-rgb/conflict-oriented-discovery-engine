import unittest

from code_engine.system_b.dashboard import DashboardAPI


class DashboardAPITests(unittest.TestCase):
    def setUp(self): self.api = DashboardAPI("system_b_outputs", "system_b_outputs/kg")

    def test_dashboard_endpoints(self):
        status, summary = self.api.dispatch("/api/dashboard/summary")
        self.assertEqual(status, 200); self.assertEqual(summary["case_count"], 1)
        _, cases = self.api.dispatch("/api/dashboard/cases")
        self.assertEqual(cases["cases"][0]["case_id"], "metformin_ampk_cancer")
        _, card = self.api.dispatch("/api/dashboard/case/metformin_ampk_cancer/card")
        self.assertEqual(card["quality_class"], "CASE_READY_FOR_ARCHIVE")

    def test_comparison_coverage_and_recommendations(self):
        _, comparison = self.api.dispatch("/api/dashboard/comparison")
        self.assertTrue(comparison["cases"])
        _, coverage = self.api.dispatch("/api/dashboard/validator-coverage")
        self.assertEqual(coverage["cases"][0]["lincs_l1000"], "executed")
        _, recommendation = self.api.dispatch("/api/dashboard/recommendations")
        self.assertEqual(recommendation["suggested_case_type"], "conflict_enriched")


if __name__ == "__main__": unittest.main()
