import tempfile
import unittest
from pathlib import Path
from tests.case_factory_test_support import generate

class CaseFactoryOverwriteTests(unittest.TestCase):
    def test_generated_package_requires_explicit_overwrite(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); generate(root)
            with self.assertRaises(FileExistsError): generate(root)
            generate(root,overwrite_generated=True)
    def test_config_copy_requires_explicit_overwrite(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); target=root/"configs/case_profiles/generic_case.case_profile.json"
            target.parent.mkdir(parents=True); target.write_text("sentinel")
            with self.assertRaises(FileExistsError): generate(root,copy_to_configs=True)
            self.assertEqual(target.read_text(),"sentinel")
