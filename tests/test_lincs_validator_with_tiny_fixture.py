import json,tempfile,unittest
from pathlib import Path
from code_engine.validation.lincs_local import LincsLocalValidator
class ValidatorTests(unittest.TestCase):
 def test_available_compact_index_produces_results(self):
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp); run=root/"run"; art=run/"artifacts"; art.mkdir(parents=True); (art/"l7_validation_targets.jsonl").write_text(json.dumps({"validation_target_id":"V","claim":"metformin AMPK mTOR axis"})+"\n")
   index=root/"external/lincs_l1000/index/GSE70138"; index.mkdir(parents=True); (index/"metformin_index_summary.json").write_text("{}")
   (index/"metformin_top_genes.jsonl").write_text(json.dumps({"sig_id":"S1","cell_id":"MCF7","top_up_genes":["PRKAA1"],"top_down_genes":["MTOR"]})+"\n")
   value=LincsLocalValidator().validate_run(run,external_data_root=root/"external")
  self.assertEqual(value["status"],"partially_completed"); self.assertTrue(value["lincs_local_validation_executed"])
if __name__=="__main__": unittest.main()
