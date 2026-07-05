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
    records=_rows(artifacts/"l35_fulltext_discovery_execution_records.jsonl") if enabled else []
    errors=sum(x.get("extraction_status") in {"provider_error","parse_error","blocked"} for x in chunks)
    no_pmcid=sum(x.get("reason")=="no_pmcid" for x in discovery_retrieval);not_oa=sum(x.get("reason")=="not_in_pmc_oa_subset" for x in discovery_retrieval)
    selected=sum(bool(x.get("selected_for_fulltext_l1")) for x in records)
    oa=sum(bool(x.get("oa_available")) for x in records)
    downloaded=sum(x.get("download_status")=="success" for x in records)
    download_attempted=sum(bool(x.get("download_attempted")) for x in records)
    parse_attempted=sum(bool(x.get("parse_attempted")) for x in records)
    l1_attempted=int(l1.get("fulltext_l1_attempted_count",sum(bool(x.get("fulltext_l1_attempted")) for x in records)) or 0)
    parsed_sections=sum(int(x.get("parsed_section_count",0) or 0) for x in records)
    selected_chunks=int(l1.get("selected_chunk_count",sum(int(x.get("selected_chunk_count",0) or 0) for x in records)) or 0)
    record_claims=sum(int(x.get("fulltext_l1_claim_count",0) or 0) for x in records)
    relevant_oa=int(shared_summary.get("relevant_oa_candidate_count",oa))
    selected_without_attempt=sum(bool(x.get("oa_available")) and not x.get("download_attempted") for x in records)
    archive_downloaded=sum(bool(x.get("archive_downloaded")) for x in records);archive_extracted=sum(bool(x.get("archive_extracted")) for x in records)
    xml_selected=sum(bool(x.get("selected_xml_file")) for x in records)
    unsupported_pdf=sum(x.get("blocking_reason")=="only_pdf_resources_available" for x in records)
    archive_no_xml=sum(x.get("blocking_reason")=="archive_contains_no_xml" for x in records)
    xml_parse_failed=sum(x.get("blocking_reason") in {"xml_parse_failed","jats_parse_failed"} for x in records)
    consistency=[]
    if selected!=int(shared_summary.get("selected_fulltext_count",selected)):consistency.append("selected_fulltext_count_mismatch")
    if downloaded!=sum(x.get("download_status")=="success" for x in records):consistency.append("downloaded_fulltext_count_mismatch")
    if record_claims!=len(claims):consistency.append("fulltext_l1_claim_count_mismatch")
    if selected_without_attempt:consistency.append("selected_oa_without_download_attempt")
    if selected and not download_attempted:consistency.append("selected_fulltext_without_any_download_attempt")
    if not enabled:status="skipped"
    elif not relevant_oa and not selected:status="completed_no_relevant_oa"
    elif selected_without_attempt or (selected and not download_attempted):status="completed_oa_selected_no_download"
    elif records and all(x.get("blocking_reason") in {"only_pdf_resources_available","oa_links_present_but_unsupported_types","bioc_xml_parser_unavailable","no_supported_oa_download_resource"} for x in records):status="completed_unsupported_resources"
    elif downloaded==0:status="completed_download_failed"
    elif parse_attempted and parsed_sections==0:status="completed_parse_failed"
    elif selected_chunks==0:status="completed_no_usable_sections"
    elif any(x.get("fulltext_l1_status")=="failed" for x in records):status="partially_completed"
    elif record_claims==0:status="completed_no_claims"
    elif any(x.get("final_status")=="failed" for x in records):status="partially_completed"
    else:status="completed_with_claims"
    mode="confirmation_and_discovery" if enabled and strict_conflict_count>0 else "discovery_escalation" if enabled else "confirmation" if strict_conflict_count>0 else "skipped"
    warnings=list(consistency)
    executed=bool(enabled and (discovery_candidates or status not in {"skipped"}))
    if expected and not executed:warnings.append("fulltext_discovery_expected_but_not_executed")
    if len(discovery_candidates)!=prepared.get("candidate_count",0):warnings.append("fulltext_discovery_candidate_count_mismatch")
    summary={"schema_version":"fulltext_discovery_escalation_summary_v1","fulltext_discovery_escalation_enabled":enabled,
        "fulltext_mode":mode,"candidate_paper_count":len(discovery_candidates),"fulltext_discovery_candidate_count":len(discovery_candidates),
        "l35_candidate_paper_count":len(shared_candidates),"oa_available_count":oa,"discovery_oa_available_count":oa,"downloaded_fulltext_count":downloaded,
        "parsed_section_count":parsed_sections,"selected_chunk_count":selected_chunks,
        "fulltext_l1_claim_count":record_claims,"fulltext_l1_error_count":errors,"skipped_no_pmcid_count":no_pmcid,
        "fulltext_l1_status":l1.get("fulltext_l1_status"),"fulltext_l1_success_count":int(l1.get("fulltext_l1_success_count",0) or 0),
        "fulltext_l1_failed_count":int(l1.get("fulltext_l1_failed_count",0) or 0),"fulltext_l1_skipped_count":int(l1.get("fulltext_l1_skipped_count",0) or 0),
        "fulltext_l1_provider":l1.get("fulltext_l1_provider"),"fulltext_l1_model":l1.get("fulltext_l1_model"),"provider_available":l1.get("provider_available"),
        "skipped_not_oa_count":not_oa,"skipped_limit_count":int(l1.get("chunks_skipped",0)),"status":status,"warnings":warnings,
        "scientific_candidate_count":int(shared_summary.get("scientific_candidate_count",len(discovery_candidates))),
        "relevance_passed_candidate_count":int(shared_summary.get("relevance_passed_candidate_count",0)),
        "relevant_oa_candidate_count":relevant_oa,"selected_fulltext_count":selected,
        "download_attempted_count":download_attempted,"parse_attempted_count":parse_attempted,
        "fulltext_l1_attempted_count":l1_attempted,"selected_oa_without_download_attempt_count":selected_without_attempt,
        "fulltext_execution_consistent":not consistency,"fulltext_execution_consistency_warnings":consistency,
        "resource_diagnostics_count":len(_rows(artifacts/"l35_fulltext_oa_resource_diagnostics.jsonl")),
        "archive_downloaded_count":archive_downloaded,"archive_extracted_count":archive_extracted,"xml_file_selected_count":xml_selected,
        "unsupported_pdf_only_count":unsupported_pdf,"archive_contains_no_xml_count":archive_no_xml,"xml_parse_failed_count":xml_parse_failed,
        "high_relevance_non_oa_count":int(shared_summary.get("high_relevance_non_oa_count",0)),
        "low_relevance_oa_count":int(shared_summary.get("low_relevance_oa_count",0)),
        "low_relevance_oa_backfill_blocked_count":int(shared_summary.get("low_relevance_oa_backfill_blocked_count",0)),
        "no_relevant_oa":bool(shared_summary.get("no_relevant_oa",False)),
        "fulltext_claims_reentered_l2":len(scored),"fulltext_seed_neighborhood_observation_count":len(neighborhood),
        "fulltext_reviewable_graph_observation_count":len(reviewable),"fulltext_low_priority_context_observation_count":sum(bool(x.get("context_only_match")) for x in scored),"fulltext_weak_conflict_candidate_count":len(weak),
        "fulltext_strict_conflict_candidate_count":int(shared_summary.get("fulltext_confirmed_conflict_count",0)),
        "fulltext_hypothesis_candidate_count":0,"formal_hypothesis_count":0,"fulltext_handoff_consistent":not any("count_mismatch" in x for x in warnings),
        "fulltext_discovery_executed_when_expected":not expected or executed,"fulltext_discovery_skip_reason":"explicitly_disabled" if explicitly_disabled else None if enabled else "not_triggered"}
    _write_json(artifacts/"l35_fulltext_discovery_escalation_summary.json",summary)
    _write_json(artifacts/"l35_fulltext_discovery_reentry_summary.json",{**{k:v for k,v in summary.items() if k.startswith("fulltext_")},"selected_chunk_count":selected_chunks,"formal_hypothesis_count":0})
    pipeline=_json(artifacts/"pipeline_stage_summary.json");pipeline.update({"status":pipeline.get("status","completed"),"l35_fulltext_discovery":summary})
    _write_json(artifacts/"pipeline_stage_summary.json",pipeline)
    md=artifacts/"pipeline_stage_summary.md";block="\n## L3.5 Fulltext Discovery Escalation\n\n"+"\n".join(f"- {k}: {v}" for k,v in summary.items())+"\n"
    md.write_text((md.read_text(encoding="utf-8") if md.is_file() else "# Pipeline Stage Summary\n")+block,encoding="utf-8")
    hypothesis=_json(artifacts/"hypothesis_summary.json");hypothesis.update({k:v for k,v in summary.items() if k.startswith("fulltext_")})
    hypothesis.update({"discovery_oa_available_count":oa,"discovery_relevant_oa_candidate_count":relevant_oa,
        "discovery_selected_fulltext_count":selected,"discovery_downloaded_fulltext_count":downloaded,"selected_chunk_count":selected_chunks})
    _write_json(artifacts/"hypothesis_summary.json",hypothesis)
    return summary

__all__=["discovery_escalation_expected","finalize_discovery_escalation","prepare_discovery_escalation"]
