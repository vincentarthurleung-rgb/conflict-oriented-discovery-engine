"""Conservative ScientificPropositionTargetV1 binding for v2.3-beta.2.

V1.1 preserves the term authorities of V1 while distinguishing absent optional
expansions from unresolved core scientific literals.  It contains no biomedical
vocabulary and performs no network or model operations.
"""

from __future__ import annotations

import hashlib
from typing import Any

from code_engine.search.scientific_target_query_binding_v1 import (
    ALLOWED_PROVENANCE_KINDS,
    FORBIDDEN_PROVENANCE_KINDS,
    QueryBindingAuthorityError,
    normalize_term,
)


BINDING_VERSION = "ScientificTargetQueryBindingV1_1"
INPUT_SCHEMA_VERSION = "QueryCompilerInputV1_1"
SEARCH_PLAN_VERSION = "v2.3-beta.2"

RESOLVED = "RESOLVED"
EMPTY_AUTHORIZED = "EMPTY_AUTHORIZED"
UNRESOLVED_CORE = "UNRESOLVED_CORE"

CORE_FIELDS = ("subject_terms", "object_terms", "relation_terms", "measurement_terms")
OPTIONAL_EXPANSION_FIELDS = ("broader_terms", "context_terms", "authorized_aliases", "unverified_terms")


def _literal_id(field: str, term: str) -> str:
    digest = hashlib.sha256(normalize_term(term).encode("utf-8")).hexdigest()[:20]
    return f"LOCAL_TARGET_LITERAL:{field}:{digest}"


def _term(
    value: str,
    *,
    provenance_kind: str,
    source_authority: str,
    canonical_id: str,
    derivation_rule: str,
    target_field: str,
) -> dict[str, str]:
    term = str(value).strip()
    if not term:
        raise QueryBindingAuthorityError("empty query term is forbidden")
    if provenance_kind not in ALLOWED_PROVENANCE_KINDS:
        raise QueryBindingAuthorityError(f"forbidden provenance kind: {provenance_kind}")
    return {
        "term": term,
        "normalized_term": normalize_term(term),
        "provenance_kind": provenance_kind,
        "source_authority": source_authority,
        "canonical_id": canonical_id,
        "derivation_rule": derivation_rule,
        "authorization_status": "AUTHORIZED",
        "target_field": target_field,
    }


def _literal(value: Any, field: str, target_field: str | None = None) -> list[dict[str, str]]:
    if value is None or not str(value).strip():
        return []
    term = str(value).strip()
    return [_term(
        term,
        provenance_kind="TARGET_LITERAL",
        source_authority=f"ScientificPropositionTargetV1#{field}",
        canonical_id=_literal_id(field, term),
        derivation_rule="verbatim frozen target field",
        target_field=target_field or field,
    )]


def _dedupe_preserve(terms: list[dict[str, str]]) -> list[dict[str, str]]:
    seen: set[str] = set()
    output = []
    for item in terms:
        normalized = item["normalized_term"]
        if normalized and normalized not in seen:
            seen.add(normalized)
            output.append(item)
    return output


def _field(name: str, terms: list[dict[str, str]], *, optional: bool, reason: str) -> dict[str, Any]:
    values = _dedupe_preserve(terms)
    if values:
        status = RESOLVED
    elif optional:
        status = EMPTY_AUTHORIZED
    else:
        status = UNRESOLVED_CORE
    return {
        "field_name": name,
        "status": status,
        "value": values,
        "optional_expansion": optional,
        "empty_reason": None if values else reason,
    }


def _authorized_records(authorities: dict[str, Any], key: str) -> list[dict[str, Any]]:
    records = list(authorities.get(key, []))
    for record in records:
        if record.get("authorization_status") != "AUTHORIZED":
            raise QueryBindingAuthorityError(
                f"unauthorized record in {key}: {record.get('canonical_id')!r}"
            )
    return records


