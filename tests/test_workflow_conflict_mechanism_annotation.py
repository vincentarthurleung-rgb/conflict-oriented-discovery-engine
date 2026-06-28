import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from code_engine.mechanism.graph_builder import build_mechanism_graph
from code_engine.mechanism.io import save_mechanism_graph
from code_engine.workflow.steps import run_conflict_step
from tests.test_mechanism_edge_builder import observation


class WorkflowConflictMechanismTests(unittest.TestCase):
    def test_conflict_step_updates_mechanism_artifact(self):
        obs = observation()
        conflict = {"edge_id": "c1", "subject_canonical_id": "CHEM:A", "object_canonical_id": "GENE:B", "conflict_type": "Type III", "conflict_status": "conflicting", "entropy": 1.0}
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp); artifacts = directory / "artifacts"; artifacts.mkdir()
            (artifacts / "l2_observations.json").write_text(json.dumps([obs]), encoding="utf-8")
            save_mechanism_graph(build_mechanism_graph([obs]), artifacts / "mechanism_graph.json")
            with patch("code_engine.graph.conflict_discovery.build_conflict_graph", return_value=([], [conflict], [], {"skipped_low_confidence_observation_count": 0})):
                result = run_conflict_step(run_dir=directory, execute=True)
            self.assertEqual(result.counts["mechanism_conflict_annotation_count"], 1)
            self.assertTrue((artifacts / "mechanism_graph_annotated.json").exists())
            annotations = json.loads((artifacts / "mechanism_conflict_annotations.json").read_text(encoding="utf-8"))
            self.assertEqual(annotations[0]["conflict_type"], "Type III")


if __name__ == "__main__": unittest.main()
