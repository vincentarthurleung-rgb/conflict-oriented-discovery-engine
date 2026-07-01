import json,tempfile,unittest
from pathlib import Path
from code_engine.search.semantic_search_intent import plan_semantic_search_intent

class WrongClient:
    def extract_json(self,prompt,**_):return {"claims":[]}

class SearchDiagnosticTests(unittest.TestCase):
    def test_wrong_schema_has_separate_diagnostics(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(Exception):plan_semantic_search_intent("x",domain_id="general_biomedical",seed_triple={},llm_client=WrongClient(),run_dir=tmp)
            record=json.loads((Path(tmp)/"artifacts/search_intent_parse_errors.jsonl").read_text())
            self.assertEqual(record["stage"],"semantic_search_intent");self.assertEqual(record["error_type"],"search_intent_schema_validation_failed")
            self.assertTrue((Path(tmp)/"artifacts/search_intent_raw_responses").is_dir())

if __name__=="__main__":unittest.main()
