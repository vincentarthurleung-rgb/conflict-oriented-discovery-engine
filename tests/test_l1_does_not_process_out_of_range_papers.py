import unittest
from code_engine.extraction.abstract_screening import run_abstract_l1_screening

class Client:
    def __init__(self): self.calls = 0
    def extract_json(self, prompt, **_): self.calls += 1; return {"claims": []}

class L1YearGuardTests(unittest.TestCase):
    def test_only_in_range_paper_reaches_client(self):
        client = Client()
        papers = [{"paper_id": "old", "publication_year": 2015, "abstract": "A"}, {"paper_id": "ok", "publication_year": 2018, "abstract": "B"}, {"paper_id": "new", "publication_year": 2021, "abstract": "C"}]
        result = run_abstract_l1_screening(papers, {}, None, execute=True, api_enabled=True, llm_client=client,
                                           paper_year_filter={"paper_year_from": 2016, "paper_year_to": 2020})
        self.assertEqual(client.calls, 1)
        self.assertEqual(result["summary"]["papers_excluded_by_year_filter"], 2)
        self.assertTrue(result["summary"]["temporal_filter_violation_detected"])

if __name__ == "__main__": unittest.main()
