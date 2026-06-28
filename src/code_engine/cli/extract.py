"""Offline CLI for L1 v2 prompt compilation and extraction planning."""

from __future__ import annotations

import argparse
import json
from typing import Sequence

from code_engine.extraction.l1_extractor import build_l1_dry_run_plan, execute_l1_extraction
from code_engine.extraction.policy import (
    DEFAULT_L1_MODEL_FAMILY,
    DEFAULT_L1_MODEL_NAME,
    DEFAULT_L1_SCHEMA_VERSION,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build an L1 v2 extraction plan without implicit API calls.")
    parser.add_argument("--text", default="", help="Fixture/chunk text used for prompt compilation.")
    parser.add_argument("--paper-id", default="DRY_RUN")
    parser.add_argument("--chunk-id", default="chunk_0")
    parser.add_argument("--chunk-index", type=int, default=0)
    parser.add_argument("--domain", choices=("general_biomedical", "neuropharmacology"))
    parser.add_argument("--auto-domain", action="store_true")
    parser.add_argument("--prompt-profile", choices=("general_biomedical", "neuropharmacology"))
    parser.add_argument("--prompt-version", default="2.0")
    parser.add_argument("--schema-version", default=DEFAULT_L1_SCHEMA_VERSION)
    parser.add_argument("--model-name", default=DEFAULT_L1_MODEL_NAME)
    parser.add_argument("--model-family", default=DEFAULT_L1_MODEL_FAMILY)
    parser.add_argument("--cache-path", default="data/index/llm_cache_index.json")
    parser.add_argument("--dry-run", action="store_true", default=True)
    parser.add_argument("--no-api", action="store_true")
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--api", action="store_true")
    parser.add_argument("--repository-root", default=".")
    parser.add_argument("--allow-legacy-l1-reuse", action="store_true")
    parser.add_argument("--experimental-temperature-schedule", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.execute:
        result = execute_l1_extraction(
            [{"paper_id": args.paper_id, "chunk_id": args.chunk_id, "content": args.text}],
            repository_root=args.repository_root,
            execute=True,
            api=args.api and not args.no_api,
            domain=args.domain,
            auto_domain=args.auto_domain,
            prompt_profile=args.prompt_profile,
            prompt_version=args.prompt_version,
            schema_version=args.schema_version,
            model_name=args.model_name,
            model_family=args.model_family,
            experimental_temperature_schedule=args.experimental_temperature_schedule,
        )
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    plan = build_l1_dry_run_plan(
        args.text,
        paper_id=args.paper_id,
        chunk_id=args.chunk_id,
        chunk_index=args.chunk_index,
        domain=args.domain,
        auto_domain=args.auto_domain,
        prompt_profile=args.prompt_profile,
        prompt_version=args.prompt_version,
        schema_version=args.schema_version,
        model_name=args.model_name,
        model_family=args.model_family,
        experimental_temperature_schedule=args.experimental_temperature_schedule,
        cache_path=args.cache_path,
    )
    plan["allow_legacy_l1_reuse"] = args.allow_legacy_l1_reuse
    print(json.dumps(plan, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
