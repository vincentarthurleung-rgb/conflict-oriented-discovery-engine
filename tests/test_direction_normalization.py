import unittest
from code_engine.normalization.graph_eligibility import normalize_direction
class DirectionNormalizationTests(unittest.TestCase):
 def test_safe_mappings(self):
  for phrase,want in (("strongly increased","positive"),("suppressed activity","negative"),("associated with outcome","associative"),("context-dependent dual role","context_dependent")):self.assertEqual(want,normalize_direction(phrase)["direction"])
 def test_ambiguous_remains_unknown(self):self.assertEqual("unknown",normalize_direction("plays a role in")["direction"])
if __name__=="__main__":unittest.main()
