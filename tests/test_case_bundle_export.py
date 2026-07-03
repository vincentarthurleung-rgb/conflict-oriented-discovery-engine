import json, tempfile, unittest
from pathlib import Path
from code_engine.cli.export_case_bundle import export_case_bundle
class BundleExportTests(unittest.TestCase):
    def test_required_missing_marks_not_ready_and_optional_does_not_crash(self):
        with tempfile.TemporaryDirectory() as td:
            run=Path(td)/"runs/source__rebuilt"; (run/"artifacts").mkdir(parents=True)
            out,m=export_case_bundle(run,"configs/case_profiles/metformin_ampk_cancer.case_profile.json",Path(td)/"bundles")
            self.assertEqual(m["schema_version"],"case_bundle_manifest_v1"); self.assertFalse(m["ready_for_system_b"]); self.assertTrue((out/"case_bundle_manifest.json").is_file())
