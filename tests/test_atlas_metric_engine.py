import unittest

from code_engine.system_b.evaluation.metric_engine import classification_metrics, cohen_kappa, macro_micro_f1


class AtlasMetricEngineTests(unittest.TestCase):
    def test_precision_recall_f1_and_missing_status(self):
        gold = {"a": "VALID", "b": "INVALID", "c": "VALID"}
        pred = {"a": "VALID", "b": "VALID", "c": "VALID"}
        metrics = classification_metrics(gold, pred, {"VALID"})
        self.assertAlmostEqual(metrics["precision"]["value"], 2 / 3)
        self.assertAlmostEqual(metrics["recall"]["value"], 1.0)
        self.assertAlmostEqual(metrics["f1"]["value"], 0.8)
        missing = classification_metrics({}, pred)
        self.assertEqual(missing["precision"]["status"], "needs_adjudication")

    def test_macro_micro_and_cohen_kappa_known_sample(self):
        gold = {"a": "Y", "b": "N", "c": "Y", "d": "N"}
        pred = {"a": "Y", "b": "N", "c": "N", "d": "N"}
        result = macro_micro_f1(gold, pred)
        self.assertEqual(result["micro_f1"]["status"], "ready")
        kappa = cohen_kappa(gold, pred)
        self.assertEqual(kappa["status"], "ready")
        self.assertAlmostEqual(kappa["observed_agreement"], 0.75)


if __name__ == "__main__":
    unittest.main()
