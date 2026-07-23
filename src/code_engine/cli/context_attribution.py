from __future__ import annotations

import argparse
import json
from pathlib import Path

from code_engine.context_attribution.runner import run_context_attribution

def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser(description="Plan or run evidence-grounded two-stage L4 context attribution.")
    value.add_argument("--input-run", required=True, type=Path, help="Existing case/run directory.")
    value.add_argument("--output-run", required=True, type=Path, help="New, non-active output run directory.")
    value.add_argument("--mode", choices=("abstract-only", "fulltext-only", "combined"), default="combined")
    modes = value.add_mutually_exclusive_group()
    modes.add_argument("--abstract-only", action="store_true", help="Alias for --mode abstract-only.")
    modes.add_argument("--fulltext-only", action="store_true", help="Alias for --mode fulltext-only.")
    modes.add_argument("--combined", action="store_true", help="Alias for --mode combined.")
    value.add_argument("--domain-profiles", default="generic,biomedical", help="Comma-separated, composable profiles.")
    value.add_argument("--candidate-pair-allowlist", type=Path)
    value.add_argument("--purpose", choices=("smoke", "complete"), default="smoke",
                       help="Representative partial smoke plan or complete candidate coverage.")
    value.add_argument("--smoke-pair-count", type=int, default=5,
                       help="Deterministic representative pair target for smoke purpose.")
    value.add_argument("--max-extraction-calls", type=int, default=50)
    value.add_argument("--max-comparison-calls", type=int, default=50)
    value.add_argument("--provider", choices=("offline", "deepseek", "openai"), default="offline")
    value.add_argument("--model", default="offline-fixture")
    value.add_argument("--thinking-mode", choices=("enabled", "disabled", "provider_default"),
                       default="provider_default")
    value.add_argument("--execute", action="store_true", help="Execute cached/fixture work. Still no API unless --api is also set.")
    value.add_argument("--api", action="store_true", help="Permit provider calls; requires --execute.")
    value.add_argument("--resume", action="store_true")
    value.add_argument("--cached-only", action="store_true")
    value.add_argument("--fixture-responses", type=Path, help="Offline extraction/pair response JSON.")
    value.add_argument("--no-activation", action="store_true", default=True,
                       help="Required safety posture; this CLI never changes an active pointer.")
    return value

def main() -> None:
    args = parser().parse_args()
    selected_mode = "abstract-only" if args.abstract_only else "fulltext-only" if args.fulltext_only else "combined" if args.combined else args.mode
    allowlist = None
    if args.candidate_pair_allowlist:
        allowlist = {x.strip() for x in args.candidate_pair_allowlist.read_text(encoding="utf-8").splitlines() if x.strip()}
    result = run_context_attribution(
        input_run=args.input_run, output_run=args.output_run, mode=selected_mode,
        profiles=[x.strip() for x in args.domain_profiles.split(",") if x.strip()],
        provider=args.provider, model=args.model, execute=args.execute, api=args.api,
        cached_only=args.cached_only, resume=args.resume,
        extraction_limit=max(0, args.max_extraction_calls), comparison_limit=max(0, args.max_comparison_calls),
        allowlist=allowlist, fixture_responses=args.fixture_responses,
        purpose=args.purpose, smoke_pair_count=max(0, args.smoke_pair_count),
        thinking_mode=args.thinking_mode,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()
