import json,tempfile,unittest
from pathlib import Path
from code_engine.discovery.lanes import build_discovery_lanes,score_discovery_records,synchronize_seed_metadata,validate_fulltext_handoff,validate_seed_metadata

def write_json(path,value):path.write_text(json.dumps(value),encoding="utf-8")
def write_rows(path,rows):path.write_text("".join(json.dumps(x)+"\n" for x in rows),encoding="utf-8")

class DiscoveryL2LaneTests(unittest.TestCase):
 def _run(self):
  tmp=tempfile.TemporaryDirectory();root=Path(tmp.name);a=root/"artifacts";a.mkdir()
  seed={"triple_id":"active","subject":{"name":"Mediator-X"},"relation":{"name":"involved_in"},"object":{"name":"disease"},"context":{"context_terms":["migration","proliferation"]}}
  write_json(a/"semantic_search_intent.json",{"discovery_planning_mode":"neutral_discovery","seed_triple":seed});write_json(a/"search_plan_replay.json",{"enabled":True})
  rows=[
   {"observation_id":"p","paper_id":"P1","subject_raw":"Mediator-X","object_raw":"migration","relation_raw":"promotes","direction":"positive","evidence_sentence":"Mediator-X promotes migration","subject_canonical_id":"LOCAL:s","object_canonical_id":"LOCAL:o","publication_year":None,"retained":True,"conflict_reasoning_eligible":False,"conflict_ineligibility_reasons":["local_canonical_id_requires_review"]},
   {"observation_id":"n","paper_id":"P2","subject_raw":"Mediator-X","object_raw":"migration","relation_raw":"inhibits","direction":"negative","evidence_sentence":"Mediator-X inhibits migration in another context","subject_canonical_id":"LOCAL:s","object_canonical_id":"LOCAL:o","retained":True,"conflict_reasoning_eligible":False,"conflict_ineligibility_reasons":["not_strict_canonical_seed_relation"]},
   {"observation_id":"u","paper_id":"P3","subject_raw":"Mediator-X","object_raw":"proliferation","relation_raw":"associated with","direction":"unknown","evidence_sentence":"Mediator-X is associated with proliferation","retained":True,"conflict_reasoning_eligible":False,"conflict_ineligibility_reasons":["direction_not_conflict_eligible"]},
   {"observation_id":"s","paper_id":"P1","subject_raw":"downstream factor","object_raw":"cell state","relation_raw":"changed","direction":"unknown","evidence_sentence":"A downstream factor changed cell state","retained":True,"conflict_reasoning_eligible":False,"conflict_ineligibility_reasons":["missing_publication_year"]},
   {"observation_id":"c","paper_id":"P4","subject_raw":"disease","object_raw":"unrelated object","relation_raw":"increased","direction":"positive","evidence_sentence":"The disease was associated with an unrelated object","retained":True,"conflict_reasoning_eligible":False,"conflict_ineligibility_reasons":["not_strict_canonical_seed_relation"]}]
  write_rows(a/"l2_retained_observations.jsonl",rows);write_rows(a/"abstract_l1_claims.jsonl",rows);write_rows(a/"l2_core_graph_observations.jsonl",[]);write_rows(a/"graph_conflict_candidates.jsonl",[]);write_json(a/"hypothesis_summary.json",{"formal_hypothesis_count":0,"seed_triple":{"triple_id":"stale"}})
  return tmp,root,build_discovery_lanes(root)
 def test_reviewable_lane_preserves_local_missing_year_unknown_direction(self):
  tmp,root,result=self._run();self.addCleanup(tmp.cleanup)
  review=result["reviewable_graph"];self.assertEqual(len(review),4)
  local=next(x for x in review if x["observation_id"]=="p");self.assertTrue(local["local_canonical_id_used"]);self.assertTrue(local["requires_review"]);self.assertFalse(local["strict_core_eligible"])
  unknown=next(x for x in review if x["observation_id"]=="u");self.assertTrue(unknown["graph_visibility_eligible"]);self.assertFalse(unknown["conflict_reasoning_eligible"])
  same=next(x for x in review if x["observation_id"]=="s");self.assertEqual(same["anchor_type"],"same_paper_seed_anchor");self.assertEqual(same["anchor_strength"],"medium")
  self.assertGreater(result["summary"]["seed_neighborhood_observation_count"],1)
  context=result["low_priority_context"];self.assertEqual(len(context),1);self.assertFalse(context[0]["eligible_for_weak_conflict"]);self.assertFalse(context[0]["eligible_for_fulltext_escalation"])
  self.assertEqual(local["anchor_calibration_version"],"v2");self.assertTrue(local["direct_seed_subject_mention"])
  self.assertGreater(review[0]["review_priority_score"],context[0]["review_priority_score"])
 def test_weak_conflict_triggers_discovery_fulltext_without_hypothesis(self):
  tmp,root,result=self._run();self.addCleanup(tmp.cleanup)
  self.assertEqual(len(result["weak_conflicts"]),1);self.assertGreater(len(result["fulltext_candidates"]),0)
  self.assertEqual(result["summary"]["strict_graph_conflict_count"],0);self.assertEqual(result["summary"]["formal_hypothesis_count"],0)
  self.assertEqual(result["summary"]["fulltext_escalation_mode"],"discovery_escalation")
  weak=result["weak_conflicts"][0]
  for key in ("supporting_observation_ids","opposing_or_contextual_observation_ids","supporting_observations_preview","pmids","evidence_sentences","blocking_reasons_for_strict_conflict"):self.assertIn(key,weak)
  self.assertTrue(result["summary"]["fulltext_handoff_consistent"])
  self.assertTrue((root/"artifacts/l35_fulltext_candidate_papers.jsonl").read_text().strip())
 def test_active_frozen_seed_mismatch_is_detected_and_repaired(self):
  tmp,root,result=self._run();self.addCleanup(tmp.cleanup)
  self.assertFalse(validate_seed_metadata(root)["seed_metadata_consistent"])
  repaired=synchronize_seed_metadata(root);self.assertTrue(repaired["seed_metadata_consistent"])
  summary=json.loads((root/"artifacts/hypothesis_summary.json").read_text());self.assertEqual(summary["seed_triple"]["triple_id"],"active")
 def test_handoff_validator_detects_mismatch_and_calibration_is_written(self):
  tmp,root,result=self._run();self.addCleanup(tmp.cleanup);a=root/"artifacts"
  (a/"l35_fulltext_candidate_papers.jsonl").write_text("")
  self.assertFalse(validate_fulltext_handoff(a)["fulltext_handoff_consistent"])
  calibration=json.loads((a/"discovery_precision_recall_calibration.json").read_text());self.assertIn("context_only_fraction_in_reviewable",calibration)
 def test_greek_symbol_alias_is_a_direct_seed_subject_anchor(self):
  with tempfile.TemporaryDirectory() as td:
   root=Path(td);a=root/"artifacts";a.mkdir();seed={"subject":{"name":"Factor-1alpha"},"object":{"name":"specific pathway"},"context":{}}
   write_json(a/"semantic_search_intent.json",{"seed_triple":seed});write_json(a/"search_plan_replay.json",{"enabled":True});write_json(a/"intake.json",{})
   row={"paper_id":"p","subject_raw":"Factor-1α","object_raw":"target","relation_raw":"activates","direction":"positive","evidence_sentence":"Factor-1α activates target"}
   scored=score_discovery_records(root,[row])[0]
   self.assertEqual(scored["anchor_strength"],"strong");self.assertTrue(scored["direct_seed_subject_mention"])
