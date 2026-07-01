import tempfile,unittest,json
from pathlib import Path
from code_engine.extraction.abstract_screening import run_abstract_l1_screening

class Client:
    def extract_json(self,prompt,**_):return {"not_claims":[]}

class L1ContractTests(unittest.TestCase):
    def test_invalid_root_is_reported_by_l1(self):
        with tempfile.TemporaryDirectory() as tmp:
            result=run_abstract_l1_screening([{"paper_id":"P","abstract":"A"}],{},Path(tmp),execute=True,api_enabled=True,llm_client=Client())
            error=json.loads((Path(tmp)/"abstract_l1_errors.jsonl").read_text())
            self.assertEqual(error["error_type"],"l1_response_missing_claims_root");self.assertEqual(result["summary"]["blocked_reason"],"all_l1_extractions_failed")

if __name__=="__main__":unittest.main()
