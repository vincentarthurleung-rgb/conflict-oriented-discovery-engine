"""User-facing offline replay from existing L1 artifacts through discovery bundle export."""
from __future__ import annotations
import argparse,json,os,shutil
from datetime import datetime
from pathlib import Path
from code_engine.cli.replay_case_from_stage import replay

def replay_fulltext_discovery(a,profile,plan,suffix):
    source=a.source_run.resolve();target=Path("runs")/f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{a.case_id}_{a.case_version}"
    if target.exists():raise FileExistsError(target)
    shutil.copytree(source,target)
    from code_engine.discovery.lanes import build_discovery_lanes
    discovery=build_discovery_lanes(target)["summary"]
    from code_engine.fulltext.discovery_escalation import discovery_escalation_expected,finalize_discovery_escalation,prepare_discovery_escalation
    from code_engine.fulltext.stage import run_l35_pmc_oa_stage
    from code_engine.extraction.client_factory import build_l1_client_from_env_or_config
    expected=discovery_escalation_expected(fulltext_enabled=True,network_enabled=a.network,discovery_mode=True,
        weak_count=discovery["weak_conflict_candidate_count"],escalation_count=discovery["fulltext_escalation_candidate_count"],reviewable_count=discovery["reviewable_graph_observation_count"])
    prepared=prepare_discovery_escalation(target,enabled=a.network)
    client=build_l1_client_from_env_or_config(os.getenv("L1_PROVIDER"),os.getenv("MODEL_NAME"),read_timeout_seconds=240,max_retries=1) if a.api else None
    shared=run_l35_pmc_oa_stage(target,enabled=True,network_enabled=a.network,api_enabled=a.api,max_papers=a.fulltext_max_papers,
        l1_client=client,l1_provider=os.getenv("L1_PROVIDER"),l1_model=os.getenv("MODEL_NAME"),max_sections_per_paper=a.fulltext_max_sections_per_paper,
        max_total_chunks=a.fulltext_max_total_chunks)
    strict=sum(bool(x.strip()) for x in (target/"artifacts/graph_conflict_candidates.jsonl").read_text().splitlines()) if (target/"artifacts/graph_conflict_candidates.jsonl").is_file() else 0
    summary=finalize_discovery_escalation(target,prepared=prepared,expected=expected,explicitly_disabled=False,shared_summary=shared,strict_conflict_count=strict)
    from code_engine.cli.export_case_bundle import export_case_bundle
    bundle,manifest=export_case_bundle(target,profile,a.output_bundle.parent,bundle_id_suffix=suffix,overwrite_bundle=a.overwrite_bundle,
        manifest_overrides={"case_version":a.case_version,"is_replay_run":True,"replay_from_stage":"fulltext_discovery","llm_used":bool(a.api),"network_used":bool(a.network)})
    return {"case_id":a.case_id,"case_version":a.case_version,"source_run":str(source),"new_run":str(target),"bundle":str(bundle),
        "network_used":bool(a.network),"llm_used":bool(a.api),**summary}

def main(argv=None):
    p=argparse.ArgumentParser(description="Replay downstream stages, including optional online fulltext discovery.")
    p.add_argument("--case-id",required=True);p.add_argument("--source-run",type=Path,required=True)
    p.add_argument("--from-stage",choices=("l2","l3","l6","bundle","fulltext_discovery"),default="l2");p.add_argument("--to-stage",choices=("bundle",),default="bundle")
    p.add_argument("--case-version",required=True);p.add_argument("--output-bundle",type=Path,required=True)
    p.add_argument("--no-llm",action="store_true");p.add_argument("--no-network",action="store_true");p.add_argument("--api",action="store_true");p.add_argument("--network",action="store_true");p.add_argument("--overwrite-bundle",action="store_true")
    p.add_argument("--fulltext-max-papers",type=int,default=20);p.add_argument("--fulltext-max-sections-per-paper",type=int,default=12);p.add_argument("--fulltext-max-total-chunks",type=int,default=200)
    a=p.parse_args(argv)
    profile=Path("configs/generated_cases")/a.case_id/"case_profile.json";plan=Path("configs/generated_cases")/a.case_id/"search_plan.frozen.json"
    if not profile.is_file() or not plan.is_file():print(json.dumps({"status":"REPLAY_BLOCKED","error":"generated case profile or frozen plan missing"}));return 2
    expected=a.case_id+"__";suffix=a.output_bundle.name[len(expected):] if a.output_bundle.name.startswith(expected) else a.case_version
    if a.from_stage=="fulltext_discovery":
        result=replay_fulltext_discovery(a,profile,plan,suffix)
    else:
        result=replay(profile,plan,a.source_run,a.from_stage,"runs",a.case_version,suffix,no_l1=True,network=False,
            skip_fulltext=True,skip_l7=True,overwrite_bundle=a.overwrite_bundle,bundle_root=a.output_bundle.parent,case_version=a.case_version)
    print(json.dumps(result,ensure_ascii=False,indent=2));return 0

if __name__=="__main__":raise SystemExit(main())
