"""Auditable deterministic reasoning over relation evidence bundles."""

from __future__ import annotations

from .bundle_builder import stable_id
from .models import GraphConflictCandidate, GraphReasoningTrace, RelationEvidenceBundle


def _has_context_partition(bundle: RelationEvidenceBundle) -> bool:
    dominants = []
    for distribution in bundle.context_distribution.values():
        if distribution:
            dominants.append(max(distribution.items(), key=lambda pair: (pair[1], pair[0]))[0])
    return len(set(dominants)) >= 2


def reason_over_bundle(bundle: RelationEvidenceBundle, *, min_conflict_papers: int = 2,
                       conflict_entropy_threshold: float = 0.55) -> tuple[GraphConflictCandidate, GraphReasoningTrace]:
    if bundle.subject_canonical_id in {"", "unknown"} or bundle.object_canonical_id in {"", "unknown"}:
        raise ValueError("identity-incomplete bundles must not enter graph conflict reasoning")
    reasoning_types = []
    if bundle.paper_count < min_conflict_papers:
        status, primary = "graph_insufficient_evidence", "insufficient_directional_evidence"
    elif bundle.distinct_direction_count == 1:
        status, primary = "graph_uncontested_relation", "single_direction_across_papers"
    elif bundle.entropy >= conflict_entropy_threshold:
        status, primary = "graph_conflict_candidate", "opposing_direction_edges_in_same_bundle"
    else:
        status, primary = "graph_insufficient_evidence", "insufficient_directional_evidence"
    reasoning_types.append(primary)
    if "mixed_direction_within_same_paper" in bundle.warnings:
        reasoning_types.append("mixed_direction_within_same_paper")
    if _has_context_partition(bundle):
        reasoning_types.append("context_partition_candidate")
    conflict_id = stable_id("graph_conflict", bundle.bundle_id)
    trace_id = stable_id("reasoning_trace", bundle.bundle_id)
    key = "|".join((bundle.subject_canonical_id, bundle.object_canonical_id, bundle.relation_family, bundle.polarity_type))
    candidate = GraphConflictCandidate(
        graph_conflict_id=conflict_id, bundle_id=bundle.bundle_id, conflict_key=key,
        subject_canonical_id=bundle.subject_canonical_id, object_canonical_id=bundle.object_canonical_id,
        relation_family=bundle.relation_family, polarity_type=bundle.polarity_type,
        reasoning_type=primary, reasoning_types=reasoning_types, reasoning_trace_id=trace_id,
        direction_distribution=bundle.direction_distribution,
        paper_level_direction_distribution=bundle.paper_level_direction_distribution,
        entropy=bundle.entropy, distinct_direction_count=bundle.distinct_direction_count,
        paper_count=bundle.paper_count, evidence_count=bundle.evidence_count,
        linked_evidence_edge_ids=bundle.evidence_edge_ids, linked_observation_ids=bundle.observation_ids,
        linked_paper_ids=bundle.paper_ids, linked_canonical_paper_ids=bundle.canonical_paper_ids,
        linked_dois=bundle.linked_dois, linked_titles=bundle.linked_titles, linked_journals=bundle.linked_journals,
        publication_year_range=bundle.publication_year_range, status=status, warnings=bundle.warnings,
        run_id=bundle.run_id, topic_id=bundle.topic_id, query_id=bundle.query_id,
        export_ready=bundle.export_ready, export_warnings=bundle.export_warnings,
    )
    trace = GraphReasoningTrace(
        reasoning_trace_id=trace_id, bundle_id=bundle.bundle_id,
        input_evidence_edge_ids=bundle.evidence_edge_ids,
        paper_level_direction_distribution=bundle.paper_level_direction_distribution,
        entropy_formula_inputs={"counts": bundle.paper_level_direction_distribution, "paper_count": bundle.paper_count},
        thresholds={"min_conflict_papers": min_conflict_papers, "conflict_entropy_threshold": conflict_entropy_threshold},
        decision={"status": status, "reasoning_type": primary, "reasoning_types": reasoning_types,
                  "system_judgment": "graph_candidate_only"},
        warnings=bundle.warnings,
        run_id=bundle.run_id, topic_id=bundle.topic_id, query_id=bundle.query_id,
        export_ready=bundle.export_ready, export_warnings=bundle.export_warnings,
    )
    return candidate, trace
