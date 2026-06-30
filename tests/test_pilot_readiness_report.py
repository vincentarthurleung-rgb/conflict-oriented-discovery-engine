import json
import tempfile
import unittest
from pathlib import Path

from code_engine.workflow.orchestrator import run_workflow


class PilotReadinessReportTests(unittest.TestCase):
    def test_real_execute_without_client_is_not_ready(self):
        with tempfile.TemporaryDirectory() as tmp:
            state=run_workflow("ketamine BDNF depression",run_dir=Path(tmp),until="intake",execute=True,api=True,network=True,allow_uncertain_intake=True,l1_mode="abstract_screening",l1_llm_client=None)
            report=json.loads((Path(tmp)/"artifacts/pilot_readiness_report.json").read_text())
            self.assertEqual(report["status"],"not_ready")
            self.assertIn("l1_llm_client_not_configured",report["blocking_reasons"])

    def test_dry_run_is_safe_without_client(self):
        with tempfile.TemporaryDirectory() as tmp:
            run_workflow("ketamine BDNF depression",run_dir=Path(tmp),until="intake")
            report=json.loads((Path(tmp)/"artifacts/pilot_readiness_report.json").read_text())
            self.assertEqual(report["status"],"dry_run_safe")
            self.assertNotEqual(report["legacy_contamination_check"]["status"],"blocked")
            self.assertNotIn("code_engine_import_shadowing",report["blocking_reasons"])


if __name__ == "__main__": unittest.main()
