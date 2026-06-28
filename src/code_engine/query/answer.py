"""Assemble evidence-bounded answers from existing local graph records."""

from __future__ import annotations

from pathlib import Path

from code_engine.query.models import CoverageReport, IngestionPlan, QueryAnswer, ResearchQuery


def _write_answer(answer: QueryAnswer, query: ResearchQuery, root: Path) -> None:
    data_path = root / f"data/query/query_answer_{query.query_id}.json"
    report_path = root / f"reports/query_answer_{query.query_id}.md"
    data_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    data_path.write_text(answer.model_dump_json(indent=2), encoding="utf-8")
    lines = [
        "# Query Answer",
        "",
        f"- Raw query: {query.raw_query}",
        f"- Normalized pair: {query.normalized_subject} -> {query.normalized_object}",
        f"- Coverage verdict: {answer.coverage_verdict}",
        f"- Answer mode: {answer.answer_mode}",
        f"- API calls made: {answer.api_calls_made}",
        f"- Runtime data status: {answer.runtime_data_status}",
        f"- Knowledge store status: {answer.knowledge_store_status}",
        f"- Using legacy data: {str(answer.using_legacy_data).lower()}",
        "",
        "## Evidence Summary",
        "",
    ]
    lines.extend(f"- {item}" for item in answer.evidence_summary or ["No direct local evidence available."])
    lines.extend(["", "## Missing Evidence", ""])
    lines.extend(f"- {item}" for item in answer.missing_evidence or ["None detected by the MVP rules."])
    lines.extend(["", "## Recommended Next Steps", ""])
    lines.extend(f"- {item}" for item in answer.recommended_next_steps)
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def assemble_query_answer(
    query: ResearchQuery,
    coverage: CoverageReport,
    plan: IngestionPlan | None = None,
    *,
    repository_root: str | Path = ".",
    write_outputs: bool = True,
) -> QueryAnswer:
    """Return only claims already represented in local hypothesis artifacts."""

    sufficient = coverage.verdict == "Sufficient_No_Update_Needed"
    partial = coverage.verdict == "Partial_Coverage_Delta_Update_Recommended"
    hypotheses = coverage.hypotheses if (sufficient or partial) else []
    if partial:
        hypotheses = [{**item, "evidence_qualification": "tentative_evidence_limited"} for item in hypotheses]
    evidence_summary = [
        f"{coverage.exact_pair_observations} exact-pair observations: "
        f"{len(coverage.supporting_triples)} supporting and {len(coverage.contradicting_triples)} contradicting.",
        f"{len(coverage.context_mentions)} context mentions and {len(coverage.validation_results)} validation results are locally indexed.",
    ] if coverage.exact_pair_observations else []
    next_steps = []
    if plan:
        next_steps.append(f"Review dry-run ingestion plan with {plan.estimated_api_calls} estimated API calls.")
        next_steps.extend(f"Search candidate: {item}" for item in plan.search_queries)
    elif not sufficient:
        next_steps.append("Generate a dry-run incremental ingestion plan before any update execution.")

    answer = QueryAnswer(
        query_id=query.query_id,
        answer_mode=("existing_graph_only" if sufficient else "evidence_limited" if partial else "insufficient_coverage"),
        coverage_verdict=coverage.verdict,
        hypotheses=hypotheses,
        evidence_summary=evidence_summary,
        missing_evidence=coverage.missing_dimensions,
        recommended_next_steps=next_steps,
        used_existing_graph_only=True,
        api_calls_made=0,
        runtime_data_status=coverage.runtime_data_status,
        knowledge_store_status=coverage.knowledge_store_status,
        using_legacy_data=coverage.using_legacy_data,
    )
    if write_outputs:
        _write_answer(answer, query, Path(repository_root))
    return answer
