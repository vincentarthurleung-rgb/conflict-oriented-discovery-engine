"""Build a biomedical-only System B KG projection."""
from __future__ import annotations
import argparse
import json
from code_engine.system_b.clean_kg import build_clean_kg

def main(argv=None) -> int:
    parser = argparse.ArgumentParser(); parser.add_argument("--bundle-root", action="append", required=True); parser.add_argument("--output-root", required=True)
    parser.add_argument("--include-review-queue"); parser.add_argument("--max-chain-depth", type=int, default=3); parser.add_argument("--min-evidence-count", type=int, default=1)
    parser.add_argument("--write-jsonl", action=argparse.BooleanOptionalAction, default=True); parser.add_argument("--write-csv", action=argparse.BooleanOptionalAction, default=True); parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--max-display-entities", type=int, default=500); parser.add_argument("--max-display-triples", type=int, default=500); parser.add_argument("--max-display-chains", type=int, default=1500); parser.add_argument("--max-display-triples-per-case", type=int, default=150); parser.add_argument("--max-display-chains-per-case", type=int, default=300)
    args = parser.parse_args(argv); summary = build_clean_kg(args.bundle_root, args.output_root, max_chain_depth=args.max_chain_depth, min_evidence_count=args.min_evidence_count, include_review_queue=args.include_review_queue, write_jsonl=args.write_jsonl, write_csv=args.write_csv, overwrite=args.overwrite, max_display_entities=args.max_display_entities, max_display_triples=args.max_display_triples, max_display_chains=args.max_display_chains, max_display_triples_per_case=args.max_display_triples_per_case, max_display_chains_per_case=args.max_display_chains_per_case)
    print(json.dumps(summary, indent=2, ensure_ascii=False)); return 0

if __name__ == "__main__": raise SystemExit(main())
