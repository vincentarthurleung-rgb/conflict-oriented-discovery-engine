import inspect,unittest
from code_engine.normalization import graph_eligibility
class GenericCanonicalizationTests(unittest.TestCase):
 def test_no_known_case_defaults(self):
  source=inspect.getsource(graph_eligibility).casefold()
  for term in ("metformin","ampk","autophagy","becn1","mtor","metformin_ampk_cancer","autophagy_cancer_chemoresistance"):self.assertNotIn(term,source)
if __name__=="__main__":unittest.main()
