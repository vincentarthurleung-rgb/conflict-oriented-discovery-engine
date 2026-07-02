import json,tempfile,unittest
from pathlib import Path
from code_engine.validation.lincs_local import LincsLocalValidator
from code_engine.reporting.full_abstract_pipeline import generate_full_abstract_pipeline
from tests.full_pipeline_test_support import make_pipeline

class StatusTests(unittest.TestCase):
 def test_executed_lincs_replaces_plan_only_status(self):
  with tempfile.TemporaryDirectory() as tmp:
   root=make_pipeline(Path(tmp)/"run"); generate_full_abstract_pipeline(root); index=Path(tmp)/"external/lincs_l1000/index/GSE70138"; index.mkdir(parents=True); (index/"metformin_index_summary.json").write_text("{}"); (index/"metformin_top_genes.jsonl").write_text(json.dumps({"sig_id":"S","cell_id":"MCF7","top_up_genes":[],"top_down_genes":[]})+"\n"); LincsLocalValidator().validate_run(root,external_data_root=Path(tmp)/"external")
   stage=json.loads((root/"artifacts/pipeline_stage_summary.json").read_text())["stages"]["L7"]; report=(root/"artifacts/whitebox_case_report.md").read_text()
  self.assertEqual(stage["status"],"partially_completed"); self.assertNotIn("| L7 External validation | not_run_config_missing |",report)
if __name__=="__main__": unittest.main()
