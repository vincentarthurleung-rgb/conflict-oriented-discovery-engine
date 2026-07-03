import tempfile,unittest
from code_engine.validation.reactome_validator import ReactomeValidatorV1
class ReactomeSemanticsTests(unittest.TestCase):
 def test_reachable_no_mapping_is_completed(self):
  with tempfile.TemporaryDirectory() as tmp:
   value=ReactomeValidatorV1().run({"genes":["GENE1"]},tmp,network_enabled=True,transport=lambda *args:{"results":[]})
   self.assertEqual("completed_no_mapping",value["status"]);self.assertTrue(value["api_reachable"]);self.assertEqual("no_mapping",value["mapping_status"])
if __name__=="__main__":unittest.main()
