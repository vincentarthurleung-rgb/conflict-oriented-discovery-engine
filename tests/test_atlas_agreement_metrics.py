import unittest

from code_engine.system_b.evaluation.metric_engine import cohen_kappa, exact_agreement, field_agreement, fleiss_kappa, icc_oneway, krippendorff_alpha, weighted_kappa


class AtlasAgreementMetricsTests(unittest.TestCase):
    def test_agreement_metrics_have_ready_status(self):
        a = {"i1": "A", "i2": "B", "i3": "A"}
        b = {"i1": "A", "i2": "A", "i3": "A"}
        self.assertEqual(cohen_kappa(a, b)["status"], "ready")
        self.assertEqual(exact_agreement(a, b)["denominator"], 3)
        self.assertEqual(weighted_kappa(a, b)["status"], "ready")
        self.assertEqual(fleiss_kappa({"i1": ["A", "A", "B"], "i2": ["B", "B", "B"]})["status"], "ready")
        self.assertEqual(krippendorff_alpha({"i1": ["A", "A"], "i2": ["A", "B"]})["status"], "ready")
        self.assertEqual(icc_oneway({"i1": [1.0, 1.1], "i2": [2.0, 1.9]})["status"], "ready")
        self.assertEqual(field_agreement({"i1": {"x": True}}, {"i1": {"x": True}})["value"], 1.0)


if __name__ == "__main__":
    unittest.main()
