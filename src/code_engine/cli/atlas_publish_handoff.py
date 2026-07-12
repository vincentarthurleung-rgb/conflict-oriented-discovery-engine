"""Offline handoff replay/backfill with frozen source inventory outputs."""
from __future__ import annotations
import argparse, json
from pathlib import Path
from typing import Any
from code_engine.integration.atlas_handoff import HANDOFF_SCHEMA_VERSION, HandoffError, build_handoff_manifest, publish_atlas_handoff

BATCH11_WNT={"case_id":"wnt_beta_catenin_cancer_stemness_immunity_discovery_v1","base_run":"runs/20260709_163622_wnt_beta_catenin_cancer_stemness_immunity_discovery_v1_wnt_beta_catenin_cancer_stemness_immunity_discovery_v1_l2_cleaner_fulltext_replay","fulltext_l1_run":"runs/20260710_140752_wnt_beta_catenin_cancer_stemness_immunity_discovery_v1_wnt_bridge_authoritative_with_deepseek_l1","reentry_run":"runs/20260710_190642_wnt_beta_catenin_cancer_stemness_immunity_discovery_v1_wnt_fulltext_reentry_high_recall_v5","fulltext_l1_reused":True}

def _atomic_json(path:Path,value:Any):
    from code_engine.system_b.system_a_sync import _atomic_json
    _atomic_json(path,value)

def build_batch_inventory(batch_id:str,runs_root:Path)->dict:
    token=f"fulltext_reentry_high_recall_v5_{batch_id}"
    by_case={}
    for run in sorted(runs_root.glob(f"*{token}*")):
        source={}
        manifest=run/"fulltext_reentry_manifest.json"
        if manifest.is_file():
            try:source=json.loads(manifest.read_text())
            except json.JSONDecodeError:source={}
        case_id=source.get("case_id")
        if not case_id:
            replay=run/"artifacts/replay_manifest.json"
            try:case_id=json.loads(replay.read_text()).get("case_id")
            except (OSError,json.JSONDecodeError):pass
        candidate={"case_id":case_id or run.name,"base_run":source.get("base_run"),"fulltext_l1_run":source.get("fulltext_run"),"reentry_run":run.relative_to(runs_root.parent).as_posix(),"fulltext_l1_reused":True,"source_state":"completed" if source.get("status")=="completed" else "incomplete"}
        previous=by_case.get(candidate["case_id"])
        if not previous or (previous["source_state"]!="completed" and candidate["source_state"]=="completed") or (previous["source_state"]==candidate["source_state"] and candidate["reentry_run"]>previous["reentry_run"]):by_case[candidate["case_id"]]=candidate
    cases=sorted(by_case.values(),key=lambda row:row["case_id"])
    if batch_id=="batch11_20260710_203635" and not any(x.get("case_id")==BATCH11_WNT["case_id"] for x in cases):cases.insert(0,{**BATCH11_WNT,"source_state":"missing"})
    return {"schema_version":"atlas_source_inventory_v1","batch_id":batch_id,"case_count":len(cases),"cases":cases}

def main(argv=None)->int:
    p=argparse.ArgumentParser(description="Publish verified Atlas handoffs from existing System A runs")
    p.add_argument("--source-inventory",type=Path);p.add_argument("--batch-id");p.add_argument("--runs-root",type=Path,default=Path("runs"));p.add_argument("--snapshot-root",type=Path);p.add_argument("--backfill",action="store_true");p.add_argument("--offline",action="store_true");p.add_argument("--dry-run",action="store_true")
    a=p.parse_args(argv)
    if a.source_inventory:inventory=json.loads(a.source_inventory.read_text(encoding="utf-8"))
    elif a.batch_id:inventory=build_batch_inventory(a.batch_id,a.runs_root)
    else:p.error("--source-inventory or --batch-id is required")
    snapshot=a.snapshot_root or Path("data/system_a_snapshots")/str(inventory.get("batch_id") or "manual")
    if not a.dry_run:snapshot.mkdir(parents=True,exist_ok=True)
    results=[];hashes={};case_index=[]
    for item in inventory.get("cases",[]):
        run=Path(item.get("reentry_run") or "")
        if not run.is_absolute():run=a.runs_root.parent/run
        lineage={key:item.get(key) for key in ("base_run","pmcid_repair_run","fulltext_l1_run","reentry_run")}
        try:
            if a.dry_run:
                manifest=build_handoff_manifest(run,runs_root=a.runs_root,lineage=lineage);status="would_publish" if not (run/"artifacts/ATLAS_READY").is_file() else "existing_requires_validation"
                result={"status":status,"manifest":manifest,"manifest_hash_plan":manifest.get("configuration_hash")}
            else:result=publish_atlas_handoff(run,runs_root=a.runs_root,lineage=lineage)
            compact={"case_id":item.get("case_id"),"reentry_run":item.get("reentry_run"),"status":result["status"],"schema_version":HANDOFF_SCHEMA_VERSION,"lineage":result["manifest"]["lineage"],"counts":result["manifest"]["counts"],"manifest_hash":result.get("manifest_hash")}
            hashes[item.get("case_id") or run.name]={name:spec["sha256"] for name,spec in result["manifest"]["artifacts"].items()};case_index.append(compact);results.append(compact)
        except Exception as error:results.append({"case_id":item.get("case_id"),"reentry_run":item.get("reentry_run"),"status":"unsafe_or_incomplete","error_code":getattr(error,"code",type(error).__name__),"error_summary":str(error)})
    report={"schema_version":"atlas_backfill_validation_v1","batch_id":inventory.get("batch_id"),"dry_run":a.dry_run,"discovered_case_count":len(inventory.get("cases",[])),"publishable_count":sum(x["status"] in {"would_publish","published","no_op","existing_requires_validation"} for x in results),"unsafe_or_incomplete_count":sum(x["status"]=="unsafe_or_incomplete" for x in results),"results":results}
    if not a.dry_run:
        _atomic_json(snapshot/"source_inventory.json",inventory);_atomic_json(snapshot/"artifact_hashes.json",hashes);_atomic_json(snapshot/"validation_report.json",report)
        with (snapshot/"case_index.jsonl").open("w",encoding="utf-8") as handle:
            for row in case_index:handle.write(json.dumps(row,ensure_ascii=False,sort_keys=True)+"\n")
    print(json.dumps(report,ensure_ascii=False,indent=2));return 0 if not report["unsafe_or_incomplete_count"] else 2
if __name__=="__main__":raise SystemExit(main())
