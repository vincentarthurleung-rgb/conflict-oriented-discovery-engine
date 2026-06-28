"""Budget-aware dry-run planner for incremental local corpus processing."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict

from code_engine.query.models import CoverageReport, IngestionPlan, ResearchQuery
from code_engine.acquisition.manifest import find_unprocessed_papers_for_query, load_artifact_inventory


DEFAULT_CHUNKS_PER_UNKNOWN_PAPER = 1


def _search_queries(query: ResearchQuery, coverage: CoverageReport) -> list[str]:
    subject, obj = query.normalized_subject, query.normalized_object
    queries = [" ".join(item for item in (subject, obj) if item)]
    if subject and obj:
        queries.append(f"{subject} {obj} mechanism")
    neighbor_entities = []
    for edge in coverage.neighbor_edges:
        neighbor_entities.extend((edge.get("subject"), edge.get("object")))
    for entity in neighbor_entities:
        if entity and entity not in {subject, obj}:
            queries.append(f"{subject} {entity}")
            break
    return list(dict.fromkeys(item for item in queries if item.strip()))


def _write_plan(plan: IngestionPlan, root: Path) -> None:
    data_path = root / f"data/query/ingestion_plan_{plan.query_id}.json"
    report_path = root / f"reports/ingestion_plan_{plan.query_id}.md"
    data_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    data_path.write_text(plan.model_dump_json(indent=2), encoding="utf-8")
    lines = [
        "# Incremental Ingestion Plan",
        "",
        "This is a dry-run plan. No literature search or LLM call was executed.",
        "",
        f"- Query ID: {plan.query_id}",
        f"- Papers needing Stage1: {len(plan.papers_need_stage1)}",
        f"- Papers needing L1: {len(plan.papers_need_l1)}",
        f"- Papers needing L1.5: {len(plan.papers_need_l1_5)}",
        f"- Estimated new chunks: {plan.estimated_new_chunks}",
        f"- Estimated API calls: {plan.estimated_api_calls}",
        f"- Budget status: {plan.budget_status}",
        f"- Runtime data status: {plan.runtime_data_status}",
        f"- Using legacy data: {str(plan.using_legacy_data).lower()}",
        "",
        "## Recommended Search Queries",
        "",
    ]
    lines.extend(f"- {item}" for item in plan.search_queries)
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def plan_incremental_ingestion(
    query: ResearchQuery,
    coverage: CoverageReport,
    dry_run: bool = True,
    budget: Dict[str, int] | None = None,
    *,
    inventory: Dict[str, Any] | None = None,
    repository_root: str | Path = ".",
    write_outputs: bool = True,
) -> IngestionPlan:
    """Plan only; update execution is intentionally outside this MVP."""

    active = (
        inventory if inventory is not None
        else load_artifact_inventory(repository_root=repository_root)
    )
    relevant = find_unprocessed_papers_for_query(query, active)
    papers = active.get("papers", [])
    existing = [paper for paper in papers if paper in relevant]
    need_stage1 = [paper for paper in relevant if paper.get("raw_available") and not paper.get("stage1_payload_available")]
    need_l1 = [paper for paper in relevant if paper.get("stage1_payload_available") and not paper.get("l1_extracted")]
    need_l1_5 = [paper for paper in relevant if paper.get("l1_extracted") and not paper.get("l1_5_refined")]
    estimated_chunks = sum(int(paper.get("chunk_count") or DEFAULT_CHUNKS_PER_UNKNOWN_PAPER) for paper in need_l1)
    estimated_calls = estimated_chunks
    limits = {
        "max_new_papers": (budget or {}).get("max_new_papers"),
        "max_api_calls": (budget or {}).get("max_api_calls"),
        "max_chunks": (budget or {}).get("max_chunks"),
    }
    over_budget = any(
        limit is not None and actual > limit
        for actual, limit in (
            (0, limits["max_new_papers"]),
            (estimated_calls, limits["max_api_calls"]),
            (estimated_chunks, limits["max_chunks"]),
        )
    )
    effective_dry_run = True  # Update execution is intentionally unavailable in this MVP.
    plan = IngestionPlan(
        query_id=query.query_id,
        search_queries=_search_queries(query, coverage),
        existing_papers=existing,
        candidate_new_papers=[],
        duplicate_papers=active.get("duplicate_groups", []),
        papers_need_stage1=need_stage1,
        papers_need_l1=need_l1,
        papers_need_l1_5=need_l1_5,
        estimated_new_chunks=estimated_chunks,
        estimated_api_calls=estimated_calls,
        budget_limit=limits,
        budget_status="over_budget" if over_budget else "within_budget",
        recommended_action=("reduce_scope_or_increase_budget" if over_budget else "review_dry_run_plan"),
        dry_run=effective_dry_run,
        runtime_data_status=str(active.get("runtime_data_status", "unknown")),
        using_legacy_data=bool(active.get("using_legacy_data", False)),
    )
    if write_outputs:
        _write_plan(plan, Path(repository_root))
    return plan
