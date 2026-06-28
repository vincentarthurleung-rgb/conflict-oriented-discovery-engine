"""Deterministic posterior-like conflict state; not a Bayesian posterior."""

from __future__ import annotations

import math
from typing import Any

from pydantic import Field

from code_engine.schemas.models import CODEBaseModel


class ProbabilisticConflictState(CODEBaseModel):
    edge_id: str
    p_conflict: float
    p_context_dependent: float
    p_noise_or_low_support: float
    p_time_or_condition_dependent: float
    p_uncontested: float
    evidence_uncertainty: float
    posterior_source: str = "deterministic_calibrated_heuristic_v1"
    classification: str
    legacy_conflict_type: str = "Uncontested"
    warnings: list[str] = Field(default_factory=list)


def relation_entropy(positive_count: int, negative_count: int) -> float:
    total = positive_count + negative_count
    if total <= 0:
        return 0.0
    probabilities = (positive_count / total, negative_count / total)
    return round(-sum(p * math.log2(p) for p in probabilities if p > 0), 6)


def compute_probabilistic_conflict_state(
    edge: dict[str, Any],
    *,
    context_attribution_score: float | None = None,
    time_or_condition_score: float | None = None,
) -> ProbabilisticConflictState:
    """Compute an uncertainty-aware state from counts and attribution signals."""

    positive = int(edge.get("positive_count", 0))
    negative = int(edge.get("negative_count", 0))
    evidence_count = int(edge.get("evidence_count") or positive + negative + int(edge.get("neutral_count", 0)))
    lab_count = int(edge.get("independent_labs_count", edge.get("independent_lab_count", 0)))
    entropy = relation_entropy(positive, negative)
    support = min(1.0, evidence_count / 5.0)
    uncertainty = 1.0 / (1.0 + evidence_count)
    context_score = max(0.0, min(1.0, float(context_attribution_score or edge.get("context_attribution_score", 0.0))))
    temporal_score = max(0.0, min(1.0, float(time_or_condition_score or edge.get("time_or_condition_score", 0.0))))
    raw = {
        "conflict": entropy * support * max(0.1, 1.0 - 0.7 * context_score),
        "context_dependent": entropy * context_score,
        "noise_or_low_support": uncertainty * (1.0 if lab_count <= 1 else 0.5),
        "time_or_condition_dependent": entropy * temporal_score,
        "uncontested": (1.0 - entropy) * (0.5 + 0.5 * support),
    }
    total = sum(raw.values()) or 1.0
    probabilities = {key: round(value / total, 6) for key, value in raw.items()}
    classification = max(probabilities, key=probabilities.get)
    warnings = ["posterior_like_state_is_deterministic_heuristic_not_bayesian"]
    if evidence_count <= 2:
        warnings.append("low_evidence_count")
    if lab_count <= 1:
        warnings.append("single_or_unknown_independent_lab")
    return ProbabilisticConflictState(
        edge_id=str(edge.get("edge_id") or f"{edge.get('source', '')}->{edge.get('target', '')}"),
        p_conflict=probabilities["conflict"],
        p_context_dependent=probabilities["context_dependent"],
        p_noise_or_low_support=probabilities["noise_or_low_support"],
        p_time_or_condition_dependent=probabilities["time_or_condition_dependent"],
        p_uncontested=probabilities["uncontested"],
        evidence_uncertainty=round(uncertainty, 6),
        classification=classification,
        legacy_conflict_type=str(edge.get("conflict_type") or "Uncontested"),
        warnings=warnings,
    )

