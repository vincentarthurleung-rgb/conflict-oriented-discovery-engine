import json
import tempfile
import unittest
from pathlib import Path

from code_engine.evidence_graph.builders import build_merged_evidence_graph_from_run_artifacts


class TemporalAttachmentTests(unittest.TestCase):
    def test_timeline_attaches_to_graph_conflict(self):
        with tempfile.TemporaryDirectory() as tmp:
            a=Path(tmp)/"artifacts"; a.mkdir()
            obs=[{"observation_id":f"o{i}","paper_id":f"p{i}","subject_canonical_id":"S","object_canonical_id":"O","relation_family":"r","polarity_type":"p","direction":d,"evidence_sentence":"span"} for i,d in enumerate(("increase","decrease"))]
            (a/"l2_abstract_observations.json").write_text(json.dumps({"observations":obs}))
            timeline={"timeline_id":"t","conflict_key":"S|O|r|p","status":"persistent_conflict","conflict_source_window":{"start_year":2010,"end_year":2012},"evidence_timeline":[{"evidence_id":"x","primary_role":"conflict_source","evidence_text":"span"}]}
            (a/"conflict_evidence_timelines.jsonl").write_text(json.dumps(timeline)+"\n")
            result=build_merged_evidence_graph_from_run_artifacts(Path(tmp))
            self.assertGreater(result["summary"]["timeline_attached_to_conflict_rate"],0)
            self.assertTrue(any(e["edge_type"]=="conflict_has_source_window" for e in result["edges"]))


if __name__ == "__main__": unittest.main()
