"""One-command source run, domain-routed rebuild, bundle export, and audit."""
from __future__ import annotations
import argparse, json, os, subprocess, sys, traceback
from datetime import datetime, timezone
from pathlib import Path
from code_engine.cli.export_case_bundle import export_case_bundle
from code_engine.validation.case_routing import load_case_domain_profile
from code_engine.validation.readiness import check_case_readiness, write_readiness_report
from code_engine.validation.external_api_smoke import load_dotenv

FINAL_ARTIFACTS=("case_domain_profile.json","validator_selection_report.json","validator_selection_report.md","case_bundle_manifest.json","pipeline_stage_summary.json","l7_external_validation_summary.json","whitebox_case_report.md")
def build_parser():
    p=argparse.ArgumentParser(description="Run one domain-aware case end to end")
    p.add_argument("--case-profile",type=Path,required=True); p.add_argument("--search-plan-file",type=Path,required=True); p.add_argument("--external-data-root",type=Path,default=Path("data/external"))
    p.add_argument("--api",action="store_true"); p.add_argument("--network",action="store_true"); p.add_argument("--max-papers",type=int,default=60); p.add_argument("--temporal-role",default="discovery",choices=("discovery","validation","unrestricted"))
    p.add_argument("--l1-read-timeout-seconds",type=float,default=180); p.add_argument("--l1-max-retries",type=int,default=2); p.add_argument("--output-case-bundle-root",type=Path,default=Path("case_bundles")); p.add_argument("--output-run-suffix")
    p.add_argument("--dry-run",action="store_true"); p.add_argument("--stop-after-readiness",action="store_true"); p.add_argument("--allow-warnings",action="store_true"); p.add_argument("--fail-if-required-validator-unavailable",action="store_true"); p.add_argument("--no-write-audit",action="store_true")
    ft=p.add_mutually_exclusive_group(); ft.add_argument("--enable-fulltext-confirmation",action="store_true",help="Enable strict-conflict confirmation and automatic discovery escalation for discovery-mode cases."); ft.add_argument("--disable-fulltext-confirmation",action="store_true")
    discovery=p.add_mutually_exclusive_group();discovery.add_argument("--enable-fulltext-discovery-escalation",action="store_true",help="Explicitly enable discovery-mode PMC OA escalation.");discovery.add_argument("--disable-fulltext-discovery-escalation",action="store_true",help="Disable discovery escalation even when fulltext confirmation is enabled.")
    p.add_argument("--fulltext-source",choices=("pmc_oa",),default="pmc_oa"); p.add_argument("--fulltext-max-papers",type=int,default=20); p.add_argument("--fulltext-include-near-conflicts",action="store_true")
    p.add_argument("--fulltext-max-sections-per-paper",type=int,default=12); p.add_argument("--fulltext-max-chunks-per-paper",type=int,default=24); p.add_argument("--fulltext-max-chars-per-chunk",type=int,default=6000); p.add_argument("--fulltext-max-total-chunks",type=int,default=200); p.add_argument("--fulltext-l1-read-timeout-seconds",type=float,default=240); p.add_argument("--fulltext-l1-max-retries",type=int,default=1)
    return p
