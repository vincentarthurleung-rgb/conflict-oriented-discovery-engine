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

def _rows(path):
    try:return [json.loads(x) for x in Path(path).read_text(encoding="utf-8").splitlines() if x.strip()]
    except (OSError,json.JSONDecodeError):return []

def _write_rows(path,rows):Path(path).write_text("".join(json.dumps(x,ensure_ascii=False)+"\n" for x in rows),encoding="utf-8")

def replay_fulltext_l1(a,profile,suffix):
    source_bundle=a.source_bundle.resolve();manifest=json.loads((source_bundle/"case_bundle_manifest.json").read_text(encoding="utf-8"))
    prior_summary=json.loads((source_bundle/"l35_fulltext_discovery_escalation_summary.json").read_text(encoding="utf-8")) if (source_bundle/"l35_fulltext_discovery_escalation_summary.json").is_file() else {}
    source=Path(manifest.get("final_run_dir") or "").resolve()
    if not (source/"artifacts/fulltext/pmc_oa").is_dir():raise FileNotFoundError("source bundle does not reference a cached parsed-fulltext run")
    target=Path("runs")/f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{a.case_id}_{a.case_version}"
    shutil.copytree(source,target);artifacts=target/"artifacts"
    from code_engine.extraction.client_factory import build_l1_client_from_env_or_config
    from code_engine.fulltext.fulltext_l1_extractor import run_fulltext_l1_extraction
    provider=os.getenv("L1_PROVIDER","");model=os.getenv("MODEL_NAME","")
    client=build_l1_client_from_env_or_config(provider,model,read_timeout_seconds=240,max_retries=1) if a.api else None
    result=run_fulltext_l1_extraction(run_dir=target,fulltext_candidates_path=artifacts/"l35_fulltext_oa_candidate_papers.jsonl",parsed_articles_dir=artifacts/"fulltext/pmc_oa",
        l1_provider=provider,l1_model=model,api_enabled=a.api,network_enabled=a.network,max_papers=a.fulltext_max_papers,max_sections_per_paper=a.fulltext_max_sections_per_paper,
        max_total_chunks=int(prior_summary.get("selected_chunk_count") or a.fulltext_max_total_chunks),client=client,read_timeout_seconds=240,max_retries=1,reuse_selected_chunks=True)
    claims=result["claims"];executions=result["chunks"];l1_records=_rows(artifacts/"l35_fulltext_l1_execution_records.jsonl")
    by_pmcid={}
    for row in l1_records:by_pmcid.setdefault(str(row.get("pmcid")),[]).append(row)
    candidate_records=_rows(artifacts/"l35_fulltext_discovery_execution_records.jsonl")
    for row in candidate_records:
        items=by_pmcid.get(str(row.get("pmcid")),[]);paper_claims=[x for x in claims if str(x.get("pmcid"))==str(row.get("pmcid"))]
        if items:
            attempted=sum(bool(x.get("fulltext_l1_attempted")) for x in items);failed=sum(x.get("fulltext_l1_status")=="failed" for x in items)
            row.update(selected_chunk_count=len(items),fulltext_l1_attempted=bool(attempted),fulltext_l1_status="failed" if failed else "success" if attempted else "skipped",
                fulltext_l1_error="fulltext_l1_provider_unavailable" if not attempted else "fulltext_l1_execution_failed" if failed else None,fulltext_l1_claim_count=len(paper_claims),
                final_status="l1_completed" if paper_claims else "no_claims" if attempted and not failed else "failed",blocking_reason=None if paper_claims else "fulltext_l1_no_claims" if attempted and not failed else "fulltext_l1_provider_unavailable" if not attempted else "fulltext_l1_execution_failed")
    _write_rows(artifacts/"l35_fulltext_discovery_execution_records.jsonl",candidate_records)
    from code_engine.fulltext.discovery_escalation import finalize_discovery_escalation,prepare_discovery_escalation
    prepared=prepare_discovery_escalation(target,enabled=True);shared=json.loads((artifacts/"l35_fulltext_conflict_confirmation_summary.json").read_text())
    shared.update(fulltext_l1_claim_count=len(claims),fulltext_l1_status=result["summary"]["fulltext_l1_status"])
    summary=finalize_discovery_escalation(target,prepared=prepared,expected=True,explicitly_disabled=False,shared_summary=shared,strict_conflict_count=0)
    from code_engine.cli.export_case_bundle import export_case_bundle
    bundle,_=export_case_bundle(target,profile,a.output_bundle.parent,bundle_id_suffix=suffix,overwrite_bundle=a.overwrite_bundle,
        manifest_overrides={"case_version":a.case_version,"is_replay_run":True,"replay_from_stage":"fulltext_l1","llm_used":bool(a.api),"network_used":bool(a.network)})
    return {"case_id":a.case_id,"case_version":a.case_version,"source_bundle":str(source_bundle),"source_run":str(source),"new_run":str(target),"bundle":str(bundle),**result["summary"],**summary}

