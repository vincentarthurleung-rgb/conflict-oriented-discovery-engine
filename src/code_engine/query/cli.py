"""Command-line interface for offline query coverage and delta planning."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Sequence

from code_engine.query.answer import assemble_query_answer
from code_engine.query.coverage import analyze_coverage
from code_engine.query.parser import parse_research_query
from code_engine.query.planner import plan_incremental_ingestion
from code_engine.query.intent import parse_research_intent
from code_engine.query.l1_batch_planner import plan_l1_batch_for_intent
from code_engine.query.prompt_compatibility import build_required_fingerprint_for_intent
from code_engine.query.search_planner import build_literature_search_plan
from code_engine.acquisition.manifest import build_artifact_inventory, match_candidate_papers_to_inventory
from code_engine.graph.knowledge_store import build_knowledge_store


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Query local C.O.D.E. artifacts without implicit API calls.")
    parser.add_argument("--query", required=True)
    parser.add_argument("--mode", choices=("parse", "coverage", "plan", "answer", "intent", "search-plan", "l1-plan", "intake", "update"), default="answer")
    parser.add_argument("--dry-run", action="store_true", help="Retained explicitly for update planning.")
    parser.add_argument("--no-api", action="store_true", help="Explicitly document offline execution.")
    parser.add_argument("--max-new-papers", type=int)
    parser.add_argument("--max-api-calls", type=int)
    parser.add_argument("--max-chunks", type=int)
    parser.add_argument("--max-tokens", type=int)
    parser.add_argument("--candidate-papers", help="Optional fixture/mock candidate-paper JSON list; no search is executed.")
    parser.add_argument("--repository-root", default=".")
    parser.add_argument(
        "--legacy-source",
        help="Explicit archived repository root; never selected automatically.",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    root = Path(args.repository_root)
    source_root = Path(args.legacy_source) if args.legacy_source else root
    legacy_source = args.legacy_source is not None
    intake_modes = {"intent", "search-plan", "l1-plan", "intake", "update"}
    if args.mode in intake_modes:
        intent = parse_research_intent(args.query, output_root=root, write_output=True)
        if args.mode == "intent":
            print(intent.model_dump_json(indent=2))
            return 0
        candidates = []
        if args.candidate_papers:
            candidates = json.loads(Path(args.candidate_papers).read_text(encoding="utf-8"))
        search_plan = build_literature_search_plan(intent, candidate_papers=candidates, output_root=root, write_outputs=True)
        if args.mode == "search-plan":
            print(search_plan.model_dump_json(indent=2))
            return 0
        inventory = build_artifact_inventory(
            source_root,
            output_path=root / "data/index/artifact_inventory.json",
            audit_path=root / "reports/artifact_inventory_audit.md",
            allow_legacy_source=legacy_source,
        )
        match_report = match_candidate_papers_to_inventory(search_plan, inventory, output_root=root, write_outputs=True)
        fingerprint = build_required_fingerprint_for_intent(intent)
        budget = {
            key: value for key, value in {
                "max_new_papers": args.max_new_papers,
                "max_api_calls": args.max_api_calls,
                "max_tokens": args.max_tokens,
            }.items() if value is not None
        }
        l1_plan = plan_l1_batch_for_intent(
            intent,
            search_plan,
            inventory,
            fingerprint,
            dry_run=True,
            budget=budget,
            output_root=root,
            write_outputs=True,
        )
        if args.mode == "update":
            print("Update execution is not implemented in this MVP; generated dry-run L1 batch plan only.")
            print(l1_plan.model_dump_json(indent=2))
            return 0
        if args.mode == "l1-plan":
            print(l1_plan.model_dump_json(indent=2))
            return 0
        print(json.dumps({
            "intent": intent.model_dump(),
            "search_plan": search_plan.model_dump(),
            "candidate_match": match_report.model_dump(),
            "l1_batch_plan": l1_plan.model_dump(),
            "api_calls_made": 0,
        }, ensure_ascii=False, indent=2))
        return 0

    preferred = root / "configs/normalization/l2_l3_ontology_rules.json"
    legacy = root / "config/schemas/l2_l3_ontology_rules.json"
    query = parse_research_query(args.query, ontology_config_path=preferred if preferred.exists() else legacy)
    if args.mode == "parse":
        print(query.model_dump_json(indent=2))
        return 0

    inventory = build_artifact_inventory(
        source_root,
        output_path=root / "data/index/artifact_inventory.json",
        audit_path=root / "reports/artifact_inventory_audit.md",
        allow_legacy_source=legacy_source,
    )
    store = build_knowledge_store(
        source_root,
        output_path=root / "data/index/knowledge_store.json",
        allow_legacy_source=legacy_source,
    )
    coverage = analyze_coverage(query, inventory=inventory, knowledge_store=store, repository_root=root)
    if args.mode == "coverage":
        print(coverage.model_dump_json(indent=2))
        return 0

    budget = {
        key: value for key, value in {
            "max_new_papers": args.max_new_papers,
            "max_api_calls": args.max_api_calls,
            "max_chunks": args.max_chunks,
        }.items() if value is not None
    }
    plan = plan_incremental_ingestion(
        query,
        coverage,
        dry_run=True,
        budget=budget,
        inventory=inventory,
        repository_root=root,
    )
    if args.mode == "plan":
        print(plan.model_dump_json(indent=2))
        return 0

    answer = assemble_query_answer(query, coverage, plan=plan, repository_root=root)
    print(answer.model_dump_json(indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
