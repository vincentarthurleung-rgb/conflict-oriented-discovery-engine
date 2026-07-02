import json,tempfile,unittest
from pathlib import Path
from code_engine.validation.lincs_local import LincsLocalValidator
class MissingTests(unittest.TestCase):
 def test_missing_index_is_non_crashing_plan_status(self):
  with tempfile.TemporaryDirectory() as tmp:
   run=Path(tmp)/"run"; (run/"artifacts").mkdir(parents=True); (run/"artifacts/l7_validation_targets.jsonl").write_text(json.dumps({"validation_target_id":"V","claim":"metformin AMPK"})+"\n"); value=LincsLocalValidator().validate_run(run,external_data_root=Path(tmp)/"external")
  self.assertEqual(value["status"],"not_run_config_missing"); self.assertTrue(value["missing_external_data"])
if __name__=="__main__": unittest.main()
