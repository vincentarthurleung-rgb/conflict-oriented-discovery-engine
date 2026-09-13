"""Generic context-dimension and applicability regressions for V1_1."""

import json
from pathlib import Path
import unittest

from code_engine.search.biological_unit_compatibility_v1_1 import (
    BiologicalUnitRegistryV1_1,
    decide_biological_unit_compatibility_v1_1,
)


ROOT = Path(__file__).resolve().parents[1]


class BiologicalUnitCompatibilityV1_1Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.base_registry = json.loads((ROOT / "configs/search_plans/biological_unit_registry_v1.json").read_text())
        cls.registry_overlay = json.loads((ROOT / "configs/search_plans/biological_unit_registry_v1_1.json").read_text())
        cls.base_policy = json.loads((ROOT / "configs/search_plans/biological_unit_policy_v1.json").read_text())
        cls.policy = json.loads((ROOT / "configs/search_plans/biological_unit_policy_v1_1.json").read_text())
        cls.registry = BiologicalUnitRegistryV1_1(cls.base_registry, cls.registry_overlay)

    def decide(self, qualifiers, abstract):
        if isinstance(qualifiers, str):
            qualifiers = [qualifiers]
        return decide_biological_unit_compatibility_v1_1(
            self.registry, self.base_policy, self.policy, qualifiers,
            title="", abstract=abstract, publication_metadata={"publication_types": ["Journal Article"]},
        )

    def test_disease_context_is_not_cell_identity(self):
        result = self.decide("acute myeloid leukemia", "We treated mantle cell lymphoma cells.")
        self.assertFalse(result.applicability["applicable"])
        self.assertEqual(result.overall_state, "UNRESOLVED")
        self.assertIn("DISEASE_CONTEXT", result.applicability["target_context_dimensions"])

    def test_genotype_context_is_not_biological_unit(self):
        result = self.decide("EGFR-mutant genotype", "We treated cancer cells.")
        self.assertFalse(result.applicability["applicable"])
        self.assertEqual(result.overall_state, "UNRESOLVED")
        self.assertIn("GENOTYPE_CONTEXT", result.applicability["target_context_dimensions"])

    def test_anatomical_location_is_distinct_from_cell_identity(self):
        result = self.decide("hepatocytes in liver", "In this study, hepatic CD4 T cells were treated.")
        self.assertTrue(result.applicability["unit_constraints_present"])
        self.assertTrue(result.applicability["region_constraints_present"])
        self.assertEqual(result.cell_identity_state, "INCOMPATIBLE")
        self.assertEqual(result.anatomical_region_state, "EXACT")

    def test_biological_unit_and_disease_context_can_coexist(self):
        result = self.decide("macrophages in acute myeloid leukemia", "Our experiments used macrophages.")
        self.assertTrue(result.applicability["applicable"])
        self.assertIn("BIOLOGICAL_UNIT", result.applicability["target_context_dimensions"])
        self.assertIn("DISEASE_CONTEXT", result.applicability["target_context_dimensions"])
        self.assertEqual(result.overall_state, "EXACT")

    def test_biological_unit_and_genotype_context_can_coexist(self):
        result = self.decide("EGFR-mutant macrophages", "Our experiments used macrophages.")
        self.assertTrue(result.applicability["applicable"])
        self.assertIn("GENOTYPE_CONTEXT", result.applicability["target_context_dimensions"])
        self.assertEqual(result.overall_state, "EXACT")

    def test_non_applicable_target_does_not_emit_false_incompatible(self):
        result = self.decide("EGFR-mutant non-small-cell lung cancer", "We treated cancer cells.")
        self.assertFalse(result.applicability["applicable"])
        self.assertEqual(result.cell_identity_state, "UNRESOLVED")
        self.assertEqual(result.overall_state, "UNRESOLVED")

    def test_resolved_wrong_cell_type_remains_incompatible(self):
        result = self.decide("macrophage", "We treated monocytes.")
        self.assertEqual(result.overall_state, "INCOMPATIBLE")
        self.assertTrue(all(result.incompatibility_preconditions.values()))

    def test_correct_organ_and_wrong_cell_type_remains_incompatible(self):
        result = self.decide("hepatocytes in liver", "In this study, hepatic CD4 T cells were treated.")
        self.assertEqual(result.overall_state, "INCOMPATIBLE")
        self.assertIn("DISTINCT_CELL_TYPE", result.reason_codes)

    def test_region_mismatch_remains_distinguishable(self):
        result = self.decide("hippocampal neurons", "In this study, cortical neurons were treated.")
        self.assertEqual(result.cell_identity_state, "EXACT")
        self.assertEqual(result.anatomical_region_state, "INCOMPATIBLE")
        self.assertEqual(result.overall_state, "INCOMPATIBLE")
        self.assertTrue(all(result.incompatibility_preconditions.values()))

    def test_background_target_like_mention_does_not_rescue_mismatch(self):
        result = self.decide(
            "macrophage", "Background macrophages regulate inflammation. In this study, monocytes were treated."
        )
        self.assertEqual(result.overall_state, "INCOMPATIBLE")

    def test_explicit_model_of_authorization_is_directional(self):
        result = self.decide("hepatocyte", "In this study, HepG2 cells were treated.")
        self.assertEqual(result.overall_state, "AUTHORIZED_COMPATIBLE")
        reverse = self.decide("HepG2", "In this study, hepatocytes were treated.")
        self.assertEqual(reverse.overall_state, "INCOMPATIBLE")

    def test_absent_model_of_authorization_does_not_imply_equivalence(self):
        result = self.decide("macrophage", "In this study, U937 cells were treated.")
        self.assertEqual(result.overall_state, "UNRESOLVED")

    def test_repeated_execution_is_deterministic_and_shadow_only(self):
        first = self.decide("fibroblast", "We cultured dermal fibroblasts.")
        second = self.decide("fibroblast", "We cultured dermal fibroblasts.")
        self.assertEqual(first, second)
        self.assertTrue(first.preacquisition_only)
        self.assertFalse(first.modifies_tier)
        self.assertFalse(first.modifies_acquisition)
        self.assertFalse(first.modifies_sample_membership)


if __name__ == "__main__":
    unittest.main()
