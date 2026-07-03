import unittest
from code_engine.normalization.graph_eligibility import local_canonical_id
class LocalCanonicalIdTests(unittest.TestCase):
 def test_stable_meaningful_local_id(self):
  a=local_canonical_id("Specific cellular response","biological_process");b=local_canonical_id("Specific cellular response","process");self.assertEqual(a["canonical_id"],b["canonical_id"]);self.assertTrue(a["requires_review"])
 def test_generic_noise_is_not_canonicalized(self):
  for text in ("effect","role","study","cells"):self.assertIsNone(local_canonical_id(text,"biological_process"))
if __name__=="__main__":unittest.main()
