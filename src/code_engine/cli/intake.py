"""End-to-end guarded natural-language intake orchestration."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Sequence

from code_engine.acquisition.literature_search import execute_acquisition_plan
from code_engine.extraction.l1_extractor import execute_l1_extraction
from code_engine.preprocessing.payload_builder import build_payloads_for_downloads
from code_engine.query.intake import parse_research_intake
from code_engine.query.search_planner import build_literature_search_plan


def run_intake_workflow(
    query: str,
    *,
    repository_root: str | Path = ".",
    execute: bool = False,
    api: bool = False,
    network: bool = False,
    max_papers: int = 30,
    llm_client: Any | None = None,
    literature_client: Any | None = None,
) -> dict[str, Any]:
    root = Path(repository_root)
    active_llm = llm_client
    if execute and api and active_llm is None:
        from code_engine.extraction.deepseek_client import DeepSeekClient
        active_llm = DeepSeekClient()
    intake = parse_research_intake(query, llm_client=active_llm, use_api=execute and api)
    search_plan = build_literature_search_plan(
        intake.research_intent,
        seed_triples=intake.seed_triples,
        llm_client=active_llm,
        use_llm=execute and api,
        output_root=root,
        write_outputs=True,
    )
    acquisition = execute_acquisition_plan(
        search_plan, repository_root=root, execute=execute,
        network=network and execute, max_papers=max_papers,
        client=literature_client,
    )
    chunks = build_payloads_for_downloads(acquisition["downloaded_papers"], root) if execute and network else []
    l1 = execute_l1_extraction(
        chunks, repository_root=str(root), execute=execute, api=api,
        client=active_llm, domain=intake.research_intent.domain_id,
    ) if chunks else {"chunks_reused": [], "chunks_extracted": [], "extraction_needed": [], "errors": [], "api_calls_made": 0}
    report = {
        "intent_id": intake.research_intent.intent_id,
        "parsed_intent": intake.research_intent.model_dump(),
        "seed_triples": [item.model_dump() for item in intake.seed_triples],
        "search_queries": [item.model_dump() for item in search_plan.pubmed_queries + search_plan.pmc_queries],
        "candidate_papers": acquisition["candidate_papers"],
        "downloaded_papers": acquisition["downloaded_papers"],
        "reused_papers": acquisition["reused_papers"],
        "l1_chunks_reused": l1["chunks_reused"],
        "l1_chunks_extracted": l1["chunks_extracted"],
        "l1_chunks_skipped_or_needed": l1["extraction_needed"],
        "api_calls_made": intake.api_calls_made + l1["api_calls_made"],
        "network_calls_made": acquisition["network_calls_made"],
        "next_recommended_command": (
            "rerun with --execute --api --network" if not execute
            else "run Stage3 refinement after reviewing acquired L1 claims"
        ),
    }
    data_path = root / f"data/query/intake_{intake.research_intent.intent_id}.json"
    md_path = root / f"reports/intake_{intake.research_intent.intent_id}.md"
    data_path.parent.mkdir(parents=True, exist_ok=True)
    md_path.parent.mkdir(parents=True, exist_ok=True)
    data_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(
        "# Intake Run Report\n\n"
        f"- Intent: {intake.research_intent.research_goal}\n"
        f"- Seed triples (not evidence): {len(intake.seed_triples)}\n"
        f"- Search queries: {len(report['search_queries'])}\n"
        f"- Downloaded papers: {len(report['downloaded_papers'])}\n"
        f"- L1 extracted claims: {len(report['l1_chunks_extracted'])}\n"
        f"- API calls: {report['api_calls_made']}\n"
        f"- Network calls: {report['network_calls_made']}\n"
        f"- Next: `{report['next_recommended_command']}`\n",
        encoding="utf-8",
    )
    return report


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run guarded natural-language literature intake.")
    parser.add_argument("--query", required=True)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--api", action="store_true")
    parser.add_argument("--no-api", action="store_true")
    parser.add_argument("--network", action="store_true")
    parser.add_argument("--no-network", action="store_true")
    parser.add_argument("--max-papers", type=int, default=30)
    parser.add_argument("--repository-root", default=".")
    args = parser.parse_args(argv)
    report = run_intake_workflow(
        args.query, repository_root=args.repository_root,
        execute=args.execute, api=args.api and not args.no_api,
        network=args.network and not args.no_network,
        max_papers=args.max_papers,
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
