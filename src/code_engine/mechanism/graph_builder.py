"""Construct and merge a local evidence-grounded MechanismGraph."""

from __future__ import annotations

import hashlib
from typing import Any

from code_engine.mechanism.edge_builder import build_mechanism_edges_from_observations
from code_engine.mechanism.models import MechanismEdge, MechanismGraph, MechanismNode
from code_engine.mechanism.path_finder import find_mechanism_paths


def _unique(values):
    return list(dict.fromkeys(value for value in values if value not in (None, "")))


def _merge_edges(edges: list[MechanismEdge]) -> list[MechanismEdge]:
    merged: dict[tuple, MechanismEdge] = {}
    for edge in edges:
        key = (edge.subject_canonical_id or edge.source_node_id, edge.object_canonical_id or edge.target_node_id, edge.relation_type, edge.direction)
        if key not in merged:
            merged[key] = edge.model_copy(deep=True)
            continue
        target = merged[key]
        for field in ("evidence_ids", "claim_ids", "observation_ids", "paper_ids", "warnings"):
            setattr(target, field, _unique(getattr(target, field) + getattr(edge, field)))
        target.support_count += edge.support_count
        target.contradict_count += edge.contradict_count
        target.neutral_count += edge.neutral_count
        target.confidence = round(max(target.confidence, edge.confidence), 6)
        target.allow_high_confidence_graph_use &= edge.allow_high_confidence_graph_use
        for slot, sources in edge.context_slots.items():
            target.context_slots.setdefault(slot, []).extend(item for item in sources if item not in target.context_slots.get(slot, []))
            target.context.setdefault(slot, edge.context.get(slot))
    for key, edge in merged.items():
        edge.edge_id = hashlib.sha256("|".join(str(item) for item in key).encode()).hexdigest()[:16]
    return list(merged.values())


def _nodes(edges: list[MechanismEdge], observations: list[dict]) -> list[MechanismNode]:
    observation_by_id = {str(item.get("observation_id") or item.get("triple_id")): item for item in observations}
    nodes: dict[str, MechanismNode] = {}
    for edge in edges:
        for role, node_id, canonical_id, name in (("subject", edge.source_node_id, edge.subject_canonical_id, edge.subject_name), ("object", edge.target_node_id, edge.object_canonical_id, edge.object_name)):
            source = next((observation_by_id.get(item) for item in edge.observation_ids if observation_by_id.get(item)), {})
            warning = [] if canonical_id else ["canonical_id_missing_stable_hash_node"]
            if node_id not in nodes:
                nodes[node_id] = MechanismNode(node_id=node_id, canonical_id=canonical_id, canonical_name=name, raw_names=_unique([source.get(role), name]), entity_type=source.get(f"{role}_entity_type"), semantic_level=source.get(f"{role}_semantic_level"), domain_id=edge.domain_id, source_observation_ids=list(edge.observation_ids), source_evidence_ids=list(edge.evidence_ids), warnings=warning)
            else:
                node = nodes[node_id]
                node.raw_names = _unique(node.raw_names + [source.get(role), name])
                node.source_observation_ids = _unique(node.source_observation_ids + edge.observation_ids)
                node.source_evidence_ids = _unique(node.source_evidence_ids + edge.evidence_ids)
    return list(nodes.values())


def build_mechanism_graph(observations: list[dict], evidence_records: list[dict] | None = None, l1_claims: list[dict] | None = None, domain_profile: dict | None = None, include_low_confidence: bool = False, max_path_length: int = 3) -> MechanismGraph:
    raw_edges = build_mechanism_edges_from_observations(observations, evidence_records, l1_claims, domain_profile, include_low_confidence)
    edges = _merge_edges(raw_edges)
    nodes = _nodes(edges, observations)
    domain_id = (domain_profile or {}).get("domain_id") or (edges[0].domain_id if edges else None)
    stable = hashlib.sha256("|".join(sorted(edge.edge_id for edge in edges)).encode()).hexdigest()[:16]
    graph = MechanismGraph(graph_id=f"mechanism_{stable}", domain_id=domain_id, subdomain_id=(domain_profile or {}).get("subdomain_id"), nodes=nodes, edges=edges, source_artifacts={"observation_count": len(observations), "evidence_record_count": len(evidence_records or []), "l1_claim_count": len(l1_claims or [])})
    graph.paths = find_mechanism_paths(graph, max_path_length=max_path_length)
    unresolved_statuses = {"ambiguous", "unresolved", "unresolved_fallback", "empty_or_invalid", "low_confidence"}
    graph.counts = {"node_count": len(nodes), "edge_count": len(edges), "path_count": len(graph.paths), "conflict_annotation_count": 0, "evidence_link_count": sum(len(edge.evidence_ids) for edge in edges), "claim_link_count": sum(len(edge.claim_ids) for edge in edges), "observation_link_count": sum(len(edge.observation_ids) for edge in edges), "skipped_low_confidence_count": sum(1 for item in observations if not item.get("allow_high_confidence_graph_use", not item.get("exclude_from_high_confidence_conflict", False)) or str(item.get("normalization_quality", "")).casefold() == "low_confidence") if not include_low_confidence else 0, "skipped_unresolved_count": sum(1 for item in observations if {str(item.get("normalization_status", "")), str(item.get("subject_normalization_status", "")), str(item.get("object_normalization_status", ""))}.intersection(unresolved_statuses)) if not include_low_confidence else 0}
    return graph
