import json
import tempfile
import unittest
from pathlib import Path

from code_engine.workflow.orchestrator import run_workflow
from code_engine.workflow.steps import run_mechanism_step
from tests.test_mechanism_edge_builder import observation


class WorkflowMechanismStepTests(unittest.TestCase):
    def test_until_mechanism_dry_run_blocks_without_l2(self):
        with tempfile.TemporaryDirectory() as tmp:
            state = run_workflow("A -> B", run_dir=Path(tmp), until="mechanism")
            self.assertEqual(state.steps["mechanism"].status, "blocked")
            self.assertEqual((state.api_calls_made, state.network_calls_made), (0, 0))

    def test_mocked_l2_builds_run_scoped_graph(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            artifacts = directory / "artifacts"
            artifacts.mkdir()
            (artifacts / "l2_observations.json").write_text(json.dumps([observation()]), encoding="utf-8")
            (artifacts / "domain_profile.json").write_text(json.dumps({"domain_id": "general_biomedical"}), encoding="utf-8")
            result = run_mechanism_step(run_dir=directory, repository_root=Path.cwd(), execute=True)
            self.assertEqual(result.status, "completed")
            self.assertTrue((artifacts / "mechanism_graph.json").exists())
            self.assertEqual(result.counts["mechanism_edge_count"], 1)

    def test_resume_records_mechanism_counts_in_run_state(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            run_workflow("A -> B", run_dir=directory, until="l2", execute=True, allow_uncertain_intake=True)
            (directory / "artifacts/l2_observations.json").write_text(json.dumps([observation()]), encoding="utf-8")
            state = run_workflow(resume=directory, until="mechanism", execute=True, allow_uncertain_intake=True)
            self.assertEqual(state.steps["mechanism"].status, "completed")
            self.assertEqual(state.counts["mechanism_edge_count"], 1)


if __name__ == "__main__": unittest.main()
