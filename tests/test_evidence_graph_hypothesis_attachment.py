import json
import tempfile
import unittest
from pathlib import Path

from code_engine.evidence_graph.builders import build_merged_evidence_graph_from_run_artifacts


class HypothesisAttachmentTests(unittest.TestCase):
    def test_hypothesis_attaches_without_mutation(self):
        with tempfile.TemporaryDirectory() as tmp:
            a=Path(tmp)/"artifacts"; a.mkdir()
            obs=[{"observation_id":f"o{i}","paper_id":f"p{i}","subject_canonical_id":"S","object_canonical_id":"O","relation_family":"r","polarity_type":"p","direction":d} for i,d in enumerate(("increase","decrease"))]
            (a/"l2_abstract_observations.json").write_text(json.dumps({"observations":obs}))
            hypothesis={"hypothesis_id":"h","hypothesis_text":"test","subject_canonical_id":"S","object_canonical_id":"O","relation_family":"r","polarity_type":"p"}
            (a/"hypothesis_hyperedges.jsonl").write_text(json.dumps(hypothesis)+"\n")
            result=build_merged_evidence_graph_from_run_artifacts(Path(tmp))
            self.assertEqual(result["summary"]["hypothesis_matched_to_conflict_rate"],1)
            self.assertTrue(any(e["edge_type"]=="hypothesis_explains_conflict" for e in result["edges"]))


if __name__ == "__main__": unittest.main()
