"""Export a stable, self-describing System B case bundle."""
from __future__ import annotations
import argparse, json, shutil
from datetime import datetime, timezone
from pathlib import Path
from code_engine.validation.case_routing import load_case_domain_profile

ARTIFACTS = ["case_domain_profile.json","validator_selection_report.json","validator_selection_report.md","pipeline_stage_summary.json","quality_score.json","core_observations.jsonl","core_observations_table.md","graph_conflict_summary.json","hypothesis_summary.json","l7_external_validation_summary.json","l7_lincs_validation_summary.json","l7_pubmed_post_cutoff_summary.json","l7_pubmed_post_cutoff_results.jsonl","l7_reactome_summary.json","l7_reactome_results.jsonl","l7_enrichr_summary.json","l7_enrichr_results.jsonl","l35_fulltext_retrieval_summary.json","l35_fulltext_retrieval_results.jsonl","l35_fulltext_candidate_papers.jsonl","l35_fulltext_l1_summary.json","l35_fulltext_l1_claims.jsonl","l35_fulltext_conflict_confirmation_summary.json","l35_fulltext_conflict_confirmations.jsonl","whitebox_case_report.md","audit_report.md"]
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
def export_case_bundle(final_run:str|Path, case_profile:str|Path, output_root:str|Path="case_bundles")->tuple[Path,dict]:
    run=Path(final_run).resolve(); artifacts=run/"artifacts"; profile=load_case_domain_profile(case_profile)
    out=Path(output_root)/profile.case_id; out.mkdir(parents=True,exist_ok=True)
    missing=[]
    for name in ARTIFACTS:
        src=artifacts/name
        if src.is_file(): shutil.copy2(src,out/name)
        else: missing.append(name)
    selection=_json(artifacts/"validator_selection_report.json").get("validator_selection",{}); export_warnings=[]
    canonical_names=("hypothesis_summary.json","graph_conflict_summary.json","l7_external_validation_summary.json","l35_fulltext_retrieval_summary.json","l35_fulltext_l1_summary.json","l35_fulltext_conflict_confirmation_summary.json")
    for name in canonical_names:
        if not (artifacts/name).is_file(): export_warnings.append(f"missing_artifact: {name}")
    core=_json(artifacts/"core_observation_summary.json"); conflict=_json(artifacts/"graph_conflict_summary.json"); hypothesis=_json(artifacts/"hypothesis_summary.json"); ext=_json(artifacts/"l7_external_validation_summary.json"); lincs=_json(artifacts/"l7_lincs_validation_summary.json")
    source_id=_json(run/"artifacts/rebuild_provenance.json").get("source_run_id") or _json(artifacts/"case_bundle_manifest.json").get("source_run_id")
    required_missing=sorted(REQUIRED & set(missing)); executed=ext.get("executed_validators",selection.get("executed_validators",[]))
    validation={**lincs,**ext}; interpretation=validation.get("interpretation") or validation.get("biological_interpretation"); retrieval=_json(artifacts/"l35_fulltext_retrieval_summary.json"); fulltext_l1=_json(artifacts/"l35_fulltext_l1_summary.json"); confirmation=_json(artifacts/"l35_fulltext_conflict_confirmation_summary.json"); fulltext={**retrieval,**fulltext_l1,**confirmation}
    if not interpretation and validation.get("interpretation_distribution"): interpretation=max(validation["interpretation_distribution"],key=validation["interpretation_distribution"].get)
    existing=_json(artifacts/"case_bundle_manifest.json")
    core_count=_canonical(core,"core_observation_count",export_warnings,"core_observation_summary.json","count",default=None) if core else None
    if core_count is None: core_count=_line_count(artifacts/"core_observations.jsonl")
    if core_count is None: core_count=existing.get("core_observation_count",0); export_warnings.append("missing_artifact: core_observation_summary.json")
    hypothesis_counts={field:int(_canonical(hypothesis,field,export_warnings,"hypothesis_summary.json",default=existing.get(field,0)) or 0) for field in ("formal_hypothesis_count","high_confidence_hypothesis_count","manual_review_followup_count","abstract_only_followup_count","display_hypothesis_count","display_followup_count")}
    manifest={"case_id":profile.case_id,"query":profile.query,"case_type":profile.case_type,"source_run_id":source_id,"final_run_id":run.name,
      "source_run_dir":str(run.parent/source_id) if source_id else None,"final_run_dir":str(run),"pipeline_complete":not required_missing,
      "pipeline_mode":"abstract_plus_domain_routed_external_validation","executed_validators":executed,
      "skipped_validators":ext.get("skipped_validators",selection.get("skipped_validators",[])),
      "recommended_but_unavailable_validators":selection.get("recommended_but_unavailable",[]),"blocked_validators":selection.get("blocked_required_validators",[]),
      "core_observation_count":int(core_count or 0),"true_graph_conflict_count":int(_canonical(conflict,"true_graph_conflict_count",export_warnings,"graph_conflict_summary.json",default=existing.get("true_graph_conflict_count",0)) or 0),
      **hypothesis_counts,
      "external_validation_status":validation.get("status", "completed" if executed else "unavailable"),"external_validation_interpretation":interpretation,"matched_signature_count":int(validation.get("matched_signature_count",0) or 0),"validation_target_count":int(validation.get("validation_target_count",0) or 0),"overall_validation_score":validation.get("overall_validation_score"),
      "fulltext_confirmation_status":fulltext.get("status","not_enabled"),"fulltext_candidate_paper_count":int(fulltext.get("candidate_paper_count",0) or 0),"fulltext_available_count":int(fulltext.get("oa_available_count",0) or 0),"fulltext_confirmed_conflict_count":int(fulltext.get("fulltext_confirmed_conflict_count",0) or 0),
      "fulltext_l1_claim_count":int(fulltext.get("fulltext_l1_claim_count",0) or 0),"fulltext_l1_api_calls":int(fulltext.get("fulltext_l1_api_calls",0) or 0),"fulltext_limit_hit":bool(fulltext.get("fulltext_limit_hit",False)),"copyright_safe":bool(fulltext.get("copyright_safe",True)),"fulltext_layer":{"enabled":fulltext.get("status","not_enabled")!="not_enabled","source":"pmc_oa","selection_policy":"conflict_related_only","status":fulltext.get("status","not_enabled"),"candidate_paper_count":int(fulltext.get("candidate_paper_count",0) or 0),"oa_available_count":int(fulltext.get("oa_available_count",0) or 0),"claim_count":int(fulltext.get("fulltext_l1_claim_count",0) or 0),"confirmed_conflict_count":int(fulltext.get("fulltext_confirmed_conflict_count",0) or 0)},
      "missing_artifacts":missing,"required_missing_artifacts":required_missing,"bundle_export_warnings":list(dict.fromkeys(export_warnings)),"bundle_complete":not missing,"ready_for_system_b":not required_missing and bool(executed),
      "created_at":datetime.now(timezone.utc).isoformat(),"schema_version":"case_bundle_manifest_v1"}
    (out/"case_bundle_manifest.json").write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    return out,manifest
def main(argv=None)->int:
    p=argparse.ArgumentParser(); p.add_argument("--final-run",type=Path,required=True); p.add_argument("--case-profile",type=Path,required=True); p.add_argument("--output-root",type=Path,default=Path("case_bundles"))
    a=p.parse_args(argv); out,m=export_case_bundle(a.final_run,a.case_profile,a.output_root); print(json.dumps({"case_bundle":str(out),**m},ensure_ascii=False)); return 0 if m["ready_for_system_b"] else 2
if __name__ == "__main__": raise SystemExit(main())
