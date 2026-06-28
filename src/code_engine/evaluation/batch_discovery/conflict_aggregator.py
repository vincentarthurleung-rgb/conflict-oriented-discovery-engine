"""Aggregate per-prompt abstract conflict candidates."""

from __future__ import annotations


def aggregate_conflict_candidates(per_prompt_results: list[dict]) -> list[dict]:
    aggregated = []
    for result in per_prompt_results:
        prompt_id = str(result.get("prompt_id") or "UNKNOWN")
        for candidate in result.get("candidates", []):
            aggregated.append({**candidate, "prompt_id": candidate.get("prompt_id") or prompt_id})
    return sorted(aggregated, key=lambda item: (-float(item.get("abstract_entropy", 0.0)), str(item.get("prompt_id")), str(item.get("candidate_id"))))


__all__ = ["aggregate_conflict_candidates"]
