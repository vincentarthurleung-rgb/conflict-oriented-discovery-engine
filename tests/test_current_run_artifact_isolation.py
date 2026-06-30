import json
import tempfile
import unittest
from pathlib import Path

from code_engine.workflow.orchestrator import run_workflow


class CurrentRunIsolationTests(unittest.TestCase):
    def test_hypothesis_timeline_and_graph_ignore_sibling_run_artifacts(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); current=root/"current"; sibling=root/"sibling"
            (sibling/"artifacts").mkdir(parents=True)
            sentinel="SIBLING_RUN_SENTINEL"
            (sibling/"artifacts/l2_abstract_observations.json").write_text(json.dumps([{
                "observation_id":sentinel,"paper_id":"P","subject_canonical_id":"S",
                "object_canonical_id":"O","direction":"increase",
            }]))
            (sibling/"artifacts/graph_conflict_candidates.jsonl").write_text(
                json.dumps({"conflict_id":sentinel,"status":"graph_conflict_candidate"})+"\n"
            )
            run_workflow(
                "ketamine BDNF depression",run_dir=current,until="report",
                enable_conflict_timeline=True,enable_evidence_graph=True,
            )
            for name in (
                "hypothesis_candidates.jsonl", "conflict_evidence_timelines.jsonl",
                "merged_evidence_graph_nodes.jsonl", "merged_evidence_graph_edges.jsonl",
            ):
                self.assertNotIn(sentinel,(current/"artifacts"/name).read_text(),name)


if __name__ == "__main__": unittest.main()
