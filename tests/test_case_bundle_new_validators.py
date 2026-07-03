import unittest
from code_engine.cli.export_case_bundle import ARTIFACTS
class BundleValidatorArtifactsTests(unittest.TestCase):
 def test_all_production_v1_artifacts_exported(self):
  for validator in ("pubmed_post_cutoff","reactome","enrichr"):
   self.assertIn(f"l7_{validator}_summary.json",ARTIFACTS);self.assertIn(f"l7_{validator}_results.jsonl",ARTIFACTS)
if __name__=="__main__":unittest.main()
