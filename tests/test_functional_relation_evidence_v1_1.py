"""Generic deterministic regressions for FunctionalRelationEvidenceV1_1."""

import json
from pathlib import Path
import unittest

from code_engine.search.functional_relation_evidence_v1_1 import (
    decide_functional_relation_evidence_v1_1,
)


ROOT = Path(__file__).resolve().parents[1]


class FunctionalRelationEvidenceV1_1Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.base = json.loads((ROOT / "configs/search_plans/functional_relation_evidence_policy_v1.json").read_text())
        cls.policy = json.loads((ROOT / "configs/search_plans/functional_relation_evidence_policy_v1_1.json").read_text())

    def decide(self, abstract, relation="increases", subject="Kinase X", endpoint="marker Y", title=""):
        target = {"subject": subject, "relation_family": relation, "object": endpoint,
                  "measurement_target": endpoint, "measurement_property_endpoint": "measured response",
                  "acceptable_endpoint_evidence": [endpoint], "therapy": None}
        return decide_functional_relation_evidence_v1_1(
            "generic_packet", target, title=title, abstract=abstract, publication_metadata={},
            base_policy=self.base, policy=self.policy,
        )

    def test_positive_perturbation(self):
        self.assertEqual(self.decide("We activated Kinase X and increased marker Y.").evidence_state,
                         "DIRECT_FUNCTIONAL")

    def test_inverse_perturbation(self):
        result = self.decide("Inhibition of Kinase X decreased marker Y.")
        self.assertEqual(result.evidence_state, "DIRECT_FUNCTIONAL")
        self.assertEqual(result.direction_compatibility, "COMPATIBLE")

    def test_knockout_necessity(self):
        self.assertEqual(self.decide("Knockout of Kinase X abolished marker Y induction.").evidence_state,
                         "DIRECT_FUNCTIONAL")

    def test_knockdown_necessity(self):
        self.assertEqual(self.decide("Kinase X knockdown reduced marker Y.").evidence_state,
                         "DIRECT_FUNCTIONAL")

    def test_pharmacological_inhibition(self):
        self.assertEqual(self.decide("A Kinase X inhibitor prevented marker Y induction.").evidence_state,
                         "DIRECT_FUNCTIONAL")

    def test_constitutive_activation(self):
        result = self.decide("Constitutively active Kinase X increased marker Y.")
        self.assertEqual(result.evidence_state, "DIRECT_FUNCTIONAL")
        self.assertIn("CONSTITUTIVE_ACTIVATION", result.reason_codes)

    def test_rescue(self):
        result = self.decide("Re-expression of Kinase X restored marker Y.")
        self.assertEqual(result.evidence_state, "DIRECT_FUNCTIONAL")
        self.assertEqual(result.response_link_state, "RESCUE_OR_NECESSITY")

    def test_loss_and_rescue_sequence(self):
        result = self.decide("Loss of Kinase X abolished marker Y. Re-expression of Kinase X restored marker Y.")
        self.assertEqual(result.evidence_state, "DIRECT_FUNCTIONAL")

    def test_adjacent_sentence_causal_composition(self):
        result = self.decide("We inhibited Kinase X. This treatment reduced marker Y.")
        self.assertEqual(result.evidence_state, "FUNCTIONAL_CHAIN")
        self.assertIn("BOUNDED_ADJACENT_COMPOSITION", result.reason_codes)

    def test_unrelated_adjacent_sentence_does_not_compose(self):
        result = self.decide("We inhibited Kinase X. An unrelated treatment reduced marker Y.")
        self.assertEqual(result.evidence_state, "UNRESOLVED")

    def test_association_language_remains_association(self):
        self.assertEqual(self.decide("Our results showed Kinase X correlated with marker Y.").evidence_state,
                         "ASSOCIATION_ONLY")

    def test_parser_uncertainty_is_not_association(self):
        result = self.decide("Treatment Z increased Kinase X and marker Y.")
        self.assertEqual(result.evidence_state, "UNRESOLVED")
        self.assertIn("PARSER_UNCERTAINTY_FAIL_CLOSED", result.reason_codes)

    def test_multi_target_ambiguity(self):
        result = self.decide("A multi-kinase inhibitor blocked Kinase X and reduced marker Y.")
        self.assertEqual(result.evidence_state, "MULTI_TARGET_AMBIGUOUS")

    def test_target_specific_evidence_survives_other_entity_mention(self):
        result = self.decide("Knockdown of Kinase X reduced marker Y while Kinase Z was measured.")
        self.assertEqual(result.evidence_state, "DIRECT_FUNCTIONAL")

    def test_background_only_proposition(self):
        result = self.decide("Previous studies showed that activation of Kinase X increased marker Y.")
        self.assertEqual(result.evidence_state, "BACKGROUND_ONLY")

    def test_unresolved_evidence_role(self):
        result = self.decide("Kinase X and marker Y were mentioned without experimental detail.")
        self.assertEqual(result.evidence_state, "UNRESOLVED")
        self.assertEqual(result.evidence_role, "UNRESOLVED")

    def test_mechanistic_functional_chain(self):
        result = self.decide("Here we activated Kinase X through an upstream receptor. This resulted in increased marker Y.")
        self.assertEqual(result.evidence_state, "FUNCTIONAL_CHAIN")

    def test_direction_conflict(self):
        result = self.decide("Activation of Kinase X decreased marker Y.")
        self.assertEqual(result.evidence_state, "UNRESOLVED")

    def test_subject_causal_predicate(self):
        result = self.decide("We show that Kinase X increased marker Y.")
        self.assertEqual(result.evidence_state, "DIRECT_FUNCTIONAL")
        self.assertIn("SUBJECT_CAUSAL_PREDICATE", result.reason_codes)

    def test_deficient_cells(self):
        result = self.decide("Kinase X-deficient cells failed to induce marker Y.")
        self.assertEqual(result.evidence_state, "DIRECT_FUNCTIONAL")
        self.assertIn("DEFICIENT_CELL_EVIDENCE", result.reason_codes)

    def test_deterministic_repeated_execution(self):
        first = self.decide("We inhibited Kinase X. This treatment reduced marker Y.")
        second = self.decide("We inhibited Kinase X. This treatment reduced marker Y.")
        self.assertEqual(first, second)
        self.assertTrue(first.preacquisition_only)
        self.assertFalse(first.modifies_tier)
        self.assertFalse(first.modifies_acquisition)


if __name__ == "__main__":
    unittest.main()
