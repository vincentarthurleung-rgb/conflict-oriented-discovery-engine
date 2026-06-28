"""Serializable MechanismGraph contracts."""

from __future__ import annotations

from typing import Any

from pydantic import Field

from code_engine.schemas.models import CODEBaseModel


class MechanismNode(CODEBaseModel):
    node_id: str
    canonical_id: str | None = None
    canonical_name: str | None = None
    raw_names: list[str] = Field(default_factory=list)
    entity_type: str | None = None
    semantic_level: str | None = None
    domain_id: str | None = None
    source_observation_ids: list[str] = Field(default_factory=list)
    source_evidence_ids: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class MechanismEdge(CODEBaseModel):
    edge_id: str
    source_node_id: str
    target_node_id: str
    subject_canonical_id: str | None = None
    object_canonical_id: str | None = None
    subject_name: str | None = None
    object_name: str | None = None
    relation_type: str = "unknown_mechanism_relation"
    relation_label: str = ""
    direction: str = "unknown"
    mechanism_role: str | None = "unknown"
    domain_id: str | None = None
    subdomain_id: str | None = None
    evidence_ids: list[str] = Field(default_factory=list)
    claim_ids: list[str] = Field(default_factory=list)
    observation_ids: list[str] = Field(default_factory=list)
    paper_ids: list[str] = Field(default_factory=list)
    context: dict[str, Any] = Field(default_factory=dict)
    context_slots: dict[str, Any] = Field(default_factory=dict)
    support_count: int = 0
    contradict_count: int = 0
    neutral_count: int = 0
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    normalization_quality: str | None = None
    allow_high_confidence_graph_use: bool = False
    conflict_edge_ids: list[str] = Field(default_factory=list)
    conflict_types: list[str] = Field(default_factory=list)
    has_conflict: bool = False
    warnings: list[str] = Field(default_factory=list)


class MechanismPath(CODEBaseModel):
    path_id: str
    node_ids: list[str] = Field(default_factory=list)
    edge_ids: list[str] = Field(default_factory=list)
    start_node_id: str
    end_node_id: str
    path_length: int = 0
    domain_id: str | None = None
    supporting_evidence_ids: list[str] = Field(default_factory=list)
    conflict_edge_ids: list[str] = Field(default_factory=list)
    mechanistic_completeness: float = Field(default=0.0, ge=0.0, le=1.0)
    warnings: list[str] = Field(default_factory=list)


class MechanismConflictAnnotation(CODEBaseModel):
    annotation_id: str
    mechanism_edge_id: str | None = None
    mechanism_path_id: str | None = None
    conflict_edge_id: str
    conflict_type: str
    entropy: float | None = None
    attribution_summary: dict[str, Any] = Field(default_factory=dict)
    context_explanation: dict[str, Any] = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)


class MechanismGraph(CODEBaseModel):
    graph_id: str
    domain_id: str | None = None
    subdomain_id: str | None = None
    nodes: list[MechanismNode] = Field(default_factory=list)
    edges: list[MechanismEdge] = Field(default_factory=list)
    paths: list[MechanismPath] = Field(default_factory=list)
    conflict_annotations: list[MechanismConflictAnnotation] = Field(default_factory=list)
    source_artifacts: dict[str, Any] = Field(default_factory=dict)
    counts: dict[str, int] = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)


class MechanismBuildReport(CODEBaseModel):
    graph_id: str
    node_count: int = 0
    edge_count: int = 0
    path_count: int = 0
    conflict_annotation_count: int = 0
    evidence_link_count: int = 0
    claim_link_count: int = 0
    observation_link_count: int = 0
    skipped_low_confidence_count: int = 0
    skipped_unresolved_count: int = 0
    warnings: list[str] = Field(default_factory=list)
