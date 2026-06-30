"""CLI for isolated seed-triple batches."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from code_engine.batch.triple_runner import run_triple_batch
from code_engine.corpus.io import iter_jsonl
from code_engine.corpus.paper_artifact_cache import DEFAULT_PAPER_ARTIFACT_CACHE_INDEX


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run a dry-run/no-network triple-first batch")
    parser.add_argument("--triples", type=Path, required=True, help="JSONL seed triples")
    parser.add_argument("--batch-dir", type=Path, required=True)
    parser.add_argument("--batch-id")
    parser.add_argument("--resume", action="store_true")
    cache = parser.add_mutually_exclusive_group()
    cache.add_argument("--enable-paper-artifact-cache", action="store_true", default=True)
    cache.add_argument("--no-cross-batch-paper-cache", action="store_true")
    parser.add_argument("--paper-artifact-cache-index", type=Path, default=DEFAULT_PAPER_ARTIFACT_CACHE_INDEX)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    result = run_triple_batch(
        list(iter_jsonl(args.triples)), args.batch_dir,
        batch_id=args.batch_id,
        resume=args.resume,
        paper_artifact_cache_enabled=args.enable_paper_artifact_cache and not args.no_cross_batch_paper_cache,
        paper_artifact_cache_index=args.paper_artifact_cache_index,
        workflow_kwargs={"until": "report", "l1_mode": "abstract_screening", "merge_knowledge_store": False},
    )
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
