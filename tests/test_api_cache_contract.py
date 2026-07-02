import tempfile,unittest
from pathlib import Path
from code_engine.external_data.api_cache import cache_api_response
class CacheTests(unittest.TestCase):
 def test_cache_record_has_provenance_contract(self):
  with tempfile.TemporaryDirectory() as tmp: value=cache_api_response(cache_root=Path(tmp),source="reactome",query="AMPK",response={"ok":True})
  self.assertTrue({"source","query","access_date","response_hash","cached_response_path","status"}<=set(value))
if __name__=="__main__": unittest.main()
