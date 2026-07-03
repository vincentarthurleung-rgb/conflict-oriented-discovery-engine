"""CLI for offline multi-case System B ingestion."""

from __future__ import annotations

import argparse

from code_engine.system_b.batch_ingest import SystemBBatchIngestor


def main() -> int:
    parser = argparse.ArgumentParser(description="Ingest multiple exported case bundles into System B")
    parser.add_argument("--bundle-root", required=True)
    parser.add_argument("--output-root", required=True)
    parser.add_argument("--registry", required=True)
    parser.add_argument("--include-preserved")
    parser.add_argument("--case-glob", default="*")
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--strict", action="store_true")
    parser.add_argument("--write-markdown", action="store_true")
    parser.add_argument("--write-csv", action="store_true")
    args = parser.parse_args()
    roots = [args.bundle_root] + ([args.include_preserved] if args.include_preserved else [])
    try:
        result = SystemBBatchIngestor().run(roots, args.output_root, args.registry, args.case_glob, args.overwrite, args.strict, args.write_markdown, args.write_csv)
    except (OSError, ValueError) as error:
        print("SYSTEM_B_BATCH_INGEST_FAIL")
        print(f"error = {error}")
        return 1
    summary = result["summary"]
    print("SYSTEM_B_BATCH_INGEST_PASS")
    print(f"case_count = {summary['case_count']}")
    print(f"ready_count = {summary['ready_count']}")
    print(f"warning_count = {result['warning_count']}")
    print(f"registry = {args.registry}")
    print(f"comparison_table = {args.output_root}/case_comparison_table.json")
    print(f"validator_matrix = {args.output_root}/validator_coverage_matrix.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
