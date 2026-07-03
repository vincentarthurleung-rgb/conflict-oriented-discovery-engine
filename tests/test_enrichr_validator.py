import tempfile,unittest
from code_engine.validation.enrichr_validator import EnrichrValidatorV1
class EnrichrValidatorTests(unittest.TestCase):
 def test_mock_enrichment_adjusted_p(self):
  def transport(method,url,data,headers):
   if "addList" in url:return {"userListId":3}
   library=url.split("backgroundType=")[-1];return {library:[[1,"Term",.001,0,12.5,["G1"],.02]]}
  with tempfile.TemporaryDirectory() as tmp:
   value=EnrichrValidatorV1().run({"genes":["G1","G2","G3"]},tmp,network_enabled=True,transport=transport,libraries=["Library"])
   self.assertEqual(1,value["significant_term_count"]);self.assertEqual("enriched_terms_found",value["interpretation"])
 def test_no_gene_set_and_small_set_skip(self):
  with tempfile.TemporaryDirectory() as tmp:
   self.assertEqual("skipped_no_gene_set",EnrichrValidatorV1().run({},tmp)["interpretation"])
   self.assertEqual("gene_set_too_small",EnrichrValidatorV1().run({"genes":["G1"]},tmp)["interpretation"])
if __name__=="__main__":unittest.main()
