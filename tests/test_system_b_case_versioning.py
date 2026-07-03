import shutil
import tempfile
import unittest
from pathlib import Path

from code_engine.system_b import SystemBBatchIngestor


class CaseVersioningTests(unittest.TestCase):
    def test_duplicate_case_version_records_warning(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            registry = root / "registry.json"
            ingestor = SystemBBatchIngestor()
            first = ingestor.run(["case_bundles"], root, registry)
            duplicate_root = root / "preserved"
            shutil.copytree("case_bundles/metformin_ampk_cancer", duplicate_root / "case_001")
            second = ingestor.run([duplicate_root], root, registry)
            self.assertEqual(first["registry"]["cases"][0]["case_version"], "v1")
            self.assertEqual(second["registry"]["case_count"], 1)
            self.assertIn("duplicate_case_version", second["registry"]["cases"][0]["warnings"])
            self.assertTrue(any(item.startswith("duplicate_case_version:") for item in second["registry"]["warnings"]))


if __name__ == "__main__":
    unittest.main()
