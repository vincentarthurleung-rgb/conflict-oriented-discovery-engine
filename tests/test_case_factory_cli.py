import json
import tempfile
import unittest
from pathlib import Path
from code_engine.cli.case_factory import main
from tests.case_factory_test_support import QUERY

class CaseFactoryCliTests(unittest.TestCase):
    def test_natural_language_generates_case_directory(self):
        with tempfile.TemporaryDirectory() as tmp:
            code=main(["--case-id","natural_case","--query",QUERY,"--output-root","generated","--repository-root",tmp,"--no-api","--no-network"])
            self.assertEqual(code,0); root=Path(tmp)/"generated/natural_case"
            self.assertTrue((root/"case_factory_manifest.json").is_file())
            self.assertEqual(json.loads((root/"case_profile.json").read_text())["case_id"],"natural_case")