def _audit(profile, decision, readiness, source_run=None, final_run=None, bundle=None, manifest=None, warnings=None, failure_reason=None, exception_type=None, exception_message=None, traceback_tail=None, missing_final_artifacts=None, blocked_required_validators=None, child_phase=None, child_return_code=None, child_command=None, child_stdout_tail=None, child_stderr_tail=None):
    warnings=warnings or []; state={}
    if source_run:
        for name in ("run_state.json","state.json"):
            try: state=json.loads((Path(source_run)/name).read_text(encoding="utf-8")); break
            except (OSError,json.JSONDecodeError): pass
    payload={"schema_version":"run_case_audit_v1","case_id":profile.case_id,"decision":decision,"created_at":datetime.now(timezone.utc).isoformat(),"source_run":str(source_run) if source_run else None,"final_run":str(final_run) if final_run else None,"readiness":readiness,"case_bundle":str(bundle) if bundle else None,"ready_for_system_b":bool(manifest and manifest.get("ready_for_system_b")),"metrics":{"api_calls":state.get("api_calls_made",state.get("summary",{}).get("api_calls_made",0)),"network_calls":state.get("network_calls_made",state.get("summary",{}).get("network_calls_made",0)),"core_observations":(manifest or {}).get("core_observation_count",0),"true_graph_conflicts":(manifest or {}).get("true_graph_conflict_count",0),"formal_hypotheses":(manifest or {}).get("formal_hypothesis_count",0),"external_validation_status":(manifest or {}).get("external_validation_status"),"fulltext_confirmation_status":(manifest or {}).get("fulltext_confirmation_status"),"fulltext_candidate_paper_count":(manifest or {}).get("fulltext_candidate_paper_count",0),"fulltext_oa_available_count":(manifest or {}).get("fulltext_available_count",0),"fulltext_l1_claim_count":(manifest or {}).get("fulltext_l1_claim_count",0),"fulltext_confirmed_conflict_count":(manifest or {}).get("fulltext_confirmed_conflict_count",0),"fulltext_l1_api_calls":(manifest or {}).get("fulltext_l1_api_calls",0),"fulltext_limit_hit":(manifest or {}).get("fulltext_limit_hit",False),"copyright_safe":(manifest or {}).get("copyright_safe",True)},"warnings":warnings}
    if failure_reason: payload["failure_reason"]=failure_reason
    if exception_type: payload["exception_type"]=exception_type
    if exception_message: payload["exception_message"]=exception_message
    if traceback_tail: payload["traceback_tail"]=traceback_tail
    if missing_final_artifacts: payload["missing_final_artifacts"]=missing_final_artifacts
    if blocked_required_validators: payload["blocked_required_validators"]=blocked_required_validators
    if child_phase: payload["child_phase"]=child_phase
    if child_return_code is not None: payload["child_return_code"]=child_return_code
    if child_command: payload["child_command"]=child_command
    if child_stdout_tail: payload["child_stdout_tail"]=child_stdout_tail
    if child_stderr_tail: payload["child_stderr_tail"]=child_stderr_tail
    lines=[f"# {profile.case_id} Run Case Audit","","## Executive Decision","",decision,"","## Runs","",f"- source run: {source_run or 'not created'}",f"- final run: {final_run or 'not created'}","","## Readiness","",f"- LLM ready: {readiness['llm']['ready']}",f"- search plan ready: {readiness['search_plan']['ready']}",f"- validator routing ready: {not readiness['routing']['blocked_required_validators']}","","## Stage Completeness","",f"- final artifacts present: {bool(final_run and all((Path(final_run)/'artifacts'/x).is_file() for x in FINAL_ARTIFACTS))}","","## Key Metrics","",f"- executed validators: {(manifest or {}).get('executed_validators',[])}",f"- unavailable validators: {(manifest or {}).get('recommended_but_unavailable_validators',readiness['routing']['recommended_but_unavailable'])}",f"- true graph conflicts: {(manifest or {}).get('true_graph_conflict_count',0)}",f"- external validation: {(manifest or {}).get('external_validation_status')}","","## Case Bundle","",f"- path: {bundle or 'not exported'}",f"- ready_for_system_b: {payload['ready_for_system_b']}"]
    if failure_reason: lines+=["","## Failure Diagnostics","",f"- failure_reason: {failure_reason}"]+([f"- exception_type: {exception_type}"] if exception_type else [])+([f"- exception_message: {exception_message}"] if exception_message else [])+([f"- missing_final_artifacts: {missing_final_artifacts}"] if missing_final_artifacts else [])+([f"- blocked_required_validators: {blocked_required_validators}"] if blocked_required_validators else [])+([f"- child_phase: {child_phase}"] if child_phase else [])+([f"- child_return_code: {child_return_code}"] if child_return_code is not None else [])
    lines+=["","## Warnings",""]+[f"- {x}" for x in warnings or ["none"]]+["","## Final Recommendation","","Configure missing resources or proceed with the exported bundle according to the decision above."]
    return payload,"\n".join(lines)+"\n"
