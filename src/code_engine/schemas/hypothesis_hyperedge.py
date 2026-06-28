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
    validation_requirements: list[str] = Field(default_factory=list)
    coverage_status: CoverageStatus = "unresolved_no_coverage"
    novelty_score: float = 0.0
    feasibility_score: float = 0.0
    significance_score: float = 0.0
    overall_score: float = 0.0
    status: str = "candidate"
    warnings: list[str] = Field(default_factory=list)

