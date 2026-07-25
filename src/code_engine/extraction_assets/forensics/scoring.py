"""Human-audit sorting only. Scores never confer authority."""
from __future__ import annotations


def diagnostic_score(*, direct_ids: int = 0, exact_hashes: int = 0,
                     replay_exact: int = 0, weak_signals: int = 0, conflicts: int = 0) -> float:
    return float(100 * direct_ids + 25 * exact_hashes + 20 * replay_exact + weak_signals - 100 * conflicts)

