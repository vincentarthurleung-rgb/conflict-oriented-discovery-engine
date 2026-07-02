import json
import unittest
from pathlib import Path


class ValidatorRegistryConfigTests(unittest.TestCase):
    def test_operational_statuses_are_honest(self):
        payload = json.loads(Path("configs/validation/validator_registry.json").read_text())
        specs = {item["validator_id"]: item for item in payload["validators"]}
        self.assertEqual(specs["lincs_l1000"]["status"], "runnable")
        for name in ("reactome", "enrichr", "opentargets", "chembl", "uniprot", "string", "geo", "pubmed_post_cutoff"):
            self.assertNotEqual(specs[name]["status"], "runnable")


if __name__ == "__main__":
    unittest.main()
