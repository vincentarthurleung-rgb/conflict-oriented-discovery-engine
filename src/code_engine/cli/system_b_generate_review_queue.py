"""Generate System B manual-review artifacts from case bundles."""

from __future__ import annotations
import argparse
import json
from code_engine.system_b.review_queue import generate


def main(argv=None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--bundle-root", action="append", required=True)
    parser.add_argument("--output-root", required=True)
    parser.add_argument("--top-reviewable-per-case", type=int, default=20)
    parser.add_argument("--random-fulltext-claims-per-case", type=int, default=30)
    parser.add_argument("--low-priority-context-per-case", type=int, default=10)
    parser.add_argument("--include-all-weak-candidates", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--include-all-non-comparable-pairs", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--include-formal-hypotheses", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--write-csv", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--write-jsonl", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args(argv)
    result = generate(args.bundle_root, args.output_root, top_reviewable=args.top_reviewable_per_case,
        random_fulltext_claims=args.random_fulltext_claims_per_case, low_priority_context=args.low_priority_context_per_case,
        include_weak=args.include_all_weak_candidates, include_non_comparable=args.include_all_non_comparable_pairs,
        include_hypotheses=args.include_formal_hypotheses, seed=args.seed, write_csv=args.write_csv,
        write_jsonl=args.write_jsonl, overwrite=args.overwrite)
    print(json.dumps(result, indent=2, ensure_ascii=False)); return 0


if __name__ == "__main__":
    raise SystemExit(main())
