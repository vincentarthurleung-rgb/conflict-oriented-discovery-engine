"""Deterministic direction normalization used by graph conflict reasoning."""

from __future__ import annotations

from collections import Counter
from typing import Mapping

POSITIVE = {"activate", "activates", "activation", "increase", "increases", "increased",
            "upregulate", "upregulates", "upregulated", "induce", "induces", "induced",
            "promote", "promotes", "promoted", "enhance", "enhances", "enhanced",
            "stimulate", "stimulates", "stimulated"}
NEGATIVE = {"inhibit", "inhibits", "inhibited", "inhibition", "decrease", "decreases",
            "decreased", "downregulate", "downregulates", "downregulated", "suppress",
            "suppresses", "suppressed", "reduce", "reduces", "reduced", "attenuate",
            "attenuates", "attenuated", "block", "blocks", "blocked"}
NEUTRAL = {"associate", "association", "correlate", "correlated", "related", "no_effect", "neutral"}


def direction_polarity(direction: object) -> str:
    value = str(direction or "unknown").strip().casefold().replace("-", "_").replace(" ", "_")
    if value in POSITIVE:
        return "positive"
    if value in NEGATIVE:
        return "negative"
    if value in NEUTRAL:
        return "neutral_or_association"
    return "unknown"


def polarity_distribution(direction_distribution: Mapping[str, int]) -> dict[str, int]:
    counts = Counter({"positive": 0, "negative": 0, "neutral_or_association": 0, "unknown": 0})
    for direction, count in direction_distribution.items():
        counts[direction_polarity(direction)] += int(count)
    return dict(counts)


def is_opposing_polarity_conflict(direction_distribution: Mapping[str, int]) -> bool:
    counts = polarity_distribution(direction_distribution)
    return counts["positive"] > 0 and counts["negative"] > 0


__all__ = ["direction_polarity", "polarity_distribution", "is_opposing_polarity_conflict"]
