import json, tempfile, unittest
from tests.rebuild_test_support import make_rebuild

class RebuildYearFilterTests(unittest.TestCase):
    def test_year_filter_is_inherited(self):
        with tempfile.TemporaryDirectory() as tmp:
            _, output = make_rebuild(tmp)
            value = json.loads((output / "artifacts/runtime_provenance_report.json").read_text())["paper_year_filter"]
        self.assertTrue(value["enabled"])
        self.assertEqual((value["paper_year_from"], value["paper_year_to"]), (2000, 2020))
        self.assertEqual(value["source"], "inherited_from_source_run_or_frozen_search_plan")

if __name__ == "__main__": unittest.main()
