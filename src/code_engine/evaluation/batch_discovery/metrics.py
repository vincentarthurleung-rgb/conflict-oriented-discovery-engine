"""Problem-discovery metrics for batch experiments."""

from __future__ import annotations

from collections import Counter
from typing import Any


VALID_LABELS = {"valid_contextual_conflict", "valid_direct_conflict", "valid_but_low_actionability"}
ACTIONABLE_LABELS = {"valid_contextual_conflict", "valid_direct_conflict"}


def compute_batch_metrics(
    *, prompts: list[dict], candidates: list[dict], annotations: list[dict] | None = None,
    run_summaries: list[dict] | None = None, hypothesis_statistics: dict | None = None,
    estimated_cost_usd: float = 0.0, actual_cost_usd: float = 0.0,
) -> dict[str, Any]:
    summaries = run_summaries or []
    labels = [str(item.get("annotation_label")) for item in (annotations or []) if item.get("annotation_label")]
    label_counts = Counter(labels)
    annotated = len(labels)
    metrics = {
        "prompt_count": len(prompts),
        "retrieved_paper_count": sum(int(item.get("retrieved_paper_count", 0)) for item in summaries),
        "abstract_processed_paper_count": sum(int(item.get("abstract_processed_paper_count", 0)) for item in summaries),
        "abstract_claim_count": sum(int(item.get("abstract_claim_count", 0)) for item in summaries),
        "normalized_observation_count": sum(int(item.get("normalized_observation_count", 0)) for item in summaries),
        "abstract_conflict_candidate_count": len(candidates),
        "fulltext_escalated_conflict_count": sum(int(item.get("fulltext_escalated_conflict_count", 0)) for item in summaries),
        "fulltext_available_rate": 0.0,
        "fulltext_evidence_count": sum(int(item.get("fulltext_evidence_count", 0)) for item in summaries),
        "confirmed_conflict_count": sum(int(item.get("confirmed_conflict_count", 0)) for item in summaries),
        "context_resolved_conflict_count": sum(int(item.get("context_resolved_conflict_count", 0)) for item in summaries),
        "hypothesis_count": int((hypothesis_statistics or {}).get("hypothesis_count", 0)),
        "traceable_hypothesis_count": int((hypothesis_statistics or {}).get("traceable_hypothesis_count", 0)),
        "manual_annotation_sample_size": annotated,
        "valid_conflict_rate": round(sum(label_counts[item] for item in VALID_LABELS) / annotated, 6) if annotated else None,
        "actionable_conflict_rate": round(sum(label_counts[item] for item in ACTIONABLE_LABELS) / annotated, 6) if annotated else None,
        "error_type_distribution": {key: value for key, value in label_counts.items() if key not in VALID_LABELS},
        "estimated_cost_usd": round(float(estimated_cost_usd), 6),
        "actual_cost_usd": round(float(actual_cost_usd), 6),
        "cost_per_conflict_candidate": round(float(estimated_cost_usd) / len(candidates), 6) if candidates else None,
        "cost_per_confirmed_conflict": None,
        "primary_evaluation_goal": "automated_problem_discovery",
    }
    available = sum(int(item.get("fulltext_available_paper_count", 0)) for item in summaries)
    unavailable = sum(int(item.get("fulltext_unavailable_paper_count", 0)) for item in summaries)
    metrics["fulltext_available_rate"] = round(available / (available + unavailable), 6) if available + unavailable else 0.0
    if metrics["confirmed_conflict_count"]:
        metrics["cost_per_confirmed_conflict"] = round(float(estimated_cost_usd) / metrics["confirmed_conflict_count"], 6)
    return metrics


__all__ = ["compute_batch_metrics"]
