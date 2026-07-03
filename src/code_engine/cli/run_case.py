"""One-command source run, domain-routed rebuild, bundle export, and audit."""
from __future__ import annotations
import argparse, json, os, subprocess, sys
from datetime import datetime, timezone
from pathlib import Path
from code_engine.cli.export_case_bundle import export_case_bundle
from code_engine.validation.case_routing import load_case_domain_profile
from code_engine.validation.readiness import check_case_readiness, write_readiness_report

FINAL_ARTIFACTS=("case_domain_profile.json","validator_selection_report.json","validator_selection_report.md","case_bundle_manifest.json","pipeline_stage_summary.json","l7_external_validation_summary.json","whitebox_case_report.md")
def build_parser():
    p=argparse.ArgumentParser(description="Run one domain-aware case end to end")
    p.add_argument("--case-profile",type=Path,required=True); p.add_argument("--search-plan-file",type=Path,required=True); p.add_argument("--external-data-root",type=Path,default=Path("data/external"))
    p.add_argument("--api",action="store_true"); p.add_argument("--network",action="store_true"); p.add_argument("--max-papers",type=int,default=60); p.add_argument("--temporal-role",default="discovery",choices=("discovery","validation","unrestricted"))
    p.add_argument("--l1-read-timeout-seconds",type=float,default=180); p.add_argument("--l1-max-retries",type=int,default=2); p.add_argument("--output-case-bundle-root",type=Path,default=Path("case_bundles")); p.add_argument("--output-run-suffix")
    p.add_argument("--dry-run",action="store_true"); p.add_argument("--stop-after-readiness",action="store_true"); p.add_argument("--allow-warnings",action="store_true"); p.add_argument("--fail-if-required-validator-unavailable",action="store_true"); p.add_argument("--no-write-audit",action="store_true")
    return p
def _audit(profile, decision, readiness, source_run=None, final_run=None, bundle=None, manifest=None, warnings=None):
    warnings=warnings or []; state={}
    if source_run:
        for name in ("run_state.json","state.json"):
            try: state=json.loads((Path(source_run)/name).read_text(encoding="utf-8")); break
            except (OSError,json.JSONDecodeError): pass
    payload={"schema_version":"run_case_audit_v1","case_id":profile.case_id,"decision":decision,"created_at":datetime.now(timezone.utc).isoformat(),"source_run":str(source_run) if source_run else None,"final_run":str(final_run) if final_run else None,"readiness":readiness,"case_bundle":str(bundle) if bundle else None,"ready_for_system_b":bool(manifest and manifest.get("ready_for_system_b")),"metrics":{"api_calls":state.get("api_calls_made",state.get("summary",{}).get("api_calls_made",0)),"network_calls":state.get("network_calls_made",state.get("summary",{}).get("network_calls_made",0)),"core_observations":(manifest or {}).get("core_observation_count",0),"true_graph_conflicts":(manifest or {}).get("true_graph_conflict_count",0),"formal_hypotheses":(manifest or {}).get("formal_hypothesis_count",0),"external_validation_status":(manifest or {}).get("external_validation_status")},"warnings":warnings}
    lines=[f"# {profile.case_id} Run Case Audit","","## Executive Decision","",decision,"","## Runs","",f"- source run: {source_run or 'not created'}",f"- final run: {final_run or 'not created'}","","## Readiness","",f"- LLM ready: {readiness['llm']['ready']}",f"- search plan ready: {readiness['search_plan']['ready']}",f"- validator routing ready: {not readiness['routing']['blocked_required_validators']}","","## Stage Completeness","",f"- final artifacts present: {bool(final_run and all((Path(final_run)/'artifacts'/x).is_file() for x in FINAL_ARTIFACTS))}","","## Key Metrics","",f"- executed validators: {(manifest or {}).get('executed_validators',[])}",f"- unavailable validators: {(manifest or {}).get('recommended_but_unavailable_validators',readiness['routing']['recommended_but_unavailable'])}",f"- true graph conflicts: {(manifest or {}).get('true_graph_conflict_count',0)}",f"- external validation: {(manifest or {}).get('external_validation_status')}","","## Case Bundle","",f"- path: {bundle or 'not exported'}",f"- ready_for_system_b: {payload['ready_for_system_b']}","","## Warnings",""]+[f"- {x}" for x in warnings or ["none"]]+["","## Final Recommendation","","Configure missing resources or proceed with the exported bundle according to the decision above."]
    return payload,"\n".join(lines)+"\n"
