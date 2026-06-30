"""Serializable models for traceable temporal evidence chains."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class ConflictEvidenceTimeline:
    timeline_id: str
    conflict_id: str
    conflict_key: str
    subject_canonical_id: str | None = None
    object_canonical_id: str | None = None
    relation_family: str = "unknown"
    polarity_type: str = "unknown"
    conflict_source_window: dict[str, Any] | None = None
    later_evidence_window: dict[str, Any] | None = None
    evidence_timeline: list[dict[str, Any]] = field(default_factory=list)
    early_conflicting_papers: list[dict[str, Any]] = field(default_factory=list)
    later_explanation_evidence_papers: list[dict[str, Any]] = field(default_factory=list)
    recent_consensus_papers: list[dict[str, Any]] = field(default_factory=list)
    stale_or_missing_recent_evidence_papers: list[dict[str, Any]] = field(default_factory=list)
    overall_direction_distribution: dict[str, int] = field(default_factory=dict)
    early_direction_distribution: dict[str, int] = field(default_factory=dict)
    later_direction_distribution: dict[str, int] = field(default_factory=dict)
    direction_distribution_by_year: dict[str, dict[str, int]] = field(default_factory=dict)
    paper_count_by_year: dict[str, int] = field(default_factory=dict)
    evidence_count_by_year: dict[str, int] = field(default_factory=dict)
    entropy_by_year: dict[str, float] = field(default_factory=dict)
    overall_entropy: float = 0.0
    early_entropy: float = 0.0
    later_entropy: float = 0.0
    later_dominant_direction: str | None = None
    later_dominant_direction_share: float = 0.0
    status: str = "uncertain_temporal_evidence_status"
    status_confidence: float = 0.0
    human_review_required: bool = True
    system_judgment: str = "non_decisive"
    recommended_action: str = "human_review"
    latest_evidence_pattern: dict[str, Any] = field(default_factory=dict)
    system_hypotheses: list[dict[str, Any]] = field(default_factory=list)
    hypothesis_vs_later_evidence: list[dict[str, Any]] = field(default_factory=list)
    possible_explanation_evidence: bool = False
    recent_consensus_signal: bool = False
    active_like_signal: bool = False
    mode: str = "time_gated"
    not_used_for_hypothesis_generation: bool = True
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
