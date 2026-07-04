import json,tempfile,unittest
from pathlib import Path
from code_engine.fulltext.candidate_selection import select_conflict_related_papers

class FulltextDiscoveryHandoffTests(unittest.TestCase):
 def test_discovery_candidates_are_consumed_without_strict_conflict(self):
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp);row={"paper_id":"P1","pmid":"123","selection_source":"anchored_reviewable","selection_score":.9,"linked_observation_ids":["O1"],"fulltext_discovery_mode":True}
   (root/"fulltext_discovery_escalation_candidates.jsonl").write_text(json.dumps(row)+"\n")
   result=select_conflict_related_papers(root,max_papers=20)
   self.assertEqual(result["candidate_paper_count"],1);self.assertTrue(result["candidate_papers"][0]["fulltext_discovery_mode"])
