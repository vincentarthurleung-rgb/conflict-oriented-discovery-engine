import io,json,os,tempfile,unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch
from code_engine.cli.run_case import main
from code_engine.fulltext.stage import run_l35_pmc_oa_stage
class IntegrationTests(unittest.TestCase):
 def test_no_candidate_stage_and_conflict_dry_plan(self):
  with tempfile.TemporaryDirectory() as td:
   run=Path(td)/"run"; (run/"artifacts").mkdir(parents=True); summary=run_l35_pmc_oa_stage(run,enabled=True)
   self.assertEqual(summary["status"],"completed_no_candidates")
   profile=Path(td)/"case.json"; profile.write_text(json.dumps({"case_id":"conflict","query":"a b","case_type":"conflict_enriched","validation_needs":["full_text_conflict_confirmation"],"profile_version":"1"}))
   plan=Path(td)/"plan.json"; plan.write_text('{"frozen":true}')
   out=io.StringIO()
   with patch.dict(os.environ,{"L1_PROVIDER":"deepseek","MODEL_NAME":"m","DEEPSEEK_API_KEY":"x"},clear=True),redirect_stdout(out): self.assertEqual(main(["--case-profile",str(profile),"--search-plan-file",str(plan),"--network","--enable-fulltext-confirmation","--dry-run"]),0)
   self.assertIn('"selection_policy": "conflict_related_only"',out.getvalue()); self.assertIn('"publisher_scraping": false',out.getvalue())
 def test_metformin_does_not_force_fulltext(self):
  out=io.StringIO()
  with patch.dict(os.environ,{"L1_PROVIDER":"deepseek","MODEL_NAME":"m","DEEPSEEK_API_KEY":"x"},clear=True),redirect_stdout(out): main(["--case-profile","configs/case_profiles/metformin_ampk_cancer.case_profile.json","--search-plan-file","configs/search_plans/metformin_ampk_cancer_2000_2020.llm_v1.frozen.json","--dry-run"])
  self.assertIn('"enabled": false',out.getvalue())
