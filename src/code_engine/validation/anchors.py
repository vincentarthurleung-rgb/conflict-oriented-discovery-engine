"""Build provenance-preserving validation anchors from scientific artifacts."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Iterable

from code_engine.schemas.validation import ValidationAnchor


def _value(item: Any, name: str, default=None):
    if isinstance(item, dict):
        return item.get(name, default)
    return getattr(item, name, default)


def _stable(anchor_type: str, *parts: Any) -> str:
    payload = "|".join((anchor_type, *(str(item or "") for item in parts)))
    return hashlib.sha256(payload.encode()).hexdigest()[:16]


def _entity(value: Any, entity_type: str | None = None) -> dict[str, Any]:
    if isinstance(value, dict):
        result = dict(value)
        result.setdefault("name", result.get("canonical_name") or result.get("raw_name") or result.get("id") or "")
        return result
    return {"name": str(value or ""), "entity_type": entity_type or "unknown"}


def _anchor(
    anchor_type: str, entities: list[dict], *, validation_intent: str,
    provenance: dict[str, list[str]] | None = None, relations: list[dict] | None = None,
    contexts: dict | None = None, domain_id: str | None = None,
    relation_family: str | None = None, polarity_type: str | None = None,
    direction: str | None = None, confidence: float = 0.8, priority: int = 1,
) -> ValidationAnchor:
    provenance = provenance or {}
    canonical = [item.get("canonical_id") or item.get("id") or item.get("name") for item in entities]
    warnings = []
    if any(not (item.get("canonical_id") or item.get("id")) for item in entities):
        confidence = min(confidence, 0.5)
        warnings.append("exploratory_anchor_entity_missing_canonical_id")
    return ValidationAnchor(
        anchor_id=_stable(anchor_type, *canonical, relation_family, direction, json.dumps(contexts or {}, sort_keys=True)),
        anchor_type=anchor_type, entities=entities, relations=relations or [], contexts=contexts or {},
        domain_id=domain_id, relation_family=relation_family, polarity_type=polarity_type,
        direction=direction, linked_hypothesis_ids=provenance.get("hypothesis_ids", []),
        linked_conflict_ids=provenance.get("conflict_ids", []),
        linked_evidence_ids=provenance.get("evidence_ids", []),
        linked_mechanism_edge_ids=provenance.get("mechanism_edge_ids", []),
        linked_mechanism_path_ids=provenance.get("mechanism_path_ids", []),
        linked_paper_ids=provenance.get("paper_ids", []),
        linked_canonical_paper_ids=provenance.get("canonical_paper_ids", []),
        linked_dois=provenance.get("dois", []), linked_titles=provenance.get("titles", []),
        linked_journals=provenance.get("journals", []),
        validation_intent=validation_intent, confidence=confidence, priority=priority,
        warnings=warnings,
    )


def build_validation_anchors_from_hypotheses(hypotheses: Iterable[Any]) -> list[ValidationAnchor]:
    anchors = []
    for hypothesis in hypotheses:
        hypothesis_id = str(_value(hypothesis, "hypothesis_id", "UNKNOWN"))
        entities = [_entity(item) for item in (_value(hypothesis, "entities", []) or [])]
        seed_pair = str(_value(hypothesis, "seed_pair", ""))
        if len(entities) < 2 and "->" in seed_pair:
            entities = [_entity(item.strip()) for item in seed_pair.split("->", 1)]
        relation = str(_value(hypothesis, "relation_family", _value(hypothesis, "relation_type", "unknown")))
        contexts = dict(_value(hypothesis, "context", {}) or {})
        contexts.update({"hypothesis_contexts": _value(hypothesis, "contexts", []) or []})
        provenance = {
            "hypothesis_ids": [hypothesis_id],
            "evidence_ids": list(_value(hypothesis, "linked_evidence_ids", _value(hypothesis, "evidence_ids", [])) or []),
            "conflict_ids": list(_value(hypothesis, "linked_conflict_ids", _value(hypothesis, "conflict_bottlenecks", [])) or []),
            "mechanism_edge_ids": list(_value(hypothesis, "linked_mechanism_edge_ids", []) or []),
            "mechanism_path_ids": list(_value(hypothesis, "linked_mechanism_path_ids", []) or []),
            "paper_ids": list(_value(hypothesis, "linked_paper_ids", []) or []),
            "canonical_paper_ids": list(_value(hypothesis, "linked_canonical_paper_ids", []) or []),
            "dois": list(_value(hypothesis, "linked_dois", []) or []),
            "titles": list(_value(hypothesis, "linked_titles", []) or []),
            "journals": list(_value(hypothesis, "linked_journals", []) or []),
        }
        requirements = list(_value(hypothesis, "validation_requirements", []) or [])
        intents = [str(item.get("requirement_type")) if isinstance(item, dict) else str(item) for item in requirements]
        intent = intents[0] if intents else _intent_for_relation(relation, contexts)
        anchors.append(_anchor("hypothesis_anchor", entities, validation_intent=intent, provenance=provenance, contexts=contexts, relation_family=relation, confidence=0.85, priority=3))
        for requested_intent in intents[1:]:
            anchors.append(_anchor("hypothesis_anchor", entities, validation_intent=requested_intent, provenance=provenance, contexts={**contexts, "validation_requirement": requested_intent}, relation_family=relation, confidence=0.8, priority=2))
        if len(entities) >= 2:
            anchors.append(_anchor("triple_anchor", entities[:2], validation_intent=intent, provenance=provenance, relations=[{"relation_family": relation}], contexts=contexts, relation_family=relation, confidence=0.8, priority=3))
        if intent == "clinical_context_check":
            anchors.append(_anchor("clinical_context_anchor", entities, validation_intent=intent, provenance=provenance, contexts=contexts, relation_family=relation, confidence=0.75, priority=2))
        if intent == "pathway_membership_check":
            anchors.append(_anchor("pathway_anchor", entities, validation_intent=intent, provenance=provenance, contexts=contexts, relation_family=relation, confidence=0.75, priority=2))
        for gap in _value(hypothesis, "predicted_missing_links", []) or []:
            gap_entities = [_entity(gap.get("source") or gap.get("subject")), _entity(gap.get("target") or gap.get("object"))]
            anchors.append(_anchor("mechanism_gap_anchor", gap_entities, validation_intent=_intent_for_relation(str(gap.get("relation_family") or "unknown"), {}), provenance=provenance, relations=[gap], relation_family=gap.get("relation_family"), confidence=0.6, priority=2))
    return _deduplicate(anchors)


def build_validation_anchors_from_conflicts(conflicts: Iterable[Any]) -> list[ValidationAnchor]:
    anchors = []
    for conflict in conflicts:
        conflict_id = str(_value(conflict, "conflict_edge_id", _value(conflict, "edge_id", _value(conflict, "candidate_id", "UNKNOWN"))))
        entities = [
            _entity({"canonical_id": _value(conflict, "subject_canonical_id"), "name": _value(conflict, "subject_name", _value(conflict, "source", ""))}),
            _entity({"canonical_id": _value(conflict, "object_canonical_id"), "name": _value(conflict, "object_name", _value(conflict, "target", ""))}),
        ]
        relation = str(_value(conflict, "relation_family", "unknown"))
        contexts = dict(_value(conflict, "context_resolution_summary", _value(conflict, "context", {})) or {})
        anchors.append(_anchor(
            "conflict_anchor", entities, validation_intent=_intent_for_relation(relation, contexts),
            provenance={"conflict_ids": [conflict_id], "evidence_ids": list(_value(conflict, "linked_evidence_ids", []) or [])},
            contexts=contexts, relation_family=relation, polarity_type=_value(conflict, "polarity_type"),
            confidence=0.85 if _value(conflict, "confirmation_status") in {"confirmed_conflict", "context_resolved_conflict"} else 0.65,
            priority=3,
        ))
    return _deduplicate(anchors)


def build_validation_anchors_from_mechanism_graph(graph: Any) -> list[ValidationAnchor]:
    anchors = []
    for path in _value(graph, "paths", []) or []:
        path_id = str(_value(path, "path_id", "UNKNOWN"))
        entities = [_entity(item) for item in (_value(path, "entities", []) or _value(path, "node_ids", []) or [])]
        anchors.append(_anchor("mechanism_path_anchor", entities, validation_intent="pathway_membership_check", provenance={"mechanism_path_ids": [path_id], "evidence_ids": list(_value(path, "supporting_evidence_ids", []) or [])}, confidence=0.8, priority=2))
    for edge in _value(graph, "edges", []) or []:
        if _value(edge, "relation_type") == "unknown_mechanism_relation" or "missing" in list(_value(edge, "warnings", []) or []):
            entities = [_entity({"canonical_id": _value(edge, "subject_canonical_id"), "name": _value(edge, "subject_name", "")}), _entity({"canonical_id": _value(edge, "object_canonical_id"), "name": _value(edge, "object_name", "")})]
            anchors.append(_anchor("mechanism_gap_anchor", entities, validation_intent=_intent_for_relation(str(_value(edge, "relation_type", "unknown")), {}), provenance={"mechanism_edge_ids": [str(_value(edge, "edge_id", "UNKNOWN"))], "evidence_ids": list(_value(edge, "evidence_ids", []) or [])}, relation_family=_value(edge, "relation_type"), confidence=0.6, priority=2))
    return _deduplicate(anchors)


def build_validation_anchors_from_observations(observations: Iterable[Any]) -> list[ValidationAnchor]:
    anchors = []
    gene_entities = []
    evidence_ids = []
    for item in observations:
        entities = [
            _entity({"canonical_id": _value(item, "subject_canonical_id"), "name": _value(item, "subject_canonical_name", _value(item, "subject", "")), "entity_type": _value(item, "subject_entity_type", "unknown")}),
            _entity({"canonical_id": _value(item, "object_canonical_id"), "name": _value(item, "object_canonical_name", _value(item, "object", "")), "entity_type": _value(item, "object_entity_type", "unknown")}),
        ]
        relation = str(_value(item, "relation_family", "unknown"))
        evidence_id = str(_value(item, "evidence_id", _value(item, "observation_id", "")))
        anchors.append(_anchor("triple_anchor", entities, validation_intent=_intent_for_relation(relation, _value(item, "context", {}) or {}), provenance={"evidence_ids": [evidence_id] if evidence_id else []}, contexts=_value(item, "context", {}) or {}, relation_family=relation, polarity_type=_value(item, "polarity_type"), direction=_value(item, "direction"), confidence=0.8 if _value(item, "allow_high_confidence_graph_use", False) else 0.45, priority=1))
        for entity in entities:
            if entity.get("entity_type") in {"gene", "protein"}:
                gene_entities.append(entity)
        if evidence_id:
            evidence_ids.append(evidence_id)
    unique_genes = {item.get("canonical_id") or item.get("name"): item for item in gene_entities}
    if len(unique_genes) >= 2:
        anchors.append(_anchor("gene_set_anchor", list(unique_genes.values()), validation_intent="dataset_discovery", provenance={"evidence_ids": evidence_ids}, confidence=0.75, priority=1))
    return _deduplicate(anchors)


def build_validation_anchors_from_triples(triples: Iterable[Any]) -> list[ValidationAnchor]:
    observations = []
    for triple in triples:
        observations.append({
            "subject": _value(triple, "subject", ""), "object": _value(triple, "object", _value(triple, "target", "")),
            "subject_canonical_id": _value(triple, "subject_canonical_id"), "object_canonical_id": _value(triple, "object_canonical_id"),
            "relation_family": _value(triple, "relation_family", _value(triple, "relation", "unknown")),
            "evidence_id": _value(triple, "evidence_id"), "context": _value(triple, "context", {}),
            "allow_high_confidence_graph_use": bool(_value(triple, "subject_canonical_id") and _value(triple, "object_canonical_id")),
        })
    return build_validation_anchors_from_observations(observations)


def _intent_for_relation(relation: str, contexts: dict) -> str:
    text = f"{relation} {json.dumps(contexts, ensure_ascii=False)}".casefold()
    if any(term in text for term in ("expression", "omics", "upregulat", "downregulat")):
        return "expression_direction_check"
    if any(term in text for term in ("binding", "receptor", "activity", "target")):
        return "binding_activity_check"
    if any(term in text for term in ("pathway", "signaling", "mechanism")):
        return "pathway_membership_check"
    if any(term in text for term in ("protein_interaction", "ligand_receptor", "ppi")):
        return "protein_interaction_check"
    if any(term in text for term in ("clinical", "disease", "outcome", "trial", "patient")):
        return "clinical_context_check"
    if any(term in text for term in ("cancer", "oncology", "dependency")):
        return "cancer_dependency_check"
    return "identity_lookup"


def _deduplicate(anchors: list[ValidationAnchor]) -> list[ValidationAnchor]:
    return list({item.anchor_id: item for item in anchors}.values())


def write_validation_anchors(anchors: list[ValidationAnchor], output_dir: str | Path) -> dict[str, str]:
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    records = output / "validation_anchors.jsonl"
    summary = output / "validation_anchor_summary.json"
    records.write_text("".join(item.model_dump_json() + "\n" for item in anchors), encoding="utf-8")
    counts: dict[str, int] = {}
    for item in anchors:
        counts[item.anchor_type] = counts.get(item.anchor_type, 0) + 1
    summary.write_text(json.dumps({"anchor_count": len(anchors), "anchor_type_counts": counts}, indent=2), encoding="utf-8")
    return {"anchors": str(records), "summary": str(summary)}


__all__ = [
    "build_validation_anchors_from_hypotheses", "build_validation_anchors_from_conflicts",
    "build_validation_anchors_from_mechanism_graph", "build_validation_anchors_from_observations",
    "build_validation_anchors_from_triples", "write_validation_anchors",
]
