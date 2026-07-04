import json,tempfile,unittest
from pathlib import Path
from code_engine.fulltext.discovery_escalation import discovery_escalation_expected,finalize_discovery_escalation,prepare_discovery_escalation

def wj(path,value):path.write_text(json.dumps(value),encoding="utf-8")
def wr(path,rows):path.write_text("".join(json.dumps(x)+"\n" for x in rows),encoding="utf-8")

class FulltextDiscoveryAutomationTests(unittest.TestCase):
 def test_trigger_and_explicit_disable(self):
  self.assertTrue(discovery_escalation_expected(fulltext_enabled=True,network_enabled=True,discovery_mode=True,weak_count=1,escalation_count=0,reviewable_count=0))
  self.assertFalse(discovery_escalation_expected(fulltext_enabled=True,network_enabled=True,discovery_mode=True,weak_count=1,escalation_count=1,reviewable_count=1,explicitly_disabled=True))
  self.assertFalse(discovery_escalation_expected(fulltext_enabled=True,network_enabled=False,discovery_mode=True,weak_count=1,escalation_count=1,reviewable_count=1))
 def _root(self,claims=None,oa=False):
  tmp=tempfile.TemporaryDirectory();root=Path(tmp.name);a=root/"artifacts";a.mkdir()
  seed={"triple_id":"S","subject":{"name":"Mediator-X"},"relation":{"name":"involved_in"},"object":{"name":"disease"},"context":{"context_terms":["migration"]}}
  wj(a/"semantic_search_intent.json",{"seed_triple":seed});wj(a/"search_plan_replay.json",{"enabled":True});wj(a/"intake.json",{"research_intent":{"primary_entities":["Mediator-X"]}})
  candidate={"paper_id":"123","pmid":"123","selection_source":"anchored_reviewable","linked_observation_ids":["O"],"anchor_strength":"strong"}
  wr(a/"fulltext_discovery_escalation_candidates.jsonl",[candidate]);wr(a/"l35_fulltext_candidate_papers.jsonl",[candidate])
  wr(a/"l35_fulltext_retrieval_results.jsonl",[{"paper_id":"123","reason":"not_in_pmc_oa_subset","full_text_status":"unavailable"}] if not oa else [{"paper_id":"123","full_text_status":"available"}])
  wr(a/"l35_fulltext_l1_claims.jsonl",claims or []);wj(a/"l35_fulltext_l1_summary.json",{"sections_selected":2,"chunks_processed":1,"chunks_skipped":0});wr(a/"l35_fulltext_l1_chunks.jsonl",[])
  wj(a/"pipeline_stage_summary.json",{});wj(a/"hypothesis_summary.json",{"formal_hypothesis_count":0});wr(a/"l2_retained_observations.jsonl",[])
  return tmp,root
 def test_no_oa_still_writes_summary_and_nonempty_pipeline(self):
  tmp,root=self._root();self.addCleanup(tmp.cleanup);prepared=prepare_discovery_escalation(root,enabled=True)
  summary=finalize_discovery_escalation(root,prepared=prepared,expected=True,explicitly_disabled=False,shared_summary={},strict_conflict_count=0)
  self.assertEqual(summary["status"],"completed_no_oa");self.assertEqual(summary["skipped_not_oa_count"],1)
  self.assertTrue(summary["fulltext_discovery_executed_when_expected"]);self.assertIn("l35_fulltext_discovery",json.loads((root/"artifacts/pipeline_stage_summary.json").read_text()))
 def test_fulltext_claim_reenters_reviewable_lane_without_formal_hypothesis(self):
  claim={"claim_id":"F1","paper_id":"123","pmid":"123","subject":"Mediator-X","predicate":"promotes","object":"migration","polarity":"positive","evidence_sentence":"Mediator-X promotes migration."}
  tmp,root=self._root([claim],oa=True);self.addCleanup(tmp.cleanup);prepared=prepare_discovery_escalation(root,enabled=True)
  summary=finalize_discovery_escalation(root,prepared=prepared,expected=True,explicitly_disabled=False,shared_summary={"fulltext_confirmed_conflict_count":0},strict_conflict_count=0)
  self.assertEqual(summary["fulltext_claims_reentered_l2"],1);self.assertEqual(summary["fulltext_reviewable_graph_observation_count"],1)
  self.assertEqual(summary["fulltext_hypothesis_candidate_count"],0);self.assertEqual(json.loads((root/"artifacts/hypothesis_summary.json").read_text())["formal_hypothesis_count"],0)
  self.assertTrue((root/"artifacts/l35_fulltext_discovery_observations.jsonl").read_text().strip())
