import json,tempfile,unittest
from pathlib import Path
from code_engine.cli.l2_canonicalization_audit import audit
class L2AuditTests(unittest.TestCase):
 def test_reports_missing_and_salvage(self):
  with tempfile.TemporaryDirectory() as tmp:
   a=Path(tmp)/"artifacts";a.mkdir();row={"subject_raw":"Specific process","subject_type":"biological_process","object_raw":"Specific phenotype","object_type":"phenotype","relation_raw":"promoted","relation_family":"activation","evidence_sentence":"Specific process promoted Specific phenotype.","paper_id":"P"};(a/"l2_retained_observations.jsonl").write_text(json.dumps(row)+"\n")
   summary,*_=audit(tmp);self.assertEqual(1,summary["missing_subject_canonical_id_count"]);self.assertEqual(1,summary["salvage_candidate_count"])
if __name__=="__main__":unittest.main()
