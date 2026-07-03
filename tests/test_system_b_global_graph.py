import tempfile,unittest
from code_engine.system_b.kg.kg_api import KGAPI
from code_engine.system_b.kg.kg_store import KGStore
class GlobalGraphTests(unittest.TestCase):
 def test_global_endpoint_includes_all_cases(self):
  with tempfile.TemporaryDirectory() as tmp:
   KGStore(tmp).write([{"id":"case:a","label":"a","type":"case","aliases":[],"case_ids":["a"],"source_count":1,"metadata":{}},{"id":"case:b","label":"b","type":"case","aliases":[],"case_ids":["b"],"source_count":1,"metadata":{}}],[],[],[])
   status,value=KGAPI(tmp).dispatch("/api/graph/global",{"detail":["summary"]});self.assertEqual(200,status);self.assertEqual(2,len(value["nodes"]))
if __name__=="__main__":unittest.main()
