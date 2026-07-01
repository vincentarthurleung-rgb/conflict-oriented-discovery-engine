import tempfile,unittest
from pathlib import Path
from tests.l2_layered_helpers import run_case

class EmptyRegistryTests(unittest.TestCase):
    def test_seed_claim_is_core_without_curated_registry(self):
        with tempfile.TemporaryDirectory() as tmp:
            result=run_case(Path(tmp));self.assertGreaterEqual(result.summary["core_canonical_observation_count"],1);self.assertTrue(result.summary["runtime_entity_hints_used"])

if __name__=="__main__":unittest.main()
