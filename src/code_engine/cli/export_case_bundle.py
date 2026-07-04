"""Export a stable, self-describing System B case bundle."""
from __future__ import annotations
import argparse, json, shutil
from datetime import datetime, timezone
from pathlib import Path
from code_engine.validation.case_routing import load_case_domain_profile

ARTIFACTS = ["case_domain_profile.json","validator_selection_report.json","validator_selection_report.md","pipeline_stage_summary.json","quality_score.json","core_observations.jsonl","core_observations_table.md","l2_graph_observations.jsonl","l2_canonicalization_audit_summary.json","l2_canonicalization_audit_report.md","graph_conflict_summary.json","hypothesis_summary.json","l7_external_validation_summary.json","l7_lincs_validation_summary.json","l7_pubmed_post_cutoff_summary.json","l7_pubmed_post_cutoff_results.jsonl","l7_reactome_summary.json","l7_reactome_results.jsonl","l7_enrichr_summary.json","l7_enrichr_results.jsonl","l35_fulltext_retrieval_summary.json","l35_fulltext_retrieval_results.jsonl","l35_fulltext_candidate_papers.jsonl","l35_fulltext_l1_summary.json","l35_fulltext_l1_claims.jsonl","l35_fulltext_conflict_confirmation_summary.json","l35_fulltext_conflict_confirmations.jsonl","whitebox_case_report.md","audit_report.md"]
ARTIFACTS += ["replay_manifest.json", "replay_report.md"]
ARTIFACTS += ["l2_seed_neighborhood_observations.jsonl","l2_seed_neighborhood_summary.json","l2_reviewable_graph_observations.jsonl","l2_reviewable_graph_summary.json","l2_low_priority_context_observations.jsonl","l2_low_priority_context_summary.json","weak_conflict_candidates.jsonl","weak_conflict_summary.json","discovery_filter_audit.jsonl","discovery_filter_summary.json","discovery_filter_summary.md","discovery_precision_recall_calibration.json","discovery_precision_recall_calibration.md","fulltext_escalation_candidates.jsonl","fulltext_discovery_escalation_candidates.jsonl","fulltext_escalation_plan.json"]
ARTIFACTS += ["l35_fulltext_discovery_escalation_summary.json","l35_fulltext_discovery_candidate_papers.jsonl","l35_fulltext_discovery_retrieval_results.jsonl","l35_fulltext_discovery_l1_claims.jsonl","l35_fulltext_discovery_observations.jsonl","l35_fulltext_discovery_reentry_summary.json","l35_fulltext_oa_candidate_papers.jsonl"]
REQUIRED = {"case_domain_profile.json","validator_selection_report.json","pipeline_stage_summary.json","l7_external_validation_summary.json","whitebox_case_report.md"}
def _json(path:Path)->dict:
    try: return json.loads(path.read_text(encoding="utf-8"))
    except (OSError,json.JSONDecodeError): return {}
def _line_count(path:Path)->int|None:
    try: return sum(bool(line.strip()) for line in path.read_text(encoding="utf-8").splitlines())
    except OSError: return None
def _canonical(data:dict, field:str, warnings:list[str], artifact_name:str, *fallback_fields:str, default=0):
    if field in data: return data[field]
    for fallback in fallback_fields:
        if fallback in data: return data[fallback]
    warnings.append(f"{artifact_name.removesuffix('.json')}_missing_field: {field}")
    return default
