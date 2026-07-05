import tempfile
import unittest
from pathlib import Path

from code_engine.system_b import SystemBBatchIngestor


class SystemBComparisonTableTests(unittest.TestCase):
    def test_comparison_preserves_mixed_interpretation(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            result = SystemBBatchIngestor().run(["tests/fixtures/system_b_case_bundles"], root, root / "registry.json", case_glob="metformin_ampk_cancer")
            row = result["comparison"]["cases"][0]
            self.assertEqual(row["lincs_interpretation"], "mixed")
            self.assertEqual(row["recommended_next_step"], "Proceed to first conflict-enriched case.")


if __name__ == "__main__":
    unittest.main()
