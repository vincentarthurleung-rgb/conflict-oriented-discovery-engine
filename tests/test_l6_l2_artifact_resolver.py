import json, tempfile, unittest
from pathlib import Path
from code_engine.reporting.full_abstract_pipeline import resolve_l2_observations

class L6ResolverTests(unittest.TestCase):
 def test_resolves_source_run_retained_observations(self):
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp); source=root/"source"; current=root/"rebuilt"; (source/"artifacts").mkdir(parents=True); (current/"artifacts").mkdir(parents=True)
   (source/"artifacts/l2_retained_observations.jsonl").write_text(json.dumps({"observation_id":"O1"})+"\n")
   (current/"artifacts/runtime_provenance_report.json").write_text(json.dumps({"rebuild_from_run":{"source_run_dir":str(source)}}))
   rows,report=resolve_l2_observations(current)
  self.assertEqual(len(rows),1); self.assertTrue(report["source_run_fallback_used"]); self.assertNotEqual(report["status"],"no_l2_observations_in_run")
if __name__=="__main__": unittest.main()
