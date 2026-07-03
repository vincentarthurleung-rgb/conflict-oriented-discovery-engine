import json
import tempfile
import unittest
from pathlib import Path

from code_engine.system_b import CaseBundleLoader


class CaseBundleLoaderTests(unittest.TestCase):
    def test_loads_metformin_bundle(self):
        bundle = CaseBundleLoader("case_bundles/metformin_ampk_cancer").load()
        self.assertEqual(bundle["case_id"], "metformin_ampk_cancer")
        self.assertEqual(bundle["missing_required_files"], [])
        self.assertEqual(bundle["external_validation"]["matched_signature_count"], 42)

    def test_missing_optional_files_do_not_crash(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td)
            for filename in CaseBundleLoader.REQUIRED_FILES.values():
                (path / filename).write_text(json.dumps({"case_id": "minimal"}), encoding="utf-8")
            bundle = CaseBundleLoader(path).load()
            self.assertTrue(bundle["missing_optional_files"])
            self.assertEqual(bundle["lincs_validation"], {})


if __name__ == "__main__":
    unittest.main()
