"""Safely archive case-specific run directories without deleting data."""

from __future__ import annotations

import argparse
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path


def cleanup_case_runs(*, case_slug: str, archive_root: str | Path = "runs_archive",
                      preserve_runs: list[str | Path] | None = None,
                      preserve_audits: list[str | Path] | None = None,
                      apply: bool = False, repository_root: str | Path = ".") -> dict:
    root = Path(repository_root).resolve(); runs = root / "runs"; timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    archive = root / archive_root / f"pre_clean_{case_slug}_{timestamp}"
    preserved = {Path(path).resolve() for path in (preserve_runs or [])}
    audit_paths = {Path(path).resolve() for path in (preserve_audits or [])}
    candidates = sorted(path for path in runs.iterdir() if path.is_dir() and case_slug in path.name)
    to_archive = [path for path in candidates if path.resolve() not in preserved]
    skipped = [str(path) for path in candidates if path.resolve() in preserved]
    skipped += [str(path) for path in audit_paths if not path.exists()]
    manifest = {"cleanup_mode":"archive_not_delete","dry_run":not apply,"timestamp":timestamp,
        "archive_dir":str(archive),"preserved_paths":sorted(str(path) for path in preserved|{path for path in audit_paths if path.exists()}),
        "archived_paths":[str(path) for path in to_archive],"skipped_paths":sorted(skipped),
        "external_data_preserved":True,"search_plan_preserved":True,"source_code_modified":False}
    reports=root/"cleanup_reports"; reports.mkdir(parents=True,exist_ok=True)
    plan=reports/f"{case_slug}_cleanup_plan_{timestamp}.md"; manifest_path=reports/f"{case_slug}_cleanup_manifest_{timestamp}.json"
    plan.write_text("# Case Run Cleanup Plan\n\n"+f"- Mode: `{'apply' if apply else 'dry-run'}`\n- Archive: `{archive}`\n\n## Archive candidates\n\n"+"".join(f"- `{path}`\n" for path in to_archive)+"\n## Preserved\n\n"+"".join(f"- `{path}`\n" for path in sorted(manifest["preserved_paths"])),encoding="utf-8")
    if apply:
        archive.mkdir(parents=True,exist_ok=False)
        moved=[]
        for source in to_archive:
            destination=archive/source.name; shutil.move(str(source),str(destination)); moved.append({"source":str(source),"destination":str(destination)})
        manifest["moves"]=moved
    manifest_path.write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding="utf-8")
    manifest["plan_path"],manifest["manifest_path"]=str(plan),str(manifest_path)
    return manifest


def main(argv:list[str]|None=None)->int:
    parser=argparse.ArgumentParser(); parser.add_argument("--case-slug",required=True); parser.add_argument("--archive-root",default="runs_archive")
    parser.add_argument("--preserve-run",action="append",default=[]); parser.add_argument("--preserve-audit",action="append",default=[])
    mode=parser.add_mutually_exclusive_group(); mode.add_argument("--dry-run",action="store_true"); mode.add_argument("--apply",action="store_true")
    args=parser.parse_args(argv); result=cleanup_case_runs(case_slug=args.case_slug,archive_root=args.archive_root,preserve_runs=args.preserve_run,preserve_audits=args.preserve_audit,apply=args.apply)
    print(json.dumps(result,ensure_ascii=False,indent=2)); return 0
if __name__=="__main__": raise SystemExit(main())
