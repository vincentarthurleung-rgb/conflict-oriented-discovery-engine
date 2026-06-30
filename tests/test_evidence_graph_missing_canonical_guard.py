import json
import tempfile
import unittest
from pathlib import Path

from code_engine.evidence_graph.builders import build_merged_evidence_graph_from_run_artifacts


class MissingCanonicalGuardTests(unittest.TestCase):
    def test_unknown_opposing_edges_never_form_conflict(self):
        with tempfile.TemporaryDirectory() as tmp:
            artifacts=Path(tmp)/"artifacts"; artifacts.mkdir()
            observations=[{"observation_id":"a","paper_id":"P1","relation_family":"affects","polarity_type":"effect","direction":"increase"},{"observation_id":"b","paper_id":"P2","relation_family":"affects","polarity_type":"effect","direction":"decrease"}]
            (artifacts/"l2_abstract_observations.json").write_text(json.dumps(observations))
            result=build_merged_evidence_graph_from_run_artifacts(Path(tmp))
            self.assertEqual(result["summary"]["graph_conflict_candidate_count"],0)
            self.assertEqual(result["summary"]["incomplete_evidence_edge_count"],2)
            self.assertEqual(result["summary"]["excluded_from_bundle_reasoning_count"],2)
            self.assertEqual(result["summary"]["identity_incomplete_conflict_candidate_count"],0)
            self.assertEqual(result["bundles"],[])
            self.assertTrue(all("excluded_from_relation_bundle_reasoning" in edge["warnings"] for edge in result["evidence_edges"]))


if __name__ == "__main__": unittest.main()
