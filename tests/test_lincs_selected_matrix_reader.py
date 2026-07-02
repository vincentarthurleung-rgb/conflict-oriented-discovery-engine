import tempfile,unittest
from pathlib import Path
import numpy as np
from code_engine.external_data.lincs_l1000 import _read_selected_matrix

try: import h5py
except ImportError: h5py=None

@unittest.skipIf(h5py is None,"h5py unavailable")
class ReaderTests(unittest.TestCase):
 def fixture(self,path,signature_first):
  values=np.arange(15,dtype=np.float32).reshape(3,5); matrix=values if signature_first else values.T
  with h5py.File(path,"w") as h:
   h.create_dataset("0/DATA/0/matrix",data=matrix); h.create_dataset("0/META/COL/id",data=np.array([b"S1",b"S2",b"S3"])); h.create_dataset("0/META/ROW/id",data=np.array([b"G1",b"G2",b"G3",b"G4",b"G5"]))
  return values
 def test_both_orientations_normalize_to_signatures_x_genes(self):
  with tempfile.TemporaryDirectory() as tmp:
   for first in (True,False):
    path=Path(tmp)/f"{first}.gctx"; expected=self.fixture(path,first); diagnostics={}; genes,sigs,values=_read_selected_matrix(path,["S3","S1"],{"G2","G5"},diagnostics)
    self.assertEqual(sigs,["S3","S1"]); self.assertEqual(genes,["G2","G5"]); self.assertEqual(values.shape,(2,2)); np.testing.assert_array_equal(values,expected[[2,0]][:,[1,4]])
    self.assertEqual(diagnostics["compact_matrix_orientation"],"signatures_x_genes")
if __name__=="__main__": unittest.main()
