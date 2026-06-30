"""Explainable temporal window detection and paper-level direction entropy."""

from __future__ import annotations

import math
from collections import Counter, defaultdict
from dataclasses import dataclass
from typing import Any, Iterable

KNOWN_DIRECTIONS = {"increase", "decrease", "activate", "inhibit", "no_effect", "mixed"}


@dataclass(frozen=True)
class TimelineConfig:
    window_size: int = 5
    min_conflict_source_papers: int = 3
    min_conflict_source_entropy: float = 0.55
    min_later_evidence_papers: int = 1
    cutoff_year: int | None = None
    max_later_window_years: int = 5


def shannon_entropy(distribution: dict[str, int]) -> float:
    total = sum(distribution.values())
    if total <= 0:
        return 0.0
    return round(-sum((n / total) * math.log2(n / total) for n in distribution.values() if n), 6)


def paper_identity(item: dict[str, Any]) -> str:
    return str(item.get("canonical_paper_id") or item.get("paper_id") or item.get("doi") or item.get("title") or "UNKNOWN")


def paper_direction_votes(records: Iterable[dict[str, Any]]) -> tuple[dict[str, str], list[str]]:
    votes: dict[str, set[str]] = defaultdict(set)
    warnings: list[str] = []
    for item in records:
        direction = str(item.get("direction") or "unknown").casefold()
        if direction not in KNOWN_DIRECTIONS:
            warnings.append("unknown_direction_excluded_from_entropy")
            continue
        votes[paper_identity(item)].add(direction)
    collapsed = {paper: next(iter(values)) if len(values) == 1 else "mixed" for paper, values in votes.items()}
    if any(len(values) > 1 for values in votes.values()):
        warnings.append("mixed_from_same_paper")
    return collapsed, sorted(set(warnings))


def direction_stats(records: Iterable[dict[str, Any]]) -> tuple[dict[str, int], float, list[str]]:
    votes, warnings = paper_direction_votes(records)
    distribution = dict(sorted(Counter(votes.values()).items()))
    return distribution, shannon_entropy(distribution), warnings


def detect_temporal_windows(records: list[dict[str, Any]], config: TimelineConfig | None = None) -> dict[str, Any]:
    config = config or TimelineConfig()
    by_year: dict[int, list[dict[str, Any]]] = defaultdict(list)
    warnings: list[str] = []
    for item in records:
        try:
            year = int(item.get("publication_year") or str(item.get("publication_date") or "")[:4])
        except (TypeError, ValueError):
            warnings.append("missing_publication_year")
            continue
        if config.cutoff_year is None or year <= config.cutoff_year:
            by_year[year].append(item)
    years = sorted(by_year)
    paper_counts = {str(y): len({paper_identity(x) for x in by_year[y]}) for y in years}
    evidence_counts = {str(y): len(by_year[y]) for y in years}
    distributions, entropies = {}, {}
    for year in years:
        dist, entropy, local = direction_stats(by_year[year])
        distributions[str(year)], entropies[str(year)] = dist, entropy
        warnings.extend(local)

    candidates = []
    for start in years:
        end = min(start + max(1, config.window_size) - 1, config.cutoff_year or years[-1])
        window_records = [x for y in years if start <= y <= end for x in by_year[y]]
        dist, entropy, local = direction_stats(window_records)
        warnings.extend(local)
        count = len({paper_identity(x) for x in window_records})
        if count >= config.min_conflict_source_papers and entropy >= config.min_conflict_source_entropy and len(dist) >= 2:
            candidates.append((entropy, count, -start, start, end, dist))
    source = None
    if candidates:
        _, count, _, start, end, dist = max(candidates)
        source = {"start_year": start, "end_year": end, "paper_count": count, "direction_distribution": dist, "entropy": shannon_entropy(dist)}
    elif years and config.cutoff_year is not None:
        eligible = [y for y in years if y <= config.cutoff_year]
        if eligible:
            start, end = min(eligible), max(eligible)
            subset = [x for y in eligible for x in by_year[y]]
            dist, entropy, local = direction_stats(subset)
            warnings.extend(local)
            if len(dist) >= 2:
                source = {"start_year": start, "end_year": end, "paper_count": len({paper_identity(x) for x in subset}), "direction_distribution": dist, "entropy": entropy}

    later = None
    if source:
        later_years = [y for y in years if y > source["end_year"]]
        if later_years:
            start = min(later_years)
            end = min(max(later_years), start + config.max_later_window_years - 1)
            subset = [x for y in later_years if y <= end for x in by_year[y]]
            dist, entropy, local = direction_stats(subset)
            warnings.extend(local)
            later = {"start_year": start, "end_year": end, "paper_count": len({paper_identity(x) for x in subset}), "direction_distribution": dist, "entropy": entropy}
    return {
        "conflict_source_window": source, "later_evidence_window": later,
        "paper_count_by_year": paper_counts, "evidence_count_by_year": evidence_counts,
        "direction_distribution_by_year": distributions, "entropy_by_year": entropies,
        "warnings": sorted(set(warnings)),
    }
