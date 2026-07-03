import tempfile,unittest
from code_engine.validation.pubmed_post_cutoff_validator import PubMedPostCutoffValidator
class PubMedQualityTests(unittest.TestCase):
 def test_huge_count_is_too_broad_not_support(self):
  def transport(method,url,data,headers):
   return {"esearchresult":{"count":"60000","idlist":[]}} if "esearch" in url else {"result":{}}
  with tempfile.TemporaryDirectory() as tmp:
   value=PubMedPostCutoffValidator().run({"search_terms":["concept one","concept two"]},tmp,network_enabled=True,transport=transport)
   self.assertEqual("too_broad",value["query_quality"]);self.assertIn("post_cutoff_literature_count_not_interpretable",value["broadness_warnings"]);self.assertNotIn(value["interpretation"],{"supportive","refuting"})
if __name__=="__main__":unittest.main()
