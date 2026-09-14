"""Generic production-candidate tests for frozen v2.3-beta Policy A."""

import json
from pathlib import Path
import unittest

from code_engine.search.search_plan_v23_beta_policy import decide_search_plan_v23_beta_disposition


ROOT = Path(__file__).resolve().parents[1]


class SearchPlanV23BetaPolicyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.config = json.loads((ROOT / "configs/search_plans/search_plan_v23_beta.json").read_text())

    def decide(self, original="TIER_A", unit="EXACT", relation="DIRECT_FUNCTIONAL",
               endpoint="EXACT", subtier="B1_SUPPORTED_OR_SINGLE_UNCERTAINTY", mode="v2.3-beta"):
        return decide_search_plan_v23_beta_disposition(
            original, biological_unit_state=unit, functional_relation_state=relation,
            endpoint_state=endpoint, tier_b_subtier_annotation=subtier,
            config=self.config, mode=mode,
        )

    def test_unit_incompatible_demotes_tier_a(self):
        self.assertEqual(self.decide(unit="INCOMPATIBLE").final_disposition, "TIER_B")

    def test_association_demotes_tier_a(self):
        self.assertEqual(self.decide(relation="ASSOCIATION_ONLY").final_disposition, "TIER_B")

    def test_background_demotes_tier_a(self):
        self.assertEqual(self.decide(relation="BACKGROUND_ONLY").final_disposition, "TIER_B")

    def test_multi_target_demotes_tier_a(self):
        self.assertEqual(self.decide(relation="MULTI_TARGET_AMBIGUOUS").final_disposition, "TIER_B")

    def test_endpoint_incompatible_demotes_tier_a(self):
        self.assertEqual(self.decide(endpoint="INCOMPATIBLE").final_disposition, "TIER_B")

    def test_all_unresolved_preserves_tier_a(self):
        self.assertEqual(self.decide(unit="UNRESOLVED", relation="UNRESOLVED",
                                     endpoint="UNRESOLVED").final_disposition, "TIER_A")

    def test_endpoint_partial_preserves_tier_a(self):
        self.assertEqual(self.decide(endpoint="PARTIAL").final_disposition, "TIER_A")

    def test_strong_tier_b_is_not_promoted(self):
        result = self.decide(original="TIER_B")
        self.assertEqual(result.final_disposition, "TIER_B")
        self.assertFalse(result.tier_b_to_tier_a_promoted)

    def test_blocked_tier_b_is_preserved_not_rejected(self):
        result = self.decide(original="TIER_B", unit="INCOMPATIBLE")
        self.assertEqual(result.final_disposition, "TIER_B")
        self.assertFalse(result.hard_rejected_by_v23_beta)

    def test_original_reject_is_preserved(self):
        self.assertEqual(self.decide(original="REJECT").final_disposition, "REJECT")

    def test_original_abstain_is_preserved(self):
        self.assertEqual(self.decide(original="ABSTAIN").final_disposition, "ABSTAIN")

    def test_subtier_annotation_never_changes_priority(self):
        priorities = {
            self.decide(original="TIER_B", subtier=subtier).acquisition_priority_tier
            for subtier in self.config["tier_b_subtiers"]["values"]
        }
        self.assertEqual(priorities, {"TIER_B"})

    def test_deterministic_replay(self):
        self.assertEqual(self.decide(relation="UNRESOLVED"), self.decide(relation="UNRESOLVED"))

    def test_v22_mode_is_unchanged(self):
        result = self.decide(unit="INCOMPATIBLE", mode="v2.2")
        self.assertEqual(result.final_disposition, "TIER_A")
        self.assertEqual(result.policy_version, "v2.2-unchanged")


if __name__ == "__main__":
    unittest.main()
