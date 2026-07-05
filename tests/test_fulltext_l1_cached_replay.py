import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from code_engine.extraction.client_factory import build_l1_client_from_env_or_config,diagnose_l1_provider
from code_engine.fulltext.fulltext_l1_extractor import run_fulltext_l1_extraction


class FakeClient:
    def extract_json(self,prompt,**kwargs):
        return {"claims":[{"subject":"mechanism A","predicate":"increased","object":"target B","polarity":"positive","direction":"positive","context_terms":["condition C"],"evidence_sentence":"Mechanism A increased target B.","confidence":.9}]}


class FulltextL1CachedReplayTests(unittest.TestCase):
    def test_deepseek_diagnostic_does_not_require_openai_key(self):
        with patch.dict(os.environ,{"L1_PROVIDER":"deepseek","MODEL_NAME":"model-x","DEEPSEEK_API_KEY":"secret"},clear=True):
            diagnostic=diagnose_l1_provider(api_enabled=True,network_enabled=True)
            self.assertTrue(diagnostic["provider_available"]);self.assertEqual(diagnostic["credential_name"],"DEEPSEEK_API_KEY")
            self.assertIsNotNone(build_l1_client_from_env_or_config())

    def test_cached_chunks_replay_without_parsed_article(self):
        with tempfile.TemporaryDirectory() as td:
            run=Path(td);artifacts=run/"artifacts";parsed=artifacts/"fulltext/pmc_oa/PMC-X";parsed.mkdir(parents=True)
            candidate={"paper_id":"paper-x","pmid":"PMID-X","pmcid":"PMC-X","title":"Example","selection_score":.8,"abstract_observation_ids":["obs-x"]}
            candidates=artifacts/"l35_fulltext_oa_candidate_papers.jsonl";candidates.write_text(json.dumps(candidate)+"\n")
            article={"sections":[{"section_title":"Results","text":"Mechanism A increased target B."}]};(parsed/"article_text.json").write_text(json.dumps(article))
            first=run_fulltext_l1_extraction(run_dir=run,fulltext_candidates_path=candidates,parsed_articles_dir=artifacts/"fulltext/pmc_oa",l1_provider="deepseek",l1_model="model-x",api_enabled=False,network_enabled=False,max_total_chunks=5)
            self.assertEqual(first["summary"]["fulltext_l1_status"],"skipped_provider_unavailable")
            selected=artifacts/"l35_fulltext_discovery_selected_chunks.jsonl";self.assertTrue(selected.read_text().strip())
            (parsed/"article_text.json").unlink()
            second=run_fulltext_l1_extraction(run_dir=run,fulltext_candidates_path=candidates,parsed_articles_dir=artifacts/"fulltext/pmc_oa",l1_provider="deepseek",l1_model="model-x",api_enabled=True,network_enabled=True,client=FakeClient(),max_total_chunks=5)
            self.assertEqual(second["summary"]["selected_chunk_count"],1);self.assertEqual(second["summary"]["fulltext_l1_attempted_count"],1)
            self.assertEqual(second["summary"]["fulltext_l1_status"],"completed_with_claims")
            claim=second["claims"][0];self.assertEqual(claim["source_scope"],"full_text");self.assertEqual(claim["pmid"],"PMID-X");self.assertEqual(claim["pmcid"],"PMC-X");self.assertEqual(claim["section_title"],"Results")
            records=[json.loads(x) for x in (artifacts/"l35_fulltext_l1_execution_records.jsonl").read_text().splitlines()];self.assertEqual(records[0]["fulltext_l1_status"],"success")


if __name__=="__main__":unittest.main()
