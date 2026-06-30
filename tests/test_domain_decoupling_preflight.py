import json
import tempfile
import unittest
from pathlib import Path

from code_engine.workflow.orchestrator import run_workflow
from code_engine.workflow.runtime_provenance import contamination_check


class DomainDecouplingPreflightTests(unittest.TestCase):
    def test_forbidden_automatic_pilot_default_blocks(self):
        result = contamination_check({"ketamine_specific_defaults_used": True, "warnings": []})
        self.assertIn("ketamine_specific_defaults_used", result["blocking_reasons"])

    def test_default_readiness_check_passes(self):
        with tempfile.TemporaryDirectory() as tmp:
            run_workflow("metformin AMPK cancer", run_dir=Path(tmp), until="intake")
            report = json.loads((Path(tmp) / "artifacts/pilot_readiness_report.json").read_text())
        self.assertEqual(report["domain_decoupling_check"]["status"], "pass")
        self.assertFalse(report["domain_decoupling_check"]["ketamine_specific_defaults_used"])


if __name__ == "__main__": unittest.main()
