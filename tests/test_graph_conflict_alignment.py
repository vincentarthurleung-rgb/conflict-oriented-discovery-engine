import json
import tempfile
import unittest
from pathlib import Path

from code_engine.evidence_graph.builders import build_merged_evidence_graph_from_run_artifacts


class AlignmentTests(unittest.TestCase):
    def test_existing_conflict_matches_graph_key(self):
        with tempfile.TemporaryDirectory() as tmp:
            a=Path(tmp)/"artifacts"; a.mkdir()
            obs=[{"observation_id":f"o{i}","paper_id":f"p{i}","subject_canonical_id":"S","object_canonical_id":"O","relation_family":"r","polarity_type":"p","direction":d} for i,d in enumerate(("increase","decrease"))]
            (a/"l2_abstract_observations.json").write_text(json.dumps({"observations":obs}))
            (a/"abstract_conflict_candidates.jsonl").write_text(json.dumps({"candidate_id":"c","subject_canonical_id":"S","object_canonical_id":"O","relation_family":"r","polarity_type":"p"})+"\n")
            result=build_merged_evidence_graph_from_run_artifacts(Path(tmp))
            self.assertEqual(result["summary"]["matched_existing_conflict_count"],1)


if __name__ == "__main__": unittest.main()
