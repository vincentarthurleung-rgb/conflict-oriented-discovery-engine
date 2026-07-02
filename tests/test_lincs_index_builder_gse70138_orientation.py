import gzip,json,tempfile,unittest
from pathlib import Path
import numpy as np
from code_engine.external_data.lincs_l1000 import build_compact_lincs_index
from tests.lincs_test_support import manifest
try: import h5py
except ImportError: h5py=None

@unittest.skipIf(h5py is None,"h5py unavailable")
class BuilderOrientationTests(unittest.TestCase):
 def test_summary_records_detected_axes(self):
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp); m=manifest(root); raw=root/"raw/TEST"; unpacked=root/"working/unpacked/TEST"; raw.mkdir(parents=True); unpacked.mkdir(parents=True)
   with gzip.open(raw/"sig.txt.gz","wt") as f:f.write("sig_id\tpert_iname\tcell_id\nS1\tmetformin\tMCF7\n")
   with gzip.open(raw/"gene.txt.gz","wt") as f:f.write("pr_gene_id\tpr_gene_symbol\tpr_is_lm\nG1\tA\t1\nG2\tB\t1\n")
   for name in ("pert.txt.gz","cell.txt.gz","matrix.gctx.gz"):
    with gzip.open(raw/name,"wb") as f:f.write(b"x")
   with h5py.File(unpacked/"matrix.gctx","w") as h:
    h.create_dataset("0/DATA/0/matrix",data=np.array([[1,2]],dtype=np.float32)); h.create_dataset("0/META/COL/id",data=np.array([b"S1"])); h.create_dataset("0/META/ROW/id",data=np.array([b"G1",b"G2"]))
   value=build_compact_lincs_index(dataset="TEST",data_root=root,manifest_path=m,perturbagen="metformin",landmark_only=True,top_k_genes=1)
  self.assertEqual(value["gctx_signature_axis"],0); self.assertEqual(value["gctx_gene_axis"],1); self.assertEqual(value["compact_values_shape"],[1,2])
if __name__=="__main__": unittest.main()
