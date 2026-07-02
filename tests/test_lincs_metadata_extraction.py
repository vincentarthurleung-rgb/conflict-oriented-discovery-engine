import unittest
from code_engine.external_data.lincs_l1000 import extract_perturbation_metadata

class MetadataTests(unittest.TestCase):
 def test_sig_id_time_fallback(self):
  value=extract_perturbation_metadata({},"REP.A024_A375_24H:P13"); self.assertEqual(value["pert_time"],24); self.assertEqual(value["pert_time_label"],"24H"); self.assertEqual(value["pert_time_source"],"sig_id_fallback")
 def test_explicit_fields_override_fallback(self):
  value=extract_perturbation_metadata({"pert_itime":"6 h","pert_idose":"10 uM"},"X_24H:A"); self.assertEqual(value["pert_time"],6); self.assertEqual(value["pert_dose"],10); self.assertEqual(value["pert_time_source"],"sig_info")
 def test_missing_dose_is_explicit(self):
  value=extract_perturbation_metadata({"pert_idose":"-666"},"X_24H:A"); self.assertIsNone(value["pert_dose"]); self.assertEqual(value["pert_dose_source"],"not_available")
if __name__=="__main__": unittest.main()
