"""Plan or explicitly execute the bounded Fulltext L1 v2 provider smoke."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from code_engine.fulltext.fulltext_l1_v2_smoke import execute_smoke, write_plan_artifacts


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Audit and plan a bounded Fulltext L1 v2 provider smoke test.")
    parser.add_argument("--run-dir", required=True, type=Path)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--plan-only", action="store_true", help="Offline default: write audit and planning artifacts only.")
    mode.add_argument("--execute", action="store_true", help="Execute only the saved 12-block smoke manifest.")
    parser.add_argument("--api", action="store_true", help="Second authorization required with --execute.")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser(); args = parser.parse_args(argv)
    if args.api and not args.execute:
        parser.error("--api is valid only with --execute")
    if args.execute and not args.api:
        parser.error("real provider smoke requires --execute --api")
    result = execute_smoke(args.run_dir, api_authorized=True) if args.execute else write_plan_artifacts(args.run_dir)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
