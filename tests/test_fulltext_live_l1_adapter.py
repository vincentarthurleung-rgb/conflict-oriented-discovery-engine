import json,tempfile,unittest
from pathlib import Path
from code_engine.fulltext.fulltext_l1_extractor import run_fulltext_l1_extraction
class Client:
 def __init__(self): self.calls=0
 def extract_json(self,prompt,**kwargs): self.calls+=1; return {"claims":[{"subject":"A","predicate":"increases","object":"B","polarity":"positive","relation_family":"regulation","evidence_sentence":"A increases B."}]}
def fixture(root):
 run=root/"run"; art=run/"artifacts"; article=art/"fulltext/pmc_oa/PMC1"; article.mkdir(parents=True)
 candidate={"paper_id":"p","pmid":"1","pmcid":"PMC1","conflict_candidate_ids":["c"],"abstract_observation_ids":["o"]}; (art/"candidates.jsonl").write_text(json.dumps(candidate)+"\n")
 (article/"article_text.json").write_text(json.dumps({"sections":[{"section_title":"Results","text":"A increases B."},{"section_title":"References","text":"Ignored"}]})); return run,art
class LiveAdapterTests(unittest.TestCase):
 def test_mock_existing_client_and_provenance(self):
  with tempfile.TemporaryDirectory() as td:
   run,art=fixture(Path(td)); client=Client(); result=run_fulltext_l1_extraction(run_dir=run,fulltext_candidates_path=art/"candidates.jsonl",parsed_articles_dir=art/"fulltext/pmc_oa",l1_provider="deepseek",l1_model="m",api_enabled=True,network_enabled=True,client=client)
   claim=result["claims"][0]; self.assertEqual(client.calls,1); self.assertEqual(claim["source_scope"],"full_text"); self.assertEqual(claim["pmcid"],"PMC1"); self.assertEqual(claim["section_title"],"Results"); self.assertTrue(claim["chunk_hash"])
