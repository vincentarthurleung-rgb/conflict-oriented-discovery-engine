import io, os, unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch
from code_engine.cli.run_case import main
class RunCasePlanningTests(unittest.TestCase):
    def test_dry_run_plans_without_creating_run(self):
        before=set(Path("runs").iterdir()) if Path("runs").exists() else set(); out=io.StringIO()
        with patch.dict(os.environ,{"L1_PROVIDER":"deepseek","MODEL_NAME":"m","DEEPSEEK_API_KEY":"x"},clear=True), redirect_stdout(out):
            self.assertEqual(main(["--case-profile","configs/case_profiles/metformin_ampk_cancer.case_profile.json","--search-plan-file","configs/search_plans/metformin_ampk_cancer_2000_2020.llm_v1.frozen.json","--dry-run"]),0)
        after=set(Path("runs").iterdir()) if Path("runs").exists() else set(); self.assertEqual(before,after); self.assertNotIn("--enable-lincs-local-validation",out.getvalue())
