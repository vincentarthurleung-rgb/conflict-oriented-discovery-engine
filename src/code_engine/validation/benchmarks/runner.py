"""Run aggregation rules against fixed signal fixtures without external calls."""

from __future__ import annotations

import json
from pathlib import Path

from code_engine.schemas.validation import ValidationAnchor, ValidationQueryPlan, ValidationResourcePolicy
from code_engine.validation.benchmarks.cases import load_benchmark_cases
from code_engine.validation.benchmarks.metrics import compute_benchmark_metrics
from code_engine.validation.result_aggregator import aggregate_validation_signals


def run_aggregator_benchmark(cases_path: str | Path, output_path: str | Path | None = None) -> dict:
    cases_file = Path(cases_path)
    outcomes = []
    for case in load_benchmark_cases(cases_file):
        anchor = ValidationAnchor.model_validate(case.anchor)
        plan = ValidationQueryPlan(
            query_plan_id=f"plan-{case.case_id}", anchor_id=anchor.anchor_id,
            validator_name="BenchmarkValidator", query_type="benchmark",
            execution_mode=case.execution_mode, status=case.plan_status,
        )
        signals_path = Path(case.signals_path)
        if not signals_path.is_absolute():
            signals_path = cases_file.parent / signals_path
        aggregate = aggregate_validation_signals(
            signals_path, [anchor], [plan],
            ValidationResourcePolicy(execution_enabled=True),
        )
        result = aggregate.results[0]
        warning_text = " ".join(result.interpretation_limits + result.warnings + [result.summary])
        matched = result.validation_status == case.expected_status
        if case.expected_min_confidence is not None:
            matched = matched and result.confidence >= case.expected_min_confidence
        matched = matched and all(fragment in warning_text for fragment in case.expected_warnings_contains)
        outcomes.append({
            "case_id": case.case_id, "expected_status": case.expected_status,
            "actual_status": result.validation_status, "confidence": result.confidence,
            "matched": matched,
        })
    metrics = compute_benchmark_metrics(outcomes)
    metrics["outcomes"] = outcomes
    if output_path:
        destination = Path(output_path)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(json.dumps(metrics, ensure_ascii=False, indent=2), encoding="utf-8")
    return metrics


__all__ = ["run_aggregator_benchmark"]