def export_case_bundle(final_run:str|Path, case_profile:str|Path, output_root:str|Path="case_bundles", *, bundle_id_suffix:str|None=None, overwrite_bundle:bool=False, manifest_overrides:dict|None=None)->tuple[Path,dict]:
    run=Path(final_run).resolve(); artifacts=run/"artifacts"; profile=load_case_domain_profile(case_profile)
    from code_engine.discovery.lanes import synchronize_seed_metadata
    seed_provenance=synchronize_seed_metadata(run)
    bundle_id=profile.case_id+(f"__{bundle_id_suffix}" if bundle_id_suffix else "");out=Path(output_root)/bundle_id
    if bundle_id_suffix and out.exists() and not overwrite_bundle: raise FileExistsError(f"replay bundle already exists: {out}")
    out.mkdir(parents=True,exist_ok=True)
    missing=[]
    for name in ARTIFACTS:
        src=artifacts/name
        if src.is_file(): shutil.copy2(src,out/name)
        else: missing.append(name)
    selection_payload=_json(artifacts/"validator_selection_report.json"); selection=selection_payload.get("validator_selection",selection_payload); export_warnings=[]
    canonical_names=("hypothesis_summary.json","graph_conflict_summary.json","l7_external_validation_summary.json","l35_fulltext_retrieval_summary.json","l35_fulltext_l1_summary.json","l35_fulltext_conflict_confirmation_summary.json")
    for name in canonical_names:
        if not (artifacts/name).is_file(): export_warnings.append(f"missing_artifact: {name}")
    core=_json(artifacts/"core_observation_summary.json"); conflict=_json(artifacts/"graph_conflict_summary.json"); hypothesis=_json(artifacts/"hypothesis_summary.json"); ext=_json(artifacts/"l7_external_validation_summary.json"); lincs=_json(artifacts/"l7_lincs_validation_summary.json")
    existing=_json(artifacts/"case_bundle_manifest.json")
    source_id=_json(run/"artifacts/rebuild_provenance.json").get("source_run_id") or existing.get("source_run_id")
    required_missing=sorted(REQUIRED & set(missing)); executed=ext.get("executed_validators",selection.get("executed_validators",[])); unavailable=[item for item in ext.get("recommended_but_unavailable",selection.get("recommended_but_unavailable",existing.get("recommended_but_unavailable_validators",[]))) if item not in executed]
    validation={**lincs,**ext}; interpretation=validation.get("interpretation") or validation.get("biological_interpretation"); retrieval=_json(artifacts/"l35_fulltext_retrieval_summary.json"); fulltext_l1=_json(artifacts/"l35_fulltext_l1_summary.json"); confirmation=_json(artifacts/"l35_fulltext_conflict_confirmation_summary.json"); fulltext={**retrieval,**fulltext_l1,**confirmation}
    if not interpretation and validation.get("interpretation_distribution"): interpretation=max(validation["interpretation_distribution"],key=validation["interpretation_distribution"].get)
    core_count=_canonical(core,"core_observation_count",export_warnings,"core_observation_summary.json","count",default=None) if core else None
    if core_count is None: core_count=_line_count(artifacts/"core_observations.jsonl")
    if core_count is None: core_count=existing.get("core_observation_count",0); export_warnings.append("missing_artifact: core_observation_summary.json")
    hypothesis_counts={field:int(_canonical(hypothesis,field,export_warnings,"hypothesis_summary.json",default=existing.get(field,0)) or 0) for field in ("formal_hypothesis_count","high_confidence_hypothesis_count","manual_review_followup_count","abstract_only_followup_count","display_hypothesis_count","display_followup_count")}
    conflict_count=int(_canonical(conflict,"true_graph_conflict_count",export_warnings,"graph_conflict_summary.json",default=existing.get("true_graph_conflict_count",0)) or 0)
    formal_count=hypothesis_counts["formal_hypothesis_count"]
    graph_count=int(_line_count(artifacts/"l2_graph_observations.jsonl") or 0)
    scientific_class="graph_observations_no_conflict" if graph_count and not conflict_count else "no_core_observations" if not core_count else "hypothesis_generated" if formal_count else "conflict_found" if conflict_count else "no_conflict"
    zero_reason="No observations passed the core canonical graph gate; inspect the forensic L1/L2 trace." if not core_count else None
    discovery=_json(artifacts/"discovery_filter_summary.json");fulltext_discovery=_json(artifacts/"l35_fulltext_discovery_escalation_summary.json")
    manifest={"case_id":profile.case_id,"query":profile.query,"case_type":profile.case_type,"source_run_id":source_id,"final_run_id":run.name,
      "source_run_dir":str(run.parent/source_id) if source_id else None,"final_run_dir":str(run),"pipeline_complete":not required_missing,
      "pipeline_mode":"abstract_plus_domain_routed_external_validation","executed_validators":executed,
      "skipped_validators":ext.get("skipped_validators",selection.get("skipped_validators",[])),
      "recommended_but_unavailable_validators":unavailable,"blocked_validators":selection.get("blocked_required_validators",[]),
      "core_observation_count":int(core_count or 0),"graph_observation_count":graph_count,"true_graph_conflict_count":conflict_count,
      **hypothesis_counts,
      "external_validation_status":validation.get("status", "completed" if executed else "unavailable"),"external_validation_interpretation":interpretation,"matched_signature_count":int(validation.get("matched_signature_count",0) or 0),"validation_target_count":int(validation.get("validation_target_count",0) or 0),"overall_validation_score":validation.get("overall_validation_score"),
      "fulltext_confirmation_status":fulltext.get("status","not_enabled"),"fulltext_candidate_paper_count":int(fulltext.get("candidate_paper_count",0) or 0),"fulltext_available_count":int(fulltext.get("oa_available_count",0) or 0),"fulltext_confirmed_conflict_count":int(fulltext.get("fulltext_confirmed_conflict_count",0) or 0),
      "fulltext_l1_claim_count":int(fulltext.get("fulltext_l1_claim_count",0) or 0),"fulltext_l1_api_calls":int(fulltext.get("fulltext_l1_api_calls",0) or 0),"fulltext_limit_hit":bool(fulltext.get("fulltext_limit_hit",False)),"copyright_safe":bool(fulltext.get("copyright_safe",True)),"fulltext_layer":{"enabled":fulltext.get("status","not_enabled")!="not_enabled","source":"pmc_oa","selection_policy":"relevance_first_oa_aware","status":fulltext.get("status","not_enabled"),"candidate_paper_count":int(fulltext.get("candidate_paper_count",0) or 0),"oa_available_count":int(fulltext.get("oa_available_count",0) or 0),"claim_count":int(fulltext.get("fulltext_l1_claim_count",0) or 0),"confirmed_conflict_count":int(fulltext.get("fulltext_confirmed_conflict_count",0) or 0)},
      "missing_artifacts":missing,"required_missing_artifacts":required_missing,"bundle_export_warnings":list(dict.fromkeys(export_warnings)),"bundle_complete":not missing,"ready_for_system_b":not required_missing and bool(executed),
      "seed_neighborhood_observation_count":int(discovery.get("seed_neighborhood_observation_count",0)),"reviewable_graph_observation_count":int(discovery.get("reviewable_graph_observation_count",0)),
      "weak_conflict_candidate_count":int(discovery.get("weak_conflict_candidate_count",0)),"fulltext_escalation_candidate_count":int(discovery.get("fulltext_escalation_candidate_count",0)),
      "low_priority_context_observation_count":int(discovery.get("low_priority_context_observation_count",0)),
      "context_only_fraction_in_reviewable":float(discovery.get("context_only_fraction_in_reviewable",0)),"strong_anchor_fraction_in_top_20_reviewable":float(discovery.get("strong_anchor_fraction_in_top_20_reviewable",0)),
      "medium_or_strong_anchor_fraction_in_weak_candidates":float(discovery.get("medium_or_strong_anchor_fraction_in_weak_candidates",0)),
      "fulltext_handoff_consistent":bool(discovery.get("fulltext_handoff_consistent",False)),"fulltext_handoff_warnings":discovery.get("fulltext_handoff_warnings",[]),
      "precision_recall_calibration_available":(artifacts/"discovery_precision_recall_calibration.json").is_file(),
      "fulltext_discovery_escalation_enabled":bool(fulltext_discovery.get("fulltext_discovery_escalation_enabled")),
      "fulltext_discovery_candidate_count":int(fulltext_discovery.get("fulltext_discovery_candidate_count",0)),
      "fulltext_discovery_oa_available_count":int(fulltext_discovery.get("oa_available_count",0)),
      "fulltext_discovery_l1_claim_count":int(fulltext_discovery.get("fulltext_l1_claim_count",0)),
      "fulltext_discovery_reentry_count":int(fulltext_discovery.get("fulltext_claims_reentered_l2",0)),
      "fulltext_discovery_status":fulltext_discovery.get("status","not_run"),"fulltext_mode":fulltext_discovery.get("fulltext_mode","confirmation" if fulltext.get("status","not_enabled")!="not_enabled" else "skipped"),
      "scientific_candidate_count":int(fulltext.get("scientific_candidate_count",0)),"relevance_passed_candidate_count":int(fulltext.get("relevance_passed_candidate_count",0)),
      "relevant_oa_candidate_count":int(fulltext.get("relevant_oa_candidate_count",0)),"selected_fulltext_count":int(fulltext.get("selected_fulltext_count",0)),
      "high_relevance_non_oa_count":int(fulltext.get("high_relevance_non_oa_count",0)),"low_relevance_oa_count":int(fulltext.get("low_relevance_oa_count",0)),
      "low_relevance_oa_backfill_blocked_count":int(fulltext.get("low_relevance_oa_backfill_blocked_count",0)),"no_relevant_oa":bool(fulltext.get("no_relevant_oa",False)),
      "fulltext_discovery_executed_when_expected":bool(fulltext_discovery.get("fulltext_discovery_executed_when_expected",not fulltext_discovery)),
      "fulltext_discovery_skip_reason":fulltext_discovery.get("fulltext_discovery_skip_reason"),
      "discovery_mode_recall_layer_available":bool(discovery),**seed_provenance,
      "created_at":datetime.now(timezone.utc).isoformat(),"schema_version":"case_bundle_manifest_v1"}
    manifest.update({"case_execution_outcome":"execution_passed" if manifest["pipeline_complete"] else "execution_incomplete","scientific_output_class":scientific_class,"zero_claim_reason":zero_reason,"is_zero_claim_case":not bool(core_count)})
    manifest.update(manifest_overrides or {})
    pipeline=_json(out/"pipeline_stage_summary.json")
    if not pipeline:
        pipeline={"case_id":profile.case_id,"status":"completed_with_warnings" if manifest["pipeline_complete"] else "missing_source_artifact","stage_counts":{"core_observations":int(core_count or 0),"conflicts":conflict_count,"hypotheses":formal_count},"warnings":["source pipeline summary was empty; counts reconstructed from canonical artifacts"],"limitations":["Detailed upstream stage timing/status was unavailable."]}
        (out/"pipeline_stage_summary.json").write_text(json.dumps(pipeline,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    exported_selection=_json(out/"validator_selection_report.json"); selected=exported_selection.get("validator_selection",exported_selection)
    selected.update({"selected_validators":list(dict.fromkeys([*selected.get("selected_validators",[]),*ext.get("validator_results",{})])),"executed_validators":executed,"skipped_validators":ext.get("skipped_validators",selection.get("skipped_validators",[])),"recommended_but_unavailable":unavailable})
    warnings=list(dict.fromkeys([*exported_selection.get("warnings",[]),*( ["source validator selection report was empty"] if not exported_selection else [])]))
    (out/"validator_selection_report.json").write_text(json.dumps({"case_id":profile.case_id,"status":"completed_with_warnings" if warnings else "completed","validator_selection":selected,"warnings":warnings},ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    (out/"case_bundle_manifest.json").write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    return out,manifest
def main(argv=None)->int:
    p=argparse.ArgumentParser(); p.add_argument("--final-run",type=Path,required=True); p.add_argument("--case-profile",type=Path,required=True); p.add_argument("--output-root",type=Path,default=Path("case_bundles"))
    a=p.parse_args(argv); out,m=export_case_bundle(a.final_run,a.case_profile,a.output_root); print(json.dumps({"case_bundle":str(out),**m},ensure_ascii=False)); return 0 if m["ready_for_system_b"] else 2
if __name__ == "__main__": raise SystemExit(main())
