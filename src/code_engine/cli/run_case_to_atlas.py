"""Thin CLI for reusable one-command System A -> Atlas orchestration."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from code_engine.orchestration import CaseToAtlasOrchestrator, CaseToAtlasRequest, OrchestrationError
from code_engine.orchestration.models import STAGES


def build_parser() -> argparse.ArgumentParser:
    parser=argparse.ArgumentParser(description="Run or resume one case from frozen package through Atlas verification")
    parser.add_argument("--case-id",required=True);parser.add_argument("--case-profile",type=Path);parser.add_argument("--search-plan-file",type=Path)
    parser.add_argument("--runs-root",type=Path,default=Path("runs"));parser.add_argument("--database-url",default="sqlite:///data/code_atlas.db");parser.add_argument("--system-b-output-root",type=Path,default=Path("system_b_outputs/system_a_sync"));parser.add_argument("--external-data-root",type=Path,default=Path("data/external"))
    parser.add_argument("--api",action=argparse.BooleanOptionalAction,default=False);parser.add_argument("--network",action=argparse.BooleanOptionalAction,default=False);parser.add_argument("--offline",action="store_true");parser.add_argument("--dry-run",action="store_true");parser.add_argument("--resume",action=argparse.BooleanOptionalAction,default=True)
    parser.add_argument("--force-stage",action="append",choices=STAGES,default=[]);parser.add_argument("--from-stage",choices=STAGES);parser.add_argument("--to-stage",choices=STAGES);parser.add_argument("--stop-after",choices=STAGES);parser.add_argument("--no-atlas-sync",action="store_true");parser.add_argument("--no-publish-handoff",action="store_true");parser.add_argument("--json",action="store_true",dest="json_output")
    return parser


def _request(args) -> CaseToAtlasRequest:
    return CaseToAtlasRequest(case_id=args.case_id,case_profile_path=args.case_profile,search_plan_path=args.search_plan_file,runs_root=args.runs_root,system_b_output_root=args.system_b_output_root,database_url=args.database_url,external_data_root=args.external_data_root,network_enabled=False if args.offline else args.network,api_enabled=False if args.offline else args.api,resume=args.resume,force_stages=frozenset(args.force_stage),from_stage=args.from_stage,to_stage=args.to_stage,stop_after=args.stop_after,publish_handoff=not args.no_publish_handoff,atlas_sync=not args.no_atlas_sync,dry_run=args.dry_run)


def main(argv=None) -> int:
    args=build_parser().parse_args(argv);orchestrator=CaseToAtlasOrchestrator()
    try:
        result=orchestrator.run(_request(args));payload=result.to_dict()
    except OrchestrationError as error:
        payload={"status":"failed","error_code":error.code,"error_summary":error.summary,"failed_stage":error.stage,"resume_from":error.resume_from}
        if args.json_output:print(json.dumps(payload,ensure_ascii=False,sort_keys=True))
        else:
            print("CASE_TO_ATLAS_FAILED");print(f"error_code: {error.code}");print(f"error_summary: {error.summary}")
            if error.resume_from:print(f"next_run_resumes_from: {error.resume_from}")
        return 2
    if args.json_output:print(json.dumps(payload,ensure_ascii=False,sort_keys=True))
    elif result.status=="dry_run":
        print("CASE_TO_ATLAS_DRY_RUN");plan=result.verification
        print(f"case_id: {result.case_id}");print(f"case_profile: {plan['case_profile']}");print(f"search_plan: {plan['frozen_search_plan']}")
        print("stages: "+", ".join(f"{x['stage']}={x['action']}" for x in plan["stages"]));print(f"base_run_action: {plan.get('base_run_recovery',{}).get('action')}");print(f"base_run_output: {plan.get('base_run_recovery',{}).get('output_run')}");print(f"next_stage: {plan.get('next_stage')}");print(f"abstract_l1_api_expected: {plan['abstract_l1_api_expected']}");print(f"fulltext_l1_api_expected: {plan['fulltext_l1_api_expected']}");print(f"reasoning_api_expected: {plan['reasoning_api_expected']}");print(f"reasoning_cache_hits: {plan['reasoning_cache_hits']}");print(f"context_consolidation_rebuild_expected: {plan['context_consolidation_rebuild_expected']}");print(f"current_projection_case_count: {plan['current_projection_case_count']}")
    else:
        print("CASE_TO_ATLAS_COMPLETED" if result.status=="completed" else "CASE_TO_ATLAS_STOPPED")
        for key in ("case_id","base_run","pmcid_repair_run","fulltext_run","reentry_run","handoff_status","sync_status","projection_id","current_case_count","claim_count","dossier_count","context_row_count","exploratory_triple_count","formal_conflict_count","api_calls","network_calls","cache_hits"):
            print(f"{key}: {getattr(result,key)}")
        print("reused_stages: "+json.dumps(result.reused_stages,ensure_ascii=False))
    return 0


if __name__=="__main__":raise SystemExit(main())
