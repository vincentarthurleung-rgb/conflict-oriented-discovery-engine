import json
import tempfile
import unittest
from pathlib import Path

from code_engine.normalization.registry import LocalBiomedicalRegistry, PILOT_REGISTRY_PATH
from code_engine.workflow.orchestrator import run_workflow


class ExplicitKetamineRegistryTests(unittest.TestCase):
    def test_explicit_fixture_resolves_pilot_entities(self):
        registry = LocalBiomedicalRegistry(PILOT_REGISTRY_PATH)
        for term in ("ketamine", "BDNF", "mTOR"):
            self.assertTrue(registry.lookup(term, term.casefold()))

    def test_explicit_pilot_profile_is_recorded(self):
        with tempfile.TemporaryDirectory() as tmp:
            run_workflow("ketamine BDNF depression", run_dir=Path(tmp), until="search", pilot_profile="ketamine")
            report = json.loads((Path(tmp) / "artifacts/runtime_provenance_report.json").read_text())
            domain = json.loads((Path(tmp) / "artifacts/domain_profile.json").read_text())
        self.assertEqual(report["pilot_profile"], "ketamine")
        self.assertTrue(report["pilot_terms_used"])
        self.assertIn("ketamine_pilot_registry.json", report["entity_registry_path"])
        self.assertEqual(domain["domain_id"], "neuropharmacology")


if __name__ == "__main__": unittest.main()
