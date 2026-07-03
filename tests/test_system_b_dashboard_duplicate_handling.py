import shutil
import tempfile
import unittest
from pathlib import Path

from code_engine.system_b import SystemBBatchIngestor
from code_engine.system_b.dashboard import DashboardData


class DashboardDuplicateHandlingTests(unittest.TestCase):
    def test_active_bundle_wins_and_duplicate_is_not_primary_warning(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td); active = root / "case_bundles"; preserved = root / "preserved_case_bundles"
            shutil.copytree("case_bundles/metformin_ampk_cancer", active / "metformin_ampk_cancer")
            shutil.copytree("case_bundles/metformin_ampk_cancer", preserved / "case_001_metformin_ampk_cancer")
            output = root / "outputs"; registry = output / "case_registry.json"
            result = SystemBBatchIngestor().run([active, preserved], output, registry)
            case = result["registry"]["cases"][0]
            self.assertEqual(result["registry"]["case_count"], 1)
            self.assertTrue(case["bundle_path"].startswith(str(active)))
            self.assertIn("duplicate_case_version", case["warnings"])
            summary = DashboardData(output, output / "kg").summary()
            self.assertFalse(any("duplicate_case_version" in item for item in summary["warnings"]))
            self.assertNotIn("duplicate", (summary["primary_next_step"] or "").lower())


if __name__ == "__main__": unittest.main()
