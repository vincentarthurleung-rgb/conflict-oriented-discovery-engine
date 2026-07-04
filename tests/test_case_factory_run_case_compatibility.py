import tempfile
import unittest
from pathlib import Path
from code_engine.cli.run_case import main
from tests.case_factory_test_support import generate

class CaseFactoryRunCaseCompatibilityTests(unittest.TestCase):
    def test_generated_paths_support_run_case_dry_run(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); generate(root); package=root/"generated/generic_case"
            code=main(["--case-profile",str(package/"case_profile.json"),"--search-plan-file",str(package/"search_plan.frozen.json"),"--external-data-root",str(root/"external"),"--dry-run"])
            self.assertEqual(code,0)
