"""Deterministic ranking for candidate hypotheses."""

from __future__ import annotations

from typing import Any, Dict, List


RANKING_WEIGHTS = {
    "consistency": 0.8,
    "identifiability": 1.0,
    "complexity": -0.15,
}


def compute_ranking_score(hypothesis: Dict[str, Any]) -> float:
    """Compute the fixed C.O.D.E. v4.0 ranking score."""

    metrics = hypothesis.get("metrics_breakdown", {})
    score = (
        metrics.get("consistency", 0.0) * RANKING_WEIGHTS["consistency"]
        + metrics.get("identifiability", 0.0) * RANKING_WEIGHTS["identifiability"]
        + metrics.get("complexity", 0.0) * RANKING_WEIGHTS["complexity"]
    )
    return round(score, 4)


def rank_hypotheses(hypotheses: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Return ranked hypotheses with deterministic tie-breaks."""

    ranked = []
    for index, hypothesis in enumerate(hypotheses):
        item = dict(hypothesis)
        item["global_ranking_score"] = compute_ranking_score(item)
        item["_ranking_input_order"] = index
        ranked.append(item)

    ranked.sort(
        key=lambda item: (
            -item["global_ranking_score"],
            item.get("objective_loss_score", 0.0),
            item.get("hypothesis_id", ""),
            item["_ranking_input_order"],
        )
    )
    for item in ranked:
        item.pop("_ranking_input_order", None)
    return ranked
