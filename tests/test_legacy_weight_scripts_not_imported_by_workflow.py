import unittest
from pathlib import Path


class LegacyWeightImportTests(unittest.TestCase):
    def test_legacy_weight_scripts_not_imported_by_workflow(self):
        workflow = "\n".join(path.read_text() for path in Path("src/code_engine/workflow").glob("*.py"))
        self.assertNotIn("stage1_clean_weight", workflow)
        self.assertNotIn("literature_quality_audit.csv", workflow)
        script = Path("scripts/stage1_clean_weight.py").read_text()
        self.assertIn("LEGACY ONLY", script)


if __name__ == "__main__": unittest.main()
