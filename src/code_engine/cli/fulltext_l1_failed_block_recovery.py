"""Plan or explicitly execute the frozen two-block Fulltext L1 recovery."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from code_engine.fulltext.failed_block_recovery import execute_recovery, write_recovery_plan


def main(argv: list[str] | None = None) -> int:
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir",type=Path,required=True)
    parser.add_argument("--output-run",type=Path)
    parser.add_argument("--execute",action="store_true")
    parser.add_argument("--api",action="store_true")
    args=parser.parse_args(argv)
    if args.execute != args.api:
        parser.error("paid execution requires both --execute and --api; omit both for plan-only")
    if args.execute:
        if args.output_run is None: parser.error("--output-run is required for execution and must match a prior plan")
        result=execute_recovery(args.run_dir,output_run=args.output_run,api_authorized=True)
    else:
        result=write_recovery_plan(args.run_dir,output_run=args.output_run)
    print(json.dumps(result,ensure_ascii=False,indent=2))
    return 0


if __name__=="__main__": raise SystemExit(main())
