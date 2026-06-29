"""Bounded deterministic hypothesis candidates from artifacts in one run."""

from __future__ import annotations

import hashlib
import json
from typing import Any, Iterable, Iterator


def _values(item: dict, *names: str) -> list[str]:
    values: list[str] = []
    for name in names:
        value = item.get(name)
        if isinstance(value, list):
            values.extend(str(part) for part in value if part not in (None, ""))
        elif value not in (None, ""):
            values.append(str(value))
    return list(dict.fromkeys(values))


def _id(kind: str, *parts: Any) -> str:
    raw = json.dumps([kind, *parts], sort_keys=True, ensure_ascii=False, default=str)
    return f"HC_{hashlib.sha256(raw.encode()).hexdigest()[:16]}"


def _base(kind: str, source: dict, *, source_scope: str, source_mode: str) -> dict:
    subject = source.get("subject_canonical_id") or source.get("source_node_id") or source.get("source")
    obj = source.get("object_canonical_id") or source.get("target_node_id") or source.get("target")
    candidate_id = _id(kind, source.get("candidate_id") or source.get("edge_id") or source.get("path_id"), subject, obj)
    linked_conflicts = _values(source, "abstract_conflict_candidate_id", "linked_conflict_candidate_ids", "conflict_edge_ids", "conflict_ids")
    if source.get("candidate_id") and not str(source.get("candidate_id")).startswith("confirmation_"):
        linked_conflicts = list(dict.fromkeys([str(source["candidate_id"]), *linked_conflicts]))
    return {
        "candidate_id": candidate_id,
        "candidate_type": kind,
        "hypothesis_type": kind,
        "source_mode": source_mode,
        "source_scope": source_scope,
        "evidence_tier": "fulltext_evidence" if source_scope == "full_text" else ("abstract_conflict_signal" if source_scope == "abstract" else "mechanism_graph_evidence"),
        "linked_conflict_candidate_ids": linked_conflicts,
        "linked_fulltext_confirmation_ids": _values(source, "confirmation_id") or ([str(source.get("candidate_id"))] if str(source.get("candidate_id", "")).startswith("confirmation_") else []),
        "linked_evidence_ids": _values(source, "linked_evidence_ids", "evidence_ids", "supporting_evidence_ids"),
        "linked_observation_ids": _values(source, "linked_observation_ids", "normalized_observation_ids", "observation_ids"),
        "linked_mechanism_edge_ids": _values(source, "mechanism_edge_ids", "edge_ids", "edge_id"),
        "linked_mechanism_path_ids": _values(source, "mechanism_path_ids", "path_id"),
        "subject_canonical_id": subject,
        "object_canonical_id": obj,
        "subject_name": source.get("subject_name"),
        "object_name": source.get("object_name"),
        "relation_family": source.get("relation_family") or source.get("relation_type") or "unknown",
        "polarity_type": source.get("polarity_type") or "unknown",
        "direction": source.get("direction") or "context_dependent",
        "direction_distribution": dict(source.get("direction_distribution") or {}),
        "abstract_entropy": source.get("abstract_entropy"),
        "fulltext_entropy": source.get("fulltext_entropy"),
        "context_conditioned_entropy": source.get("context_conditioned_entropy"),
        "context_variables": list(source.get("context_variables") or []),
        "context_groups": source.get("context_groups") or (source.get("context_resolution_summary") or {}).get("groups", {}),
        "resolved_direction_by_context": source.get("resolved_direction_by_context") or {},
        "warnings": list(source.get("warnings") or []),
        "requires_manual_review": False,
        "requires_fulltext_confirmation": False,
        "requires_external_validation": False,
        "high_confidence": source_scope == "full_text",
        "coverage_status": "unresolved_no_coverage",
        "tradeoffs_or_limitations": [],
        "confidence_components": {},
    }


