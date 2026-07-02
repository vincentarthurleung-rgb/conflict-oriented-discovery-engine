import json,tempfile,unittest
from pathlib import Path
from code_engine.validation.lincs_local import LincsLocalValidator
class L7SummaryTests(unittest.TestCase):
 def test_missing_and_available_states_are_explicit(self):
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp); run=root/"run"; (run/"artifacts").mkdir(parents=True); (run/"artifacts/l7_validation_targets.jsonl").write_text(""); value=LincsLocalValidator().validate_run(run,external_data_root=root)
   saved=json.loads((run/"artifacts/l7_external_validation_summary.json").read_text())
  self.assertEqual(value["status"],saved["status"]); self.assertFalse(saved["validation_executed"])
if __name__=="__main__": unittest.main()
