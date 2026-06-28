import tempfile
import unittest
from pathlib import Path

from code_engine.extraction.abstract_screening import run_abstract_l1_screening


class FakeClient:
    def __init__(self): self.calls = 0
    def extract_json(self, prompt, **kwargs):
        self.calls += 1
        return {"claims":[{"subject":"sirolimus","relation_raw":"inhibits","object":"mTOR","evidence_sentence":"Sirolimus inhibits mTOR."}]}


class AbstractL1ScreeningTests(unittest.TestCase):
    def test_execute_fake_and_missing_abstract(self):
        papers=[{"paper_id":"P1","pmid":"1","abstract":"Sirolimus inhibits mTOR."},{"paper_id":"P2","abstract":""}]
        client=FakeClient()
        with tempfile.TemporaryDirectory() as tmp:
            result=run_abstract_l1_screening(papers,{"domain_id":"pathway_biology"},Path(tmp),execute=True,api_enabled=True,llm_client=client)
            self.assertEqual(client.calls,1)
            self.assertEqual(result["claims"][0]["source_scope"],"abstract")
            self.assertEqual(result["claims"][0]["evidence_tier"],"abstract_screening")
            self.assertEqual(result["summary"]["abstract_missing_count"],1)
            self.assertIn("estimated_cost_usd",result["summary"]["budget_report"])

    def test_dry_run_never_calls_client(self):
        client=FakeClient()
        result=run_abstract_l1_screening([{"paper_id":"P1","abstract":"A inhibits B."}],None,None,llm_client=client)
        self.assertEqual(client.calls,0)
        self.assertEqual(result["summary"]["api_calls_made"],0)
        self.assertGreater(result["summary"]["planned_l1_call_count"],0)


if __name__ == "__main__": unittest.main()
