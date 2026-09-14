"""Generic rule tests for CompositePreAcquisitionProfileV1."""

import json
from pathlib import Path
import unittest

from code_engine.search.composite_preacquisition_profile_v1 import decide_composite_preacquisition_profile_v1


ROOT = Path(__file__).resolve().parents[1]


class CompositePreAcquisitionProfileV1Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.policy = json.loads((ROOT / "configs/search_plans/composite_preacquisition_policy_v1.json").read_text())
        cls.tier_b = json.loads((ROOT / "configs/search_plans/tier_b_acquisition_policy_v1.json").read_text())

    def decide(self, unit="EXACT", relation="DIRECT_FUNCTIONAL", endpoint="EXACT", disposition="TIER_A"):
        return decide_composite_preacquisition_profile_v1(
            "generic_candidate", "generic_case", disposition,
            biological_unit_state=unit, biological_unit_reason_codes=("unit",),
            functional_relation_state=relation, functional_relation_reason_codes=("relation",),
            endpoint_state=endpoint, endpoint_reason_codes=("endpoint",),
            policy=self.policy, tier_b_policy=self.tier_b,
        )

    def test_unit_incompatibility_is_class_0(self):
        self.assertEqual(self.decide(unit="INCOMPATIBLE").evidence_class, "CLASS_0_POSITIVE_INCOMPATIBILITY")

    def test_endpoint_incompatibility_is_class_0(self):
        self.assertEqual(self.decide(endpoint="INCOMPATIBLE").evidence_class, "CLASS_0_POSITIVE_INCOMPATIBILITY")

    def test_association_only_is_class_1(self):
        self.assertEqual(self.decide(relation="ASSOCIATION_ONLY").evidence_class, "CLASS_1_RELATION_WEAK")

    def test_background_only_is_class_1(self):
        self.assertEqual(self.decide(relation="BACKGROUND_ONLY").evidence_class, "CLASS_1_RELATION_WEAK")

    def test_multi_target_is_class_1(self):
        self.assertEqual(self.decide(relation="MULTI_TARGET_AMBIGUOUS").evidence_class, "CLASS_1_RELATION_WEAK")

    def test_both_unresolved_is_class_2_and_b2(self):
        result = self.decide(unit="UNRESOLVED", relation="UNRESOLVED")
        self.assertEqual((result.evidence_class, result.tier_b_subtier),
                         ("CLASS_2_REVIEWABLE_UNRESOLVED", "B2_MULTI_UNRESOLVED"))

    def test_compatible_unit_relation_unresolved_is_b1(self):
        self.assertEqual(self.decide(relation="UNRESOLVED").tier_b_subtier,
                         "B1_SUPPORTED_OR_SINGLE_UNCERTAINTY")

    def test_unresolved_unit_direct_relation_is_b1(self):
        self.assertEqual(self.decide(unit="UNRESOLVED").tier_b_subtier,
                         "B1_SUPPORTED_OR_SINGLE_UNCERTAINTY")

    def test_compatible_and_direct_is_class_3_b1(self):
        result = self.decide()
        self.assertEqual((result.evidence_class, result.tier_b_subtier),
                         ("CLASS_3_POSITIVELY_SUPPORTED", "B1_SUPPORTED_OR_SINGLE_UNCERTAINTY"))

    def test_endpoint_partial_does_not_block(self):
        self.assertTrue(self.decide(endpoint="PARTIAL").tier_a_eligible_shadow)

    def test_endpoint_unresolved_does_not_block(self):
        self.assertTrue(self.decide(endpoint="UNRESOLVED").tier_a_eligible_shadow)

    def test_relation_unresolved_does_not_block_tier_a(self):
        self.assertTrue(self.decide(relation="UNRESOLVED").tier_a_eligible_shadow)

    def test_unit_unresolved_does_not_block_tier_a(self):
        self.assertTrue(self.decide(unit="UNRESOLVED").tier_a_eligible_shadow)

    def test_relation_weak_blocks_tier_a(self):
        self.assertFalse(self.decide(relation="ASSOCIATION_ONLY").tier_a_eligible_shadow)

    def test_positive_incompatibility_blocks_tier_a(self):
        self.assertFalse(self.decide(unit="INCOMPATIBLE").tier_a_eligible_shadow)

    def test_original_reject_cannot_be_resurrected(self):
        result = self.decide(disposition="REJECT")
        self.assertFalse(result.alpha4_original_eligible)
        self.assertFalse(any(result.fulltext_eligibility_by_policy.values()))
        self.assertEqual(result.composite_disposition, "ORIGINAL_REJECT_PRESERVED")

    def test_original_abstain_cannot_be_resurrected(self):
        result = self.decide(disposition="ABSTAIN")
        self.assertFalse(result.alpha4_original_eligible)
        self.assertFalse(any(result.fulltext_eligibility_by_policy.values()))
        self.assertEqual(result.composite_disposition, "ORIGINAL_ABSTAIN_PRESERVED")

    def test_deterministic_repeated_execution(self):
        self.assertEqual(self.decide(endpoint="PARTIAL"), self.decide(endpoint="PARTIAL"))
        self.assertIsNone(self.decide().numeric_scientific_score)

    def test_exact_one_class_assignment(self):
        self.assertIn(self.decide().evidence_class, self.policy_class_names())

    def test_exact_one_subtier_or_preserved_disposition(self):
        result = self.decide(disposition="TIER_B")
        self.assertIsNotNone(result.tier_b_subtier)
        self.assertEqual(result.composite_disposition, result.tier_b_subtier)
        self.assertFalse(result.tier_a_eligible_shadow)
        self.assertTrue(result.passes_tier_a_blocker_rule_shadow)
        self.assertEqual(
            result.fulltext_priority_class_by_policy["POLICY_B_CONSERVATIVE_PRIORITY"],
            "B1_SUPPORTED_OR_SINGLE_UNCERTAINTY",
        )

    @staticmethod
    def policy_class_names():
        return {"CLASS_0_POSITIVE_INCOMPATIBILITY", "CLASS_1_RELATION_WEAK",
                "CLASS_2_REVIEWABLE_UNRESOLVED", "CLASS_3_POSITIVELY_SUPPORTED"}


if __name__ == "__main__":
    unittest.main()
