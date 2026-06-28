import json
import unittest
from pathlib import Path

from code_engine.domain.models import default_domain_profiles
from code_engine.normalization.registry import DEFAULT_REGISTRY_PATH, PILOT_REGISTRY_PATH


class LegacyRegistryCleanupTests(unittest.TestCase):
    def test_pilot_is_fixture_and_default_is_stub(self):
        stub=json.loads(DEFAULT_REGISTRY_PATH.read_text())
        pilot=json.loads(PILOT_REGISTRY_PATH.read_text())
        self.assertTrue(stub["do_not_use_as_production_general_registry"])
        self.assertEqual(stub["replacement"], "EntityResolutionHub")
        self.assertEqual(pilot["registry_status"], "pilot_fixture_only")
        self.assertTrue(all("_registry" not in profile.entity_registry_profile for profile in default_domain_profiles()))

    def test_type_rules_are_absent(self):
        import code_engine.normalization.entity_type as module
        self.assertFalse(hasattr(module, "TYPE_RULES"))


if __name__ == "__main__": unittest.main()
