import json
import tempfile
import unittest
from pathlib import Path

from code_engine.evidence_graph.builders import build_merged_evidence_graph_from_run_artifacts


def observation(identifier, paper, direction, layer, core):
    return {"observation_id": identifier, "claim_id": identifier, "paper_id": paper,
            "canonical_paper_id": paper, "subject_canonical_id": "S", "object_canonical_id": "O",
            "relation_family": "regulation", "polarity_type": "effect", "direction": direction,
            "evidence_sentence": identifier, "graph_layer": layer, "canonical_graph_eligible": core,
            "allow_high_confidence_graph_use": core, "core_context_eligible": core,
            "strong_context_match": core, "query_context_only": not core,
            "context_compatibility_status": "context_matched" if core else "context_unknown"}


class ContextSpecificGraphGateTests(unittest.TestCase):
    def build(self, rows):
        temporary = tempfile.TemporaryDirectory(); self.addCleanup(temporary.cleanup)
        run = Path(temporary.name); artifacts = run / "artifacts"; artifacts.mkdir()
        (artifacts / "runtime_provenance_report.json").write_text(json.dumps(
            {"context_aware_evidence_layering": {"context_specific_run": True}}))
        (artifacts / "l2_abstract_observations.json").write_text(json.dumps(rows))
        return build_merged_evidence_graph_from_run_artifacts(run)

    def test_non_core_opposing_observation_cannot_manufacture_conflict(self):
        result = self.build([observation("O1", "P1", "activate", "core_canonical_graph", True),
                             observation("O2", "P2", "inhibit", "mechanism_layer", False)])
        self.assertEqual(result["summary"]["true_graph_conflict_count"], 0)
        excluded = result["insufficient"][0]["excluded_observation_provenance"]
        self.assertEqual(excluded[0]["observation_id"], "O2")

    def test_true_conflict_has_observation_provenance(self):
        result = self.build([observation("O1", "P1", "activate", "core_canonical_graph", True),
                             observation("O2", "P2", "inhibit", "core_canonical_graph", True)])
        self.assertEqual(result["summary"]["true_graph_conflict_count"], 1)
        conflict = result["conflicts"][0]
        self.assertTrue(conflict["is_true_graph_conflict"])
        self.assertEqual(conflict["qualified_observation_ids"], ["O1", "O2"])
        self.assertEqual(len(conflict["observation_provenance"]), 2)


if __name__ == "__main__": unittest.main()
