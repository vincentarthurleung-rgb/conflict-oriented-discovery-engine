"""Explicit, assignment-free import of generated staging candidates into a pilot project."""
from __future__ import annotations
import argparse,hashlib,json
from pathlib import Path
from sqlalchemy import select
from code_engine.system_b.persistence.database import create_atlas_engine,session_factory,session_scope
from code_engine.system_b.persistence.models import EvaluationProject,ReviewItem
from code_engine.system_b.persistence.services.audit_service import write_audit_event

def _rows(root:Path):
    for filename,item_type in (("claim_review_candidates.jsonl","fulltext_l1_claim"),("conflict_pair_candidates.jsonl","conflict_pair"),("context_candidates.jsonl","context_attribution")):
        path=root/filename
        if not path.is_file():continue
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip():yield item_type,json.loads(line)

def main(argv=None)->int:
    p=argparse.ArgumentParser();p.add_argument("--staging-root",type=Path,required=True);p.add_argument("--project-id",required=True);p.add_argument("--database-url");p.add_argument("--split",default="unspecified");p.add_argument("--sampling-plan",default="all");p.add_argument("--apply",action="store_true");p.add_argument("--allow-production",action="store_true")
    a=p.parse_args(argv);rows=list(_rows(a.staging_root));factory=session_factory(create_atlas_engine(a.database_url))
    with session_scope(factory) as session:
        project=session.get(EvaluationProject,a.project_id)
        if not project:raise ValueError("project not found")
        if project.namespace!="pilot" and not a.allow_production:raise ValueError("staging import is limited to pilot unless --allow-production is explicit")
        project_namespace=project.namespace
        existing=set(session.execute(select(ReviewItem.review_item_id)).scalars());planned=[]
        for item_type,row in rows:
            item_id="stg_"+hashlib.sha256(row["source_key"].encode()).hexdigest()[:40]
            if item_id not in existing:planned.append((item_id,item_type,row))
        if a.apply:
            for item_id,item_type,row in planned:session.add(ReviewItem(review_item_id=item_id,case_id=row.get("case_id") or "",item_type=item_type,source_scope="system_a_staging",source_file=str(a.staging_root),source_line=None,payload_json=json.dumps(row,ensure_ascii=False,sort_keys=True),source_hash=hashlib.sha256(json.dumps(row,sort_keys=True,separators=(",",":"),ensure_ascii=False).encode()).hexdigest(),import_run_id="staging_"+hashlib.sha256(str(a.staging_root.resolve()).encode()).hexdigest()[:16],namespace=project.namespace))
            write_audit_event(session,action="evaluation_staging_imported",object_type="evaluation_project",object_id=project.project_id,project_id=project.project_id,metadata={"inserted":len(planned),"assignments_created":0,"split":a.split,"sampling_plan":a.sampling_plan})
    print(json.dumps({"status":"imported" if a.apply else "preview","project_id":a.project_id,"namespace":project_namespace,"candidates_seen":len(rows),"review_items_to_insert":len(planned),"assignments_created":0},indent=2));return 0
if __name__=="__main__":raise SystemExit(main())
