import json,tempfile,unittest
from pathlib import Path
from code_engine.fulltext.fulltext_l1_extractor import chunk_text,run_fulltext_l1_extraction
from tests.test_fulltext_live_l1_adapter import Client,fixture
class ChunkTests(unittest.TestCase):
 def test_hard_limits_recorded(self):
  self.assertGreater(len(chunk_text("x "*100,20)),1)
  with tempfile.TemporaryDirectory() as td:
   run,art=fixture(Path(td)); article=art/"fulltext/pmc_oa/PMC1/article_text.json"; article.write_text(json.dumps({"sections":[{"section_title":"Results","text":"x "*200}]}))
   result=run_fulltext_l1_extraction(run_dir=run,fulltext_candidates_path=art/"candidates.jsonl",parsed_articles_dir=art/"fulltext/pmc_oa",l1_provider="x",l1_model="m",api_enabled=True,network_enabled=True,client=Client(),max_chars_per_chunk=20,max_total_chunks=2)
   self.assertTrue(result["summary"]["limit_hit"]); self.assertEqual(result["summary"]["chunks_planned"],2)
