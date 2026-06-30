import json
import tempfile
import unittest
from pathlib import Path

from code_engine.workflow.orchestrator import run_workflow


class NoDefaultPilotTermsTests(unittest.TestCase):
    def test_default_workflow_has_no_pilot_terms(self):
        with tempfile.TemporaryDirectory() as tmp:
            run_workflow("ketamine BDNF depression", run_dir=Path(tmp), until="search")
            report = json.loads((Path(tmp) / "artifacts/runtime_provenance_report.json").read_text())
        self.assertIsNone(report["pilot_profile"])
        self.assertEqual(report["pilot_terms_used"], [])
        self.assertFalse(report["ketamine_specific_defaults_used"])


if __name__ == "__main__": unittest.main()
