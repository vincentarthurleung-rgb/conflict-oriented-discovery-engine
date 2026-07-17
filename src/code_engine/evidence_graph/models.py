"""JSON-serializable merged evidence graph contracts."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field, is_dataclass
from typing import Any, cast

NODE_TYPES = {
    "paper", "entity", "claim", "evidence_span", "observation", "relation_bundle", "conflict",
    "mechanism_node", "mechanism_edge", "mechanism_path", "hypothesis", "temporal_window",
    "timeline_evidence_item", "validation_anchor", "validation_result",
}

EDGE_TYPES = {
    "paper_contains_claim", "paper_contains_evidence", "claim_grounded_by_evidence", "observation_from_claim",
    "observation_subject_entity", "observation_object_entity", "observation_supported_by_evidence",
    "bundle_contains_observation", "bundle_contains_evidence_edge", "bundle_has_conflict",
    "conflict_derived_from_bundle", "conflict_supported_by_observation", "conflict_supported_by_evidence",
    "conflict_has_source_window", "conflict_has_later_window", "temporal_window_contains_evidence",
    "hypothesis_explains_conflict", "hypothesis_uses_evidence", "hypothesis_uses_mechanism_edge",
    "hypothesis_uses_mechanism_path", "hypothesis_compared_with_later_evidence",
    "projected_core_relation",
}


class Serializable:
    def to_dict(self) -> dict[str, Any]:
        if not is_dataclass(self):
            raise TypeError(f"{type(self).__name__} must be a dataclass to be serialized")
        return cast(dict[str, Any], asdict(self))  # type: ignore[arg-type]


@dataclass
class EvidenceGraphNode(Serializable):
    node_id: str
    node_type: str
    label: str
    canonical_id: str | None = None
    attributes: dict[str, Any] = field(default_factory=dict)
    provenance: dict[str, Any] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
    run_id: str | None = None
    topic_id: str | None = None
    query_id: str | None = None
    artifact_schema_version: str = "evidence_graph.v1"
    export_ready: bool = True
    export_warnings: list[str] = field(default_factory=list)


@dataclass
class EvidenceGraphEdge(Serializable):
    edge_id: str
    source: str
    target: str
    edge_type: str
    attributes: dict[str, Any] = field(default_factory=dict)
    provenance: dict[str, Any] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
    run_id: str | None = None
    topic_id: str | None = None
    query_id: str | None = None
    artifact_schema_version: str = "evidence_graph.v1"
    export_ready: bool = True
    export_warnings: list[str] = field(default_factory=list)


@dataclass
class EvidenceEdge(Serializable):
    evidence_edge_id: str
    source_entity_id: str | None
    target_entity_id: str | None
    relation_family: str
    polarity_type: str
    direction: str
    direction_polarity: str = "unknown"
    direction_polarity_source: str = "normalized_from_direction"
    context_variables: Any = field(default_factory=dict)
    evidence_span: Any = None
    evidence_text: str | None = None
    source_scope: str | None = None
    evidence_tier: str | None = None
    graph_layer: str | None = None
    canonical_graph_eligible: bool | None = None
    allow_high_confidence_graph_use: bool | None = None
    context_compatibility_status: str | None = None
    strong_context_match: bool | None = None
    query_context_only: bool | None = None
    core_context_eligible: bool | None = None
    excluded_from_core_reason: str | None = None
    strong_context_terms_matched: list[str] = field(default_factory=list)
    weak_context_terms_matched: list[str] = field(default_factory=list)
    confidence: float | None = None
    paper_id: str | None = None
    canonical_paper_id: str | None = None
    doi: str | None = None
    title: str | None = None
    journal: str | None = None
    publication_year: int | None = None
    observation_id: str | None = None
    claim_id: str | None = None
    evidence_id: str | None = None
    warnings: list[str] = field(default_factory=list)
    subject_name: str | None = None
    subject_type: str | None = None
    subject_canonical_id: str | None = None
    subject_canonical_name: str | None = None
    subject_resolution_status: str | None = None
    subject_resolution_decision_id: str | None = None
    object_name: str | None = None
    object_type: str | None = None
    object_canonical_id: str | None = None
    object_canonical_name: str | None = None
    object_resolution_status: str | None = None
    object_resolution_decision_id: str | None = None
    original_subject_canonical_id: str | None = None
    original_object_canonical_id: str | None = None
    original_relation_family: str | None = None
    relation_raw: str | None = None
    core_projection_status: str | None = None
    core_projection_role: str | None = None
    core_projection_relation: str | None = None
    core_projection_reason: str | None = None
    subject_endpoint: dict[str, Any] = field(default_factory=dict)
    object_endpoint: dict[str, Any] = field(default_factory=dict)
    linked_claim_ids: list[str] = field(default_factory=list)
    linked_evidence_ids: list[str] = field(default_factory=list)
    linked_observation_ids: list[str] = field(default_factory=list)
    linked_conflict_ids: list[str] = field(default_factory=list)
    linked_mechanism_edge_ids: list[str] = field(default_factory=list)
    linked_mechanism_path_ids: list[str] = field(default_factory=list)
    linked_hypothesis_ids: list[str] = field(default_factory=list)
    run_id: str | None = None
    topic_id: str | None = None
    query_id: str | None = None
    artifact_schema_version: str = "evidence_edge.v1"
    export_ready: bool = True
    export_warnings: list[str] = field(default_factory=list)


@dataclass
class RelationEvidenceBundle(Serializable):
    bundle_id: str
    subject_canonical_id: str
    object_canonical_id: str
    relation_family: str
    polarity_type: str
    evidence_edge_ids: list[str] = field(default_factory=list)
    observation_ids: list[str] = field(default_factory=list)
    paper_ids: list[str] = field(default_factory=list)
    canonical_paper_ids: list[str] = field(default_factory=list)
    linked_dois: list[str] = field(default_factory=list)
    linked_titles: list[str] = field(default_factory=list)
    linked_journals: list[str] = field(default_factory=list)
    publication_year_range: list[int] = field(default_factory=list)
    paper_count: int = 0
    evidence_count: int = 0
    direction_distribution: dict[str, int] = field(default_factory=dict)
    paper_level_direction_distribution: dict[str, int] = field(default_factory=dict)
    entropy: float = 0.0
    distinct_direction_count: int = 0
    context_variables: list[Any] = field(default_factory=list)
    context_distribution: dict[str, dict[str, int]] = field(default_factory=dict)
    evidence_tier_distribution: dict[str, int] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
    subject_name: str | None = None
    subject_type: str | None = None
    object_name: str | None = None
    object_type: str | None = None
    linked_claim_ids: list[str] = field(default_factory=list)
    linked_evidence_ids: list[str] = field(default_factory=list)
    linked_conflict_ids: list[str] = field(default_factory=list)
    linked_mechanism_edge_ids: list[str] = field(default_factory=list)
    linked_mechanism_path_ids: list[str] = field(default_factory=list)
    linked_hypothesis_ids: list[str] = field(default_factory=list)
    run_id: str | None = None
    topic_id: str | None = None
    query_id: str | None = None
    artifact_schema_version: str = "relation_evidence_bundle.v1"
    export_ready: bool = True
    export_warnings: list[str] = field(default_factory=list)


@dataclass
class GraphConflictCandidate(Serializable):
    graph_conflict_id: str
    bundle_id: str
    conflict_key: str
    subject_canonical_id: str
    object_canonical_id: str
    relation_family: str
    polarity_type: str
    reasoning_type: str
    reasoning_types: list[str]
    reasoning_trace_id: str
    direction_distribution: dict[str, int]
    paper_level_direction_distribution: dict[str, int]
    entropy: float
    distinct_direction_count: int
    paper_count: int
    evidence_count: int
    linked_evidence_edge_ids: list[str]
    linked_observation_ids: list[str]
    linked_paper_ids: list[str]
    linked_canonical_paper_ids: list[str]
    linked_dois: list[str]
    linked_titles: list[str]
    linked_journals: list[str]
    publication_year_range: list[int]
    status: str
    warnings: list[str] = field(default_factory=list)
    run_id: str | None = None
    topic_id: str | None = None
    query_id: str | None = None
    artifact_schema_version: str = "graph_conflict_candidate.v1"
    export_ready: bool = True
    export_warnings: list[str] = field(default_factory=list)


@dataclass
class GraphReasoningTrace(Serializable):
    reasoning_trace_id: str
    bundle_id: str
    input_evidence_edge_ids: list[str]
    paper_level_direction_distribution: dict[str, int]
    entropy_formula_inputs: dict[str, Any]
    thresholds: dict[str, Any]
    decision: dict[str, Any]
    warnings: list[str] = field(default_factory=list)
    run_id: str | None = None
    topic_id: str | None = None
    query_id: str | None = None
    artifact_schema_version: str = "graph_reasoning_trace.v1"
    export_ready: bool = True
    export_warnings: list[str] = field(default_factory=list)
