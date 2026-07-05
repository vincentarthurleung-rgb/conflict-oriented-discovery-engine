import tempfile
import unittest
from pathlib import Path

from code_engine.system_b import SystemBBatchIngestor


class NextCaseRecommendationTests(unittest.TestCase):
    def test_positive_control_only_recommends_conflict_case(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            result = SystemBBatchIngestor().run(["tests/fixtures/system_b_case_bundles"], root, root / "registry.json", case_glob="metformin_ampk_cancer")
            recommendation = result["recommendation"]
            self.assertEqual(recommendation["suggested_case_type"], "conflict_enriched")
            self.assertEqual(recommendation["primary_recommendation"], "Proceed to first conflict-enriched case.")


if __name__ == "__main__":
    unittest.main()
