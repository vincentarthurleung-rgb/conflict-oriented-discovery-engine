import tempfile
import unittest
from pathlib import Path

from code_engine.system_b import SystemBBatchIngestor


class SystemBCaseRegistryTests(unittest.TestCase):
    def test_registry_contains_case_001_and_followup_count(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            result = SystemBBatchIngestor().run(["tests/fixtures/system_b_case_bundles"], root, root / "case_registry.json", case_glob="metformin_ampk_cancer")
            case = result["registry"]["cases"][0]
            self.assertEqual(case["case_label"], "case_001")
            self.assertEqual(case["case_id"], "metformin_ampk_cancer")
            self.assertEqual(case["manual_review_followup_count"], 2)


if __name__ == "__main__":
    unittest.main()
