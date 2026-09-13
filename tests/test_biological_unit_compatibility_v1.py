"""Generic deterministic regressions for BiologicalUnitCompatibilityV1."""

import json
import copy
from pathlib import Path
import unittest

from code_engine.search.biological_unit_compatibility_v1 import (
    BiologicalUnitRegistryV1,
    decide_biological_unit_compatibility,
)


ROOT = Path(__file__).resolve().parents[1]


class BiologicalUnitCompatibilityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.registry = BiologicalUnitRegistryV1(json.loads(
            (ROOT / "configs/search_plans/biological_unit_registry_v1.json").read_text()
        ))
        cls.policy = json.loads(
            (ROOT / "configs/search_plans/biological_unit_policy_v1.json").read_text()
        )

    def decide(self, target, abstract):
        return decide_biological_unit_compatibility(
            self.registry, self.policy, [target], title="", abstract=abstract,
            publication_metadata={"publication_types": ["Journal Article"]},
        )

    def test_exact_canonical_match(self):
        result = self.decide("macrophage", "In this study, a macrophage was treated and analyzed.")
        self.assertEqual(result.overall_state, "EXACT")
        self.assertIn("EXACT_CANONICAL_MATCH", result.reason_codes)

    def test_alias_match(self):
        result = self.decide("macrophage", "Our experiments used macrophages.")
        self.assertEqual(result.overall_state, "EXACT")
        self.assertIn("ALIAS_MATCH", result.reason_codes)

    def test_alias_policy_is_enforced(self):
        policy = copy.deepcopy(self.policy)
        policy["allow_alias"] = False
        result = decide_biological_unit_compatibility(
            self.registry, policy, ["macrophage"], title="",
            abstract="Our experiments used macrophages.", publication_metadata={},
        )
        self.assertEqual(result.overall_state, "UNRESOLVED")
        self.assertNotIn("ALIAS_MATCH", result.reason_codes)

    def test_authorized_subtype_is_directional(self):
        result = self.decide("macrophage", "We treated bone-marrow-derived macrophages.")
        self.assertEqual(result.overall_state, "AUTHORIZED_COMPATIBLE")
        self.assertIn("AUTHORIZED_SUBTYPE", result.reason_codes)
        reverse = self.decide("bone-marrow-derived macrophage", "We treated macrophages.")
        self.assertEqual(reverse.overall_state, "INCOMPATIBLE")

    def test_explicit_model_of_relation(self):
        result = self.decide("hepatocyte", "In this study, HepG2 cells were treated.")
        self.assertEqual(result.overall_state, "AUTHORIZED_COMPATIBLE")
        self.assertIn("AUTHORIZED_MODEL_OF", result.reason_codes)

    def test_related_but_distinct_cell_type(self):
        result = self.decide("macrophage", "We isolated and analyzed primary human monocytes.")
        self.assertEqual(result.overall_state, "INCOMPATIBLE")
        self.assertIn("DISTINCT_CELL_TYPE", result.reason_codes)

    def test_cell_type_present_in_wrong_region(self):
        result = self.decide("hippocampal neurons", "In this study, cortical neurons were treated.")
        self.assertEqual(result.cell_identity_state, "EXACT")
        self.assertEqual(result.anatomical_region_state, "INCOMPATIBLE")
        self.assertEqual(result.overall_state, "INCOMPATIBLE")

    def test_correct_organ_words_do_not_rescue_wrong_cell_type(self):
        result = self.decide("hepatocyte", "In this study, hepatic CD4 T cells were analyzed.")
        self.assertEqual(result.overall_state, "INCOMPATIBLE")
        self.assertIn("DISTINCT_CELL_TYPE", result.reason_codes)

    def test_broader_tissue_is_unresolved_for_specific_cell_target(self):
        result = self.decide("skeletal muscle cell", "In this study, isolated skeletal muscle tissue was analyzed.")
        self.assertEqual(result.overall_state, "UNRESOLVED")
        self.assertIn("BROADER_CONTAINER_ONLY", result.reason_codes)

    def test_specific_compatible_subtype_for_broad_target(self):
        result = self.decide("fibroblast", "We cultured dermal fibroblasts.")
        self.assertEqual(result.overall_state, "AUTHORIZED_COMPATIBLE")
        self.assertIn("AUTHORIZED_SUBTYPE", result.reason_codes)

    def test_region_mismatch_for_same_cell_type(self):
        result = self.decide("hippocampal neurons", "Our experiments used olfactory-bulb granule cells and neurons.")
        self.assertNotEqual(result.cell_identity_state, "INCOMPATIBLE")
        self.assertEqual(result.anatomical_region_state, "INCOMPATIBLE")
        self.assertEqual(result.overall_state, "INCOMPATIBLE")

    def test_multiple_conflicting_experimental_units(self):
        result = self.decide("macrophage", "In this study, macrophages and monocytes were treated.")
        self.assertEqual(result.overall_state, "UNRESOLVED")
        self.assertIn("MULTIPLE_CONFLICTING_UNITS", result.reason_codes)

    def test_no_biological_unit_evidence(self):
        result = self.decide("fibroblast", "The pathway was measured under several conditions.")
        self.assertEqual(result.overall_state, "UNRESOLVED")
        self.assertIn("NO_BIOLOGICAL_UNIT_EVIDENCE", result.reason_codes)

    def test_cell_line_without_target_model_authorization(self):
        result = self.decide("macrophage", "This study used U937 cells.")
        self.assertEqual(result.overall_state, "UNRESOLVED")
        self.assertNotIn("AUTHORIZED_MODEL_OF", result.reason_codes)

    def test_cell_line_with_explicit_model_authorization(self):
        result = self.decide("pancreatic beta cell", "This study used INS-1 cells.")
        self.assertEqual(result.overall_state, "AUTHORIZED_COMPATIBLE")
        self.assertIn("AUTHORIZED_MODEL_OF", result.reason_codes)

    def test_background_or_mention_does_not_promote_exact(self):
        result = self.decide(
            "macrophage",
            "Background macrophages regulate inflammation. The current study measured a soluble marker.",
        )
        self.assertEqual(result.overall_state, "UNRESOLVED")
        self.assertTrue(all(item["evidence_role"] != "experimental_biological_unit" for item in result.matched_surfaces))

    def test_deterministic_repeated_execution_and_shadow_flags(self):
        first = self.decide("fibroblast", "We cultured dermal fibroblasts.")
        second = self.decide("fibroblast", "We cultured dermal fibroblasts.")
        self.assertEqual(first, second)
        self.assertTrue(first.preacquisition_only)
        self.assertFalse(first.modifies_tier)
        self.assertFalse(first.modifies_acquisition)
        self.assertFalse(first.modifies_sample_membership)


if __name__ == "__main__":
    unittest.main()
