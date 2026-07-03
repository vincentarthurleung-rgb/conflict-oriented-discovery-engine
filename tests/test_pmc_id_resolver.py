import tempfile,unittest
from pathlib import Path
from code_engine.fulltext.pmc_id_resolver import resolve_pmcid
class ResolverTests(unittest.TestCase):
 def test_resolved_no_pmcid_and_cache(self):
  with tempfile.TemporaryDirectory() as td:
   transport=lambda _: {"records":[{"pmcid":"PMC1"}]}; first=resolve_pmcid({"paper_id":"p","pmid":"1"},network_enabled=True,cache_dir=td,transport=transport)
   self.assertEqual(first["pmcid"],"PMC1"); cached=resolve_pmcid({"paper_id":"p","pmid":"1"},cache_dir=td); self.assertEqual(cached["idconv_source"],"cache")
   self.assertEqual(resolve_pmcid({"paper_id":"x"})["idconv_status"],"no_pmcid")
 def test_error_is_recorded(self): self.assertEqual(resolve_pmcid({"pmid":"1"},network_enabled=True,transport=lambda _:1/0)["idconv_status"],"error")