def _confirmed(confirmation: dict, abstract: dict) -> dict:
    merged = {**abstract, **confirmation}
    status = str(confirmation.get("confirmation_status"))
    kinds = {
        "confirmed_conflict": "mechanism_conflict_hypothesis",
        "context_resolved_conflict": "context_partition_hypothesis",
        "false_conflict_due_to_abstract_loss": "abstract_conflict_followup_hypothesis",
        "insufficient_fulltext_coverage": "coverage_gap_hypothesis",
    }
    kind = kinds.get(status, "abstract_conflict_followup_hypothesis")
    item = _base(kind, merged, source_scope="full_text" if status in {"confirmed_conflict", "context_resolved_conflict"} else "abstract", source_mode="fulltext_conflict_confirmation")
    item["linked_fulltext_confirmation_ids"] = [str(confirmation.get("candidate_id") or confirmation.get("confirmation_id") or "UNKNOWN")]
    if abstract.get("candidate_id"):
        item["linked_conflict_candidate_ids"] = [str(abstract["candidate_id"])]
    context_groups = item.get("context_groups") or {}
    item["context_variables"] = list(merged.get("context_variables") or sorted({key for raw in context_groups for key in _parse_context(raw)}))
    if status == "confirmed_conflict":
        item["hypothesis_text"] = "The full-text directional conflict may be explained by context variables or a different mechanism path."
        item["confidence_components"] = {"evidence_strength": 0.9, "conflict_strength": merged.get("fulltext_entropy", 0.8), "context_separability": 0.45}
    elif status == "context_resolved_conflict":
        item["hypothesis_text"] = "The abstract-level conflict may represent different directions in separable contexts rather than a direct contradiction."
        item["resolved_direction_by_context"] = {key: max(value.get("direction_distribution", {}), key=value.get("direction_distribution", {}).get) for key, value in context_groups.items() if value.get("direction_distribution")}
        item["confidence_components"] = {"evidence_strength": 0.85, "conflict_strength": merged.get("fulltext_entropy", 0.75), "context_separability": 0.9, "novelty_hint": 0.4}
    elif status == "insufficient_fulltext_coverage":
        item.update(hypothesis_text="Additional full-text evidence is required before a scientific mechanism hypothesis can be formed.", hypothesis_role="evidence_gap_followup", validation_priority="low", requires_manual_review=True, requires_fulltext_confirmation=True, high_confidence=False, coverage_status="insufficient_coverage")
        item["tradeoffs_or_limitations"] = ["Insufficient full-text coverage; absence of evidence is not contradiction."]
    else:
        item.update(hypothesis_text="The abstract conflict signal requires manual review and should not be treated as a confirmed mechanism conflict.", validation_priority="low", requires_manual_review=True, requires_fulltext_confirmation=True, high_confidence=False)
        item["warnings"] = list(dict.fromkeys([*item["warnings"], "abstract_conflict_not_supported_by_fulltext"]))
        item["tradeoffs_or_limitations"] = ["Full text does not support a high-confidence directional conflict."]
    return item


def _parse_context(raw: str) -> dict:
    try:
        value = json.loads(raw)
        return value if isinstance(value, dict) else {}
    except (TypeError, ValueError):
        return {}


