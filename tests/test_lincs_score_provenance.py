import json,tempfile,unittest
from pathlib import Path
from code_engine.validation.lincs_local import LincsLocalValidator

def validated(tmp):
 root=Path(tmp); run=root/"run"; art=run/"artifacts"; art.mkdir(parents=True); (art/"l7_validation_targets.jsonl").write_text(json.dumps({"validation_target_id":"V","claim":"compound AMPK mTOR axis"})+"\n")
 index=root/"external/lincs_l1000/index/GSE70138"; index.mkdir(parents=True); (index/"metformin_index_summary.json").write_text("{}"); (index/"metformin_top_genes.jsonl").write_text(json.dumps({"sig_id":"S","cell_id":"A375","top_up_genes":["OTHER"],"top_down_genes":[]})+"\n")
 summary=LincsLocalValidator().validate_run(run,external_data_root=root/"external"); result=json.loads((art/"l7_lincs_validation_results.jsonl").read_text().splitlines()[0]); return summary,result

class ProvenanceTests(unittest.TestCase):
 def test_score_components_are_explained(self):
  with tempfile.TemporaryDirectory() as tmp: summary,result=validated(tmp)
  self.assertEqual(result["score_provenance"]["scoring_version"],"lincs_transcriptomic_consistency_v1"); self.assertIn("median",summary["score_distribution"]); self.assertEqual(result["validation_interpretation"],"mixed")
if __name__=="__main__": unittest.main()
