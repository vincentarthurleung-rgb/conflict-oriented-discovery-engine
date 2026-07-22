"""Plan or explicitly execute the bounded Prompt v7 authoritative-anchor smoke."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from code_engine.fulltext.fulltext_l1_v3_smoke import execute_v3_smoke, write_v3_plan_artifacts


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Audit and plan the frozen five-block Fulltext L1 v3 provider smoke.")
    parser.add_argument("--run-dir", required=True, type=Path)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--plan-only", action="store_true", help="Offline default: write only the v3 manifest and preflight.")
    mode.add_argument("--execute", action="store_true", help="Execute only the frozen five-block v3 manifest.")
    parser.add_argument("--api", action="store_true", help="Second authorization required with --execute.")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser(); args = parser.parse_args(argv)
    if args.api and not args.execute: parser.error("--api is valid only with --execute")
    if args.execute and not args.api: parser.error("real provider smoke requires --execute --api")
    result = execute_v3_smoke(args.run_dir, api_authorized=True) if args.execute else write_v3_plan_artifacts(args.run_dir)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
