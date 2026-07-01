import unittest
import tempfile
from pathlib import Path

from tests.l2_layered_helpers import run_case


class L2LayeredSummaryCountTests(unittest.TestCase):
    def test_counts_distinguish_non_core_from_discarded(self):
        with tempfile.TemporaryDirectory() as tmp:
            summary = run_case(Path(tmp)).summary
            self.assertTrue(summary["layered_retention_enabled"])
            self.assertEqual(summary["excluded_from_core_count"], summary["non_core_observation_count"])
            self.assertEqual(summary["excluded_from_retention_count"], summary["excluded_observation_count"])
            self.assertEqual(summary["retained_observation_count"] + summary["excluded_from_retention_count"], summary["normalized_observation_count"])


if __name__ == "__main__": unittest.main()
