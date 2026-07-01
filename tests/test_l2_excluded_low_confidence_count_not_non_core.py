import tempfile
import unittest
from pathlib import Path

from tests.l2_layered_helpers import run_case


class DeprecatedLowConfidenceCountTests(unittest.TestCase):
    def test_low_confidence_exclusion_is_not_non_core_count(self):
        with tempfile.TemporaryDirectory() as tmp:
            summary = run_case(Path(tmp)).summary
            self.assertEqual(summary["excluded_low_confidence_count"], summary["low_confidence_excluded_from_retention_count"])
            self.assertEqual(summary["legacy_excluded_low_confidence_count"], summary["non_core_observation_count"])
            self.assertTrue(summary["excluded_low_confidence_count_deprecated_previous_semantics"])


if __name__ == "__main__": unittest.main()
