import tempfile
import unittest
from pathlib import Path
from code_engine.validation.case_routing import load_case_domain_profile
from tests.case_factory_test_support import generate

class CaseFactoryProfileTests(unittest.TestCase):
    def test_required_profile_contract(self):
        with tempfile.TemporaryDirectory() as tmp:
            generate(Path(tmp)); profile=load_case_domain_profile(Path(tmp)/"generated/generic_case/case_profile.json")
            self.assertEqual(profile.schema_version,"case_domain_profile_v1")
            self.assertEqual(profile.case_version,"v1"); self.assertTrue(profile.validation_needs)
            self.assertIn("do_not_overclaim",profile.scientific_notes)