def build_hypothesis_candidates_from_run_artifacts(
    mechanism_graph: dict | None,
    fulltext_conflict_confirmations: Iterable[dict],
    abstract_conflict_candidates: Iterable[dict],
    conflict_focus_set: Iterable[dict],
    legacy_conflict_edges: Iterable[dict],
    observations: Iterable[dict],
    max_candidates: int = 50,
) -> Iterator[dict]:
    """Yield at most ``max_candidates`` traceable candidates in stable priority order."""

    limit = max(0, int(max_candidates))
    abstract_index: dict[str, dict] = {}
    for source in (abstract_conflict_candidates, conflict_focus_set):
        for item in source:
            key = str(item.get("candidate_id") or "")
            if key and key not in abstract_index and len(abstract_index) < max(1, limit * 4):
                abstract_index[key] = item
    observation_index: dict[str, dict] = {}
    observation_by_conflict: dict[str, dict] = {}
    for item in observations:
        for key in _values(item, "observation_id", "triple_id", "claim_id", "evidence_id"):
            if len(observation_index) < max(1, limit * 8):
                observation_index.setdefault(key, item)
        for key in _values(item, "linked_conflict_candidate_ids", "conflict_candidate_ids"):
            if len(observation_by_conflict) < max(1, limit * 8):
                observation_by_conflict.setdefault(key, item)
    for abstract in abstract_index.values():
        linked = [observation_index[key] for key in _values(abstract, "normalized_observation_ids", "observation_ids", "claim_ids") if key in observation_index]
        if linked:
            abstract["linked_observation_ids"] = list(dict.fromkeys([*_values(abstract, "normalized_observation_ids", "observation_ids"), *[str(item.get("observation_id") or item.get("triple_id") or "") for item in linked if item.get("observation_id") or item.get("triple_id")]]))
            abstract["linked_evidence_ids"] = list(dict.fromkeys([*_values(abstract, "linked_evidence_ids"), *[str(item.get("evidence_id")) for item in linked if item.get("evidence_id")]]))
    emitted: set[str] = set()
    count = 0
    graph = mechanism_graph or {}
    nodes = {str(node.get("node_id")): node for node in graph.get("nodes", [])}

    def link_matching_mechanism(item: dict) -> None:
        subject, obj = str(item.get("subject_canonical_id") or ""), str(item.get("object_canonical_id") or "")
        if not subject or not obj:
            return
        matching_edges = [edge for edge in graph.get("edges", []) if str(edge.get("subject_canonical_id") or "") == subject and str(edge.get("object_canonical_id") or "") == obj]
        matching_paths = []
        for path in graph.get("paths", []):
            node_ids = [str(value) for value in path.get("node_ids", [])]
            start = nodes.get(node_ids[0], {}).get("canonical_id") if node_ids else path.get("start_node_id")
            end = nodes.get(node_ids[-1], {}).get("canonical_id") if node_ids else path.get("end_node_id")
            if str(start or "") == subject and str(end or "") == obj:
                matching_paths.append(path)
        item["linked_mechanism_edge_ids"] = list(dict.fromkeys([*item.get("linked_mechanism_edge_ids", []), *[str(edge.get("edge_id")) for edge in matching_edges if edge.get("edge_id")], *[str(edge_id) for path in matching_paths for edge_id in path.get("edge_ids", [])]]))
        item["linked_mechanism_path_ids"] = list(dict.fromkeys([*item.get("linked_mechanism_path_ids", []), *[str(path.get("path_id")) for path in matching_paths if path.get("path_id")]]))
        if matching_paths:
            item["mechanism_specificity"] = max(float(path.get("mechanistic_completeness", 0.0)) for path in matching_paths)
            item["confidence_components"]["mechanism_specificity"] = item["mechanism_specificity"]

    def emit(item: dict):
        nonlocal count
        if count >= limit or item["candidate_id"] in emitted:
            return None
        emitted.add(item["candidate_id"])
        count += 1
        return item

    confirmed_abstract_ids: set[str] = set()
    for confirmation in fulltext_conflict_confirmations:
        abstract_id = str(confirmation.get("abstract_conflict_candidate_id") or "")
        if abstract_id:
            confirmed_abstract_ids.add(abstract_id)
        supporting = abstract_index.get(abstract_id) or observation_by_conflict.get(abstract_id, {})
        candidate = _confirmed(confirmation, supporting)
        link_matching_mechanism(candidate)
        item = emit(candidate)
        if item:
            yield item
        if count >= limit:
            return

    for path in graph.get("paths", []):
        node_ids = [str(value) for value in path.get("node_ids", [])]
        source = {**path, "subject_canonical_id": (nodes.get(node_ids[0], {}).get("canonical_id") if node_ids else path.get("start_node_id")), "object_canonical_id": (nodes.get(node_ids[-1], {}).get("canonical_id") if node_ids else path.get("end_node_id"))}
        item = _base("pathway_bridge_hypothesis", source, source_scope="mechanism", source_mode="mechanism_graph")
        item.update(hypothesis_text="The observed relationship may be mediated by an intermediate mechanism path whose effect varies by context.", mechanism_path=node_ids, intermediate_entities=[nodes.get(node_id, {}).get("canonical_name") or node_id for node_id in node_ids[1:-1]], path_length=int(path.get("path_length", max(0, len(node_ids) - 1))), mechanistic_completeness=float(path.get("mechanistic_completeness", 0.0)), mechanism_specificity=float(path.get("mechanistic_completeness", 0.0)), high_confidence=False)
        item["confidence_components"] = {"evidence_strength": 0.7 if item["linked_evidence_ids"] else 0.45, "mechanism_specificity": item["mechanism_specificity"], "conflict_strength": 0.65 if item["linked_conflict_candidate_ids"] else 0.3}
        result = emit(item)
        if result:
            yield result
        if count >= limit:
            return
    for edge in graph.get("edges", []):
        relation = str(edge.get("relation_type") or "")
        if relation == "unknown_mechanism_relation" or any("missing" in str(value) for value in edge.get("warnings", [])):
            item = _base("mechanism_gap_hypothesis", edge, source_scope="mechanism", source_mode="mechanism_graph")
            item.update(hypothesis_text="Available evidence links the entities, but an explicit mechanism bridge is missing.", requires_external_validation=True, high_confidence=False, mechanism_specificity=0.2, predicted_missing_links=[{"source": edge.get("subject_canonical_id") or edge.get("source_node_id"), "target": edge.get("object_canonical_id") or edge.get("target_node_id"), "relation_family": "unknown_mechanism_relation"}], tradeoffs_or_limitations=["The mechanism bridge is not present in current run evidence."])
            result = emit(item)
            if result:
                yield result
        elif any(word in relation.casefold() for word in ("binding", "target", "receptor")):
            item = _base("target_mediated_hypothesis", edge, source_scope="mechanism", source_mode="mechanism_graph")
            item.update(hypothesis_text="The observed effect may be mediated through the recorded target interaction.", mechanism_specificity=float(edge.get("confidence", 0.5)), high_confidence=False)
            result = emit(item)
            if result:
                yield result
        if count >= limit:
            return
    for abstract_id, abstract in abstract_index.items():
        if abstract_id in confirmed_abstract_ids:
            continue
        item = _base("abstract_conflict_followup_hypothesis", abstract, source_scope="abstract", source_mode="abstract_conflict_screening")
        item.update(hypothesis_text="The abstract-only directional conflict requires full-text confirmation before mechanism interpretation.", high_confidence=False, requires_fulltext_confirmation=True, requires_manual_review=True, validation_priority="low", tradeoffs_or_limitations=["Only abstract-level conflict evidence is available."])
        item["warnings"] = list(dict.fromkeys([*item["warnings"], "abstract_only_not_high_confidence"]))
        result = emit(item)
        if result:
            yield result
        if count >= limit:
            return
    for edge in legacy_conflict_edges if count == 0 else ():
        item = _base("legacy_conflict_hypothesis", edge, source_scope="legacy", source_mode="legacy_conflict_graph")
        item.update(hypothesis_text="The legacy conflict edge is a follow-up hypothesis requiring current-run evidence confirmation.", high_confidence=False, requires_fulltext_confirmation=True, requires_manual_review=True, tradeoffs_or_limitations=["Legacy conflict graph provenance has not been upgraded to full-text confirmation."])
        result = emit(item)
        if result:
            yield result
        if count >= limit:
            return


__all__ = ["build_hypothesis_candidates_from_run_artifacts"]