def main(argv=None)->int:
    a=build_parser().parse_args(argv); profile=load_case_domain_profile(a.case_profile); readiness=check_case_readiness(a.case_profile,a.search_plan_file,a.external_data_root); write_readiness_report(readiness)
    source=[sys.executable,"-m","code_engine.cli.run","--query",profile.query,"--execute",
      "--api" if a.api else "--no-api", "--network" if a.network else "--no-network",
      "--allow-uncertain-intake","--l1-provider",os.getenv("L1_PROVIDER","<L1_PROVIDER>"),"--l1-model",os.getenv("MODEL_NAME","<MODEL_NAME>"),"--enable-conflict-timeline","--enable-evidence-graph","--no-cross-batch-paper-cache","--l1-read-timeout-seconds",str(a.l1_read_timeout_seconds),"--l1-max-retries",str(a.l1_max_retries),"--temporal-role",a.temporal_role,"--max-papers",str(a.max_papers),"--until","report","--search-plan-file",str(a.search_plan_file),"--fail-if-search-plan-drift","--diversify-acquisition","--json"]
    suffix=a.output_run_suffix or f"{profile.case_id}_clean_domain_routed_lincs_v1"
    def rebuild(run): return [sys.executable,"-m","code_engine.cli.run","--rebuild-from-run",str(run),"--rebuild-stages","l4,l5,l6,l7,report","--output-run-suffix",suffix,"--case-profile",str(a.case_profile),"--external-data-root",str(a.external_data_root),"--json"]
    if a.dry_run:
        print("SOURCE_COMMAND: "+" ".join(source)); print("REBUILD_COMMAND: "+" ".join(rebuild("<NEW_SOURCE_RUN_DIR>")))
        print("selected_validators = "+json.dumps(readiness["routing"]["selected_validators"])); print("recommended_but_unavailable = "+json.dumps(readiness["routing"]["recommended_but_unavailable"])); print("expected_outputs = "+json.dumps(list(FINAL_ARTIFACTS))); print("CASE_RUN_DRY_RUN")
        return 0
    if a.stop_after_readiness: print("CASE_RUN_PASS" if readiness["ready"] else "CASE_RUN_BLOCKED"); return 0 if readiness["ready"] else 2
    if not readiness["ready"]:
        decision="CASE_RUN_BLOCKED"; payload,md=_audit(profile,decision,readiness)
        if not a.no_write_audit:
            root=Path("audit_reports"); root.mkdir(exist_ok=True); (root/f"{profile.case_id}_run_case_audit.json").write_text(json.dumps(payload,ensure_ascii=False,indent=2)+"\n"); (root/f"{profile.case_id}_run_case_audit.md").write_text(md)
        print(decision); print("blocking_reasons = "+json.dumps(readiness["blocking_reasons"])); return 2
    try:
        first=subprocess.run(source,check=True,text=True,capture_output=True); source_data=json.loads(first.stdout.strip().splitlines()[-1]); source_run=Path(source_data["run_dir"])
        second=subprocess.run(rebuild(source_run),check=True,text=True,capture_output=True); final_data=json.loads(second.stdout.strip().splitlines()[-1]); final_run=Path(final_data["run_dir"])
        missing=[x for x in FINAL_ARTIFACTS if not (final_run/"artifacts"/x).is_file()]
        bundle,manifest=export_case_bundle(final_run,a.case_profile,a.output_case_bundle_root); warnings=[f"missing final artifact: {x}" for x in missing]+[f"validator unavailable: {x}" for x in readiness["routing"]["recommended_but_unavailable"]]
        decision="CASE_RUN_PASS" if not warnings else "CASE_RUN_PASS_WITH_WARNINGS"
        if missing or (a.fail_if_required_validator_unavailable and readiness["routing"]["blocked_required_validators"]): decision="CASE_RUN_FAIL"
        payload,md=_audit(profile,decision,readiness,source_run,final_run,bundle,manifest,warnings)
    except (subprocess.CalledProcessError,KeyError,json.JSONDecodeError) as exc:
        decision="CASE_RUN_FAIL"; payload,md=_audit(profile,decision,readiness,warnings=[str(exc)]); source_run=final_run=bundle=None; manifest={}
    if not a.no_write_audit:
        root=Path("audit_reports"); root.mkdir(exist_ok=True); (root/f"{profile.case_id}_run_case_audit.json").write_text(json.dumps(payload,ensure_ascii=False,indent=2)+"\n"); (root/f"{profile.case_id}_run_case_audit.md").write_text(md)
    print(decision); print(f"source_run = {source_run}"); print(f"final_run = {final_run}"); print(f"case_bundle = {bundle}"); print("executed_validators = "+json.dumps(manifest.get("executed_validators",[]))); print("recommended_but_unavailable = "+json.dumps(readiness["routing"]["recommended_but_unavailable"])); return 0 if decision.startswith("CASE_RUN_PASS") else 1
if __name__ == "__main__": raise SystemExit(main())
