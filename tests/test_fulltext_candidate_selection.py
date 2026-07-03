import json,tempfile,unittest
from pathlib import Path
from code_engine.fulltext.candidate_selection import select_conflict_related_papers
class CandidateSelectionTests(unittest.TestCase):
 def test_only_conflict_related_selected(self):
  with tempfile.TemporaryDirectory() as td:
   root=Path(td); (root/"graph_conflict_candidates.jsonl").write_text(json.dumps({"candidate_id":"c1","is_true_graph_conflict":True,"paper_ids":["P1"]})+"\n"+json.dumps({"candidate_id":"c2","is_true_graph_conflict":False,"paper_ids":["P2"]})+"\n")
   result=select_conflict_related_papers(root)
   self.assertEqual([x["paper_id"] for x in result["candidate_papers"]],["P1"])
 def test_no_candidates_is_completed(self):
  with tempfile.TemporaryDirectory() as td: self.assertEqual(select_conflict_related_papers(td)["status"],"completed_no_candidates")