def _entity_aliases(literal: str | None, target_field: str, authorities: dict[str, Any]) -> list[dict[str, str]]:
    if literal is None or not str(literal).strip():
        return []
    normalized = normalize_term(literal)
    matches = []
    for record in _authorized_records(authorities, "entity_alias_records"):
        surfaces = [record.get("canonical_name", ""), *record.get("aliases", [])]
        if normalized in {normalize_term(value) for value in surfaces if str(value).strip()}:
            matches.append(record)
    matches.sort(key=lambda row: row["canonical_id"])
    canonical_ids = {record["canonical_id"] for record in matches}
    if len(canonical_ids) > 1:
        raise QueryBindingAuthorityError(f"ambiguous entity authority for {target_field}")
    if not matches:
        return []
    record = matches[0]
    output = []
    surfaces = sorted(
        {str(value).strip() for value in [record.get("canonical_name", ""), *record.get("aliases", [])]
         if str(value).strip()},
        key=lambda value: (normalize_term(value), value),
    )
    for value in surfaces:
        if normalize_term(value) != normalized:
            output.append(_term(
                value,
                provenance_kind="CANONICAL_ENTITY_ALIAS",
                source_authority=record["source_authority"],
                canonical_id=record["canonical_id"],
                derivation_rule="exact normalized surface lookup in frozen entity authority",
                target_field=target_field,
            ))
    return _dedupe_preserve(output)


def _group_aliases(
    literals: list[str],
    records: list[dict[str, Any]],
    *,
    provenance_kind: str,
    target_field: str,
) -> list[dict[str, str]]:
    normalized_literals = {normalize_term(value) for value in literals if str(value).strip()}
    matches = []
    for record in records:
        normalized_terms = {normalize_term(value) for value in record.get("terms", []) if str(value).strip()}
        if normalized_literals & normalized_terms:
            matches.append(record)
    matches.sort(key=lambda row: row["canonical_id"])
    canonical_ids = {record["canonical_id"] for record in matches}
    if len(canonical_ids) > 1:
        raise QueryBindingAuthorityError(f"ambiguous alias groups for {target_field}")
    output = []
    for record in matches:
        for value in sorted(record.get("terms", []), key=lambda item: (normalize_term(item), item)):
            if normalize_term(value) not in normalized_literals:
                output.append(_term(
                    value,
                    provenance_kind=provenance_kind,
                    source_authority=record["source_authority"],
                    canonical_id=record["canonical_id"],
                    derivation_rule="exact normalized lookup in frozen generic alias group",
                    target_field=target_field,
                ))
    return _dedupe_preserve(output)


def _broader_terms(target: dict[str, Any], authorities: dict[str, Any]) -> list[dict[str, str]]:
    literals = [
        str(target.get(field) or "")
        for field in ("object", "measurement_target", "measurement_property_endpoint")
    ]
    normalized_literals = {normalize_term(value) for value in literals if value.strip()}
    matches = []
    for record in _authorized_records(authorities, "broader_concept_relations"):
        narrower = {normalize_term(value) for value in record.get("narrower_terms", [])}
        if normalized_literals & narrower:
            matches.append(record)
    matches.sort(key=lambda row: row["canonical_id"])
    distinct = {normalize_term(record.get("broader_term", "")) for record in matches}
    distinct.discard("")
    if len(distinct) > 1:
        raise QueryBindingAuthorityError("multiple authorized broader concepts matched target")
    if not matches:
        return []
    record = matches[0]
    return [_term(
        record["broader_term"],
        provenance_kind="AUTHORIZED_BROADER_CONCEPT",
        source_authority=record["source_authority"],
        canonical_id=record["canonical_id"],
        derivation_rule="exact frozen narrower-to-broader authority relation",
        target_field="measurement_property_endpoint",
    )]


