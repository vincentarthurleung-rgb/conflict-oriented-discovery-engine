"""Bounded concurrent runner for modern generated case packages."""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable


def _now(): return datetime.now(timezone.utc).isoformat()
def _write(path:Path,value:Any):
    path.parent.mkdir(parents=True,exist_ok=True); path.write_text(json.dumps(value,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
def _read(path:Path,default=None):
    try:return json.loads(path.read_text(encoding="utf-8"))
    except (OSError,json.JSONDecodeError):return default


def build_parser():
    p=argparse.ArgumentParser(description="Run generated modern case packages with safe bounded concurrency.")
    p.add_argument("--generated-case-root",type=Path,default=Path("configs/generated_cases")); p.add_argument("--case-ids")
    p.add_argument("--case-inventory",type=Path); p.add_argument("--external-data-root",type=Path,default=Path("data/external"))
    p.add_argument("--api",action=argparse.BooleanOptionalAction,default=False); p.add_argument("--network",action=argparse.BooleanOptionalAction,default=False)
    p.add_argument("--enable-fulltext-confirmation",action="store_true"); p.add_argument("--max-workers",type=int,default=1)
    p.add_argument("--l1-concurrency",type=int,default=1); p.add_argument("--pubmed-concurrency",type=int,default=1); p.add_argument("--validator-concurrency",type=int,default=1)
    p.add_argument("--case-start-stagger-seconds",type=float,default=0); p.add_argument("--max-retries",type=int,default=0); p.add_argument("--retry-backoff-seconds",type=float,default=30)
    p.add_argument("--resume",action="store_true"); p.add_argument("--overwrite-bundles",action="store_true"); p.add_argument("--allow-degraded-intake",action="store_true")
    p.add_argument("--allow-narrow-discovery-plan",action="store_true")
    p.add_argument("--fail-fast",action="store_true"); p.add_argument("--dry-run",action="store_true"); p.add_argument("--output-root",type=Path,required=True)
    return p


def _case_ids(args)->list[str]:
    values=[x.strip() for x in (args.case_ids or "").split(",") if x.strip()]
    if args.case_inventory:
        data=_read(args.case_inventory,{})
        rows=data if isinstance(data,list) else data.get("case_ids") or data.get("results") or []
        values += [str(x.get("case_id")) if isinstance(x,dict) else str(x) for x in rows]
    return list(dict.fromkeys(x for x in values if x and x!="None"))


def _status_template(case_id:str,package:Path,root:Path)->dict:
    return {"case_id":case_id,"status":"queued","case_profile":str(package/"case_profile.json"),
        "search_plan":str(package/"search_plan.frozen.json"),"case_bundle":str(root/"bundles"/case_id),
        "started_at":None,"finished_at":None,"duration_seconds":0,"return_code":None,
        "stdout_log":str(root/"logs"/f"{case_id}.stdout.log"),"stderr_log":str(root/"logs"/f"{case_id}.stderr.log"),
        "executed_validators":[],"scientific_output_class":None,"graph_observation_count":0,
        "core_observation_count":0,"true_graph_conflict_count":0,"formal_hypothesis_count":0,"warnings":[]}


def _summary(batch_id:str,statuses:list[dict])->dict:
    counts={name:sum(item["status"]==name for item in statuses) for name in ("queued","running","completed","failed","blocked","skipped")}
    return {"schema_version":"run_case_batch_status_v1","batch_id":batch_id,"total_cases":len(statuses),
        **{f"{name}_count":count for name,count in counts.items()},"case_statuses":statuses,"updated_at":_now()}


def run_case_batch(args, *, subprocess_runner:Callable[...,Any]=subprocess.run)->dict:
    if args.max_workers<1 or min(args.l1_concurrency,args.pubmed_concurrency,args.validator_concurrency)<1: raise ValueError("concurrency values must be >= 1")
    case_ids=_case_ids(args)
    if not case_ids: raise ValueError("provide --case-ids or --case-inventory with at least one case")
    root=args.output_root; (root/"logs").mkdir(parents=True,exist_ok=True); (root/"cases").mkdir(parents=True,exist_ok=True)
    batch_id=root.name; lock=threading.Lock(); stop=threading.Event()
    warnings=[]
    if args.api and args.network and args.max_workers>4: warnings.append("api_network_max_workers_above_4_rate_limit_risk")
    effective=args.max_workers
    if args.api or args.network:
        effective=min(effective,args.l1_concurrency,args.pubmed_concurrency,args.validator_concurrency)
        if effective<args.max_workers: warnings.append(f"effective_api_case_concurrency_limited_to_{effective}")
    statuses=[]
    for case_id in case_ids:
        package=args.generated_case_root/case_id; item=_status_template(case_id,package,root); prior=_read(root/"cases"/f"{case_id}.status.json",{})
        if args.resume and prior.get("status") in {"completed","skipped"}: item=prior
        statuses.append(item)
    def persist(item=None):
        with lock:
            if item:_write(root/"cases"/f"{item['case_id']}.status.json",item)
            _write(root/"batch_status.json",_summary(batch_id,statuses))
    persist()
    manifest={"schema_version":"run_case_batch_manifest_v1","batch_id":batch_id,"created_at":_now(),"case_ids":case_ids,
        "generated_case_root":str(args.generated_case_root),"external_data_root":str(args.external_data_root),"requested_max_workers":args.max_workers,
        "effective_max_workers":effective,"l1_concurrency":args.l1_concurrency,"pubmed_concurrency":args.pubmed_concurrency,
        "validator_concurrency":args.validator_concurrency,"dry_run":args.dry_run,"resume":args.resume,"warnings":warnings}
    _write(root/"batch_manifest.json",manifest)
    def execute(item):
        if item["status"] in {"completed","skipped"}: return item
        if stop.is_set(): item.update(status="skipped",finished_at=_now(),warnings=["fail_fast_cancelled"]); persist(item); return item
        package=args.generated_case_root/item["case_id"]; factory=_read(package/"case_factory_manifest.json",{})
        missing=[name for name in ("case_profile.json","search_plan.frozen.json") if not (package/name).is_file()]
        degraded=not factory.get("semantic_intake_valid",True) or factory.get("seed_triple_quality")=="invalid"
        narrow=(factory.get("case_type")=="conflict_enriched" and
                (factory.get("discovery_query_balance_valid") is False or factory.get("one_sided_retrieval_risk")=="high"))
        if missing or (degraded and not args.allow_degraded_intake) or (narrow and not args.allow_narrow_discovery_plan):
            reason=("missing package files: "+", ".join(missing) if missing else
                    "case_factory_semantic_quality_blocked" if degraded and not args.allow_degraded_intake else
                    "case_factory_discovery_planning_quality_blocked")
            item.update(status="blocked",finished_at=_now(),return_code=2,warnings=[reason]); persist(item); return item
        bundle=root/"bundles"/item["case_id"]
        if bundle.exists() and not args.overwrite_bundles:
            item.update(status="skipped",finished_at=_now(),return_code=0,warnings=["case_bundle_already_exists"]); persist(item); return item
        if bundle.exists() and args.overwrite_bundles: shutil.rmtree(bundle)
        item.update(status="running",started_at=_now()); persist(item); started=time.monotonic()
        command=[sys.executable,"-m","code_engine.cli.run_case","--case-profile",item["case_profile"],"--search-plan-file",item["search_plan"],
            "--external-data-root",str(args.external_data_root),"--output-case-bundle-root",str(root/"bundles")]
        command += ["--api"] if args.api else []; command += ["--network"] if args.network else []
        command += ["--enable-fulltext-confirmation"] if args.enable_fulltext_confirmation else []
        command += ["--dry-run"] if args.dry_run else []
        Path(item["stdout_log"]).write_text("COMMAND: "+" ".join(command)+"\n",encoding="utf-8"); Path(item["stderr_log"]).write_text("",encoding="utf-8")
        if args.case_start_stagger_seconds: time.sleep(args.case_start_stagger_seconds)
        result=None
        for attempt in range(args.max_retries+1):
            result=subprocess_runner(command,text=True,capture_output=True)
            with Path(item["stdout_log"]).open("a",encoding="utf-8") as h:h.write(result.stdout or "")
            with Path(item["stderr_log"]).open("a",encoding="utf-8") as h:h.write(result.stderr or "")
            if result.returncode==0:break
            if attempt<args.max_retries:time.sleep(args.retry_backoff_seconds*(2**attempt))
        bundle_manifest=_read(bundle/"case_bundle_manifest.json",{}) if not args.dry_run else {}
        ok=result is not None and result.returncode==0
        item.update(status="completed" if ok else "failed",finished_at=_now(),duration_seconds=round(time.monotonic()-started,3),
            return_code=result.returncode if result else 1,executed_validators=bundle_manifest.get("executed_validators",[]),
            scientific_output_class=bundle_manifest.get("scientific_output_class"),graph_observation_count=bundle_manifest.get("graph_observation_count",0),
            core_observation_count=bundle_manifest.get("core_observation_count",0),true_graph_conflict_count=bundle_manifest.get("true_graph_conflict_count",0),
            formal_hypothesis_count=bundle_manifest.get("formal_hypothesis_count",0),warnings=["dry_run_no_execution"] if args.dry_run else bundle_manifest.get("bundle_export_warnings",[]))
        if not ok and args.fail_fast:stop.set()
        persist(item); return item
    with ThreadPoolExecutor(max_workers=effective,thread_name_prefix="run-case") as pool:
        futures=[pool.submit(execute,item) for item in statuses]
        for future in as_completed(futures): future.result()
    result=_summary(batch_id,statuses); _write(root/"batch_status.json",result)
    lines=["# Run Case Batch Report","",f"- Batch: `{batch_id}`",f"- Total cases: {len(statuses)}",f"- Effective workers: {effective}",
        f"- Completed: {result['completed_count']}",f"- Failed: {result['failed_count']}",f"- Blocked: {result['blocked_count']}",f"- Skipped: {result['skipped_count']}","","## Cases",""]
    lines += [f"- `{x['case_id']}`: {x['status']}" for x in statuses]
    (root/"batch_report.md").write_text("\n".join(lines)+"\n",encoding="utf-8")
    return result


def main(argv=None):
    args=build_parser().parse_args(argv)
    try: result=run_case_batch(args)
    except (ValueError,OSError) as exc: print(json.dumps({"status":"RUN_CASE_BATCH_BLOCKED","error":str(exc)})); return 2
    print(json.dumps(result,ensure_ascii=False,indent=2)); return 1 if result["failed_count"] else 2 if result["blocked_count"] else 0


if __name__=="__main__":raise SystemExit(main())
