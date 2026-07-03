import unittest

from code_engine.system_b import BundleSchemaValidator, CaseBundleLoader, QualityClassifier


class QualityClassifierTests(unittest.TestCase):
    def test_metformin_positive_control_is_archive_ready(self):
        bundle = CaseBundleLoader("case_bundles/metformin_ampk_cancer").load()
        validation = BundleSchemaValidator().validate(bundle)
        result = QualityClassifier().classify(bundle, validation)
        self.assertEqual(result["quality_class"], "CASE_READY_FOR_ARCHIVE")
        self.assertEqual(result["comparison_readiness"], "READY_AS_POSITIVE_CONTROL")
        self.assertTrue(result["validator_expansion_needed"])


if __name__ == "__main__":
    unittest.main()
