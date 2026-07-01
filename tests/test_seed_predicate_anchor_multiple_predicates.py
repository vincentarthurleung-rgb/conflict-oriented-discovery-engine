import unittest

from code_engine.normalization.layered_grounding import anchor_seed_predicate


class PredicateAnchorTests(unittest.TestCase):
    def test_seed_object_predicate_wins_over_sentence_primary(self):
        result = anchor_seed_predicate("Metformin suppressed CHMP2B accumulation by activating AMPK.", ["metformin"], ["AMPK"], "activates", {})
        self.assertEqual(result.anchor_status, "multiple_predicates_resolved")
        self.assertEqual(result.seed_predicate_span, "activating AMPK")
        self.assertEqual(result.sentence_primary_predicate, "suppressed")
        self.assertEqual(result.direct_relation_sign, 1)
        self.assertTrue(result.predicate_direction_consistent)

    def test_object_then_nominal_predicate_is_supported(self):
        result = anchor_seed_predicate("The effect occurred through AMPK activation in cancer cells.", ["metformin"], ["AMPK"], "activation", {})
        self.assertEqual(result.seed_predicate_span, "AMPK activation")
        self.assertEqual(result.direct_relation_sign, 1)


if __name__ == "__main__": unittest.main()