def main(argv=None)->int:
    a=build_parser().parse_args(argv); load_dotenv(); profile=load_case_domain_profile(a.case_profile); policy=dict(profile.fulltext_policy or {})
    fulltext_enabled=not a.disable_fulltext_confirmation and (a.enable_fulltext_confirmation or bool(policy.get("enabled")) or "full_text_conflict_confirmation" in profile.validation_needs or profile.case_type=="conflict_enriched")
    try:frozen_metadata=json.loads(a.search_plan_file.read_text(encoding="utf-8"))
    except (OSError,json.JSONDecodeError):frozen_metadata={}
    discovery_mode=profile.case_type=="conflict_enriched" or frozen_metadata.get("discovery_planning_mode")=="neutral_discovery"
    discovery_requested=not a.disable_fulltext_discovery_escalation and (a.enable_fulltext_discovery_escalation or (fulltext_enabled and discovery_mode))
    readiness=check_case_readiness(a.case_profile,a.search_plan_file,a.external_data_root,network_allowed=a.network); write_readiness_report(readiness)
    source=[sys.executable,"-m","code_engine.cli.run","--query",profile.query,"--execute",
      "--api" if a.api else "--no-api", "--network" if a.network else "--no-network",
      "--allow-uncertain-intake","--l1-provider",os.getenv("L1_PROVIDER","<L1_PROVIDER>"),"--l1-model",os.getenv("MODEL_NAME","<MODEL_NAME>"),"--enable-conflict-timeline","--enable-evidence-graph","--no-cross-batch-paper-cache","--l1-read-timeout-seconds",str(a.l1_read_timeout_seconds),"--l1-max-retries",str(a.l1_max_retries),"--temporal-role",a.temporal_role,"--max-papers",str(a.max_papers),"--until","report","--search-plan-file",str(a.search_plan_file),"--fail-if-search-plan-drift","--diversify-acquisition","--json"]
    suffix=a.output_run_suffix or f"{profile.case_id}_clean_domain_routed_lincs_v1"
    def rebuild(run): return [sys.executable,"-m","code_engine.cli.run","--rebuild-from-run",str(run),"--rebuild-stages","l4,l5,l6,l7,report","--output-run-suffix",suffix,"--case-profile",str(a.case_profile),"--external-data-root",str(a.external_data_root),"--json"]
    if a.dry_run:
        print("SOURCE_COMMAND: "+" ".join(source)); print("REBUILD_COMMAND: "+" ".join(rebuild("<NEW_SOURCE_RUN_DIR>")))
        print("selected_validators = "+json.dumps(readiness["routing"]["selected_validators"])); print("recommended_but_unavailable = "+json.dumps(readiness["routing"]["recommended_but_unavailable"])); print("fulltext_plan = "+json.dumps({"enabled":fulltext_enabled,"discovery_escalation_requested":discovery_requested,"discovery_mode":discovery_mode,"source":a.fulltext_source,"selection_policy":"relevance_first_oa_aware","discovery_selection_policy":"anchored_reviewable_and_weak_conflict","max_papers":a.fulltext_max_papers,"max_sections_per_paper":a.fulltext_max_sections_per_paper,"max_chunks_per_paper":a.fulltext_max_chunks_per_paper,"max_total_chunks":a.fulltext_max_total_chunks,"l1_extractor_connected":True,"l1_planned":fulltext_enabled and a.api,"include_near_conflicts":a.fulltext_include_near_conflicts,"skip_non_oa":True,"publisher_scraping":False})); print("expected_outputs = "+json.dumps(list(FINAL_ARTIFACTS))); print("CASE_RUN_DRY_RUN")
        return 0
    if a.stop_after_readiness: print("CASE_RUN_PASS" if readiness["ready"] else "CASE_RUN_BLOCKED"); return 0 if readiness["ready"] else 2
    if not readiness["ready"]:
        decision="CASE_RUN_BLOCKED"; payload,md=_audit(profile,decision,readiness)
        if not a.no_write_audit:
            root=Path("audit_reports"); root.mkdir(exist_ok=True); (root/f"{profile.case_id}_run_case_audit.json").write_text(json.dumps(payload,ensure_ascii=False,indent=2)+"\n"); (root/f"{profile.case_id}_run_case_audit.md").write_text(md)
        print(decision); print("blocking_reasons = "+json.dumps(readiness["blocking_reasons"])); return 2
    failure_reason=None
    try:
        current_phase="source_run"
        first=subprocess.run(source,check=True,text=True,capture_output=True); source_data=json.loads(first.stdout.strip().splitlines()[-1]); source_run=Path(source_data["run_dir"])
        current_phase="final_run"
        second=subprocess.run(rebuild(source_run),check=True,text=True,capture_output=True); final_data=json.loads(second.stdout.strip().splitlines()[-1]); final_run=Path(final_data["run_dir"])
        from code_engine.validation.production_v1_runner import run_production_v1_validators
        run_production_v1_validators(final_run,a.case_profile,a.search_plan_file,readiness["routing"]["selected_validators"],network_enabled=a.network,unavailable=readiness["routing"]["recommended_but_unavailable"])
        from code_engine.fulltext.stage import run_l35_pmc_oa_stage
        from code_engine.fulltext.discovery_escalation import discovery_escalation_expected,finalize_discovery_escalation,prepare_discovery_escalation
        from code_engine.extraction.client_factory import build_l1_client_from_env_or_config
        fulltext_client=build_l1_client_from_env_or_config(os.getenv("L1_PROVIDER"),os.getenv("MODEL_NAME"),read_timeout_seconds=a.fulltext_l1_read_timeout_seconds,max_retries=a.fulltext_l1_max_retries) if a.api and fulltext_enabled else None
        discovery_counts=json.loads((final_run/"artifacts/discovery_filter_summary.json").read_text(encoding="utf-8")) if (final_run/"artifacts/discovery_filter_summary.json").is_file() else {}
        discovery_online=bool(discovery_requested and a.network);prepared=prepare_discovery_escalation(final_run,enabled=discovery_online)
        expected=discovery_escalation_expected(fulltext_enabled=fulltext_enabled,network_enabled=a.network,discovery_mode=discovery_mode,
            weak_count=int(discovery_counts.get("weak_conflict_candidate_count",0)),escalation_count=int(discovery_counts.get("fulltext_escalation_candidate_count",0)),reviewable_count=int(discovery_counts.get("reviewable_graph_observation_count",0)),explicitly_disabled=a.disable_fulltext_discovery_escalation)
        shared_fulltext=run_l35_pmc_oa_stage(final_run,enabled=fulltext_enabled,network_enabled=a.network,api_enabled=a.api,max_papers=a.fulltext_max_papers,include_near_conflicts=a.fulltext_include_near_conflicts,l1_client=fulltext_client,l1_provider=os.getenv("L1_PROVIDER"),l1_model=os.getenv("MODEL_NAME"),max_sections_per_paper=a.fulltext_max_sections_per_paper,max_chunks_per_paper=a.fulltext_max_chunks_per_paper,max_chars_per_chunk=a.fulltext_max_chars_per_chunk,max_total_chunks=a.fulltext_max_total_chunks,l1_read_timeout_seconds=a.fulltext_l1_read_timeout_seconds,l1_max_retries=a.fulltext_l1_max_retries)
        strict_count=sum(1 for x in (final_run/"artifacts/graph_conflict_candidates.jsonl").read_text(encoding="utf-8").splitlines() if x.strip()) if (final_run/"artifacts/graph_conflict_candidates.jsonl").is_file() else 0
        discovery_fulltext=finalize_discovery_escalation(final_run,prepared=prepared,expected=expected,explicitly_disabled=a.disable_fulltext_discovery_escalation,shared_summary=shared_fulltext,strict_conflict_count=strict_count)
        missing=[x for x in FINAL_ARTIFACTS if not (final_run/"artifacts"/x).is_file()]
        bundle,manifest=export_case_bundle(final_run,a.case_profile,a.output_case_bundle_root); warnings=[f"missing final artifact: {x}" for x in missing]+[f"validator unavailable: {x}" for x in readiness["routing"]["recommended_but_unavailable"]]+list(discovery_fulltext.get("warnings",[]))
        decision="CASE_RUN_PASS" if not warnings else "CASE_RUN_PASS_WITH_WARNINGS"
        failure_reason=None; missing_final=None; blocked_req=None
        if a.fail_if_required_validator_unavailable and readiness["routing"]["blocked_required_validators"]:
            blocked_req=list(readiness["routing"]["blocked_required_validators"])
            decision="CASE_RUN_FAIL"; failure_reason="blocked_required_validators"
        if missing:
            missing_final=list(missing)
            decision="CASE_RUN_FAIL"; failure_reason=failure_reason or "missing_final_artifacts"
        kwargs={"failure_reason":failure_reason} if failure_reason else {}
        if missing_final: kwargs["missing_final_artifacts"]=missing_final
        if blocked_req: kwargs["blocked_required_validators"]=blocked_req
        payload,md=_audit(profile,decision,readiness,source_run,final_run,bundle,manifest,warnings,**kwargs)
    except subprocess.CalledProcessError as exc:
        tb=traceback.format_exc()
        child_stdout=(exc.stdout or "") if isinstance(exc.stdout,str) else ""
        child_stderr=(exc.stderr or "") if isinstance(exc.stderr,str) else ""
        child_cmd=[str(x) for x in (exc.cmd if isinstance(exc.cmd,list) else [str(exc.cmd)])]
        stdout_lines=child_stdout.splitlines(); stderr_lines=child_stderr.splitlines()
        child_stdout_tail=stdout_lines[-80:] if len(stdout_lines)>80 else stdout_lines
        child_stderr_tail=stderr_lines[-120:] if len(stderr_lines)>120 else stderr_lines
        tb_lines=tb.splitlines(); tb_tail=tb_lines[-30:] if len(tb_lines)>30 else tb_lines
        decision="CASE_RUN_FAIL"; failure_reason="child_process_failed"
        if child_stderr: print(child_stderr,file=sys.stderr)
        print(tb,file=sys.stderr)
        payload,md=_audit(profile,decision,readiness,warnings=[str(exc)],
            failure_reason="child_process_failed",exception_type=type(exc).__name__,
            exception_message=str(exc),traceback_tail=tb_tail,
            child_phase=current_phase if "current_phase" in dir() else "unknown",
            child_return_code=exc.returncode,child_command=child_cmd,
            child_stdout_tail=child_stdout_tail,child_stderr_tail=child_stderr_tail)
        source_run=final_run=bundle=None; manifest={}
        print(f"failure_reason = child_process_failed",file=sys.stderr)
        print(f"child_phase = {current_phase if 'current_phase' in dir() else 'unknown'}",file=sys.stderr)
        print(f"child_return_code = {exc.returncode}",file=sys.stderr)
        # Also emit to stdout for CASE_RUN_FAIL output visibility
        print(f"failure_reason = child_process_failed")
        print(f"child_phase = {current_phase if 'current_phase' in dir() else 'unknown'}")
        print(f"child_return_code = {exc.returncode}")
        if child_stderr_tail:
            print("child_stderr_tail =")
            for line in child_stderr_tail[:20]: print(f"  {line}")
    except Exception as exc:
        tb=traceback.format_exc()
        print(tb,file=sys.stderr)
        tb_lines=tb.splitlines()
        tb_tail=tb_lines[-30:] if len(tb_lines)>30 else tb_lines
        decision="CASE_RUN_FAIL"; failure_reason="exception"
        payload,md=_audit(profile,decision,readiness,warnings=[str(exc)],
            failure_reason="exception",exception_type=type(exc).__name__,
            exception_message=str(exc),traceback_tail=tb_tail)
        source_run=final_run=bundle=None; manifest={}
        print(f"failure_reason = exception",file=sys.stderr)
        print(f"exception_type = {type(exc).__name__}",file=sys.stderr)
        print(f"exception_message = {str(exc)}",file=sys.stderr)
    if not a.no_write_audit:
        root=Path("audit_reports"); root.mkdir(exist_ok=True); (root/f"{profile.case_id}_run_case_audit.json").write_text(json.dumps(payload,ensure_ascii=False,indent=2)+"\n"); (root/f"{profile.case_id}_run_case_audit.md").write_text(md)
    print(decision); print(f"source_run = {source_run}"); print(f"final_run = {final_run}"); print(f"case_bundle = {bundle}"); print("executed_validators = "+json.dumps(manifest.get("executed_validators",[]))); print("recommended_but_unavailable = "+json.dumps(readiness["routing"]["recommended_but_unavailable"]))
    if failure_reason: print(f"failure_reason = {failure_reason}")
    return 0 if decision.startswith("CASE_RUN_PASS") else 1
if __name__ == "__main__": raise SystemExit(main())
