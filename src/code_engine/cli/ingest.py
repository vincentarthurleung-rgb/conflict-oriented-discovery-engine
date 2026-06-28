"""CLI for dynamic search-plan-driven literature acquisition."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Sequence

from code_engine.acquisition.literature_search import execute_acquisition_plan
from code_engine.query.intent import parse_research_intent
from code_engine.query.search_planner import LiteratureSearchPlan, build_literature_search_plan


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Plan or execute dynamic PMC/PubMed acquisition.")
    parser.add_argument("--query")
    parser.add_argument("--mode", default="intake")
    parser.add_argument("--search-plan")
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--network", action="store_true")
    parser.add_argument("--no-network", action="store_true")
    parser.add_argument("--max-papers", type=int, default=50)
    parser.add_argument("--source", choices=("pmc", "pubmed", "both"), default="both")
    parser.add_argument("--year-from", type=int)
    parser.add_argument("--year-to", type=int)
    parser.add_argument("--repository-root", default=".")
    args = parser.parse_args(argv)
    if args.search_plan:
        plan = LiteratureSearchPlan.model_validate_json(Path(args.search_plan).read_text(encoding="utf-8"))
    elif args.query:
        intent = parse_research_intent(args.query)
        plan = build_literature_search_plan(intent, output_root=args.repository_root, write_outputs=True)
    else:
        intent = parse_research_intent("ketamine depression antidepressant mechanism")
        plan = build_literature_search_plan(intent, output_root=args.repository_root, write_outputs=True)
        plan.warnings.append("legacy_ketamine_query_fallback_used")
    report = execute_acquisition_plan(
        plan, repository_root=args.repository_root,
        execute=args.execute, network=args.network and not args.no_network,
        source=args.source, max_papers=args.max_papers,
        year_from=args.year_from, year_to=args.year_to,
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
