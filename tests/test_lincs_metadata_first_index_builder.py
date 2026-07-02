import tempfile, unittest
from pathlib import Path
from code_engine.external_data.lincs_l1000 import build_compact_lincs_index
from tests.lincs_test_support import tiny_dataset
class IndexTests(unittest.TestCase):
 def test_index_filters_signatures_and_landmarks(self):
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp); m=tiny_dataset(root); value=build_compact_lincs_index(dataset="TEST",data_root=root,manifest_path=m,perturbagen="metformin",landmark_only=True,top_k_genes=1)
  self.assertEqual(value["signature_count"],1); self.assertEqual(value["landmark_gene_count"],2); self.assertFalse(value["full_matrix_loaded"])
if __name__=="__main__": unittest.main()
