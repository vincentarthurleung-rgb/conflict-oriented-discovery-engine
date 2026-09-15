"""Offline integrity tests for the prospective held-out-v2 case freeze."""

import unittest

from tools import freeze_search_plan_v23_beta_heldout_v2_cases_offline as freeze


class HeldoutV2CaseFreezeTests(unittest.TestCase):
    def setUp(self):
        self.targets = freeze.build_targets()
        self.cases = freeze.build_cases(self.targets)

    def test_exact_eight_unique_cases(self):
        self.assertEqual(len(self.targets), 8)
        self.assertEqual(len({row["case_id"] for row in self.targets}), 8)

    def test_strata_and_domain_counts(self):
        ambiguity, domain = freeze.validate_targets(self.targets, self.cases)
        self.assertEqual(dict(ambiguity), {"LOW": 2, "MEDIUM": 2, "HIGH": 4})
        self.assertEqual(dict(domain), {"non_oncology": 6, "oncology": 2})

    def test_targets_are_complete_and_frozen(self):
        for row in self.targets:
            self.assertTrue(row["frozen"])
            self.assertTrue(row["subject"])
            self.assertTrue(row["relation_family"])
            self.assertTrue(row["measurement_target"])
            self.assertTrue(row["measurement_property_endpoint"])
            self.assertTrue(row["required_evidence_mode"])
            self.assertTrue(row["context_qualifiers"])

    def test_no_exact_heldout_v1_overlap(self):
        audit = freeze.build_nonoverlap(self.targets)
        self.assertEqual(audit["exact_proposition_overlap"], 0)
        self.assertEqual(audit["exact_subject_relation_endpoint_triple_overlap"], 0)

    def test_deterministic_case_construction(self):
        self.assertEqual(self.targets, freeze.build_targets())
        self.assertEqual(self.cases, freeze.build_cases(freeze.build_targets()))


if __name__ == "__main__":
    unittest.main()