def bind_scientific_target_v1_1(
    target: dict[str, Any],
    authorities: dict[str, Any],
    *,
    target_source_hash: str,
) -> dict[str, Any]:
    """Return a complete status-bearing binding, including unresolved core fields."""
    if target.get("artifact_schema_version") not in {None, "ScientificPropositionTargetV1"}:
        raise QueryBindingAuthorityError("unsupported target schema")

    subject = str(target.get("subject") or "").strip()
    object_ = str(target.get("object") or "").strip()
    relation = str(target.get("relation_family") or "").strip()
    measurement_target = str(target.get("measurement_target") or "").strip()
    measurement_endpoint = str(target.get("measurement_property_endpoint") or "").strip()
    contexts_value = target.get("context_qualifiers") or []
    if not isinstance(contexts_value, list):
        raise QueryBindingAuthorityError("context_qualifiers must be a list when present")

    endpoint_records = _authorized_records(authorities, "endpoint_alias_groups")
    relation_records = _authorized_records(authorities, "relation_alias_groups")
    relation_aliases = _group_aliases(
        [relation], relation_records,
        provenance_kind="CANONICAL_RELATION_ALIAS", target_field="relation_family",
    )
    measurement_aliases = _group_aliases(
        [measurement_target, measurement_endpoint], endpoint_records,
        provenance_kind="CANONICAL_ENDPOINT_ALIAS", target_field="measurement_property_endpoint",
    )
    object_endpoint_aliases = _group_aliases(
        [object_], endpoint_records,
        provenance_kind="CANONICAL_ENDPOINT_ALIAS", target_field="object",
    )
    aliases = _dedupe_preserve(
        _entity_aliases(subject, "subject", authorities)
        + _entity_aliases(object_, "object", authorities)
        + object_endpoint_aliases
    )

    broader_values = _broader_terms(target, authorities)
    measurement_candidates = (
        _literal(measurement_target, "measurement_target", "measurement_property_endpoint")
        + _literal(measurement_endpoint, "measurement_property_endpoint", "measurement_property_endpoint")
        + measurement_aliases
    )
    excluded_measurements = {normalize_term(object_)} if object_ else set()
    excluded_measurements.update(item["normalized_term"] for item in broader_values)
    measurement_literals = (
        [item for item in measurement_candidates if item["normalized_term"] not in excluded_measurements]
        + [item for item in measurement_candidates if item["normalized_term"] in excluded_measurements]
    )
    contexts = []
    for value in contexts_value:
        contexts.extend(_literal(value, "context_qualifiers", "context_qualifiers"))
    supplied_unverified = list(target.get("unverified_terms") or []) + list(authorities.get("unverified_terms") or [])

    fields = {
        "subject_terms": _field(
            "subject_terms", _literal(subject, "subject"), optional=False,
            reason="target subject literal is missing",
        ),
        "object_terms": _field(
            "object_terms", _literal(object_, "object"), optional=False,
            reason="target object literal is missing",
        ),
        "broader_terms": _field(
            "broader_terms", broader_values, optional=True,
            reason="no authorized generic broader relation exists",
        ),
        "measurement_terms": _field(
            "measurement_terms", measurement_literals, optional=False,
            reason="target measurement literal is missing",
        ),
        "relation_terms": _field(
            "relation_terms", _literal(relation, "relation_family") + relation_aliases, optional=False,
            reason="target relation literal is missing",
        ),
        "context_terms": _field(
            "context_terms", contexts, optional=True,
            reason="no authorized context literal exists",
        ),
        "authorized_aliases": _field(
            "authorized_aliases", aliases, optional=True,
            reason="no authorized entity or endpoint alias exists",
        ),
        "unverified_terms": _field(
            "unverified_terms", [], optional=True,
            reason="unverified lexical fallback is prohibited in v2.3-beta.2",
        ),
    }
    unresolved_core = [name for name in CORE_FIELDS if fields[name]["status"] == UNRESOLVED_CORE]
    return {
        "artifact_schema_version": INPUT_SCHEMA_VERSION,
        "binding_version": BINDING_VERSION,
        "search_plan_version": SEARCH_PLAN_VERSION,
        "target_schema_version": target.get("artifact_schema_version"),
        "target_identity": target.get("scientific_proposition_target_id"),
        "target_source_hash": target_source_hash,
        "fields": fields,
        "unresolved_core_fields": unresolved_core,
        "core_binding_valid": not unresolved_core,
        "rejected_unverified_term_count": len(supplied_unverified),
        "unverified_lexical_fallback_enabled": False,
        "network_calls": 0,
        "provider_calls": 0,
        "llm_calls": 0,
    }


__all__ = [
    "ALLOWED_PROVENANCE_KINDS",
    "BINDING_VERSION",
    "CORE_FIELDS",
    "EMPTY_AUTHORIZED",
    "FORBIDDEN_PROVENANCE_KINDS",
    "INPUT_SCHEMA_VERSION",
    "OPTIONAL_EXPANSION_FIELDS",
    "RESOLVED",
    "SEARCH_PLAN_VERSION",
    "UNRESOLVED_CORE",
    "bind_scientific_target_v1_1",
]
