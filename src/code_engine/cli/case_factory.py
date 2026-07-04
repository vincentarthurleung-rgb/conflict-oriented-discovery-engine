"""CLI for generating one modern case package from natural language."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from code_engine.case_factory import generate_case_package
from code_engine.validation.external_api_smoke import load_dotenv


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Generate a run_case-compatible case profile and frozen search plan.")
    parser.add_argument("--case-id", required=True); parser.add_argument("--query", required=True)
    parser.add_argument("--case-type", default="conflict_enriched")
    parser.add_argument("--year-from", type=int); parser.add_argument("--year-to", type=int)
    parser.add_argument("--output-root", type=Path, default=Path("configs/generated_cases"))
    parser.add_argument("--api", action=argparse.BooleanOptionalAction, default=False)
    parser.add_argument("--network", action=argparse.BooleanOptionalAction, default=False)
    parser.add_argument("--freeze-search-plan", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--run-readiness", action="store_true"); parser.add_argument("--copy-to-configs", action="store_true")
    parser.add_argument("--overwrite-generated", action="store_true"); parser.add_argument("--overwrite-configs", action="store_true")
    parser.add_argument("--allow-degraded-intake", action="store_true")
    parser.add_argument("--seed-confidence-threshold", type=float, default=0.6)
    parser.add_argument("--repository-root", type=Path, default=Path("."))
    return parser


def main(argv=None) -> int:
    args = build_parser().parse_args(argv); load_dotenv()
    try:
        result = generate_case_package(case_id=args.case_id, query=args.query, case_type=args.case_type,
            year_from=args.year_from, year_to=args.year_to, output_root=args.output_root, api=args.api,
            network=args.network, freeze_search_plan=args.freeze_search_plan, run_readiness=args.run_readiness,
            copy_to_configs=args.copy_to_configs, overwrite_generated=args.overwrite_generated,
            overwrite_configs=args.overwrite_configs, repository_root=args.repository_root,
            allow_degraded_intake=args.allow_degraded_intake, seed_confidence_threshold=args.seed_confidence_threshold)
    except (FileExistsError, RuntimeError, ValueError) as exc:
        print(json.dumps({"status": "CASE_FACTORY_BLOCKED", "error": str(exc)}, ensure_ascii=False)); return 2
    print(json.dumps(result, ensure_ascii=False, indent=2)); return 2 if result["status"] == "CASE_FACTORY_BLOCKED_SEMANTIC_INTAKE" else 0


if __name__ == "__main__": raise SystemExit(main())
