import json, unittest
from pathlib import Path
from code_engine.external_data.lincs_l1000 import load_lincs_manifest
class ManifestTests(unittest.TestCase):
 def test_repository_manifest_has_required_phase_one_roles(self):
  value=load_lincs_manifest(Path("configs/external_data/lincs_l1000_gse70138_manifest.json")); roles={x["role"] for x in value["files"] if x["required"]}
  self.assertEqual(value["dataset_id"],"GSE70138"); self.assertTrue({"level5_matrix","gene_info","sig_info","pert_info","cell_info"}<=roles)
if __name__=="__main__": unittest.main()
