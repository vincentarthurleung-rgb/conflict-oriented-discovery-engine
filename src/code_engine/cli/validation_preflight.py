"""CLI for read-only external validation preflight checks."""

import argparse

from code_engine.schemas.validation import ValidationResourcePolicy
from code_engine.validation.preflight import run_external_validation_preflight, write_preflight_report
from code_engine.validation.registry import ValidatorRegistry


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Audit external validation indexes and policy without executing queries")
    parser.add_argument("--validation-index-dir")
    parser.add_argument("--validation-cache-dir")
    parser.add_argument("--output-dir", default=".")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    policy = ValidationResourcePolicy(index_dir=args.validation_index_dir, cache_dir=args.validation_cache_dir)
    report = run_external_validation_preflight(args.validation_index_dir, args.validation_cache_dir, ValidatorRegistry().register_defaults(), policy)
    write_preflight_report(report, args.output_dir)
    print(report.model_dump_json(indent=2) if args.json else report.status)
    return 1 if report.status == "not_ready" else 0


if __name__ == "__main__":
    raise SystemExit(main())
