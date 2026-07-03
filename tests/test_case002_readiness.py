import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from code_engine.validation.readiness import check_case_readiness


class Case002ReadinessTests(unittest.TestCase):
    def test_placeholder_blocks_run_and_smoke_does_not_enable_validator(self):
        with tempfile.TemporaryDirectory() as td:
            smoke = Path(td) / "smoke.json"
            smoke.write_text(json.dumps({"results": {"reactome": {"status": "reachable", "production_validator_ready": False}}}))
            env = {"L1_PROVIDER": "deepseek", "MODEL_NAME": "fixture", "DEEPSEEK_API_KEY": "fixture"}
            with patch.dict(os.environ, env, clear=True), patch("urllib.request.urlopen", side_effect=AssertionError("network call")):
                report = check_case_readiness(
                    "configs/case_profiles/autophagy_cancer_chemoresistance.case_profile.json",
                    "configs/search_plans/autophagy_cancer_chemoresistance.placeholder.json",
                    td, network_allowed=True, smoke_report_file=smoke,
                )
        self.assertTrue(report["case_profile"]["ready"])
        self.assertEqual(report["search_plan"]["status"], "placeholder")
        self.assertFalse(report["search_plan"]["ready"]); self.assertFalse(report["ready"])
        self.assertTrue(report["fulltext"]["enabled"]); self.assertTrue(report["fulltext"]["ready"])
        reactome = next(item for item in report["resources"] if item["validator_id"] == "reactome")
        self.assertTrue(reactome["api_reachable"]); self.assertFalse(reactome["production_validator_ready"])
        self.assertFalse(reactome["blocking"])
        self.assertEqual(report["routing"]["required_validator_policy"], "warning_only")


if __name__ == "__main__": unittest.main()
