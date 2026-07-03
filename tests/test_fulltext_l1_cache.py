import tempfile,unittest
from pathlib import Path
from code_engine.fulltext.fulltext_l1_extractor import run_fulltext_l1_extraction
from tests.test_fulltext_live_l1_adapter import Client,fixture
class CacheTests(unittest.TestCase):
 def test_hit_avoids_provider(self):
  with tempfile.TemporaryDirectory() as td:
   run,art=fixture(Path(td)); first=Client(); args=dict(run_dir=run,fulltext_candidates_path=art/"candidates.jsonl",parsed_articles_dir=art/"fulltext/pmc_oa",l1_provider="x",l1_model="m",api_enabled=True,network_enabled=True)
   run_fulltext_l1_extraction(**args,client=first); second=Client(); result=run_fulltext_l1_extraction(**args,client=second)
   self.assertEqual(second.calls,0); self.assertEqual(result["summary"]["cache_hits"],1)
