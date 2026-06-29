"""Schema-bound, local/cache-only external validation for batch candidates."""

from __future__ import annotations

import json
import shutil
from collections import Counter, defaultdict
from pathlib import Path

from code_engine.schemas.validation import ValidationResourcePolicy
from code_engine.validation.anchors import build_validation_anchors_from_conflicts, build_validation_anchors_from_hypotheses
from code_engine.validation.execution import execute_validation_query_plans
from code_engine.validation.query_planner import plan_validation_queries
from code_engine.validation.question_builder import build_validation_questions_from_anchors
from code_engine.validation.registry import ValidatorRegistry
from code_engine.validation.result_aggregator import aggregate_validation_signals
from code_engine.validation.router import route_validation_questions


def _write_jsonl(path: Path, records) -> None:
    with path.open("w", encoding="utf-8") as handle:
        for item in records:
            payload = item.model_dump(mode="json") if hasattr(item, "model_dump") else item
            handle.write(json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + "\n")


def _validation_metrics(anchors, questions, routes, plans, execution, aggregate) -> dict:
    statuses = Counter(item.validation_status for item in aggregate.results)
    count = len(aggregate.results)
    configured_missing = statuses["external_index_not_configured"]
    return {
        "validation_anchor_count": len(anchors), "validation_question_count": len(questions),
        "validation_route_count": len(routes), "validation_query_plan_count": len(plans),
        "validation_executed_query_count": execution.executed_query_count,
        "validation_blocked_query_count": execution.blocked_query_count,
        "validation_evidence_count": execution.evidence_count,
        "validation_signal_count": execution.signal_count,
        "validation_supported_count": statuses["supported"],
        "validation_contradicted_count": statuses["contradicted"],
        "validation_mixed_count": statuses["mixed"],
        "validation_no_coverage_count": statuses["no_coverage"],
        "validation_external_index_not_configured_count": configured_missing,
        "validation_insufficient_quality_count": statuses["insufficient_quality"],
        "validation_error_count": statuses["error"],
        "validation_coverage_rate": round((count - statuses["no_coverage"] - configured_missing) / count, 6) if count else 0.0,
        "validation_supported_rate": round(statuses["supported"] / count, 6) if count else 0.0,
        "validation_mixed_rate": round(statuses["mixed"] / count, 6) if count else 0.0,
        "validation_no_coverage_rate": round(statuses["no_coverage"] / count, 6) if count else 0.0,
        "interpretation": "Batch validation status is external evidence coverage, not hypothesis accuracy.",
    }


def run_batch_external_validation(
    candidates: list[dict], output_dir: str | Path, *, execute: bool = False,
    query_mode: str = "disabled", index_dir: str | None = None,
    cache_dir: str | None = None, max_anchors: int = 100,
    max_query_plans: int = 400, max_records_per_validator: int = 100,
    max_signals_per_run: int = 500, hypotheses: list[dict] | None = None,
) -> dict:
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    anchors = build_validation_anchors_from_conflicts(candidates)
    anchors.extend(build_validation_anchors_from_hypotheses(hypotheses or []))
    anchors = list({item.anchor_id: item for item in anchors}.values())[:max_anchors]
    questions = build_validation_questions_from_anchors(anchors, {})
    registry = ValidatorRegistry().register_defaults()
    routes = route_validation_questions(questions, registry)
    policy = ValidationResourcePolicy(
        external_validation_enabled=bool(execute), network_enabled=False,
        execution_enabled=bool(execute), index_dir=index_dir, cache_dir=cache_dir,
        max_records_per_validator=max_records_per_validator,
        max_records_per_anchor=max_records_per_validator,
        max_signals_per_run=max_signals_per_run,
    )
    plans = plan_validation_queries(routes, questions, anchors, registry, policy, query_mode)[:max_query_plans]
    _write_jsonl(output / "batch_validation_anchors.jsonl", anchors)
    _write_jsonl(output / "batch_validation_questions.jsonl", questions)
    _write_jsonl(output / "batch_validation_routes.jsonl", routes)
    _write_jsonl(output / "batch_validation_query_plans.jsonl", plans)
    execution_dir = output / ".batch_validation_execution"
    execution = execute_validation_query_plans(
        plans, registry, policy, execute=execute, network_enabled=False,
        cache_enabled=True, run_dir=execution_dir,
    )
    aggregate = aggregate_validation_signals(
        Path(execution.artifact_refs["signals"]), anchors, plans, policy,
        output_dir=execution_dir,
    )
    destinations = {
        "evidence": output / "batch_external_validation_evidence.jsonl",
        "signals": output / "batch_external_validation_signals.jsonl",
        "results": output / "batch_external_validation_results.jsonl",
    }
    for key, destination in destinations.items():
        source = Path(execution.artifact_refs[key]) if key in execution.artifact_refs else Path(aggregate.artifact_refs[key])
        shutil.copyfile(source, destination)
    grouped: dict[str, Counter] = defaultdict(Counter)
    anchors_by_id = {item.anchor_id: item for item in anchors}
    prompt_by_conflict = {
        str(item.get("candidate_id") or item.get("conflict_edge_id") or item.get("edge_id")): str(item.get("prompt_id"))
        for item in candidates if item.get("prompt_id") is not None
    }
    for result in aggregate.results:
        anchor = anchors_by_id.get(result.anchor_ids[0]) if result.anchor_ids else None
        group_ids = list(anchor.linked_conflict_ids if anchor else []) + list(anchor.linked_hypothesis_ids if anchor else [])
        group_ids.extend(prompt_by_conflict[item] for item in (anchor.linked_conflict_ids if anchor else []) if item in prompt_by_conflict)
        group_ids = list(dict.fromkeys(group_ids)) or ["unlinked"]
        for group_id in group_ids:
            grouped[group_id][result.validation_status] += 1
    metrics = _validation_metrics(anchors, questions, routes, plans, execution, aggregate)
    summary = {
        "execution_status": execution.status, "aggregate_status": aggregate.aggregate_status,
        "status_counts": aggregate.status_counts,
        "grouped_status_counts": {key: dict(value) for key, value in grouped.items()},
        "resource_usage": execution.model_dump(mode="json", exclude={"artifact_refs"}),
        "warnings": aggregate.warnings + execution.warnings,
    }
    (output / "batch_external_validation_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    (output / "batch_validation_metrics.json").write_text(json.dumps(metrics, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"metrics": metrics, "summary": summary, "execution": execution, "aggregate": aggregate}


__all__ = ["run_batch_external_validation"]
