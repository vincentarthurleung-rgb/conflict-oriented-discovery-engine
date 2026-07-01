import tempfile,unittest,json
from pathlib import Path
from tests.l2_layered_helpers import run_case

class RegistryArtifactTests(unittest.TestCase):
    def test_run_registry_is_non_curated(self):
        with tempfile.TemporaryDirectory() as tmp:
            run=Path(tmp);run_case(run);value=json.loads((run/"artifacts/run_entity_registry.json").read_text());self.assertFalse(value["curated"]);self.assertGreaterEqual(len(value["entities"]),2)

if __name__=="__main__":unittest.main()
