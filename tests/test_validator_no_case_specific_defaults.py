import inspect,unittest
from code_engine.validation import pubmed_post_cutoff_validator,reactome_validator,enrichr_validator
class NoSpecificDefaultsTests(unittest.TestCase):
 def test_modules_have_no_known_case_ids(self):
  source="\n".join(inspect.getsource(x) for x in (pubmed_post_cutoff_validator,reactome_validator,enrichr_validator))
  for value in ("metformin_ampk_cancer","autophagy_cancer_chemoresistance"):self.assertNotIn(value,source)
if __name__=="__main__":unittest.main()
