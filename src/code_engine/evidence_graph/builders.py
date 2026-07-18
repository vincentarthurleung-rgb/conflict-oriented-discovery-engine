"""Build one run-scoped merged evidence graph from local artifacts."""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any

from .bundle_builder import build_relation_evidence_bundles, stable_id
from .conflict_reasoning import reason_over_bundle
from .direction_polarity import direction_polarity, polarity_distribution
from .graph_io import load_artifact, records, write_json, write_jsonl
from .models import EvidenceEdge, EvidenceGraphEdge, EvidenceGraphNode
from .validators import validate_graph_contract

SCHEMA_VERSION = "merged_evidence_graph.v1"


def _first(item: dict[str, Any], *paths: str) -> Any:
    for path in paths:
        value: Any = item
        for part in path.split("."):
            value = value.get(part) if isinstance(value, dict) else None
        if value not in (None, "", []):
            return value
    return None


def _list(item: dict[str, Any], *names: str) -> list[str]:
    values = []
    for name in names:
        value = item.get(name)
        if isinstance(value, list):
            values.extend(str(entry) for entry in value if entry not in (None, ""))
        elif value not in (None, ""):
            values.append(str(value))
    return list(dict.fromkeys(values))


def _year(value: Any) -> int | None:
    try:
        return int(str(value)[:4])
    except (TypeError, ValueError):
        return None


