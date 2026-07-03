import unittest
from code_engine.validation.readiness import load_external_registry
class RegistryTests(unittest.TestCase):
    def test_production_status_is_honest(self):
        r=load_external_registry(); self.assertTrue(r["lincs_l1000"]["runnable_now"]); self.assertEqual(r["chembl"]["status"],"local_fixture_only")
        for name in ("pubmed_post_cutoff","reactome","enrichr"): self.assertTrue(r[name]["runnable_now"])
