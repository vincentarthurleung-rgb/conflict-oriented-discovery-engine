import tempfile
import unittest
from pathlib import Path

from code_engine.extraction.progressive_l1 import run_fulltext_evidence_l1


class FakeClient:
    def __init__(self): self.calls=0
    def extract_json(self,prompt,**kwargs):
        self.calls+=1
        return {"claims":[{"subject":"sirolimus","relation_raw":"inhibits","object":"mTOR","evidence_sentence":"Sirolimus inhibited mTOR in mouse cells.","context":{"species":"mouse"}}]}


class FulltextEvidenceL1Tests(unittest.TestCase):
    def test_traceability_dry_run_and_cache(self):
        span={"span_id":"S1","paper_id":"P1","section_id":"R1","section_type":"results","source_scope":"full_text","text":"Sirolimus inhibited mTOR in mouse cells.","conflict_candidate_ids":["C1"]}
        candidate={"candidate_id":"C1","claim_ids":["A1"]}
        client=FakeClient()
        dry=run_fulltext_evidence_l1([span],[candidate],{},None,llm_client=client)
        self.assertEqual(client.calls,0)
        self.assertEqual(dry["summary"]["api_calls_made"],0)
        with tempfile.TemporaryDirectory() as tmp:
            first=run_fulltext_evidence_l1([span],[candidate],{},Path(tmp),execute=True,api_enabled=True,llm_client=client)
            second=run_fulltext_evidence_l1([span],[candidate],{},Path(tmp),execute=True,api_enabled=True,llm_client=client)
            record=first["evidence_records"][0]
            self.assertEqual(record["source_scope"],"full_text")
            self.assertEqual(record["linked_abstract_claim_ids"],["A1"])
            self.assertEqual(record["linked_conflict_candidate_ids"],["C1"])
            self.assertEqual(client.calls,1)
            self.assertEqual(second["summary"]["cache_hit_count"],1)


if __name__ == "__main__": unittest.main()
