"""Discover and synchronize ready System A handoffs into Atlas."""
from __future__ import annotations
import argparse, json
from pathlib import Path
from code_engine.system_b.adapters import ADAPTER_VERSION
from code_engine.system_b.system_a_sync import sync_system_a

def main(argv=None) -> int:
    parser=argparse.ArgumentParser(description="Offline, idempotent System A to Atlas synchronization")
    parser.add_argument("--runs-root",type=Path,default=Path("runs"));parser.add_argument("--database-url");parser.add_argument("--output-root",type=Path,default=Path("system_b_outputs/system_a_sync"));parser.add_argument("--once",action="store_true",default=True);parser.add_argument("--dry-run",action="store_true");parser.add_argument("--manifest",type=Path);parser.add_argument("--batch-id");parser.add_argument("--adapter-version",default=ADAPTER_VERSION);parser.add_argument("--quarantine-root",type=Path);parser.add_argument("--no-database-write",action="store_true");parser.add_argument("--refresh-current-projection",action=argparse.BooleanOptionalAction,default=True)
    args=parser.parse_args(argv)
    result=sync_system_a(runs_root=args.runs_root,database_url=args.database_url,output_root=args.output_root,manifest=args.manifest,batch_id=args.batch_id,adapter_version=args.adapter_version,dry_run=args.dry_run,quarantine_root=args.quarantine_root,no_database_write=args.no_database_write,refresh_current_projection=args.refresh_current_projection)
    print(json.dumps(result,ensure_ascii=False,indent=2));return 0 if not result.get("rejected") else 2
if __name__=="__main__":raise SystemExit(main())
