import unittest
from code_engine.fulltext.jats_parser import parse_jats
class JatsTests(unittest.TestCase):
 def test_sections_and_reference_exclusion(self):
  doc='<article><front><article-title>T</article-title></front><body><sec><title>Results</title><p>Finding.</p></sec><sec><title>References</title><p>Citation</p></sec></body></article>'
  parsed=parse_jats(doc); self.assertEqual(parsed["sections"][0]["section_title"],"Results"); self.assertEqual(len(parsed["sections"]),1)
