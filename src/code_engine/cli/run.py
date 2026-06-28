"""Command-line entry point for reproducible end-to-end runs."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from code_engine.workflow.models import STEP_ORDER
from code_engine.workflow.orchestrator import run_workflow


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the C.O.D.E. research workflow")
    parser.add_argument("--query")
    parser.add_argument("--resume", type=Path)
    parser.add_argument("--run-dir", type=Path)
    parser.add_argument("--until", choices=STEP_ORDER, default="report")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--dry-run", action="store_true")
    mode.add_argument("--execute", action="store_true")
    api = parser.add_mutually_exclusive_group()
    api.add_argument("--api", action="store_true")
    api.add_argument("--no-api", action="store_true")
    network = parser.add_mutually_exclusive_group()
    network.add_argument("--network", action="store_true")
    network.add_argument("--no-network", action="store_true")
    parser.add_argument("--max-papers", type=int)
    parser.add_argument("--allow-legacy", action="store_true")
    parser.add_argument("--json", action="store_true", dest="json_output")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if not args.resume and not args.query:
        build_parser().error("--query is required unless --resume is used")
    state = run_workflow(query=args.query or "", run_dir=args.run_dir, until=args.until, execute=args.execute, api=args.api, network=args.network, max_papers=args.max_papers, resume=args.resume, allow_legacy=args.allow_legacy)
    directory = args.resume.resolve() if args.resume else (args.run_dir.resolve() if args.run_dir else Path("runs") / state.run_id)
    if args.json_output:
        print(json.dumps({"run_id": state.run_id, "run_dir": str(directory), "mode": state.mode, "api_calls_made": state.api_calls_made, "network_calls_made": state.network_calls_made, "final_status": state.final_status, "report": str(directory / "run_report.md")}, ensure_ascii=False))
    else:
        print(f"Run ID: {state.run_id}")
        print(f"Run dir: {directory}")
        print(f"Mode: {state.mode}")
        print(f"API calls: {state.api_calls_made}")
        print(f"Network calls: {state.network_calls_made}")
        print(f"Final status: {state.final_status}")
        print(f"Report: {directory / 'run_report.md'}")
        for warning in state.warnings:
            if "execute=false" in warning:
                print(f"Warning: {warning}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
