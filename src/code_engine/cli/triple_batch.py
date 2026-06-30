"""CLI for isolated seed-triple batches."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from code_engine.batch.triple_runner import run_triple_batch
from code_engine.corpus.io import iter_jsonl
from code_engine.corpus.paper_artifact_cache import DEFAULT_PAPER_ARTIFACT_CACHE_INDEX
from code_engine.workflow.models import STEP_ORDER


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run a dry-run/no-network triple-first batch")
    parser.add_argument("--triples", type=Path, required=True, help="JSONL seed triples")
    parser.add_argument("--batch-dir", type=Path, required=True)
    parser.add_argument("--batch-id")
    parser.add_argument("--resume", action="store_true")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--execute", action="store_true")
    mode.add_argument("--dry-run", action="store_true")
    api = parser.add_mutually_exclusive_group()
    api.add_argument("--api", action="store_true")
    api.add_argument("--no-api", action="store_true")
    network = parser.add_mutually_exclusive_group()
    network.add_argument("--network", action="store_true")
    network.add_argument("--no-network", action="store_true")
    parser.add_argument("--l1-mode", choices=("abstract_screening", "progressive_fulltext"), default="abstract_screening")
    parser.add_argument("--enable-fulltext-escalation", action="store_true")
    parser.add_argument("--enable-conflict-timeline", action="store_true", default=True)
    parser.add_argument("--enable-evidence-graph", action="store_true", default=True)
    parser.add_argument("--pilot-profile", choices=("ketamine",))
    parser.add_argument("--l1-provider", choices=("deepseek", "openai"))
    parser.add_argument("--l1-model")
    parser.add_argument("--max-papers", type=int)
    parser.add_argument("--until", choices=STEP_ORDER, default="report")
    parser.add_argument("--allow-uncertain-intake", action="store_true")
    cache = parser.add_mutually_exclusive_group()
    cache.add_argument("--enable-paper-artifact-cache", action="store_true", default=True)
    cache.add_argument("--no-cross-batch-paper-cache", action="store_true")
    parser.add_argument("--paper-artifact-cache-index", type=Path, default=DEFAULT_PAPER_ARTIFACT_CACHE_INDEX)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    l1_client = None
    if args.execute and args.api:
        from code_engine.extraction.client_factory import build_l1_client_from_env_or_config
        l1_client = build_l1_client_from_env_or_config(args.l1_provider, args.l1_model)
    result = run_triple_batch(
        list(iter_jsonl(args.triples)), args.batch_dir,
        batch_id=args.batch_id,
        resume=args.resume,
        paper_artifact_cache_enabled=args.enable_paper_artifact_cache and not args.no_cross_batch_paper_cache,
        paper_artifact_cache_index=args.paper_artifact_cache_index,
        execute=args.execute, api=args.api, network=args.network,
        workflow_kwargs={"until": args.until, "l1_mode": args.l1_mode,
                         "enable_fulltext_escalation": args.enable_fulltext_escalation,
                         "enable_conflict_timeline": args.enable_conflict_timeline,
                         "enable_evidence_graph": args.enable_evidence_graph,
                         "pilot_profile": args.pilot_profile, "max_papers": args.max_papers,
                         "allow_uncertain_intake": args.allow_uncertain_intake,
                         "l1_llm_client": l1_client, "semantic_llm_client": l1_client,
                         "merge_knowledge_store": False},
    )
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
