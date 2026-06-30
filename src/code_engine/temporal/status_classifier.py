"""Conservative temporal evidence status rules. No resolution verdict exists here."""

from __future__ import annotations

from typing import Any

ALLOWED_STATUSES = {
    "persistent_conflict", "emerging_conflict", "conflict_with_later_explanation_evidence",
    "recent_consensus_signal", "context_partition_supported", "stale_unresolved_conflict",
    "abandoned_or_understudied_conflict", "insufficient_later_evidence",
    "uncertain_temporal_evidence_status",
}


def classify_temporal_status(*, early_entropy: float, later_entropy: float,
                             early_paper_count: int, later_paper_count: int,
                             later_dominant_direction_share: float,
                             min_later_evidence_papers: int = 1,
                             has_context_partition: bool = False,
                             has_mechanism_evidence: bool = False,
                             has_explanation_evidence: bool = False,
                             critical_fields_missing: bool = False) -> tuple[str, float]:
    if critical_fields_missing or early_paper_count < 2:
        return "uncertain_temporal_evidence_status", 0.35
    if early_entropy >= 0.55 and later_paper_count < min_later_evidence_papers:
        if early_paper_count >= max(5, min_later_evidence_papers * 3):
            return "abandoned_or_understudied_conflict", 0.65
        return "stale_unresolved_conflict", 0.7
    if has_context_partition:
        return "context_partition_supported", 0.8
    if early_entropy >= 0.55 and later_entropy >= 0.55 and later_paper_count >= min_later_evidence_papers:
        return "persistent_conflict", 0.8
    if early_entropy < 0.35 and later_entropy >= 0.55 and later_paper_count >= min_later_evidence_papers:
        return "emerging_conflict", 0.75
    convergence = early_entropy >= 0.55 and later_entropy <= 0.35 and later_dominant_direction_share >= 0.75
    if later_paper_count >= min_later_evidence_papers and (has_explanation_evidence or has_mechanism_evidence or convergence):
        return ("conflict_with_later_explanation_evidence" if has_explanation_evidence or has_mechanism_evidence else "recent_consensus_signal"), 0.75
    if later_paper_count:
        return "insufficient_later_evidence", 0.5
    return "uncertain_temporal_evidence_status", 0.35
