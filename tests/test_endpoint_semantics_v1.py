"""Generic deterministic tests for EndpointSemanticsV1."""

import json
from pathlib import Path
import unittest

from code_engine.search.endpoint_semantics_v1 import decide_endpoint_semantics_v1


ROOT = Path(__file__).resolve().parents[1]


class EndpointSemanticsV1Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.registry = json.loads((ROOT / "configs/search_plans/endpoint_semantics_registry_v1.json").read_text())
        cls.policy = json.loads((ROOT / "configs/search_plans/endpoint_semantics_policy_v1.json").read_text())

    def target(self, *, entity="biomarker", prop=None, process=None, state=None, compartment=None,
               condition=None, response_context=None, required=None, optional=None):
        dimensions = {
            "measurement_entity": entity, "measurement_property": prop,
            "measurement_process": process, "measurement_state": state,
            "measurement_compartment": compartment, "measurement_condition": condition,
            "response_context": response_context,
        }
        required = required or tuple(name for name, value in dimensions.items() if value is not None)
        optional = optional or tuple(name for name in dimensions if name not in required)
        return {
            "measurement_target": entity,
            "endpoint_target_spec": {
                "required_entity": entity, "required_property": prop, "required_process": process,
                "required_state": state, "required_compartment": compartment,
                "required_condition": condition, "required_response_context": response_context,
                "authorized_equivalences": [], "required_dimensions": list(required),
                "optional_dimensions": list(optional),
            },
        }

    def decide(self, text, target=None, title=""):
        return decide_endpoint_semantics_v1(
            "generic_endpoint_packet", target or self.target(prop="abundance"), title=title,
            abstract=text, publication_metadata={}, registry=self.registry, policy=self.policy,
        )

    def test_exact_endpoint_match(self):
        self.assertEqual(self.decide("We measured biomarker abundance.").overall_state, "EXACT")

    def test_authorized_equivalent(self):
        result = self.decide("We measured biomarker count.", self.target(prop="number"))
        self.assertEqual(result.overall_state, "AUTHORIZED_EQUIVALENT")
        self.assertEqual(result.property_state, "AUTHORIZED_EQUIVALENT")

    def test_missing_required_property_is_partial(self):
        result = self.decide("We measured biomarker.")
        self.assertEqual(result.overall_state, "PARTIAL")
        self.assertEqual(result.property_state, "UNRESOLVED")

    def test_explicit_wrong_property_is_incompatible(self):
        result = self.decide("We measured biomarker abundance.", self.target(prop="activation"))
        self.assertEqual(result.overall_state, "INCOMPATIBLE")

    def test_abundance_is_not_phosphorylation(self):
        result = self.decide("We measured biomarker abundance.", self.target(prop="phosphorylation"))
        self.assertEqual(result.overall_state, "INCOMPATIBLE")
        self.assertIn("ABUNDANCE_NOT_ACTIVATION", result.reason_codes)

    def test_transcription_is_not_secretion(self):
        result = self.decide("We measured cytokine mRNA expression.", self.target(entity="cytokine", process="secretion"))
        self.assertEqual(result.overall_state, "INCOMPATIBLE")
        self.assertIn("TRANSCRIPTION_NOT_SECRETION", result.reason_codes)

    def test_precursor_is_not_mature_product(self):
        result = self.decide("We measured pro-cytokine abundance.", self.target(entity="cytokine", state="mature"))
        self.assertEqual(result.overall_state, "INCOMPATIBLE")
        self.assertIn("PRECURSOR_NOT_MATURE_PRODUCT", result.reason_codes)

    def test_intracellular_is_not_extracellular(self):
        result = self.decide("We measured intracellular cytokine abundance.",
                             self.target(entity="cytokine", compartment="extracellular"))
        self.assertEqual(result.overall_state, "INCOMPATIBLE")
        self.assertIn("INTRACELLULAR_NOT_EXTRACELLULAR", result.reason_codes)

    def test_morphology_is_not_density(self):
        result = self.decide("We measured dendritic spine morphology.",
                             self.target(entity="dendritic spine", prop="density"))
        self.assertEqual(result.overall_state, "INCOMPATIBLE")
        self.assertIn("MORPHOLOGY_NOT_DENSITY", result.reason_codes)

    def test_translocation_is_not_uptake(self):
        result = self.decide("We measured glucose transporter translocation.",
                             self.target(entity="glucose transporter", process="uptake"))
        self.assertEqual(result.overall_state, "INCOMPATIBLE")
        self.assertIn("TRANSLOCATION_NOT_UPTAKE", result.reason_codes)

    def test_generic_secretion_is_partial_for_stimulated_secretion(self):
        target = self.target(entity="insulin", process="secretion", condition="glucose_stimulated")
        result = self.decide("We measured insulin secretion.", target)
        self.assertEqual(result.overall_state, "PARTIAL")
        self.assertIn("GENERIC_SECRETION_NOT_STIMULATED_SECRETION", result.reason_codes)

    def test_basal_is_incompatible_with_stimulated_condition(self):
        target = self.target(entity="insulin", process="secretion", condition="glucose_stimulated")
        result = self.decide("We measured basal insulin secretion.", target)
        self.assertEqual(result.overall_state, "INCOMPATIBLE")
        self.assertEqual(result.condition_state, "INCOMPATIBLE")

    def test_viability_is_not_drug_sensitivity(self):
        target = self.target(entity="drug response", prop="sensitivity", response_context="compound a")
        target["therapy"] = "compound A"
        result = self.decide("We measured viability after compound A treatment.", target)
        self.assertEqual(result.overall_state, "INCOMPATIBLE")
        self.assertIn("VIABILITY_NOT_DRUG_SENSITIVITY", result.reason_codes)

    def test_surrogate_is_not_functional_endpoint(self):
        result = self.decide("We measured transporter translocation.",
                             self.target(entity="transporter", process="uptake"))
        self.assertEqual(result.endpoint_evidence_role, "CURRENT_STUDY_SURROGATE")
        self.assertIn("SURROGATE_NOT_FUNCTIONAL_ENDPOINT", result.reason_codes)

    def test_multiple_endpoint_ambiguity(self):
        result = self.decide("We measured biomarker abundance and phosphorylation.")
        self.assertEqual(result.overall_state, "UNRESOLVED")
        self.assertIn("MULTIPLE_ENDPOINTS_UNRESOLVED", result.reason_codes)

    def test_background_endpoint_only(self):
        result = self.decide("Previous studies measured biomarker abundance.")
        self.assertEqual(result.overall_state, "UNRESOLVED")
        self.assertEqual(result.endpoint_evidence_role, "BACKGROUND_ENDPOINT")

    def test_current_study_endpoint_preferred_over_background(self):
        result = self.decide(
            "Previous studies measured biomarker phosphorylation. We measured biomarker abundance."
        )
        self.assertEqual(result.overall_state, "EXACT")
        self.assertEqual(result.endpoint_evidence_role, "CURRENT_STUDY_MEASUREMENT")

    def test_missing_endpoint_evidence_is_unresolved(self):
        result = self.decide("We measured an unrelated quantity.")
        self.assertEqual(result.overall_state, "UNRESOLVED")
        self.assertIn("NO_ENDPOINT_EVIDENCE", result.reason_codes)

    def test_optional_dimension_does_not_create_incompatible(self):
        target = self.target(prop="abundance", optional=("measurement_state",))
        result = self.decide("We measured total biomarker abundance.", target)
        self.assertEqual(result.overall_state, "EXACT")
        self.assertEqual(result.molecular_state_state, "NOT_APPLICABLE")

    def test_required_dimension_incompatibility_controls_overall(self):
        target = self.target(prop="abundance", condition="stimulated")
        result = self.decide("We measured basal biomarker abundance.", target)
        self.assertEqual(result.overall_state, "INCOMPATIBLE")

    def test_deterministic_replay_and_shadow_flags(self):
        first = self.decide("We measured biomarker abundance.")
        second = self.decide("We measured biomarker abundance.")
        self.assertEqual(first, second)
        self.assertTrue(first.preacquisition_only)
        self.assertFalse(first.modifies_tier)
        self.assertFalse(first.modifies_acquisition)
        self.assertFalse(first.modifies_sample_membership)
        self.assertFalse(first.modifies_reject_status)


if __name__ == "__main__":
    unittest.main()
