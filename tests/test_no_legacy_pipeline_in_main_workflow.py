import json
import sys
import tempfile
import unittest
from pathlib import Path

import code_engine.workflow.steps
import code_engine.hypothesis.search

from code_engine.workflow.orchestrator import run_workflow


class LegacyPipelineIsolationTests(unittest.TestCase):
    def test_importing_main_modules_does_not_import_legacy_stage6(self):
        self.assertNotIn("src.pipelines.stage6_l4_beam_search", sys.modules)

    def test_main_workflow_does_not_import_legacy_stage6(self):
        with tempfile.TemporaryDirectory() as tmp:
            run_workflow("ketamine BDNF depression",run_dir=Path(tmp),until="hypothesis")
            report=json.loads((Path(tmp)/"artifacts/runtime_provenance_report.json").read_text())
            self.assertNotIn("src.pipelines.stage6_l4_beam_search",report["legacy_modules_imported"])
            self.assertFalse(report["import_shadowing_risk"])


if __name__ == "__main__": unittest.main()
