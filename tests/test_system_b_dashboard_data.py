import tempfile
import unittest
from pathlib import Path

from code_engine.system_b.dashboard import DashboardData


class DashboardDataTests(unittest.TestCase):
    def test_summary_and_case_data(self):
        data = DashboardData("system_b_outputs", "system_b_outputs/kg")
        summary = data.summary(); cases = data.cases()
        self.assertEqual(summary["case_count"], 1)
        self.assertGreater(summary["kg"]["node_count"], 0)
        self.assertEqual(cases["cases"][0]["case_id"], "metformin_ampk_cancer")
        self.assertEqual(data.case_card("metformin_ampk_cancer")["quality_class"], "CASE_READY_FOR_ARCHIVE")

    def test_missing_optional_files_return_warnings(self):
        with tempfile.TemporaryDirectory() as td:
            data = DashboardData(td, Path(td) / "kg")
            summary = data.summary()
            self.assertEqual(summary["case_count"], 0)
            self.assertTrue(summary["warnings"])
            self.assertEqual(data.comparison()["cases"], [])


if __name__ == "__main__": unittest.main()
