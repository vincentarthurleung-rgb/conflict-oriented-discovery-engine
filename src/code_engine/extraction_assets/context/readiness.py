"""Multi-axis readiness kept independent from L4 scientific authority."""
from __future__ import annotations


DEFAULT_THRESHOLDS = {
    "contract": "context_asset_readiness_thresholds_v1",
    "high_min": 0.8,
    "medium_min": 0.5,
}


def coverage_band(rate: float, thresholds: dict | None = None) -> str:
    limits = thresholds or DEFAULT_THRESHOLDS
    if rate >= limits["high_min"]: return "high"
    if rate >= limits["medium_min"]: return "medium"
    return "low"
