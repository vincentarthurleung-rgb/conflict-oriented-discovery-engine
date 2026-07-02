import unittest

from code_engine.evidence_graph.direction_polarity import direction_polarity, is_opposing_polarity_conflict


class DirectionPolarityTests(unittest.TestCase):
    def test_mapping_and_conflict_semantics(self):
        self.assertEqual(direction_polarity("activate"), "positive")
        self.assertEqual(direction_polarity("increase"), "positive")
        self.assertEqual(direction_polarity("inhibit"), "negative")
        self.assertEqual(direction_polarity("decrease"), "negative")
        self.assertFalse(is_opposing_polarity_conflict({"decrease": 1, "inhibit": 1}))
        self.assertFalse(is_opposing_polarity_conflict({"activate": 1}))
        self.assertTrue(is_opposing_polarity_conflict({"activate": 1, "inhibit": 1}))
        self.assertTrue(is_opposing_polarity_conflict({"increase": 1, "decrease": 1}))


if __name__ == "__main__": unittest.main()
