import json,tempfile,unittest
from pathlib import Path
from code_engine.validation.pubmed_post_cutoff_validator import PubMedPostCutoffValidator,build_queries

class PubMedPostCutoffTests(unittest.TestCase):
 def test_mocked_search_and_summary_are_presence_only(self):
  def transport(method,url,data,headers):
   if "esearch" in url:return {"esearchresult":{"count":"1","idlist":["7"]}}
   return {"result":{"7":{"title":"A result","pubdate":"2024 Jan","source":"Journal","articleids":[{"idtype":"doi","value":"10.test/x"}]}}}
  with tempfile.TemporaryDirectory() as tmp:
   value=PubMedPostCutoffValidator().run({"search_terms":["signal context"],"time_window":{"post_cutoff_from":2021}},tmp,network_enabled=True,transport=transport)
   self.assertEqual("post_cutoff_literature_found",value["interpretation"]);self.assertNotIn(value["interpretation"],{"supportive","refuting"})
   row=json.loads(Path(tmp,"l7_pubmed_post_cutoff_results.jsonl").read_text());self.assertEqual("7",row["pmid"])
 def test_query_uses_runtime_input(self):
  query=build_queries({"search_terms":["runtime phrase"],"time_window":{"post_cutoff_from":2022}})[0]["query"]
  self.assertIn("runtime phrase",query);self.assertIn("2022",query)
if __name__=="__main__":unittest.main()
