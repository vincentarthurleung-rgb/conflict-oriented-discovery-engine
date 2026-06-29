"""Hyperedge representation for context-conditioned mechanism hypotheses."""

from typing import Any, Literal

from pydantic import Field

from code_engine.schemas.models import CODEBaseModel


CoverageStatus = Literal[
    "existing_graph_supported", "partial_coverage", "insufficient_coverage",
    "requires_delta_ingestion", "unresolved_no_coverage",
]


class HypothesisHyperedge(CODEBaseModel):
    hypothesis_id: str
    hypothesis_type: str = "legacy_hypothesis"
    hypothesis_text: str = ""
    source_mode: str = "legacy_adapter"
    source_scope: str = "unknown"
    evidence_tier: str = "unknown"
    seed_query: str = ""
    seed_pair: str = ""
    entities: list[dict[str, Any]] = Field(default_factory=list)
    contexts: list[dict[str, Any]] = Field(default_factory=list)
    mechanism_path: list[str] = Field(default_factory=list)
    predicted_missing_links: list[dict[str, Any]] = Field(default_factory=list)
    conflict_bottlenecks: list[str] = Field(default_factory=list)
    proposed_mechanism: str = "unspecified"
    tradeoffs_or_limitations: list[str] = Field(default_factory=list)
    supporting_edge_ids: list[str] = Field(default_factory=list)
    contradicting_edge_ids: list[str] = Field(default_factory=list)
    evidence_ids: list[str] = Field(default_factory=list)
    linked_conflict_ids: list[str] = Field(default_factory=list)
    linked_fulltext_confirmation_ids: list[str] = Field(default_factory=list)
    linked_mechanism_edge_ids: list[str] = Field(default_factory=list)
    linked_mechanism_path_ids: list[str] = Field(default_factory=list)
    linked_observation_ids: list[str] = Field(default_factory=list)
    relation_family: str = "unknown"
    polarity_type: str = "unknown"
    direction: str = "unknown"
    context_variables: list[str] = Field(default_factory=list)
    validation_requirements: list[Any] = Field(default_factory=list)
    coverage_status: CoverageStatus = "unresolved_no_coverage"
    requires_manual_review: bool = False
    requires_fulltext_confirmation: bool = False
    requires_external_validation: bool = False
    confidence: float = 0.0
    novelty_score: float = 0.0
    feasibility_score: float = 0.0
    significance_score: float = 0.0
    overall_score: float = 0.0
    mechanism_specificity: float = 0.0
    context_specificity: float = 0.0
    evidence_strength: float = 0.0
    conflict_strength: float = 0.0
    score_components: dict[str, float] = Field(default_factory=dict)
    status: str = "candidate"
    warnings: list[str] = Field(default_factory=list)
