"""Offline coverage loop that plans updates without executing ingestion or APIs."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any, Literal

from pydantic import Field

from code_engine.hypothesis.hyperedge_builder import build_hypothesis_hyperedge
from code_engine.query.answer import assemble_query_answer
from code_engine.query.coverage import analyze_coverage
from code_engine.query.models import ResearchQuery
from code_engine.query.parser import parse_research_query
from code_engine.query.planner import plan_incremental_ingestion
from code_engine.schemas.models import CODEBaseModel


NextAction = Literal[
    "answer_from_existing_graph", "run_delta_ingestion_plan", "request_user_budget",
    "wait_for_new_evidence", "manual_review_required",
]


class DryLabLoopState(CODEBaseModel):
    loop_id: str
    query_id: str
    coverage_verdict: str
    current_graph_version: str = "local_json_graph_v1"
    hypotheses: list[dict[str, Any]] = Field(default_factory=list)
    missing_evidence: list[str] = Field(default_factory=list)
    delta_ingestion_plan: dict[str, Any] = Field(default_factory=dict)
    validation_plan: list[str] = Field(default_factory=list)
    next_action: NextAction
    api_calls_made: int = 0
    status: str = "planned"


def plan_dry_lab_loop(
    query: str | ResearchQuery,
    *,
    inventory: dict[str, Any] | None = None,
    knowledge_store: dict[str, Any] | None = None,
    budget: dict[str, int] | None = None,
    repository_root: str | Path = ".",
) -> DryLabLoopState:
    """Plan a closed dry-lab iteration using local deterministic components only."""

    parsed = query if isinstance(query, ResearchQuery) else parse_research_query(query)
    coverage = analyze_coverage(
        parsed,
        inventory=inventory,
        knowledge_store=knowledge_store,
        repository_root=repository_root,
        write_outputs=False,
    )
    sufficient = coverage.verdict == "Sufficient_No_Update_Needed"
    partial = coverage.verdict == "Partial_Coverage_Delta_Update_Recommended"
    plan = None if sufficient else plan_incremental_ingestion(
        parsed,
        coverage,
        budget=budget,
        inventory=inventory,
        repository_root=repository_root,
        write_outputs=False,
    )
    assemble_query_answer(parsed, coverage, plan=plan, repository_root=repository_root, write_outputs=False)
    hyperedges = []
    if sufficient or partial:
        for hypothesis in coverage.hypotheses:
            hyperedges.append(build_hypothesis_hyperedge(
                hypothesis,
                conflict_edges=coverage.conflict_edges,
                validation_results=coverage.validation_results,
                coverage_verdict=coverage.verdict,
                seed_query=parsed.raw_query,
            ).model_dump())
    next_action: NextAction
    if sufficient:
        next_action = "answer_from_existing_graph"
    elif plan and plan.budget_status == "over_budget":
        next_action = "request_user_budget"
    elif partial:
        next_action = "run_delta_ingestion_plan"
    else:
        next_action = "wait_for_new_evidence"
    validation_plan = list(dict.fromkeys(
        requirement for item in hyperedges for requirement in item.get("validation_requirements", [])
    ))
    loop_key = f"{parsed.query_id}|{coverage.verdict}|{coverage.coverage_score}"
    return DryLabLoopState(
        loop_id=hashlib.sha256(loop_key.encode()).hexdigest()[:16],
        query_id=parsed.query_id,
        coverage_verdict=coverage.verdict,
        hypotheses=hyperedges,
        missing_evidence=coverage.missing_dimensions,
        delta_ingestion_plan=plan.model_dump() if plan else {},
        validation_plan=validation_plan,
        next_action=next_action,
        api_calls_made=0,
        status="planned_no_execution",
    )

