import tempfile,unittest
from pathlib import Path
from code_engine.validation.production_v1_runner import aggregate_l7
class L7AggregationTests(unittest.TestCase):
 def test_categories_remain_distinct(self):
  results={key:{"status":"completed","interpretation":"found"} for key in ("pubmed_post_cutoff","reactome","enrichr")}
  with tempfile.TemporaryDirectory() as tmp:
   value=aggregate_l7(tmp,results,["chembl"])
   self.assertEqual(list(results),value["executed_validators"]);self.assertFalse(value["semantic_support_refutation_attempted"]);self.assertTrue(Path(tmp,"l7_external_validation_summary.json").is_file())
if __name__=="__main__":unittest.main()
