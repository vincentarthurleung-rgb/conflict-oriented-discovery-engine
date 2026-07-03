import copy
import unittest

from code_engine.system_b import BundleSchemaValidator, CaseBundleLoader


class BundleSchemaValidatorTests(unittest.TestCase):
    def setUp(self):
        self.bundle = CaseBundleLoader("case_bundles/metformin_ampk_cancer").load()

    def test_case_001_is_valid_and_consistent(self):
        result = BundleSchemaValidator().validate(self.bundle)
        self.assertTrue(result["schema_valid"])
        self.assertTrue(result["bundle_consistent"])

    def test_missing_required_file_is_invalid(self):
        bundle = copy.deepcopy(self.bundle)
        bundle["missing_required_files"] = ["hypothesis_summary.json"]
        result = BundleSchemaValidator().validate(bundle)
        self.assertFalse(result["schema_valid"])

    def test_manifest_hypothesis_count_mismatch_is_inconsistent(self):
        bundle = copy.deepcopy(self.bundle)
        bundle["manifest"]["formal_hypothesis_count"] = 99
        result = BundleSchemaValidator().validate(bundle)
        self.assertTrue(result["schema_valid"])
        self.assertFalse(result["bundle_consistent"])
        self.assertIn("manifest_count_mismatch: formal_hypothesis_count", result["warnings"])

    def test_not_enabled_fulltext_is_not_an_error(self):
        result = BundleSchemaValidator().validate(self.bundle)
        self.assertNotIn("fulltext_status_missing", result["errors"])


if __name__ == "__main__":
    unittest.main()
