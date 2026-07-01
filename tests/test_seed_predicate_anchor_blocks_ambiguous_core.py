import unittest

from code_engine.normalization.layered_grounding import anchor_seed_predicate


class PredicateAnchorAmbiguityTests(unittest.TestCase):
    def test_unanchored_altered_relation_is_ambiguous(self):
        result = anchor_seed_predicate("Metformin altered AMPK and CHMP2B signaling.", ["metformin"], ["AMPK"], "activation", {})
        self.assertEqual(result.anchor_status, "no_seed_predicate_found")
        self.assertFalse(result.predicate_direction_consistent)


if __name__ == "__main__": unittest.main()
