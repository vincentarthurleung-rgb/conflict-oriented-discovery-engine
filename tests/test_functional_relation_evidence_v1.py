"""Generic deterministic regressions for FunctionalRelationEvidenceV1."""

import json
from pathlib import Path
import unittest

from code_engine.search.functional_relation_evidence_v1 import decide_functional_relation_evidence_v1


ROOT = Path(__file__).resolve().parents[1]


class FunctionalRelationEvidenceV1Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.policy = json.loads(
            (ROOT / "configs/search_plans/functional_relation_evidence_policy_v1.json").read_text()
        )

    def decide(self, abstract, relation="increases", subject="Kinase X", endpoint="marker Y"):
        target = {
            "subject": subject,
            "relation_family": relation,
            "object": endpoint,
            "measurement_target": endpoint,
            "measurement_property_endpoint": "measured abundance",
            "acceptable_endpoint_evidence": [endpoint],
        }
        return decide_functional_relation_evidence_v1(
            "generic_packet", target, title="", abstract=abstract,
            publication_metadata={"publication_types": ["Journal Article"]}, policy=self.policy,
        )

    def test_direct_positive_perturbation(self):
        result = self.decide("We activated Kinase X and observed increased marker Y.")
        self.assertEqual(result.evidence_state, "DIRECT_FUNCTIONAL")
        self.assertEqual(result.perturbation_polarity, "POSITIVE")
        self.assertEqual(result.direction_compatibility, "COMPATIBLE")

    def test_subject_treatment_positive_perturbation(self):
        result = self.decide("Kinase X treatment increased marker Y.")
        self.assertEqual(result.evidence_state, "DIRECT_FUNCTIONAL")
        self.assertEqual(result.direction_compatibility, "COMPATIBLE")

    def test_receptor_agonist_is_positive_subject_perturbation(self):
        result = self.decide(
            "A Receptor X agonist increased marker Y.", subject="Receptor X activation"
        )
        self.assertEqual(result.evidence_state, "DIRECT_FUNCTIONAL")
        self.assertIn("TARGET_SPECIFIC_ACTIVATION", result.reason_codes)

    def test_direct_inverse_perturbation(self):
        result = self.decide("Inhibition of Kinase X decreased marker Y.")
        self.assertEqual(result.evidence_state, "DIRECT_FUNCTIONAL")
        self.assertEqual(result.perturbation_polarity, "NEGATIVE")
        self.assertEqual(result.direction_compatibility, "COMPATIBLE")

    def test_knockout_necessity_evidence(self):
        result = self.decide("Knockout of Kinase X abolished marker Y induction.")
        self.assertEqual(result.evidence_state, "DIRECT_FUNCTIONAL")
        self.assertIn("TARGET_SPECIFIC_KNOCKOUT", result.reason_codes)
        self.assertIn("LOSS_OF_FUNCTION", result.reason_codes)

    def test_knockdown_evidence(self):
        result = self.decide("Knockdown of Kinase X reduced marker Y.")
        self.assertEqual(result.evidence_state, "DIRECT_FUNCTIONAL")
        self.assertIn("TARGET_SPECIFIC_KNOCKDOWN", result.reason_codes)

    def test_inhibitor_evidence(self):
        result = self.decide("A Kinase X inhibitor decreased marker Y.")
        self.assertEqual(result.evidence_state, "DIRECT_FUNCTIONAL")
        self.assertIn("TARGET_SPECIFIC_INHIBITION", result.reason_codes)

    def test_gain_of_function(self):
        result = self.decide("Overexpression of Kinase X increased marker Y.")
        self.assertEqual(result.evidence_state, "DIRECT_FUNCTIONAL")
        self.assertIn("GAIN_OF_FUNCTION", result.reason_codes)

    def test_rescue(self):
        result = self.decide("Re-expression of Kinase X rescued marker Y.")
        self.assertEqual(result.evidence_state, "DIRECT_FUNCTIONAL")
        self.assertEqual(result.response_link_state, "RESCUE_OR_NECESSITY")
        self.assertIn("RESCUE_EVIDENCE", result.reason_codes)

    def test_functional_mechanistic_chain(self):
        result = self.decide(
            "Here we activated Kinase X through an upstream receptor. This resulted in increased marker Y."
        )
        self.assertEqual(result.evidence_state, "FUNCTIONAL_CHAIN")
        self.assertEqual(result.response_link_state, "MECHANISTIC_CHAIN")

    def test_cochange_without_subject_perturbation(self):
        result = self.decide("This study found Kinase X and marker Y were concurrently increased.")
        self.assertEqual(result.evidence_state, "ASSOCIATION_ONLY")
        self.assertIn("COCHANGE_ONLY", result.reason_codes)

    def test_third_intervention_activating_subject_and_endpoint_is_cochange(self):
        result = self.decide("Treatment Z activated Kinase X and increased marker Y.")
        self.assertEqual(result.evidence_state, "ASSOCIATION_ONLY")
        self.assertEqual(result.subject_perturbation_specificity, "NO_SUBJECT_PERTURBATION")

    def test_correlation_only(self):
        result = self.decide("Our results showed that Kinase X correlated with marker Y.")
        self.assertEqual(result.evidence_state, "ASSOCIATION_ONLY")
        self.assertEqual(result.response_link_state, "CORRELATION")

    def test_resistant_sensitive_association_only(self):
        result = self.decide(
            "Our results showed Kinase X was elevated in resistant cells and associated with drug resistance.",
            endpoint="drug resistance",
        )
        self.assertEqual(result.evidence_state, "ASSOCIATION_ONLY")
        self.assertIn("RESISTANT_SENSITIVE_ASSOCIATION_ONLY", result.reason_codes)

    def test_inverse_perturbation_resolves_therapy_sensitivity_contrast(self):
        result = self.decide(
            "Knockdown of Kinase X sensitized Drug Q-resistant cells.",
            relation="contributes_to", endpoint="Drug Q resistance",
        )
        self.assertEqual(result.evidence_state, "DIRECT_FUNCTIONAL")
        self.assertEqual(result.direction_compatibility, "COMPATIBLE")

    def test_multi_target_intervention(self):
        result = self.decide(
            "This study found that a multi-kinase inhibitor reduced marker Y while Kinase X was present."
        )
        self.assertEqual(result.evidence_state, "MULTI_TARGET_AMBIGUOUS")
        self.assertEqual(result.subject_perturbation_specificity, "MULTI_TARGET")

    def test_multi_target_therapy_response_contrast(self):
        result = self.decide(
            "This study found that dual inhibition of Kinase X and Kinase Z sensitized Drug Q-resistant cells.",
            relation="contributes_to", endpoint="Drug Q resistance",
        )
        self.assertEqual(result.evidence_state, "MULTI_TARGET_AMBIGUOUS")

    def test_both_target_silencing_is_multi_target(self):
        result = self.decide(
            "This study found that silencing of both Kinase X and Kinase Z reduced marker Y."
        )
        self.assertEqual(result.evidence_state, "MULTI_TARGET_AMBIGUOUS")

    def test_background_proposition_only(self):
        result = self.decide("Previous studies reported that activation of Kinase X increased marker Y.")
        self.assertEqual(result.evidence_state, "BACKGROUND_ONLY")
        self.assertEqual(result.evidence_role, "BACKGROUND_PRIOR_WORK")

    def test_discussion_speculation_only(self):
        result = self.decide("Kinase X may increase marker Y.")
        self.assertEqual(result.evidence_state, "UNRESOLVED")
        self.assertEqual(result.evidence_role, "DISCUSSION_SPECULATION")

    def test_current_functional_evidence_overrides_background_noise(self):
        result = self.decide(
            "Previous studies reported that Kinase X correlated with marker Y. "
            "Here we activated Kinase X and observed increased marker Y."
        )
        self.assertEqual(result.evidence_state, "DIRECT_FUNCTIONAL")
        self.assertEqual(result.evidence_role, "MIXED")

    def test_unrelated_functional_experiment_does_not_rescue_target(self):
        result = self.decide(
            "Our results showed Kinase X correlated with marker Y, while knockdown of Kinase Z increased marker Y."
        )
        self.assertEqual(result.evidence_state, "ASSOCIATION_ONLY")
        self.assertEqual(result.subject_perturbation_specificity, "NO_SUBJECT_PERTURBATION")

    def test_endpoint_as_actor_does_not_become_endpoint_response(self):
        result = self.decide(
            "Marker Y binds a promoter and enhances marker Z in response to Kinase X treatment."
        )
        self.assertNotEqual(result.evidence_state, "DIRECT_FUNCTIONAL")

    def test_endpoint_response_absent(self):
        result = self.decide("This study knocked down Kinase X and measured an unrelated phenotype.")
        self.assertEqual(result.evidence_state, "UNRESOLVED")
        self.assertIn("NO_ENDPOINT_RESPONSE_EVIDENCE", result.reason_codes)

    def test_subject_perturbation_absent(self):
        result = self.decide("Our analysis measured marker Y in samples expressing Kinase X.")
        self.assertEqual(result.evidence_state, "UNRESOLVED")
        self.assertIn("NO_TARGET_PERTURBATION_EVIDENCE", result.reason_codes)

    def test_direction_conflict(self):
        result = self.decide("Activation of Kinase X decreased marker Y.")
        self.assertEqual(result.evidence_state, "UNRESOLVED")
        self.assertEqual(result.direction_compatibility, "CONFLICT")
        self.assertIn("DIRECTION_CONFLICT", result.reason_codes)

    def test_one_pathway_activation_cue_cannot_fill_both_roles(self):
        result = self.decide("This study found activation of the Kinase X/marker Y pathway.")
        self.assertNotEqual(result.evidence_state, "DIRECT_FUNCTIONAL")

    def test_bare_chain_word_is_not_functional_chain(self):
        result = self.decide("Kinase X and marker Y occur in an axis via an upstream pathway.")
        self.assertNotEqual(result.evidence_state, "FUNCTIONAL_CHAIN")

    def test_multi_endpoint_wording_is_not_a_multi_target_intervention(self):
        result = self.decide("We found Kinase X involved in both phenotype A and marker Y.")
        self.assertNotEqual(result.evidence_state, "MULTI_TARGET_AMBIGUOUS")

    def test_insufficient_abstract_is_unresolved(self):
        result = self.decide("Kinase X and marker Y were discussed.")
        self.assertEqual(result.evidence_state, "UNRESOLVED")

    def test_associative_target_does_not_require_functional_evidence(self):
        result = self.decide("Kinase X correlated with marker Y.", relation="associated_with")
        self.assertFalse(result.applicable)
        self.assertFalse(result.applicability["requires_functional_evidence"])
        self.assertEqual(result.evidence_state, "UNRESOLVED")

    def test_deterministic_replay_and_shadow_flags(self):
        first = self.decide("We activated Kinase X and observed increased marker Y.")
        second = self.decide("We activated Kinase X and observed increased marker Y.")
        self.assertEqual(first, second)
        self.assertTrue(first.preacquisition_only)
        self.assertFalse(first.modifies_tier)
        self.assertFalse(first.modifies_acquisition)
        self.assertFalse(first.modifies_sample_membership)
        self.assertFalse(first.modifies_reject_status)


if __name__ == "__main__":
    unittest.main()
