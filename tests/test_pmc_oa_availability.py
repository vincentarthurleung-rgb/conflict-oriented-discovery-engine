import unittest
from code_engine.fulltext.pmc_oa_client import check_oa_availability
class OATests(unittest.TestCase):
 def test_oa_and_non_oa_decisions(self):
  oa=b'<OA><records><record license="CC BY"><link format="xml" href="https://pmc.ncbi.nlm.nih.gov/a.xml"/></record></records></OA>'
  self.assertEqual(check_oa_availability("PMC1",network_enabled=True,transport=lambda _:oa)["decision"],"download_allowed")
  non=b'<OA><error code="idIsNotOpenAccess">not OA</error></OA>'
  self.assertEqual(check_oa_availability("PMC2",network_enabled=True,transport=lambda _:non)["decision"],"skip_non_oa")
