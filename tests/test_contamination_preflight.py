import unittest

from code_engine.workflow.runtime_provenance import contamination_check


class ContaminationPreflightTests(unittest.TestCase):
    def test_shadowing_and_unapproved_history_are_blocking(self):
        result=contamination_check({"import_shadowing_risk":True,"legacy_modules_imported":[],"historical_runs_read":True,"resume_explicit":False,"global_evidence_injected_before_reasoning":False,"warnings":[]})
        self.assertEqual(result["status"],"blocked")
        self.assertIn("code_engine_import_shadowing",result["blocking_reasons"])
        self.assertIn("historical_runs_read_without_explicit_resume",result["blocking_reasons"])


if __name__ == "__main__": unittest.main()
