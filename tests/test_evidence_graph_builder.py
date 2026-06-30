import json
import tempfile
import unittest
from pathlib import Path

from code_engine.evidence_graph.builders import build_merged_evidence_graph_from_run_artifacts


class EvidenceGraphBuilderTests(unittest.TestCase):
    def test_three_papers_form_one_bundle(self):
        with tempfile.TemporaryDirectory() as tmp:
            artifacts = Path(tmp) / "artifacts"; artifacts.mkdir()
            observations = [{"observation_id":f"o{i}","paper_id":f"p{i}","subject_canonical_id":"ketamine","object_canonical_id":"BDNF","relation_family":"affects","polarity_type":"effect","direction":direction,"evidence_sentence":direction} for i,direction in enumerate(("increase","decrease","no_effect"))]
            (artifacts / "l2_abstract_observations.json").write_text(json.dumps({"observations": observations}))
            result = build_merged_evidence_graph_from_run_artifacts(Path(tmp))
            self.assertEqual(result["summary"]["relation_bundle_count"], 1)
            self.assertEqual(result["summary"]["graph_conflict_candidate_count"], 1)
            self.assertEqual(result["bundles"][0]["paper_count"], 3)


if __name__ == "__main__": unittest.main()