def _float(value: Any) -> float | None:
    try:
        return float(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def _context(run_dir: Path) -> dict[str, Any]:
    state = load_artifact(run_dir / "run_state.json")
    intake = load_artifact(run_dir / "artifacts" / "intake.json")
    query = state.get("query") if isinstance(state, dict) else None
    run_id = state.get("run_id") if isinstance(state, dict) else run_dir.name
    topic_id = _first(intake, "topic_id", "research_intent.topic_id") if isinstance(intake, dict) else None
    return {"run_id": str(run_id or run_dir.name), "topic_id": topic_id,
            "query_id": stable_id("query", query) if query else None, "query": query}


def _manifest_index(items: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    index = {}
    for item in items:
        for name in ("paper_id", "canonical_paper_id", "original_paper_id", "doi"):
            if item.get(name):
                index[str(item[name])] = item
    return index


def normalize_observation_to_evidence_edge(item: dict[str, Any], manifest: dict[str, dict[str, Any]],
                                           graph_context: dict[str, Any]) -> EvidenceEdge:
    paper_key = _first(item, "canonical_paper_id", "paper_id", "source_paper_id", "doi", "provenance.paper_id")
    paper = manifest.get(str(paper_key), {})
    observation_id = _first(item, "observation_id", "triple_id", "normalized_observation_id")
    claim_id = _first(item, "claim_id", "l1_claim_id")
    evidence_id = _first(item, "evidence_id", "linked_evidence_id")
    original_subject_canonical_id = _first(item, "subject_canonical_id", "subject_id", "normalized_subject_id")
    original_object_canonical_id = _first(item, "object_canonical_id", "object_id", "normalized_object_id")
    subject_canonical_id = original_subject_canonical_id
    object_canonical_id = original_object_canonical_id
    projection_status = _first(item, "core_projection_status")
    projection_role = _first(item, "core_projection_role")
    projection_relation = _first(item, "core_projection_relation")
    if projection_status == "projected" and projection_role == "subject":
        subject_canonical_id = _first(item, "projected_subject_canonical_id", "subject_endpoint.measured_entity_canonical_id") or subject_canonical_id
    if projection_status == "projected" and projection_role == "object":
        object_canonical_id = _first(item, "projected_object_canonical_id", "object_endpoint.measured_entity_canonical_id") or object_canonical_id
    source = subject_canonical_id
    target = object_canonical_id
    direction = _first(item, "direction", "relation_direction", "effect_direction")
    if direction is None:
        sign = _first(item, "relation_sign", "sign")
        direction = "increase" if sign in (1, "+1", "positive") else "decrease" if sign in (-1, "-1", "negative") else "unknown"
    direction = str(direction).casefold()
    span = _first(item, "evidence_span", "evidence_sentence", "span", "sentence")
    paper_id = _first(item, "paper_id", "source_paper_id") or paper.get("paper_id")
    canonical = _first(item, "canonical_paper_id") or paper.get("canonical_paper_id") or paper_key
    warnings = []
    if not source:
        warnings.extend(["missing_subject_canonical_id", "unresolved_subject_scoped_fallback_identity"])
        source = f"RUN:{graph_context['run_id']}:OBS:{observation_id or evidence_id or claim_id or 'unknown'}:subject:{_first(item, 'subject_raw', 'subject_raw_name', 'subject_name', 'subject') or 'unknown'}"
    if not target:
        warnings.extend(["missing_object_canonical_id", "unresolved_object_scoped_fallback_identity"])
        target = f"RUN:{graph_context['run_id']}:OBS:{observation_id or evidence_id or claim_id or 'unknown'}:object:{_first(item, 'object_raw', 'object_raw_name', 'object_name', 'object') or 'unknown'}"
    if direction == "unknown":
        warnings.append("missing_or_unknown_direction")
    if not (paper_id or canonical):
        warnings.append("missing_paper_provenance")
    if span is None:
        warnings.append("missing_evidence_span")
    publication_year = _year(_first(item, "publication_year", "year", "publication_date", "provenance.publication_year") or paper.get("publication_year") or paper.get("year"))
    if publication_year is None:
        warnings.append("missing_publication_year")
    export_warnings = list(warnings)
    identity = observation_id or evidence_id or claim_id or json.dumps(item, ensure_ascii=False, sort_keys=True, default=str)
    return EvidenceEdge(
        evidence_edge_id=stable_id("evidence_edge", canonical, identity, source, target),
        source_entity_id=str(source) if source else None, target_entity_id=str(target) if target else None,
        relation_family=str(projection_relation or _first(item, "formal_relation", "relation_family", "relation_type", "predicate") or "unknown"),
        polarity_type=str(_first(item, "polarity_type", "polarity") or "unknown"), direction=direction,
        direction_polarity=direction_polarity(direction),
        context_variables=_first(item, "context_variables", "context_slots", "context", "conditions") or {},
        evidence_span=span, evidence_text=_first(item, "evidence_text", "evidence_sentence", "text", "sentence"),
        source_scope=_first(item, "source_scope", "scope"), evidence_tier=_first(item, "evidence_tier", "tier"),
        graph_layer=_first(item, "graph_layer"),
        canonical_graph_eligible=item.get("canonical_graph_eligible"),
        allow_high_confidence_graph_use=item.get("allow_high_confidence_graph_use"),
        context_compatibility_status=_first(item, "context_compatibility_status", "context_compatibility.status"),
        strong_context_match=bool(_first(item, "strong_context_match", "context_compatibility.strong_context_match")),
        query_context_only=bool(_first(item, "query_context_only", "context_compatibility.query_context_only")),
        core_context_eligible=bool(_first(item, "core_context_eligible", "context_compatibility.core_context_eligible")),
        excluded_from_core_reason=item.get("excluded_from_core_reason"),
        strong_context_terms_matched=list(_first(item, "strong_context_terms_matched", "context_compatibility.strong_context_terms_matched") or []),
        weak_context_terms_matched=list(_first(item, "weak_context_terms_matched", "context_compatibility.weak_context_terms_matched") or []),
        # Never promote legacy belief_weight into evidence confidence.
        confidence=_float(_first(item, "confidence", "score")),
        paper_id=str(paper_id) if paper_id else None, canonical_paper_id=str(canonical) if canonical else None,
        doi=_first(item, "doi", "provenance.doi") or paper.get("doi"),
        title=_first(item, "title", "article_title", "paper_title", "provenance.title") or paper.get("title"),
        journal=_first(item, "journal", "journal_name", "provenance.journal") or paper.get("journal"),
        publication_year=publication_year, observation_id=str(observation_id) if observation_id else None,
        claim_id=str(claim_id) if claim_id else None, evidence_id=str(evidence_id) if evidence_id else None,
        warnings=warnings, subject_name=_first(item, "subject_name", "subject_canonical_name", "normalized_subject", "subject"),
        subject_type=_first(item, "subject_type", "subject_entity_type"),
        subject_canonical_id=str(subject_canonical_id) if subject_canonical_id else None,
        subject_canonical_name=(_first(item, "projected_subject_canonical_name", "subject_endpoint.measured_entity_canonical_name")
                                if projection_status == "projected" and projection_role == "subject" else None) or _first(item, "subject_canonical_name", "normalized_subject"),
        subject_resolution_status=_first(item, "subject_resolution_status", "subject_normalization_status"),
        subject_resolution_decision_id=_first(item, "subject_resolution_decision_id"),
        object_name=_first(item, "object_name", "object_canonical_name", "normalized_object", "object"),
        object_type=_first(item, "object_type", "object_entity_type"),
        object_canonical_id=str(object_canonical_id) if object_canonical_id else None,
        object_canonical_name=(_first(item, "projected_object_canonical_name", "object_endpoint.measured_entity_canonical_name")
                               if projection_status == "projected" and projection_role == "object" else None) or _first(item, "object_canonical_name", "normalized_object"),
        object_resolution_status=_first(item, "object_resolution_status", "object_normalization_status"),
        object_resolution_decision_id=_first(item, "object_resolution_decision_id"),
        original_subject_canonical_id=str(original_subject_canonical_id) if original_subject_canonical_id else None,
        original_object_canonical_id=str(original_object_canonical_id) if original_object_canonical_id else None,
        original_relation_family=_first(item, "relation_family", "relation_type", "predicate"),
        relation_raw=_first(item, "relation_raw"),
        core_projection_status=projection_status,
        core_projection_role=projection_role,
        core_projection_relation=projection_relation,
        core_projection_reason=_first(item, "core_projection_reason"),
        subject_endpoint=item.get("subject_endpoint") if isinstance(item.get("subject_endpoint"), dict) else {},
        object_endpoint=item.get("object_endpoint") if isinstance(item.get("object_endpoint"), dict) else {},
        linked_claim_ids=_list(item, "linked_claim_ids", "claim_id", "l1_claim_id"),
        linked_evidence_ids=_list(item, "linked_evidence_ids", "evidence_id"),
        linked_observation_ids=_list(item, "linked_observation_ids", "observation_id", "triple_id"),
        linked_conflict_ids=_list(item, "linked_conflict_ids", "linked_conflict_candidate_ids"),
        linked_mechanism_edge_ids=_list(item, "linked_mechanism_edge_ids"),
        linked_mechanism_path_ids=_list(item, "linked_mechanism_path_ids"),
        linked_hypothesis_ids=_list(item, "linked_hypothesis_ids"),
        run_id=graph_context["run_id"], topic_id=graph_context["topic_id"], query_id=graph_context["query_id"],
        export_ready=not bool({"missing_subject_canonical_id", "missing_object_canonical_id", "missing_paper_provenance"} & set(warnings)),
        export_warnings=export_warnings,
    )


def _provenance(edge: EvidenceEdge) -> dict[str, Any]:
    return {key: getattr(edge, key) for key in ("paper_id", "canonical_paper_id", "doi", "title", "journal", "publication_year", "evidence_span", "evidence_text")}


def _key(item: dict[str, Any]) -> str:
    return "|".join(str(item.get(name) or "unknown") for name in ("subject_canonical_id", "object_canonical_id", "relation_family", "polarity_type"))


def _matches_hypothesis(hypothesis: dict[str, Any], conflict: dict[str, Any]) -> bool:
    ids = {str(conflict.get("graph_conflict_id")), str(conflict.get("bundle_id"))}
    if ids & set(_list(hypothesis, "linked_conflict_ids")):
        return True
    if set(_list(hypothesis, "linked_evidence_ids", "linked_observation_ids")) & set(conflict.get("linked_evidence_edge_ids", []) + conflict.get("linked_observation_ids", [])):
        return True
    return _key(hypothesis) == conflict.get("conflict_key") and not conflict.get("conflict_key", "").startswith("unknown|unknown")


def _dedup(values: list[Any], field: str) -> list[Any]:
    return list({str(getattr(item, field) if hasattr(item, field) else item[field]): item for item in values}.values())


def _source_gate_exclusion(edge: EvidenceEdge, context_specific: bool) -> str | None:
    if not edge.observation_id:
        return "missing_observation_provenance"
    if not edge.subject_canonical_id or not edge.object_canonical_id:
        return "missing_endpoint_canonical_id"
    if edge.query_context_only:
        return "query_context_only"
    if edge.graph_layer in {"mechanism_layer", "cross_context_mechanism_layer"}:
        return "cross_context" if edge.graph_layer == "cross_context_mechanism_layer" else "mechanism_layer"
    if edge.graph_layer == "review_layer":
        return "review_layer"
    if edge.graph_layer == "excluded":
        return "not_core_graph_layer"
    if context_specific:
        if edge.graph_layer != "core_canonical_graph":
            return "not_core_graph_layer"
        if edge.canonical_graph_eligible is not True or edge.allow_high_confidence_graph_use is not True:
            return "not_canonical_graph_eligible"
        if edge.core_context_eligible is not True or edge.strong_context_match is not True:
            return "context_mismatch"
        if edge.context_compatibility_status != "context_matched":
            return "context_mismatch"
    else:
        # Older non-context artifacts predate these flags. Explicit false still
        # blocks high-confidence use; absent values remain backwards compatible.
        if edge.canonical_graph_eligible is False or edge.allow_high_confidence_graph_use is False:
            return "not_canonical_graph_eligible"
    if edge.direction_polarity not in {"positive", "negative"}:
        return "missing_polarity"
    return None


def _observation_provenance(edge: EvidenceEdge) -> dict[str, Any]:
    value = {key: getattr(edge, key) for key in (
        "observation_id", "claim_id", "paper_id", "canonical_paper_id", "title", "publication_year",
        "subject_name", "object_name", "relation_family", "direction", "direction_polarity", "graph_layer",
        "canonical_graph_eligible", "allow_high_confidence_graph_use", "context_compatibility_status",
        "strong_context_match", "query_context_only", "core_context_eligible", "excluded_from_core_reason",
        "evidence_text")}
    value["evidence_sentence"] = edge.evidence_text or edge.evidence_span
    return value


def build_merged_evidence_graph_from_run_artifacts(
    run_dir: Path, *, output_dir: Path | None = None, include_abstract: bool = True,
    include_fulltext: bool = True, include_temporal: bool = True, include_hypotheses: bool = True,
    max_edges: int | None = None, min_conflict_papers: int = 2,
    conflict_entropy_threshold: float = 0.55,
) -> dict[str, Any]:
    run_dir = Path(run_dir)
    source_dir, output = run_dir / "artifacts", Path(output_dir) if output_dir else run_dir / "artifacts"
    output.mkdir(parents=True, exist_ok=True)
    context = _context(run_dir)
    runtime_provenance = load_artifact(source_dir / "runtime_provenance_report.json")
    search_intent = load_artifact(source_dir / "semantic_search_intent.json")
    intent_context = ((search_intent.get("seed_triple") or {}).get("context") or {}) if isinstance(search_intent, dict) else {}
    context_specific = bool(
        ((runtime_provenance.get("context_aware_evidence_layering") or {}).get("context_specific_run")
         if isinstance(runtime_provenance, dict) else False)
        or intent_context.get("context_terms") or intent_context.get("terms")
    )
    manifest_items = records(load_artifact(source_dir / "run_paper_manifest.jsonl"))
    manifest = _manifest_index(manifest_items)
    raw = []
    if include_abstract:
        raw.extend(records(load_artifact(source_dir / "l2_abstract_observations.json")))
    if include_fulltext:
        raw.extend(records(load_artifact(source_dir / "l2_fulltext_observations.json")))
    # Full-text evidence remains useful when normalized observation output is absent.
    if include_fulltext:
        raw.extend(records(load_artifact(source_dir / "fulltext_evidence_records.jsonl")))
    evidence_edges = _dedup([normalize_observation_to_evidence_edge(item, manifest, context) for item in raw], "evidence_edge_id")
    incomplete_evidence_edges = [item for item in evidence_edges if not item.subject_canonical_id or not item.object_canonical_id]
    truncation_warning = None
    if max_edges is not None and len(evidence_edges) > max_edges:
        evidence_edges = evidence_edges[:max_edges]
        truncation_warning = "evidence_graph_max_edges_applied"
    bundles = build_relation_evidence_bundles(evidence_edges)
    edge_by_id = {edge.evidence_edge_id: edge for edge in evidence_edges}
    candidates, traces, candidate_rows = [], [], []
    uncontested_rows, insufficient_rows = [], []
    exclusion_counts: Counter[str] = Counter()
    for bundle in bundles:
        all_edges = [edge_by_id[value] for value in bundle.evidence_edge_ids if value in edge_by_id]
        qualified = [edge for edge in all_edges if _source_gate_exclusion(edge, context_specific) is None]
        excluded = [(edge, _source_gate_exclusion(edge, context_specific)) for edge in all_edges if _source_gate_exclusion(edge, context_specific) is not None]
        exclusion_counts.update(reason for _, reason in excluded if reason)
        qualified_bundles = build_relation_evidence_bundles(qualified)
        reason_bundle = qualified_bundles[0] if qualified_bundles else bundle
        candidate, trace = reason_over_bundle(reason_bundle, min_conflict_papers=min_conflict_papers,
                                              conflict_entropy_threshold=conflict_entropy_threshold)
        if not qualified_bundles:
            candidate.status = "graph_insufficient_evidence"
            candidate.reasoning_type = "source_gate_removed_all_observations"
            candidate.reasoning_types = [candidate.reasoning_type]
        row = candidate.to_dict()
        polarity_counts = polarity_distribution(reason_bundle.direction_distribution)
        row.update({
            "candidate_id": candidate.graph_conflict_id,
            "artifact_schema_version": "graph_conflict_candidate.v2",
            "is_true_graph_conflict": candidate.status == "graph_conflict_candidate",
            "conflict_definition": "opposing_direction_polarity_after_source_gate",
            "min_conflict_observations": 2, "min_conflict_papers": min_conflict_papers,
            "qualified_observation_count": len(qualified), "qualified_paper_count": reason_bundle.paper_count if qualified else 0,
            "excluded_observation_count": len(excluded),
            "normalized_observation_ids": sorted(str(edge.observation_id) for edge in all_edges if edge.observation_id),
            "qualified_observation_ids": sorted(str(edge.observation_id) for edge in qualified if edge.observation_id),
            "excluded_observation_ids": sorted(str(edge.observation_id) for edge, _ in excluded if edge.observation_id),
            "direction_polarity_distribution": polarity_counts,
            "opposing_polarity_present": polarity_counts["positive"] > 0 and polarity_counts["negative"] > 0,
            "selection_reason": "opposing_polarity_core_context_qualified" if candidate.status == "graph_conflict_candidate" else candidate.reasoning_type,
            "evidence_tier": "core_context_graph_conflict" if candidate.status == "graph_conflict_candidate" else "insufficient_or_uncontested",
            "observation_provenance": [_observation_provenance(edge) for edge in qualified],
            "excluded_observation_provenance": [{"observation_id": edge.observation_id,
                "exclusion_reason": reason, **_observation_provenance(edge)} for edge, reason in excluded],
            "source_gate_failed": not bool(qualified),
        })
        if candidate.status == "graph_conflict_candidate":
            candidates.append(candidate); candidate_rows.append(row); traces.append(trace)
        elif candidate.status == "graph_uncontested_relation":
            uncontested_rows.append(row); traces.append(trace)
        else:
            insufficient_rows.append(row); traces.append(trace)
    bundle_rows = [item.to_dict() for item in bundles]

    nodes: list[EvidenceGraphNode] = []
    graph_edges: list[EvidenceGraphEdge] = []
    node_ids: set[str] = set()
    edge_ids: set[str] = set()

    def add_node(node: EvidenceGraphNode) -> None:
        if node.node_id not in node_ids:
            node.run_id, node.topic_id, node.query_id = context["run_id"], context["topic_id"], context["query_id"]
            node_ids.add(node.node_id); nodes.append(node)

    def add_edge(source: str, target: str, edge_type: str, *, attributes: dict[str, Any] | None = None,
                 provenance: dict[str, Any] | None = None, warnings: list[str] | None = None) -> None:
        edge_id = stable_id("graph_edge", source, target, edge_type, json.dumps(attributes or {}, sort_keys=True, default=str))
        if edge_id not in edge_ids:
            edge_ids.add(edge_id); graph_edges.append(EvidenceGraphEdge(
                edge_id, source, target, edge_type, attributes or {}, provenance or {}, warnings or [],
                context["run_id"], context["topic_id"], context["query_id"], export_warnings=warnings or []))

    observation_node_by_evidence: dict[str, str] = {}
    observation_node_by_source_id: dict[str, str] = {}
    for item in evidence_edges:
        provenance = _provenance(item)
        paper_identity = item.canonical_paper_id or item.paper_id or item.doi or f"unknown:{item.evidence_edge_id}"
        paper_node = stable_id("paper", paper_identity)
        add_node(EvidenceGraphNode(paper_node, "paper", item.title or str(paper_identity), str(paper_identity), provenance=provenance,
                                   warnings=[w for w in item.warnings if "paper" in w], export_ready=bool(item.canonical_paper_id or item.doi)))
        for entity_id, name, entity_type, role in ((item.source_entity_id, item.subject_name, item.subject_type, "subject"), (item.target_entity_id, item.object_name, item.object_type, "object")):
            if entity_id:
                canonical = item.subject_canonical_id if role == "subject" else item.object_canonical_id
                status = item.subject_resolution_status if role == "subject" else item.object_resolution_status
                add_node(EvidenceGraphNode(stable_id("entity", entity_id), "entity", name or entity_id, entity_id,
                                           attributes={"entity_type": entity_type, "role": role, "canonical_id": canonical, "resolution_status": status,
                                                       "identity_scope": "canonical" if canonical else "observation_scoped_raw_fallback"}))
        observation_identity = item.observation_id or item.evidence_id or item.claim_id or item.evidence_edge_id
        observation_node = stable_id("observation", observation_identity)
        observation_node_by_evidence[item.evidence_edge_id] = observation_node
        for source_id in (item.observation_id, item.evidence_id, item.claim_id, *item.linked_observation_ids, *item.linked_evidence_ids, *item.linked_claim_ids):
            if source_id:
                observation_node_by_source_id[str(source_id)] = observation_node
        attrs = item.to_dict(); attrs.pop("warnings", None)
        add_node(EvidenceGraphNode(observation_node, "observation", f"{item.source_entity_id} {item.direction} {item.target_entity_id}", str(observation_identity), attrs, provenance, item.warnings,
                                   export_ready=item.export_ready, export_warnings=item.export_warnings))
        if item.evidence_span is not None:
            span_node = stable_id("evidence_span", item.evidence_edge_id)
            add_node(EvidenceGraphNode(span_node, "evidence_span", str(item.evidence_text or item.evidence_span)[:160], item.evidence_id,
                                       {"evidence_span": item.evidence_span, "evidence_text": item.evidence_text}, provenance))
            add_edge(paper_node, span_node, "paper_contains_evidence", provenance=provenance)
            add_edge(observation_node, span_node, "observation_supported_by_evidence", provenance=provenance)
        if item.source_entity_id:
            add_edge(observation_node, stable_id("entity", item.source_entity_id), "observation_subject_entity",
                     attributes={"subject_canonical_id": item.subject_canonical_id, "subject_canonical_name": item.subject_canonical_name,
                                 "subject_resolution_status": item.subject_resolution_status,
                                 "subject_resolution_decision_id": item.subject_resolution_decision_id},
                     provenance=provenance)
        if item.target_entity_id:
            add_edge(observation_node, stable_id("entity", item.target_entity_id), "observation_object_entity",
                     attributes={"object_canonical_id": item.object_canonical_id, "object_canonical_name": item.object_canonical_name,
                                 "object_resolution_status": item.object_resolution_status,
                                 "object_resolution_decision_id": item.object_resolution_decision_id},
                     provenance=provenance)
        if item.core_projection_status == "projected" and item.source_entity_id and item.target_entity_id and item.core_projection_relation:
            add_edge(stable_id("entity", item.source_entity_id), stable_id("entity", item.target_entity_id), "projected_core_relation",
                     attributes={
                         "relation": item.core_projection_relation,
                         "projection_role": item.core_projection_role,
                         "projection_reason": item.core_projection_reason,
                         "subject_canonical_id": item.subject_canonical_id,
                         "object_canonical_id": item.object_canonical_id,
                         "original_subject_canonical_id": item.original_subject_canonical_id,
                         "original_object_canonical_id": item.original_object_canonical_id,
                         "original_relation_family": item.original_relation_family,
                         "relation_raw": item.relation_raw,
                         "subject_endpoint": item.subject_endpoint,
                         "object_endpoint": item.object_endpoint,
                         "observation_id": item.observation_id,
                         "evidence_id": item.evidence_id,
                     },
                     provenance=provenance)

    candidate_by_bundle = {item.bundle_id: item for item in candidates}
    for bundle in bundles:
        bundle_node = bundle.bundle_id
        add_node(EvidenceGraphNode(bundle_node, "relation_bundle", f"{bundle.subject_canonical_id} {bundle.relation_family} {bundle.object_canonical_id}", bundle.bundle_id,
                                   bundle.to_dict(), {"canonical_paper_ids": bundle.canonical_paper_ids, "dois": bundle.linked_dois, "publication_year_range": bundle.publication_year_range}, bundle.warnings,
                                   export_ready=bundle.export_ready, export_warnings=bundle.export_warnings))
        for evidence_edge_id in bundle.evidence_edge_ids:
            observation_node = observation_node_by_evidence.get(evidence_edge_id)
            if observation_node:
                add_edge(bundle_node, observation_node, "bundle_contains_observation", attributes={"evidence_edge_id": evidence_edge_id})
                add_edge(bundle_node, observation_node, "bundle_contains_evidence_edge", attributes={"evidence_edge_id": evidence_edge_id})
        candidate = candidate_by_bundle.get(bundle.bundle_id)
        if candidate is None:
            continue
        conflict_node = candidate.graph_conflict_id
        add_node(EvidenceGraphNode(conflict_node, "conflict", candidate.conflict_key, conflict_node, candidate.to_dict(),
                                   {"canonical_paper_ids": candidate.linked_canonical_paper_ids, "dois": candidate.linked_dois}, candidate.warnings,
                                   export_ready=candidate.export_ready, export_warnings=candidate.export_warnings))
        add_edge(bundle_node, conflict_node, "bundle_has_conflict", attributes={"status": candidate.status})
        add_edge(conflict_node, bundle_node, "conflict_derived_from_bundle", attributes={"reasoning_trace_id": candidate.reasoning_trace_id})
        for evidence_edge_id in candidate.linked_evidence_edge_ids:
            observation_node = observation_node_by_evidence.get(evidence_edge_id)
            if observation_node:
                add_edge(conflict_node, observation_node, "conflict_supported_by_observation", attributes={"evidence_edge_id": evidence_edge_id})

    timeline_rows = records(load_artifact(source_dir / "conflict_evidence_timelines.jsonl")) if include_temporal else []
    unmatched_timelines, matched_timeline_ids = [], set()
    conflict_by_key = {item.conflict_key: item for item in candidates}
    for timeline in timeline_rows:
        candidate = conflict_by_key.get(str(timeline.get("conflict_key")))
        if candidate is None and timeline.get("bundle_id"):
            candidate = candidate_by_bundle.get(str(timeline["bundle_id"]))
        timeline_id = str(timeline.get("timeline_id") or timeline.get("conflict_id") or "unknown")
        if candidate is None:
            unmatched_timelines.append(timeline_id); continue
        matched_timeline_ids.add(timeline_id)
        for window_name, edge_type in (("conflict_source_window", "conflict_has_source_window"), ("later_evidence_window", "conflict_has_later_window")):
            window = timeline.get(window_name)
            if not isinstance(window, dict):
                continue
            window_node = stable_id("temporal_window", candidate.graph_conflict_id, window_name)
            add_node(EvidenceGraphNode(window_node, "temporal_window", window_name, window_node,
                                       {**window, "timeline_id": timeline_id, "temporal_status": timeline.get("status")}, {}))
            add_edge(candidate.graph_conflict_id, window_node, edge_type, attributes={"temporal_status": timeline.get("status")})
            for index, timeline_item in enumerate(timeline.get("evidence_timeline", [])):
                role = str(timeline_item.get("primary_role") or timeline_item.get("role") or "")
                belongs = window_name == "conflict_source_window" and role == "conflict_source" or window_name == "later_evidence_window" and role != "conflict_source"
                if not belongs:
                    continue
                item_node = stable_id("timeline_evidence", timeline_id, index, timeline_item.get("evidence_id"))
                provenance = {key: timeline_item.get(key) for key in ("paper_id", "canonical_paper_id", "doi", "title", "journal", "year", "evidence_span", "evidence_text")}
                add_node(EvidenceGraphNode(item_node, "timeline_evidence_item", str(timeline_item.get("evidence_text") or timeline_item.get("evidence_span") or role)[:160],
                                           str(timeline_item.get("evidence_id") or item_node), timeline_item, provenance))
                add_edge(window_node, item_node, "temporal_window_contains_evidence", provenance=provenance)

    mechanism_graph = load_artifact(source_dir / "mechanism_graph.json")
    mechanism_edge_nodes, mechanism_path_nodes = {}, {}
    if isinstance(mechanism_graph, dict):
        for index, mechanism_edge in enumerate(mechanism_graph.get("edges", [])):
            identity = str(mechanism_edge.get("edge_id") or mechanism_edge.get("mechanism_edge_id") or index)
            node_id = stable_id("mechanism_edge", identity); mechanism_edge_nodes[identity] = node_id
            add_node(EvidenceGraphNode(node_id, "mechanism_edge", identity, identity, mechanism_edge, {}))
        for index, mechanism_path in enumerate(mechanism_graph.get("paths", [])):
            identity = str(mechanism_path.get("path_id") or mechanism_path.get("mechanism_path_id") or index)
            node_id = stable_id("mechanism_path", identity); mechanism_path_nodes[identity] = node_id
            add_node(EvidenceGraphNode(node_id, "mechanism_path", identity, identity, mechanism_path, {}))

    hypotheses = records(load_artifact(source_dir / "hypothesis_hyperedges.jsonl")) if include_hypotheses else []
    comparisons = records(load_artifact(source_dir / "hypothesis_later_evidence_comparisons.jsonl")) if include_hypotheses else []
    comparison_by_hypothesis = {str(item.get("hypothesis_id")): item for item in comparisons if item.get("hypothesis_id")}
    unmatched_hypotheses, matched_hypotheses = [], set()
    for hypothesis in hypotheses:
        hypothesis_id = str(hypothesis.get("hypothesis_id") or hypothesis.get("candidate_id") or stable_id("hypothesis", json.dumps(hypothesis, sort_keys=True, default=str)))
        hypothesis_node = stable_id("hypothesis", hypothesis_id)
        provenance = {key: hypothesis.get(key) for key in ("linked_dois", "linked_titles", "linked_journals", "publication_year_range")}
        add_node(EvidenceGraphNode(hypothesis_node, "hypothesis", str(hypothesis.get("hypothesis_text") or hypothesis.get("text") or hypothesis_id), hypothesis_id, hypothesis, provenance))
        matches = [candidate for candidate in candidates if _matches_hypothesis(hypothesis, candidate.to_dict())]
        if not matches:
            if hypothesis.get("hypothesis_type") == "graph_conflict_hypothesis":
                unmatched_hypotheses.append(hypothesis_id)
                nodes[-1].warnings.append("hypothesis_unmatched_to_graph_conflict")
                nodes[-1].export_warnings.append("hypothesis_unmatched_to_graph_conflict")
            else:
                nodes[-1].warnings.append("abstract_only_hypothesis_without_graph_conflict_match")
        for candidate in matches:
            matched_hypotheses.add(hypothesis_id)
            add_edge(hypothesis_node, candidate.graph_conflict_id, "hypothesis_explains_conflict")
            comparison = comparison_by_hypothesis.get(hypothesis_id)
            if comparison:
                add_edge(hypothesis_node, candidate.graph_conflict_id, "hypothesis_compared_with_later_evidence", attributes=comparison)
        for evidence_id in _list(hypothesis, "linked_evidence_ids", "linked_observation_ids"):
            target = observation_node_by_source_id.get(evidence_id)
            if target:
                add_edge(hypothesis_node, target, "hypothesis_uses_evidence")
        for mechanism_id in _list(hypothesis, "linked_mechanism_edge_ids"):
            if mechanism_id in mechanism_edge_nodes:
                add_edge(hypothesis_node, mechanism_edge_nodes[mechanism_id], "hypothesis_uses_mechanism_edge")
        for mechanism_id in _list(hypothesis, "linked_mechanism_path_ids"):
            if mechanism_id in mechanism_path_nodes:
                add_edge(hypothesis_node, mechanism_path_nodes[mechanism_id], "hypothesis_uses_mechanism_path")

    validation_count = 0
    for filename, node_type in (("validation_anchors.jsonl", "validation_anchor"), ("external_validation_results.jsonl", "validation_result")):
        for index, item in enumerate(records(load_artifact(source_dir / filename))):
            identity = str(_first(item, "anchor_id", "result_id", "validation_id") or index)
            add_node(EvidenceGraphNode(stable_id(node_type, identity), node_type, identity, identity, item, {}))
            validation_count += 1

    node_rows, graph_edge_rows = [item.to_dict() for item in nodes], [item.to_dict() for item in graph_edges]
    contract = validate_graph_contract(node_rows, graph_edge_rows, bundle_rows, candidate_rows,
                                       hypotheses_without_match=unmatched_hypotheses,
                                       timelines_without_match=unmatched_timelines if candidate_rows else [])
    contract.update({
        "incomplete_evidence_edge_count": len(incomplete_evidence_edges),
        "excluded_from_bundle_reasoning_count": len(incomplete_evidence_edges),
        "missing_subject_canonical_id_count": sum(not item.subject_canonical_id for item in evidence_edges),
        "missing_object_canonical_id_count": sum(not item.object_canonical_id for item in evidence_edges),
        "missing_raw_subject_endpoint_canonical_id_count": sum(not item.original_subject_canonical_id for item in evidence_edges),
        "missing_raw_object_endpoint_canonical_id_count": sum(not item.original_object_canonical_id for item in evidence_edges),
        "successful_core_projections": sum(item.core_projection_status == "projected" for item in evidence_edges),
        "unsupported_relation_projections": sum(item.core_projection_reason == "relation_projection_not_supported" for item in evidence_edges),
        "graph_policy_exclusions": sum(item.core_projection_status in {"excluded", "unsupported"} for item in evidence_edges),
        "non_molecular_readout_exclusions": sum(item.core_projection_reason == "non_molecular_readout" for item in evidence_edges),
        "identity_incomplete_conflict_candidate_count": 0,
    })
    graph_subject_ids = {
        edge["attributes"].get("subject_canonical_id")
        for edge in graph_edge_rows
        if edge.get("edge_type") == "observation_subject_entity" and edge.get("attributes", {}).get("subject_canonical_id")
    }
    graph_object_ids = {
        edge["attributes"].get("object_canonical_id")
        for edge in graph_edge_rows
        if edge.get("edge_type") == "observation_object_entity" and edge.get("attributes", {}).get("object_canonical_id")
    }
    resolved_subject_obs = {edge.subject_canonical_id for edge in evidence_edges if edge.subject_resolution_status == "resolved" and edge.subject_canonical_id}
    resolved_object_obs = {edge.object_canonical_id for edge in evidence_edges if edge.object_resolution_status == "resolved" and edge.object_canonical_id}
    contract["canonical_subject_ids_written_to_graph"] = len(resolved_subject_obs & graph_subject_ids)
    contract["canonical_object_ids_written_to_graph"] = len(resolved_object_obs & graph_object_ids)
    def _resolved_missing_observation_id_failure(edge: EvidenceEdge, role: str) -> bool:
        endpoint = edge.subject_endpoint if role == "subject" else edge.object_endpoint
        if endpoint.get("endpoint_decomposition_status") == "decomposed" and endpoint.get("core_projection_status") != "projected":
            return False
        status = edge.subject_resolution_status if role == "subject" else edge.object_resolution_status
        canonical_id = edge.subject_canonical_id if role == "subject" else edge.object_canonical_id
        return bool(status == "resolved" and not canonical_id)

    resolved_missing_obs = sum(
        _resolved_missing_observation_id_failure(edge, "subject")
        + _resolved_missing_observation_id_failure(edge, "object")
        for edge in evidence_edges
    )
    contract["resolved_endpoint_missing_observation_canonical_id_failures"] = resolved_missing_obs
    contract["observation_to_graph_propagation_failures"] = (
        len(resolved_subject_obs - graph_subject_ids) + len(resolved_object_obs - graph_object_ids) + resolved_missing_obs
    )
    contract["engineering_propagation_errors"] = {
        "endpoint_decision_join_failures": 0,
        "decision_to_observation_propagation_failures": resolved_missing_obs,
        "observation_to_graph_propagation_failures": contract["observation_to_graph_propagation_failures"],
    }
    contract["intentional_core_graph_exclusions"] = {
        "relation_projection_not_supported": contract["unsupported_relation_projections"],
        "graph_policy_exclusions": contract["graph_policy_exclusions"],
        "non_molecular_readout": contract["non_molecular_readout_exclusions"],
    }
    if contract["observation_to_graph_propagation_failures"]:
        contract["status"] = "warnings"
        contract["warnings"] = sorted(set(contract.get("warnings", []) + ["observation_to_graph_propagation_failures"]))
    existing = records(load_artifact(source_dir / "abstract_conflict_candidates.jsonl"))
    existing_keys = {_key(item): item for item in existing}
    graph_conflicts = [item for item in candidate_rows if item["status"] == "graph_conflict_candidate"]
    graph_keys = {item["conflict_key"]: item for item in graph_conflicts}
    matched_keys = sorted(set(existing_keys) & set(graph_keys))
    alignment = {
        "artifact_schema_version": "graph_conflict_alignment.v1", "run_id": context["run_id"],
        "matched_conflicts": [{"conflict_key": key, "graph_conflict_id": graph_keys[key]["graph_conflict_id"], "existing_candidate_id": existing_keys[key].get("candidate_id")} for key in matched_keys],
        "graph_only_conflicts": [graph_keys[key] for key in sorted(set(graph_keys) - set(existing_keys))],
        "existing_only_conflicts": [existing_keys[key] for key in sorted(set(existing_keys) - set(graph_keys))],
        "warnings": [], "export_ready": True, "export_warnings": [],
    }
    status_counts = Counter({"graph_conflict_candidate": len(candidate_rows),
                            "graph_uncontested_relation": len(uncontested_rows),
                            "graph_insufficient_evidence": len(insufficient_rows)})
    hypothesis_summary = load_artifact(source_dir / "hypothesis_summary.json")
    timeline_summary = load_artifact(source_dir / "conflict_evidence_timeline_summary.json")
    evidence_with_span = sum(bool(item.evidence_span or item.evidence_text) for item in evidence_edges)
    evidence_with_year = sum(item.publication_year is not None for item in evidence_edges)
    provenance_count = sum(bool(item.paper_id or item.canonical_paper_id or item.doi) for item in evidence_edges)
    warnings = sorted({warning for item in evidence_edges for warning in item.warnings} | ({truncation_warning} if truncation_warning else set()))
    if not raw:
        warnings.append("no_observation_input")
    summary = {
        "status": "completed" if raw else "no_input", "run_id": context["run_id"], "topic_id": context["topic_id"],
        "query_id": context["query_id"], "artifact_schema_version": SCHEMA_VERSION, "scope": "run_level_graph_ready_reasoning_layer",
        "node_count": len(nodes), "edge_count": len(graph_edges),
        **{f"{kind}_node_count": sum(item.node_type == kind for item in nodes) for kind in ("paper", "entity", "observation", "evidence_span", "hypothesis")},
        "relation_bundle_count": len(bundles), "graph_relation_bundle_count": len(bundles),
        "graph_conflict_candidate_count": status_counts["graph_conflict_candidate"],
        "true_graph_conflict_count": status_counts["graph_conflict_candidate"],
        "graph_uncontested_relation_count": status_counts["graph_uncontested_relation"],
        "graph_insufficient_evidence_count": status_counts["graph_insufficient_evidence"],
        "graph_insufficient_conflict_bundle_count": status_counts["graph_insufficient_evidence"],
        "single_paper_bundle_excluded_count": sum(row.get("qualified_paper_count", 0) < min_conflict_papers for row in insufficient_rows),
        "same_polarity_bundle_excluded_count": len(uncontested_rows),
        "missing_observation_provenance_excluded_count": exclusion_counts["missing_observation_provenance"],
        "non_core_source_excluded_count": sum(exclusion_counts[key] for key in ("not_core_graph_layer", "not_canonical_graph_eligible")),
        "query_context_only_excluded_count": exclusion_counts["query_context_only"],
        "cross_context_excluded_count": exclusion_counts["cross_context"],
        "review_layer_excluded_count": exclusion_counts["review_layer"],
        "mechanism_layer_excluded_count": exclusion_counts["mechanism_layer"],
        "direction_polarity_normalization_enabled": True, "source_gate_enabled": True,
        "graph_conflict_source_gate_enabled": True,
        "timeline_node_count": sum(item.node_type in {"temporal_window", "timeline_evidence_item"} for item in nodes),
        "validation_node_count": validation_count,
        "bundle_with_conflict_rate": round(status_counts["graph_conflict_candidate"] / len(bundles), 6) if bundles else 0.0,
        "observation_with_paper_provenance_rate": round(provenance_count / len(evidence_edges), 6) if evidence_edges else 0.0,
        "evidence_with_span_rate": round(evidence_with_span / len(evidence_edges), 6) if evidence_edges else 0.0,
        "evidence_with_publication_year_rate": round(evidence_with_year / len(evidence_edges), 6) if evidence_edges else 0.0,
        "hypothesis_matched_to_conflict_rate": round(len(matched_hypotheses) / len(hypotheses), 6) if hypotheses else 0.0,
        "timeline_attached_to_conflict_rate": round(len(matched_timeline_ids) / len(timeline_rows), 6) if timeline_rows else 0.0,
        "existing_abstract_conflict_candidate_count": len(existing),
        "matched_existing_conflict_count": len(matched_keys), "graph_only_conflict_count": len(set(graph_keys) - set(existing_keys)),
        "existing_only_conflict_count": len(set(existing_keys) - set(graph_keys)),
        "incomplete_evidence_edge_count": len(incomplete_evidence_edges),
        "excluded_from_bundle_reasoning_count": len(incomplete_evidence_edges),
        "missing_subject_canonical_id_count": sum(not item.subject_canonical_id for item in evidence_edges),
        "missing_object_canonical_id_count": sum(not item.object_canonical_id for item in evidence_edges),
        "missing_raw_subject_endpoint_canonical_id_count": sum(not item.original_subject_canonical_id for item in evidence_edges),
        "missing_raw_object_endpoint_canonical_id_count": sum(not item.original_object_canonical_id for item in evidence_edges),
        "successful_core_projections": sum(item.core_projection_status == "projected" for item in evidence_edges),
        "unsupported_relation_projections": sum(item.core_projection_reason == "relation_projection_not_supported" for item in evidence_edges),
        "graph_policy_exclusions": sum(item.core_projection_status in {"excluded", "unsupported"} for item in evidence_edges),
        "non_molecular_readout_exclusions": sum(item.core_projection_reason == "non_molecular_readout" for item in evidence_edges),
        "identity_incomplete_conflict_candidate_count": 0,
        "canonical_subject_ids_written_to_graph": contract["canonical_subject_ids_written_to_graph"],
        "canonical_object_ids_written_to_graph": contract["canonical_object_ids_written_to_graph"],
        "observation_to_graph_propagation_failures": contract["observation_to_graph_propagation_failures"],
        "graph_conflict_candidates_used_by_hypothesis": int(hypothesis_summary.get("graph_conflict_candidates_used", 0)) if isinstance(hypothesis_summary, dict) else 0,
        "graph_conflict_candidates_used_by_timeline": int(timeline_summary.get("graph_conflict_candidates_used", 0)) if isinstance(timeline_summary, dict) else 0,
        "timeline_rebuild_status": timeline_summary.get("timeline_rebuild_status") if isinstance(timeline_summary, dict) else None,
        "stale_source_timeline_artifacts_ignored": bool(timeline_summary.get("stale_source_timeline_artifacts_ignored")) if isinstance(timeline_summary, dict) else False,
        "timeline_conflict_attachment_status": ("not_applicable_no_true_graph_conflicts" if not candidate_rows
            else "attached" if matched_timeline_ids else "no_matching_timeline"),
        "warnings": sorted(set(warnings)), "export_ready": contract["status"] == "valid", "export_warnings": contract["warnings"],
    }
    artifacts = {
        "nodes": write_jsonl(output / "merged_evidence_graph_nodes.jsonl", nodes),
        "edges": write_jsonl(output / "merged_evidence_graph_edges.jsonl", graph_edges),
        "bundles": write_jsonl(output / "relation_evidence_bundles.jsonl", bundles),
        "graph_relation_bundles": write_jsonl(output / "graph_relation_bundles.jsonl", bundles),
        "uncontested": write_jsonl(output / "graph_uncontested_relation_bundles.jsonl", uncontested_rows),
        "insufficient": write_jsonl(output / "graph_insufficient_conflict_bundles.jsonl", insufficient_rows),
        "conflicts": write_jsonl(output / "graph_conflict_candidates.jsonl", candidate_rows),
        "graph_conflict_summary": write_json(output / "graph_conflict_summary.json", summary),
        "reasoning_traces": write_jsonl(output / "graph_reasoning_traces.jsonl", traces),
        "summary": write_json(output / "merged_evidence_graph_summary.json", summary),
        "contract_report": write_json(output / "merged_evidence_graph_contract_report.json", contract),
        "alignment_report": write_json(output / "graph_conflict_alignment_report.json", alignment),
    }
    return {"summary": summary, "artifacts": artifacts, "contract_report": contract, "alignment_report": alignment,
            "evidence_edges": [item.to_dict() for item in evidence_edges], "bundles": bundle_rows,
            "conflicts": candidate_rows, "uncontested": uncontested_rows, "insufficient": insufficient_rows,
            "reasoning_traces": [item.to_dict() for item in traces],
            "nodes": node_rows, "edges": graph_edge_rows}
