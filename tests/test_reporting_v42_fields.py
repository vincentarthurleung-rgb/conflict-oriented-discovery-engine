import json
import tempfile
import unittest
from pathlib import Path

from code_engine.graph.probabilistic_conflict import compute_probabilistic_conflict_state
from code_engine.hypothesis.hyperedge_builder import build_hypothesis_hyperedge
from code_engine.reporting.blueprint import build_report_blueprints
from code_engine.reporting.markdown import render_markdown_report


FIXTURE = json.loads((Path(__file__).parent / "fixtures/v42_minimal.json").read_text())


class ReportingV42Tests(unittest.TestCase):
    def test_v42_sections_render_without_overstrong_legacy_status(self):
        hypothesis = dict(FIXTURE["hypothesis"])
        hypothesis["validation_result"] = FIXTURE["validation"]
        hypothesis["validation_status"] = "Passed_By_General_Fallback"
        hypothesis["conflict_edges"] = [dict(FIXTURE["conflict_edge"])]
        hypothesis["probabilistic_conflict_state"] = compute_probabilistic_conflict_state(FIXTURE["conflict_edge"]).model_dump()
        hypothesis["hypothesis_hyperedge"] = build_hypothesis_hyperedge(hypothesis, conflict_edges=hypothesis["conflict_edges"], coverage_verdict="Partial_Coverage_Delta_Update_Recommended").model_dump()
        hypothesis["dry_lab_next_action"] = "run_delta_ingestion_plan"
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "report.md"
            render_markdown_report(build_report_blueprints([hypothesis]), str(path))
            text = path.read_text(encoding="utf-8")
        for heading in ("Evidence Record Summary", "Probabilistic Conflict State", "Hypothesis Hyperedge View", "Bottleneck / Mechanism / Tradeoff", "Coverage status", "Dry-lab next action"):
            self.assertIn(heading, text)
        self.assertNotIn("Passed_By_General_Fallback", text)


if __name__ == "__main__": unittest.main()
