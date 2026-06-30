import unittest

from code_engine.temporal.status_classifier import classify_temporal_status


class StatusTests(unittest.TestCase):
    def test_persistent(self):
        self.assertEqual(classify_temporal_status(early_entropy=1, later_entropy=1, early_paper_count=4, later_paper_count=2, later_dominant_direction_share=.5)[0], "persistent_conflict")

    def test_stale_is_not_resolved(self):
        status, _ = classify_temporal_status(early_entropy=1, later_entropy=0, early_paper_count=4, later_paper_count=0, later_dominant_direction_share=0)
        self.assertEqual(status, "stale_unresolved_conflict")


if __name__ == "__main__": unittest.main()
