import json, tempfile, unittest
from tests.rebuild_test_support import make_rebuild

class RebuildPathTests(unittest.TestCase):
    def test_paths_point_to_rebuilt_run(self):
        with tempfile.TemporaryDirectory() as tmp:
            source, output = make_rebuild(tmp)
            value = json.loads((output / "artifacts/runtime_provenance_report.json").read_text())
        self.assertEqual(value["run_dir"], str(output))
        self.assertEqual(value["artifacts_dir"], str(output / "artifacts"))
        self.assertEqual(value["rebuild_from_run"]["source_run_dir"], str(source))
        self.assertNotEqual(value["run_dir"], value["rebuild_from_run"]["source_run_dir"])

if __name__ == "__main__": unittest.main()
