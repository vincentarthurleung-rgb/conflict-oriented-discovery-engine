import unittest

from code_engine.system_b import CaseBundleLoader, CaseCardBuilder, LimitationReporter


class CaseCardTests(unittest.TestCase):
    def setUp(self):
        self.bundle = CaseBundleLoader("case_bundles/metformin_ampk_cancer").load()
        self.card = CaseCardBuilder().build(self.bundle)

    def test_preserves_mixed_lincs_interpretation(self):
        self.assertEqual(self.card["validation_summary"]["lincs_interpretation"], "mixed")
        self.assertEqual(self.card["evidence_summary"]["manual_review_followup_count"], 2)

    def test_unavailable_validators_are_limitations_not_failures(self):
        limitations = LimitationReporter().generate(self.bundle, self.card)
        self.assertTrue(any("recommended but unavailable" in item for item in limitations))
        self.assertFalse(any("failed" in item.lower() for item in limitations))


if __name__ == "__main__":
    unittest.main()
