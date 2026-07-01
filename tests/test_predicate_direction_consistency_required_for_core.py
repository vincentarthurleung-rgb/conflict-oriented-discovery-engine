import unittest

from code_engine.normalization.layered_grounding import anchor_seed_predicate


class PredicateConsistencyTests(unittest.TestCase):
    def test_inhibition_anchor_conflicts_with_activation_seed(self):
        result = anchor_seed_predicate("Metformin inhibits AMPK.", ["metformin"], ["AMPK"], "activation", {})
        self.assertEqual(result.direct_relation_sign, -1)
        self.assertFalse(result.predicate_direction_consistent)
        self.assertIn("predicate_direction_inconsistent", result.warnings)


if __name__ == "__main__": unittest.main()