def replay_weak_conflict(a,profile,suffix):
    source_bundle=a.source_bundle.resolve();manifest=json.loads((source_bundle/"case_bundle_manifest.json").read_text(encoding="utf-8"));source=Path(manifest.get("final_run_dir") or "").resolve()
    target=Path("runs")/f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{a.case_id}_{a.case_version}";shutil.copytree(source,target);artifacts=target/"artifacts"
    from code_engine.fulltext.fulltext_l1_extractor import SECTION_WEIGHTS
    for name in ("l35_fulltext_l1_claims.jsonl","l35_fulltext_discovery_l1_claims.jsonl"):
        rows=_rows(artifacts/name)
        for row in rows:
            tier=row.get("section_type") or "other";row["section_evidence_tier"]=tier;row["section_evidence_weight"]=SECTION_WEIGHTS.get(tier,.25)
        _write_rows(artifacts/name,rows)
    from code_engine.fulltext.discovery_escalation import finalize_discovery_escalation,prepare_discovery_escalation
    prepared=prepare_discovery_escalation(target,enabled=True);shared=json.loads((artifacts/"l35_fulltext_conflict_confirmation_summary.json").read_text())
    summary=finalize_discovery_escalation(target,prepared=prepared,expected=True,explicitly_disabled=False,shared_summary=shared,strict_conflict_count=0)
    from code_engine.cli.export_case_bundle import export_case_bundle
    bundle,_=export_case_bundle(target,profile,a.output_bundle.parent,bundle_id_suffix=suffix,overwrite_bundle=a.overwrite_bundle,
        manifest_overrides={"case_version":a.case_version,"is_replay_run":True,"replay_from_stage":"weak_conflict","llm_used":False,"network_used":False})
    return {"case_id":a.case_id,"case_version":a.case_version,"source_bundle":str(source_bundle),"source_run":str(source),"new_run":str(target),"bundle":str(bundle),**summary}

def main(argv=None):
    p=argparse.ArgumentParser(description="Replay downstream stages, including optional online fulltext discovery.")
    p.add_argument("--case-id",required=True);p.add_argument("--source-run",type=Path);p.add_argument("--source-bundle",type=Path)
    p.add_argument("--from-stage",choices=("l2","l3","l6","bundle","fulltext_discovery","fulltext_l1","weak_conflict"),default="l2");p.add_argument("--to-stage",choices=("bundle",),default="bundle")
    p.add_argument("--case-version",required=True);p.add_argument("--output-bundle",type=Path,required=True)
    p.add_argument("--no-llm",action="store_true");p.add_argument("--no-network",action="store_true");p.add_argument("--api",action="store_true");p.add_argument("--network",action="store_true");p.add_argument("--overwrite-bundle",action="store_true")
    p.add_argument("--fulltext-max-papers",type=int,default=20);p.add_argument("--fulltext-max-sections-per-paper",type=int,default=12);p.add_argument("--fulltext-max-total-chunks",type=int,default=200)
    a=p.parse_args(argv)
    from code_engine.validation.external_api_smoke import load_dotenv
    load_dotenv()
    profile=Path("configs/generated_cases")/a.case_id/"case_profile.json";plan=Path("configs/generated_cases")/a.case_id/"search_plan.frozen.json"
    if not profile.is_file() or not plan.is_file():print(json.dumps({"status":"REPLAY_BLOCKED","error":"generated case profile or frozen plan missing"}));return 2
    expected=a.case_id+"__";suffix=a.output_bundle.name[len(expected):] if a.output_bundle.name.startswith(expected) else a.case_version
    if a.from_stage=="weak_conflict":
        if not a.source_bundle:p.error("--source-bundle is required for --from-stage weak_conflict")
        result=replay_weak_conflict(a,profile,suffix)
    elif a.from_stage=="fulltext_l1":
        if not a.source_bundle:p.error("--source-bundle is required for --from-stage fulltext_l1")
        result=replay_fulltext_l1(a,profile,suffix)
    elif a.from_stage=="fulltext_discovery":
        if not a.source_run:p.error("--source-run is required for --from-stage fulltext_discovery")
        result=replay_fulltext_discovery(a,profile,plan,suffix)
    else:
        if not a.source_run:p.error("--source-run is required for this replay stage")
        result=replay(profile,plan,a.source_run,a.from_stage,"runs",a.case_version,suffix,no_l1=True,network=a.network,api=a.api,
            skip_fulltext=True,skip_l7=True,overwrite_bundle=a.overwrite_bundle,bundle_root=a.output_bundle.parent,case_version=a.case_version)
    print(json.dumps(result,ensure_ascii=False,indent=2));return 0

if __name__=="__main__":raise SystemExit(main())
