import json, unittest
from pathlib import Path
class NoOverfitTests(unittest.TestCase):
    def test_runner_does_not_change_scoring_and_profile_remains_generic(self):
        source=Path("src/code_engine/cli/run_case.py").read_text(); self.assertNotIn("AMPK gene",source); self.assertNotIn("mixed result into supportive",source)
        profile=json.loads(Path("configs/case_profiles/metformin_ampk_cancer.case_profile.json").read_text()); self.assertEqual(profile["expected_validators"],["lincs_l1000"])
