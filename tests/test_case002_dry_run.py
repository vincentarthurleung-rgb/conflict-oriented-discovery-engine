import io
import os
import unittest
from contextlib import redirect_stdout
from unittest.mock import patch

from code_engine.cli.run_case import main


class Case002DryRunTests(unittest.TestCase):
    def test_dry_run_plans_fulltext_without_execution(self):
        output = io.StringIO()
        env = {"L1_PROVIDER": "deepseek", "MODEL_NAME": "fixture", "DEEPSEEK_API_KEY": "fixture"}
        with patch.dict(os.environ, env, clear=True), patch("subprocess.run", side_effect=AssertionError("source run executed")), patch("urllib.request.urlopen", side_effect=AssertionError("network call")), redirect_stdout(output):
            status = main(["--case-profile", "configs/case_profiles/autophagy_cancer_chemoresistance.case_profile.json", "--search-plan-file", "configs/search_plans/autophagy_cancer_chemoresistance_2000_2020.llm_v1.frozen.json", "--external-data-root", "data/external", "--api", "--network", "--enable-fulltext-confirmation", "--fulltext-max-papers", "20", "--fulltext-max-sections-per-paper", "12", "--fulltext-max-total-chunks", "200", "--dry-run"])
        text = output.getvalue()
        self.assertEqual(status, 0); self.assertIn("SOURCE_COMMAND:", text); self.assertIn("REBUILD_COMMAND:", text)
        self.assertIn('"enabled": true', text); self.assertIn('"source": "pmc_oa"', text)
        self.assertIn("CASE_RUN_DRY_RUN", text); self.assertIn('"reactome"', text)
        self.assertIn("recommended_but_unavailable", text)


if __name__ == "__main__": unittest.main()
