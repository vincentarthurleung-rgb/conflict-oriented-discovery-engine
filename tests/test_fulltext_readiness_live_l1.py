import json,os,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from code_engine.validation.readiness import check_case_readiness
class LiveReadinessTests(unittest.TestCase):
 def test_conflict_case_reports_pmc_and_l1_requirements(self):
  with tempfile.TemporaryDirectory() as td:
   p=Path(td)/"p.json"; p.write_text(json.dumps({"case_id":"c","query":"a b","case_type":"conflict_enriched","validation_needs":["full_text_conflict_confirmation"],"profile_version":"1"})); plan=Path(td)/"s.json"; plan.write_text('{"frozen":true}')
   with patch.dict(os.environ,{"L1_PROVIDER":"deepseek","MODEL_NAME":"m","DEEPSEEK_API_KEY":"x"},clear=True): report=check_case_readiness(p,plan,network_allowed=True)
   self.assertTrue(report["fulltext"]["pmc_client_configured"]); self.assertTrue(report["fulltext"]["l1_required_if_oa_available"]); self.assertTrue(report["fulltext"]["ready"])
