import gzip,json,tempfile,unittest
from pathlib import Path
from code_engine.external_data.lincs_l1000 import build_compact_lincs_index
from tests.lincs_test_support import tiny_dataset

class MetricsTests(unittest.TestCase):
 def test_metrics_join_populates_quality(self):
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp); manifest_path=tiny_dataset(root); manifest=json.loads(manifest_path.read_text()); manifest["files"].append({"role":"sig_metrics","filename":"metrics.txt.gz","required":False,"unpack":False}); manifest_path.write_text(json.dumps(manifest))
   with gzip.open(root/"raw/TEST/metrics.txt.gz","wt") as f:f.write("sig_id\tdistil_cc_q75\tdistil_ss\ttas\nS1\t0.8\t5.0\t0.7\n")
   build_compact_lincs_index(dataset="TEST",data_root=root,manifest_path=manifest_path,perturbagen="metformin",landmark_only=True,top_k_genes=1)
   row=json.loads((root/"index/TEST/metformin_top_genes.jsonl").read_text().splitlines()[0])
  self.assertTrue(row["signature_quality"]["sig_metrics_available"]); self.assertEqual(row["signature_quality"]["tas"],"0.7")
 def test_missing_metrics_is_nonfatal(self):
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp); manifest_path=tiny_dataset(root); build_compact_lincs_index(dataset="TEST",data_root=root,manifest_path=manifest_path,perturbagen="metformin",landmark_only=True,top_k_genes=1); row=json.loads((root/"index/TEST/metformin_top_genes.jsonl").read_text().splitlines()[0])
  self.assertFalse(row["signature_quality"]["sig_metrics_available"])
if __name__=="__main__": unittest.main()
