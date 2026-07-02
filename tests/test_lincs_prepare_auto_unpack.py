import tempfile, unittest
from pathlib import Path
from code_engine.external_data.lincs_l1000 import prepare_lincs_dataset
from tests.lincs_test_support import tiny_dataset
class PrepareTests(unittest.TestCase):
 def test_streaming_unpack_preserves_raw(self):
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp); m=tiny_dataset(root); (root/"working/unpacked/TEST/matrix.gctx").unlink(); value=prepare_lincs_dataset(dataset="TEST",data_root=root,manifest_path=m,unpack=True)
  self.assertTrue(value["required_files_present"]); self.assertTrue(value["unpacked_gctx_present"])
if __name__=="__main__": unittest.main()
