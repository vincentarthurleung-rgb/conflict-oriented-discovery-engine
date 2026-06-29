"""Metrics for deterministic aggregator benchmark runs."""

from typing import Any


def compute_benchmark_metrics(outcomes: list[dict[str, Any]]) -> dict[str, Any]:
    mismatches = [item for item in outcomes if not item["matched"]]
    count = len(outcomes)
    return {
        "case_count": count, "matched_status_count": count - len(mismatches),
        "status_accuracy": round((count - len(mismatches)) / count, 6) if count else 0.0,
        "mismatches": mismatches, "warnings": [] if count else ["no_benchmark_cases"],
    }


__all__ = ["compute_benchmark_metrics"]
