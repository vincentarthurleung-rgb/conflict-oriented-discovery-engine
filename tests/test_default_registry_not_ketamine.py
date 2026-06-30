import json
import tempfile
import unittest
from pathlib import Path

from code_engine.workflow.orchestrator import run_workflow


class DefaultRegistryTests(unittest.TestCase):
    def test_default_registry_is_domain_neutral(self):
        with tempfile.TemporaryDirectory() as tmp:
            run_workflow("metformin AMPK cancer", run_dir=Path(tmp), until="intake")
            report = json.loads((Path(tmp) / "artifacts/runtime_provenance_report.json").read_text())
        self.assertNotIn("ketamine_pilot", report["entity_registry_path"])
        self.assertTrue(report["entity_registry_path"].endswith("configs/normalization/entity_registry.json"))


if __name__ == "__main__": unittest.main()
