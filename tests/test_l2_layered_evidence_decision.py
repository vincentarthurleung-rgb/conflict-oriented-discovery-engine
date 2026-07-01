import tempfile,unittest
from pathlib import Path
from tests.l2_layered_helpers import run_case

class LayerDecisionTests(unittest.TestCase):
    def test_all_expected_layers_exist(self):
        with tempfile.TemporaryDirectory() as tmp:
            summary=run_case(Path(tmp)).summary
            self.assertGreaterEqual(summary["core_canonical_observation_count"],1);self.assertGreaterEqual(summary["mechanism_observation_count"],1);self.assertGreaterEqual(summary["context_observation_count"],1);self.assertGreaterEqual(summary["excluded_observation_count"],1)

if __name__=="__main__":unittest.main()
