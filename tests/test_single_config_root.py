import json
import unittest
from pathlib import Path


class SingleConfigRootTests(unittest.TestCase):
    def test_only_canonical_entity_registry_exists(self):
        root = Path(__file__).parents[1]
        payload = json.loads((root / "configs/normalization/entity_registry.json").read_text())
        self.assertFalse((root / "config").exists())
        self.assertEqual(payload["registry_status"], "domain_neutral_empty")
        self.assertEqual(payload["entities"], [])


if __name__ == "__main__": unittest.main()
