import unittest

from code_engine.discovery.lanes import DiscoveryRecallPolicy,evaluate_claim_comparability,evaluate_weak_candidate_pairs


def observation(identifier,direction,obj,subject="Factor A",relation=None,context=None):
    return {"observation_id":identifier,"subject_raw":subject,"subject_canonical_name":"factor a","object_raw":obj,
        "relation_raw":relation or ("increases" if direction=="positive" else "decreases"),"direction":direction,
        "context_terms":context or [],"eligible_for_weak_conflict":True,"anchor_strength":"strong","seed_neighborhood_score":.9,
        "paper_id":identifier,"pmid":identifier,"evidence_sentence":f"{subject} {relation or direction} {obj}."}


class WeakConflictComparabilityTests(unittest.TestCase):
    def test_different_object_families_are_diagnostic_not_weak_conflict(self):
        left=observation("p","positive","enzyme expression");right=observation("n","negative","channel expression")
        weak,rejected=evaluate_weak_candidate_pairs([left,right])
        self.assertEqual(weak,[]);self.assertEqual(len(rejected),1);self.assertEqual(rejected[0]["candidate_type"],"mechanism_split")
        self.assertIn("object_family_mismatch",rejected[0]["non_comparability_reasons"])

    def test_same_subject_object_and_regulatory_relation_can_be_weak(self):
        weak,rejected=evaluate_weak_candidate_pairs([observation("p","positive","target protein level"),observation("n","negative","target protein expression")])
        self.assertEqual(len(weak),1);self.assertFalse(rejected);self.assertTrue(weak[0]["is_weak_conflict"])
        for field in ("comparability_score","comparability_label","subject_family_match","object_family_match","relation_family_match","intervention_state_match","context_match","direction_opposed"):self.assertIn(field,weak[0])

    def test_intervention_effect_pair_is_blocked_by_default(self):
        left=observation("p","positive","target expression");right=observation("n","negative","target expression",subject="depletion of Factor A")
        comparison=evaluate_claim_comparability(left,right)
        self.assertEqual(comparison["candidate_type"],"intervention_effect_pair");self.assertFalse(comparison["eligible_for_weak_conflict"])

    def test_context_split_remains_reviewable_weak_candidate(self):
        left=observation("p","positive","target expression",context=["model one"]);right=observation("n","negative","target expression",context=["model two"])
        weak,_=evaluate_weak_candidate_pairs([left,right]);self.assertEqual(len(weak),1);self.assertEqual(weak[0]["candidate_type"],"context_split")

    def test_process_divergence_is_mechanism_split(self):
        left=observation("p","positive","target accumulation");right=observation("n","negative","target cytoplasmic translocation")
        comparison=evaluate_claim_comparability(left,right)
        self.assertFalse(comparison["eligible_for_weak_conflict"]);self.assertIn("object_process_type_mismatch",comparison["non_comparability_reasons"])

    def test_different_subcellular_compartments_are_mechanism_split(self):
        left=observation("p","positive","target protein level in the nucleus");right=observation("n","negative","target protein level in the cytoplasm")
        comparison=evaluate_claim_comparability(left,right);self.assertFalse(comparison["eligible_for_weak_conflict"]);self.assertIn("object_compartment_mismatch",comparison["non_comparability_reasons"])


if __name__=="__main__":unittest.main()
