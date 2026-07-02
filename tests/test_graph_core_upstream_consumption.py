import json
import tempfile
import unittest
from pathlib import Path

from code_engine.hypothesis.search import run_hypothesis_search_for_run
from code_engine.temporal.io import run_conflict_timeline
from code_engine.workflow.models import STEP_ORDER


class GraphCoreConsumptionTests(unittest.TestCase):
    def test_core_precedes_hypothesis_and_graph_conflict_is_consumed(self):
        self.assertLess(STEP_ORDER.index("evidence_graph_core"),STEP_ORDER.index("hypothesis"))
        with tempfile.TemporaryDirectory() as tmp:
            a=Path(tmp)/"artifacts"; a.mkdir()
            conflict={"graph_conflict_id":"GC","bundle_id":"B","conflict_key":"S|O|r|p","subject_canonical_id":"S","object_canonical_id":"O","relation_family":"r","polarity_type":"p","status":"graph_conflict_candidate","is_true_graph_conflict":True,"observation_provenance":[{"observation_id":"O1"}],"entropy":1.0,"linked_evidence_edge_ids":["E1"],"linked_observation_ids":["O1"]}
            (a/"graph_conflict_candidates.jsonl").write_text(json.dumps(conflict)+"\n")
            result=run_hypothesis_search_for_run({}, {}, {}, Path(tmp))
            self.assertEqual(result["graph_conflict_candidates_used"],1)
            self.assertEqual(result["hypotheses_from_graph_conflicts"],1)
            (a/"l2_abstract_observations.json").write_text(json.dumps([{"observation_id":"O1","evidence_id":"E1","paper_id":"P1","publication_year":2020,"subject_canonical_id":"S","object_canonical_id":"O","relation_family":"r","polarity_type":"p","direction":"increase"}]))
            timeline=run_conflict_timeline(Path(tmp),min_conflict_papers=1)
            self.assertEqual(timeline["graph_conflict_candidates_used"],1)
            self.assertEqual(timeline["timelines_from_graph_conflicts"],1)


if __name__ == "__main__": unittest.main()
