"""Automatic discovery-mode L3.5 orchestration around the shared PMC OA stage."""
from __future__ import annotations
import json,shutil
from pathlib import Path
from typing import Any
from code_engine.discovery.lanes import build_weak_candidates,load_policy,score_discovery_records

def _rows(path:Path)->list[dict]:
    try:return [json.loads(x) for x in path.read_text(encoding="utf-8").splitlines() if x.strip()]
    except (OSError,json.JSONDecodeError):return []
def _json(path:Path)->dict:
    try:return json.loads(path.read_text(encoding="utf-8"))
    except (OSError,json.JSONDecodeError):return {}
def _write_json(path:Path,value:Any):path.write_text(json.dumps(value,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
def _write_rows(path:Path,rows:list[dict]):path.write_text("".join(json.dumps(x,ensure_ascii=False)+"\n" for x in rows),encoding="utf-8")

def discovery_escalation_expected(*,fulltext_enabled:bool,network_enabled:bool,discovery_mode:bool,
                                  weak_count:int,escalation_count:int,reviewable_count:int,explicitly_disabled:bool=False)->bool:
    return bool(fulltext_enabled and network_enabled and discovery_mode and not explicitly_disabled and
                (weak_count>0 or escalation_count>0 or reviewable_count>0))

def prepare_discovery_escalation(run_dir:str|Path,*,enabled:bool)->dict[str,Any]:
    artifacts=Path(run_dir)/"artifacts";candidates=_rows(artifacts/"fulltext_discovery_escalation_candidates.jsonl") if enabled else []
    _write_rows(artifacts/"l35_fulltext_discovery_candidate_papers.jsonl",candidates)
    return {"enabled":enabled,"candidate_count":len(candidates),"candidate_ids":{str(x.get("paper_id") or x.get("pmid") or x.get("canonical_paper_id") or "") for x in candidates}}

def _claim_observation(claim:dict)->dict:
    polarity=str(claim.get("polarity") or "").casefold();direction="positive" if polarity=="positive" else "negative" if polarity=="negative" else "unknown"
    return {"observation_id":claim.get("claim_id"),"claim_id":claim.get("claim_id"),"paper_id":claim.get("paper_id") or claim.get("pmid"),
        "pmid":claim.get("pmid"),"pmcid":claim.get("pmcid"),"subject_raw":claim.get("subject") or claim.get("subject_raw"),
        "object_raw":claim.get("object") or claim.get("object_raw"),"relation_raw":claim.get("predicate") or claim.get("relation_raw") or claim.get("relation_family"),
        "relation_family":claim.get("relation_family"),"direction":direction,"evidence_sentence":claim.get("evidence_sentence"),
        "source_scope":"full_text","retained":True,"conflict_reasoning_eligible":False,"strict_core_eligible":False,
        "requires_review":True,"conflict_ineligibility_reasons":["fulltext_discovery_reentry_requires_strict_adjudication"]}

def finalize_discovery_escalation(run_dir:str|Path,*,prepared:dict[str,Any],expected:bool,explicitly_disabled:bool,
                                  shared_summary:dict[str,Any],strict_conflict_count:int=0)->dict[str,Any]:
    artifacts=Path(run_dir)/"artifacts";candidate_ids=prepared.get("candidate_ids",set());enabled=bool(prepared.get("enabled"))
    shared_candidates=_rows(artifacts/"l35_fulltext_candidate_papers.jsonl")
    discovery_candidates=[x for x in shared_candidates if str(x.get("paper_id") or x.get("pmid") or x.get("canonical_paper_id") or "") in candidate_ids]
    if enabled and not discovery_candidates:discovery_candidates=_rows(artifacts/"l35_fulltext_discovery_candidate_papers.jsonl")
    _write_rows(artifacts/"l35_fulltext_discovery_candidate_papers.jsonl",discovery_candidates)
    retrieval=_rows(artifacts/"l35_fulltext_retrieval_results.jsonl")
    discovery_papers={str(x.get("paper_id") or x.get("pmid") or x.get("canonical_paper_id") or "") for x in discovery_candidates}
    discovery_retrieval=[x for x in retrieval if not discovery_papers or str(x.get("paper_id") or x.get("pmid") or x.get("canonical_paper_id") or "") in discovery_papers]
    _write_rows(artifacts/"l35_fulltext_discovery_retrieval_results.jsonl",discovery_retrieval)
    claims=_rows(artifacts/"l35_fulltext_l1_claims.jsonl") if enabled else []
    _write_rows(artifacts/"l35_fulltext_discovery_l1_claims.jsonl",claims)
    raw_observations=[_claim_observation(x) for x in claims];scored=score_discovery_records(run_dir,raw_observations) if raw_observations else []
    neighborhood=[x for x in scored if x.get("seed_neighborhood_score",0)>=load_policy().seed_neighborhood_min_score and not x.get("context_only_match")]
    reviewable=[x for x in neighborhood if x.get("graph_visibility_eligible")];weak=build_weak_candidates(reviewable)
    _write_rows(artifacts/"l35_fulltext_discovery_observations.jsonl",scored)
    l1=_json(artifacts/"l35_fulltext_l1_summary.json");chunks=_rows(artifacts/"l35_fulltext_l1_chunks.jsonl")
    errors=sum(x.get("extraction_status") in {"provider_error","parse_error","blocked"} for x in chunks)
    no_pmcid=sum(x.get("reason")=="no_pmcid" for x in discovery_retrieval);not_oa=sum(x.get("reason")=="not_in_pmc_oa_subset" for x in discovery_retrieval)
    downloaded=sum(x.get("full_text_status")=="available" for x in discovery_retrieval);oa=downloaded
    if not enabled:status="skipped"
    elif shared_summary.get("status")=="completed_no_relevant_oa":status="completed_no_relevant_oa"
    elif not oa:status="completed_no_oa"
    elif not claims:status="completed_no_claims"
    else:status="completed"
    mode="confirmation_and_discovery" if enabled and strict_conflict_count>0 else "discovery_escalation" if enabled else "confirmation" if strict_conflict_count>0 else "skipped"
    warnings=[]
    executed=bool(enabled and (discovery_candidates or status in {"completed_no_oa","completed_no_claims","completed"}))
    if expected and not executed:warnings.append("fulltext_discovery_expected_but_not_executed")
    if len(discovery_candidates)!=prepared.get("candidate_count",0):warnings.append("fulltext_discovery_candidate_count_mismatch")
    summary={"schema_version":"fulltext_discovery_escalation_summary_v1","fulltext_discovery_escalation_enabled":enabled,
        "fulltext_mode":mode,"candidate_paper_count":len(discovery_candidates),"fulltext_discovery_candidate_count":len(discovery_candidates),
        "l35_candidate_paper_count":len(shared_candidates),"oa_available_count":oa,"downloaded_fulltext_count":downloaded,
        "parsed_section_count":int(l1.get("sections_selected",0)),"selected_chunk_count":int(l1.get("chunks_processed",0)),
        "fulltext_l1_claim_count":len(claims),"fulltext_l1_error_count":errors,"skipped_no_pmcid_count":no_pmcid,
        "skipped_not_oa_count":not_oa,"skipped_limit_count":int(l1.get("chunks_skipped",0)),"status":status,"warnings":warnings,
        "scientific_candidate_count":int(shared_summary.get("scientific_candidate_count",len(discovery_candidates))),
        "relevance_passed_candidate_count":int(shared_summary.get("relevance_passed_candidate_count",0)),
        "relevant_oa_candidate_count":int(shared_summary.get("relevant_oa_candidate_count",0)),
        "selected_fulltext_count":int(shared_summary.get("selected_fulltext_count",0)),
        "high_relevance_non_oa_count":int(shared_summary.get("high_relevance_non_oa_count",0)),
        "low_relevance_oa_count":int(shared_summary.get("low_relevance_oa_count",0)),
        "low_relevance_oa_backfill_blocked_count":int(shared_summary.get("low_relevance_oa_backfill_blocked_count",0)),
        "no_relevant_oa":bool(shared_summary.get("no_relevant_oa",False)),
        "fulltext_claims_reentered_l2":len(scored),"fulltext_seed_neighborhood_observation_count":len(neighborhood),
        "fulltext_reviewable_graph_observation_count":len(reviewable),"fulltext_weak_conflict_candidate_count":len(weak),
        "fulltext_strict_conflict_candidate_count":int(shared_summary.get("fulltext_confirmed_conflict_count",0)),
        "fulltext_hypothesis_candidate_count":0,"fulltext_handoff_consistent":not any("count_mismatch" in x for x in warnings),
        "fulltext_discovery_executed_when_expected":not expected or executed,"fulltext_discovery_skip_reason":"explicitly_disabled" if explicitly_disabled else None if enabled else "not_triggered"}
    _write_json(artifacts/"l35_fulltext_discovery_escalation_summary.json",summary)
    _write_json(artifacts/"l35_fulltext_discovery_reentry_summary.json",{k:v for k,v in summary.items() if k.startswith("fulltext_")})
    pipeline=_json(artifacts/"pipeline_stage_summary.json");pipeline.update({"status":pipeline.get("status","completed"),"l35_fulltext_discovery":summary})
    _write_json(artifacts/"pipeline_stage_summary.json",pipeline)
    md=artifacts/"pipeline_stage_summary.md";block="\n## L3.5 Fulltext Discovery Escalation\n\n"+"\n".join(f"- {k}: {v}" for k,v in summary.items())+"\n"
    md.write_text((md.read_text(encoding="utf-8") if md.is_file() else "# Pipeline Stage Summary\n")+block,encoding="utf-8")
    hypothesis=_json(artifacts/"hypothesis_summary.json");hypothesis.update({k:v for k,v in summary.items() if k.startswith("fulltext_")});_write_json(artifacts/"hypothesis_summary.json",hypothesis)
    return summary

__all__=["discovery_escalation_expected","finalize_discovery_escalation","prepare_discovery_escalation"]
