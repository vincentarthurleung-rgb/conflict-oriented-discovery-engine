"""CLI for offline-first batch scientific problem discovery evaluation."""

from __future__ import annotations

import argparse
import json

from code_engine.evaluation.batch_discovery.batch_runner import run_batch_discovery


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run batch abstract conflict discovery evaluation")
    parser.add_argument("--prompt-bank", required=True)
    parser.add_argument("--run-dir")
    parser.add_argument("--max-prompts", type=int)
    parser.add_argument("--l1-mode", choices=("abstract_screening", "progressive_fulltext", "fulltext_oracle", "legacy"), default="abstract_screening")
    parser.add_argument("--sample-conflicts", type=int, default=300)
    parser.add_argument("--min-abstract-conflict-entropy", type=float, default=0.65)
    parser.add_argument("--min-abstract-evidence-count", type=int, default=3)
    parser.add_argument("--dry-run", action="store_true", default=True)
    parser.add_argument("--no-api", action="store_true")
    parser.add_argument("--no-network", action="store_true")
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--annotations")
    parser.add_argument("--external-validation", action="store_true")
    parser.add_argument("--no-external-validation", action="store_true")
    parser.add_argument("--validation-query-mode", choices=("auto", "local_index", "remote_api", "cache_only", "disabled"), default="auto")
    parser.add_argument("--validation-index-dir")
    parser.add_argument("--validation-cache-dir")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    result = run_batch_discovery(
        args.prompt_bank, run_dir=args.run_dir, max_prompts=args.max_prompts,
        l1_mode=args.l1_mode, sample_conflict_count=args.sample_conflicts,
        dry_run=True, api_enabled=False, network_enabled=False, resume=args.resume,
        min_evidence_count=args.min_abstract_evidence_count,
        min_entropy=args.min_abstract_conflict_entropy,
        annotations_path=args.annotations,
        external_validation=args.external_validation and not args.no_external_validation,
        validation_query_mode=args.validation_query_mode,
        validation_index_dir=args.validation_index_dir,
        validation_cache_dir=args.validation_cache_dir,
    )
    print(json.dumps({"run_dir": result["run_dir"], "metrics": result["metrics"], "api_calls_made": 0, "network_calls_made": 0}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
