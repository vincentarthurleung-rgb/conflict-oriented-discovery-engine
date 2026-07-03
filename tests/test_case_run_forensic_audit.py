import json,tempfile,unittest
from pathlib import Path
from code_engine.cli.case_run_forensic_audit import audit_case_run
class ForensicAuditTests(unittest.TestCase):
 def test_detects_core_gate_loss(self):
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp);bundle=root/"bundle";source=root/"source/artifacts";final=root/"final/artifacts"
   for p in (bundle,source,final):p.mkdir(parents=True)
   (bundle/"case_bundle_manifest.json").write_text(json.dumps({"case_id":"fixture","core_observation_count":0}))
   (source/"abstract_l1_summary.json").write_text('{"paper_count":1}')
   (source/"abstract_l1_claims.jsonl").write_text('{"claim_id":"c"}\n')
   (final/"l2_retained_observations.jsonl").write_text(json.dumps({"canonical_graph_eligible":False})+'\n')
   value=audit_case_run(bundle,source.parent,final.parent)
   self.assertEqual("CANONICALIZATION_FAILED",value["zero_claim_diagnosis"]["diagnosis"])
if __name__=="__main__":unittest.main()
