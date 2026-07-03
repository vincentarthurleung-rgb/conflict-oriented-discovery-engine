import unittest
from code_engine.fulltext.pmc_oa_downloader import download_oa_article
class CopyrightTests(unittest.TestCase):
 def test_non_oa_and_non_official_resource_never_download(self):
  calls=[]; result=download_oa_article({"pmcid":"PMC1"},{"decision":"skip_non_oa"},"/tmp/never",network_enabled=True,transport=lambda u:calls.append(u))
  self.assertEqual(calls,[]); self.assertTrue(result["copyright_safe"])
  result=download_oa_article({"pmcid":"PMC1"},{"decision":"download_allowed","selected_resource":{"format":"jats_xml","url":"https://publisher.example/a.xml"}},"/tmp/never",network_enabled=True,transport=lambda u:calls.append(u))
  self.assertEqual(result["reason"],"non_official_resource_rejected"); self.assertEqual(calls,[])
