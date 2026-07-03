"""Export a stable, self-describing System B case bundle."""
from __future__ import annotations
import argparse, json, shutil
from datetime import datetime, timezone
from pathlib import Path
from code_engine.validation.case_routing import load_case_domain_profile

ARTIFACTS = ["case_domain_profile.json","validator_selection_report.json","validator_selection_report.md","pipeline_stage_summary.json","quality_score.json","core_observations.jsonl","core_observations_table.md","graph_conflict_summary.json","hypothesis_summary.json","l7_external_validation_summary.json","l7_lincs_validation_summary.json","l35_fulltext_retrieval_summary.json","l35_fulltext_retrieval_results.jsonl","l35_fulltext_candidate_papers.jsonl","l35_fulltext_l1_summary.json","l35_fulltext_l1_claims.jsonl","l35_fulltext_conflict_confirmation_summary.json","l35_fulltext_conflict_confirmations.jsonl","whitebox_case_report.md","audit_report.md"]
REQUIRED = {"case_domain_profile.json","validator_selection_report.json","pipeline_stage_summary.json","l7_external_validation_summary.json","whitebox_case_report.md"}
def _json(path:Path)->dict:
    try: return json.loads(path.read_text(encoding="utf-8"))
    except (OSError,json.JSONDecodeError): return {}
def export_case_bundle(final_run:str|Path, case_profile:str|Path, output_root:str|Path="case_bundles")->tuple[Path,dict]:
    run=Path(final_run).resolve(); artifacts=run/"artifacts"; profile=load_case_domain_profile(case_profile)
    out=Path(output_root)/profile.case_id; out.mkdir(parents=True,exist_ok=True)
    missing=[]
    for name in ARTIFACTS:
        src=artifacts/name
        if src.is_file(): shutil.copy2(src,out/name)
        else: missing.append(name)
    selection=_json(artifacts/"validator_selection_report.json").get("validator_selection",{})
    core=_json(artifacts/"core_observation_summary.json"); conflict=_json(artifacts/"graph_conflict_summary.json"); hypothesis=_json(artifacts/"hypothesis_summary.json"); ext=_json(artifacts/"l7_external_validation_summary.json"); lincs=_json(artifacts/"l7_lincs_validation_summary.json")
    source_id=_json(run/"artifacts/rebuild_provenance.json").get("source_run_id") or _json(artifacts/"case_bundle_manifest.json").get("source_run_id")
    required_missing=sorted(REQUIRED & set(missing)); executed=selection.get("executed_validators",[])
    interpretation=lincs.get("interpretation") or ext.get("interpretation"); fulltext=_json(artifacts/"l35_fulltext_conflict_confirmation_summary.json")
    if not interpretation and lincs.get("interpretation_distribution"): interpretation=max(lincs["interpretation_distribution"],key=lincs["interpretation_distribution"].get)
    manifest={"case_id":profile.case_id,"query":profile.query,"case_type":profile.case_type,"source_run_id":source_id,"final_run_id":run.name,
      "source_run_dir":str(run.parent/source_id) if source_id else None,"final_run_dir":str(run),"pipeline_complete":not required_missing,
      "pipeline_mode":"abstract_plus_domain_routed_external_validation","executed_validators":executed,
      "recommended_but_unavailable_validators":selection.get("recommended_but_unavailable",[]),"blocked_validators":selection.get("blocked_required_validators",[]),
      "core_observation_count":int(core.get("core_observation_count",core.get("count",0)) or 0),"true_graph_conflict_count":int(conflict.get("true_graph_conflict_count",0) or 0),
      "formal_hypothesis_count":int(hypothesis.get("formal_hypothesis_count",hypothesis.get("hypothesis_count",0)) or 0),"manual_review_followup_count":int(core.get("manual_review_followup_count",0) or 0),
      "external_validation_status":ext.get("status", "completed" if executed else "unavailable"),"external_validation_interpretation":interpretation,
      "fulltext_confirmation_status":fulltext.get("status","not_enabled"),"fulltext_candidate_paper_count":int(fulltext.get("candidate_paper_count",0) or 0),"fulltext_available_count":int(fulltext.get("oa_available_count",0) or 0),"fulltext_confirmed_conflict_count":int(fulltext.get("fulltext_confirmed_conflict_count",0) or 0),
      "missing_artifacts":missing,"required_missing_artifacts":required_missing,"bundle_complete":not missing,"ready_for_system_b":not required_missing and bool(executed),
      "created_at":datetime.now(timezone.utc).isoformat(),"schema_version":"case_bundle_manifest_v1"}
    (out/"case_bundle_manifest.json").write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    return out,manifest
def main(argv=None)->int:
    p=argparse.ArgumentParser(); p.add_argument("--final-run",type=Path,required=True); p.add_argument("--case-profile",type=Path,required=True); p.add_argument("--output-root",type=Path,default=Path("case_bundles"))
    a=p.parse_args(argv); out,m=export_case_bundle(a.final_run,a.case_profile,a.output_root); print(json.dumps({"case_bundle":str(out),**m},ensure_ascii=False)); return 0 if m["ready_for_system_b"] else 2
if __name__ == "__main__": raise SystemExit(main())
