import json,tempfile,unittest
from pathlib import Path
from code_engine.validation.reactome_validator import ReactomeValidatorV1
class ReactomeValidatorTests(unittest.TestCase):
 def test_mock_pathway_membership_is_not_causal(self):
  transport=lambda *args:{"results":[{"stId":"R-HSA-1","name":"Runtime pathway","speciesName":"Homo sapiens"}]}
  with tempfile.TemporaryDirectory() as tmp:
   value=ReactomeValidatorV1().run({"pathways":["Runtime pathway"]},tmp,network_enabled=True,transport=transport)
   self.assertEqual("pathway_membership_found",value["interpretation"]);self.assertIn("does not establish causal",value["limitations"][0])
   self.assertEqual("Runtime pathway",json.loads(Path(tmp,"l7_reactome_results.jsonl").read_text())["entity"])
 def test_missing_terms_skips(self):
  with tempfile.TemporaryDirectory() as tmp:self.assertEqual("skipped_no_pathway_terms",ReactomeValidatorV1().run({},tmp)["interpretation"])
if __name__=="__main__":unittest.main()
