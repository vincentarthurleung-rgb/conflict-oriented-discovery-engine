"""Seed-triple experiment identity, separate from discovered relations."""

from __future__ import annotations

import hashlib
import json
import re
from typing import Any

from pydantic import Field

from code_engine.schemas.models import CODEBaseModel, ScientificTriple


class TripleEntity(CODEBaseModel):
    name: str
    canonical_id: str = ""
    type: str = "unknown"


class TripleRelation(CODEBaseModel):
    name: str
    family: str = "unknown"


class TripleContext(CODEBaseModel):
    domain: str = "general_biomedical"
    context_terms: list[str] = Field(default_factory=list)


class SeedTriple(CODEBaseModel):
    triple_id: str
    subject: TripleEntity
    relation: TripleRelation
    object: TripleEntity
    context: TripleContext = Field(default_factory=TripleContext)
    query_text: str
    query_hash: str
    display_title: str
    identity_kind: str = "seed_triple"
    source: str = "semantic_intake"
    confidence: float = 1.0
    human_review_required: bool = False
    intake_mode: str = "semantic"


def _normalized(value: str) -> str:
    return " ".join(str(value or "").casefold().split())


def build_seed_triple(
    query_text: str, *, domain: str = "general_biomedical",
    subject: str | None = None, relation: str | None = None, obj: str | None = None,
    subject_canonical_id: str = "", object_canonical_id: str = "",
    subject_type: str = "unknown", object_type: str = "unknown",
    relation_family: str | None = None, context_terms: list[str] | None = None,
    source: str = "semantic_intake", confidence: float = 1.0,
    human_review_required: bool = False, intake_mode: str = "semantic",
) -> SeedTriple:
    """Build a stable experiment identity without claiming discovered evidence."""

    query = " ".join(str(query_text or "").split())
    directed = re.match(r"^\s*(.+?)\s*(?:->|=>)\s*(.+?)\s*$", query)
    tokens = query.split()
    subject_name = subject or (directed.group(1).strip() if directed else (tokens[0] if tokens else "unknown"))
    object_name = obj or (directed.group(2).strip() if directed else (tokens[-1] if len(tokens) > 1 else "unknown"))
    relation_name = relation or ("explicit_relation" if directed else (" ".join(tokens[1:-1]) or "associated_with"))
    family = relation_family or relation_name
    context = TripleContext(domain=domain or "general_biomedical", context_terms=context_terms or [])
    identity = {
        "subject": _normalized(subject_canonical_id or subject_name),
        "relation": _normalized(family),
        "object": _normalized(object_canonical_id or object_name),
        "domain": _normalized(context.domain),
        "context_terms": sorted(_normalized(item) for item in context.context_terms),
    }
    triple_id = hashlib.sha256(json.dumps(identity, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    query_hash = hashlib.sha256(_normalized(query).encode()).hexdigest()
    context_label = f" in {context.domain}" if context.domain else ""
    return SeedTriple(
        triple_id=triple_id,
        subject=TripleEntity(name=subject_name, canonical_id=subject_canonical_id, type=subject_type),
        relation=TripleRelation(name=relation_name, family=family),
        object=TripleEntity(name=object_name, canonical_id=object_canonical_id, type=object_type),
        context=context, query_text=query, query_hash=query_hash,
        display_title=f"{subject_name} — {relation_name} — {object_name}{context_label}",
        source=source, confidence=confidence, human_review_required=human_review_required,
        intake_mode=intake_mode,
    )


def seed_triple_from_payload(payload: dict[str, Any] | SeedTriple, query_text: str = "") -> SeedTriple:
    if isinstance(payload, SeedTriple):
        return payload
    if payload.get("triple_id") and isinstance(payload.get("subject"), dict):
        return SeedTriple.model_validate(payload)
    subject_payload = payload.get("subject")
    object_payload = payload.get("object")
    relation_payload = payload.get("relation")
    subject = subject_payload if isinstance(subject_payload, str) else (subject_payload or {}).get("name", "")
    obj = object_payload if isinstance(object_payload, str) else (object_payload or {}).get("name", "")
    relation = relation_payload if isinstance(relation_payload, str) else (relation_payload or {}).get("name", "")
    relation_family = payload.get("relation_family") or (
        (relation_payload or {}).get("family", "") if isinstance(relation_payload, dict) else relation
    )
    context = payload.get("context") if isinstance(payload.get("context"), dict) else {}
    return build_seed_triple(
        query_text or str(payload.get("query_text") or ""),
        domain=str(payload.get("domain") or context.get("domain") or "general_biomedical"),
        subject=str(subject), relation=str(relation), obj=str(obj), relation_family=str(relation_family),
        subject_canonical_id=str((subject_payload or {}).get("canonical_id", "") if isinstance(subject_payload, dict) else ""),
        object_canonical_id=str((object_payload or {}).get("canonical_id", "") if isinstance(object_payload, dict) else ""),
        subject_type=str((subject_payload or {}).get("type", "unknown") if isinstance(subject_payload, dict) else "unknown"),
        object_type=str((object_payload or {}).get("type", "unknown") if isinstance(object_payload, dict) else "unknown"),
        context_terms=list(payload.get("context_terms") or context.get("context_terms") or []),
        source=str(payload.get("source") or "semantic_intake"),
        confidence=float(payload.get("confidence", 1.0)),
        human_review_required=bool(payload.get("human_review_required", False)),
        intake_mode=str(payload.get("intake_mode") or "semantic"),
    )


__all__ = [
    "ScientificTriple", "TripleEntity", "TripleRelation", "TripleContext", "SeedTriple",
    "build_seed_triple", "seed_triple_from_payload",
]
