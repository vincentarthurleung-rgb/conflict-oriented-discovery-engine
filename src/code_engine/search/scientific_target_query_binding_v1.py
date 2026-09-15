"""Deterministic, fail-closed binding for frozen scientific search targets.

This module deliberately does not contain biomedical aliases or case-specific
vocabulary.  Callers must supply a frozen authority manifest.  A binding may be
inspected while unresolved, but it cannot be converted to the legacy v2.2
compiler input until every field required by the frozen A--F architecture is
resolved.
"""

from __future__ import annotations

import hashlib
import json
import re
from typing import Any


BINDING_VERSION = "ScientificTargetQueryBindingV1"
INPUT_SCHEMA_VERSION = "QueryCompilerInputV1"
SEARCH_PLAN_VERSION = "v2.3-beta.1"

RESOLVED = "RESOLVED"
EMPTY_AUTHORIZED = "EMPTY_AUTHORIZED"
UNRESOLVED_REQUIRED = "UNRESOLVED_REQUIRED"

ALLOWED_PROVENANCE_KINDS = frozenset({
    "TARGET_LITERAL",
    "CANONICAL_ENTITY_ALIAS",
    "CANONICAL_RELATION_ALIAS",
    "CANONICAL_ENDPOINT_ALIAS",
    "AUTHORIZED_BROADER_CONCEPT",
    "LEGACY_FROZEN_GENERIC_RULE",
})
FORBIDDEN_PROVENANCE_KINDS = frozenset({
    "CASE_SPECIFIC_MANUAL_ALIAS",
    "LLM_EXPANSION",
    "POST_HOC_QUERY_TERM",
    "RETRIEVAL_YIELD_TUNED_TERM",
})
REQUIRED_TARGET_FIELDS = (
    "subject",
    "object",
    "relation_family",
    "measurement_target",
    "measurement_property_endpoint",
    "context_qualifiers",
)


class QueryBindingError(ValueError):
    """Base class for deterministic binding failures."""


class QueryBindingAuthorityError(QueryBindingError):
    """Raised when a supplied authority record is ambiguous or unauthorized."""


class QueryBindingUnresolvedError(QueryBindingError):
    """Raised before compiler invocation when required fields are unresolved."""


def normalize_term(value: str) -> str:
    """Generic comparison normalization; never emits a query term."""
    return re.sub(r"[^a-z0-9]+", " ", str(value).casefold()).strip()


def _literal_id(field: str, term: str) -> str:
    digest = hashlib.sha256(normalize_term(term).encode("utf-8")).hexdigest()[:20]
    return f"LOCAL_TARGET_LITERAL:{field}:{digest}"


def _term(
    term: str,
    *,
    provenance_kind: str,
    source_authority: str,
    canonical_id: str,
    derivation_rule: str,
    target_field: str,
) -> dict[str, str]:
    value = str(term).strip()
    if not value:
        raise QueryBindingAuthorityError("empty query term is not permitted")
    if provenance_kind not in ALLOWED_PROVENANCE_KINDS:
        raise QueryBindingAuthorityError(f"forbidden provenance kind: {provenance_kind}")
    return {
        "term": value,
        "normalized_term": normalize_term(value),
        "provenance_kind": provenance_kind,
        "source_authority": source_authority,
        "canonical_id": canonical_id,
        "derivation_rule": derivation_rule,
        "authorization_status": "AUTHORIZED",
        "target_field": target_field,
    }


def _dedupe(terms: list[dict[str, str]]) -> list[dict[str, str]]:
    by_normalized: dict[str, dict[str, str]] = {}
    for item in terms:
        normalized = item["normalized_term"]
        if normalized and normalized not in by_normalized:
            by_normalized[normalized] = item
    return [by_normalized[key] for key in sorted(by_normalized)]


def _field(
    name: str,
    terms: list[dict[str, str]],
    *,
    required: bool,
    empty_reason: str,
) -> dict[str, Any]:
    deduped = _dedupe(terms)
    if deduped:
        state = RESOLVED
    elif required:
        state = UNRESOLVED_REQUIRED
    else:
        state = EMPTY_AUTHORIZED
    return {
        "field_name": name,
        "resolution_state": state,
        "required_for_compilation": required,
        "terms": deduped,
        "empty_reason": None if deduped else empty_reason,
    }


def _authorized_records(authorities: dict[str, Any], key: str) -> list[dict[str, Any]]:
    records = list(authorities.get(key, []))
    for record in records:
        if record.get("authorization_status") != "AUTHORIZED":
            raise QueryBindingAuthorityError(
                f"unauthorized record in {key}: {record.get('canonical_id')!r}"
            )
    return records


def _match_entity_aliases(
    literal: str,
    target_field: str,
    authorities: dict[str, Any],
) -> list[dict[str, str]]:
    normalized = normalize_term(literal)
    matches = []
    for record in _authorized_records(authorities, "entity_alias_records"):
        surfaces = [record.get("canonical_name", ""), *record.get("aliases", [])]
        if normalized in {normalize_term(value) for value in surfaces if str(value).strip()}:
            matches.append(record)
    canonical_ids = {record["canonical_id"] for record in matches}
    if len(canonical_ids) > 1:
        raise QueryBindingAuthorityError(
            f"ambiguous entity authority for {target_field}: {literal!r}"
        )
    if not matches:
        return []
    record = matches[0]
    terms = []
    for value in [record.get("canonical_name", ""), *record.get("aliases", [])]:
        if str(value).strip() and normalize_term(value) != normalized:
            terms.append(_term(
                value,
                provenance_kind="CANONICAL_ENTITY_ALIAS",
                source_authority=record["source_authority"],
                canonical_id=record["canonical_id"],
                derivation_rule="exact normalized surface lookup in frozen entity alias authority",
                target_field=target_field,
            ))
    return _dedupe(terms)


def _matching_group_aliases(
    literals: list[str],
    *,
    records: list[dict[str, Any]],
    provenance_kind: str,
    target_field: str,
) -> list[dict[str, str]]:
    normalized_literals = {normalize_term(value) for value in literals if str(value).strip()}
    matched_groups = []
    for record in records:
        terms = {normalize_term(value) for value in record.get("terms", []) if str(value).strip()}
        if normalized_literals & terms:
            matched_groups.append(record)
    canonical_ids = {record["canonical_id"] for record in matched_groups}
    if len(canonical_ids) > 1:
        raise QueryBindingAuthorityError(
            f"ambiguous {target_field} alias authority: {sorted(canonical_ids)}"
        )
    output = []
    for record in matched_groups:
        for value in record.get("terms", []):
            if normalize_term(value) not in normalized_literals:
                output.append(_term(
                    value,
                    provenance_kind=provenance_kind,
                    source_authority=record["source_authority"],
                    canonical_id=record["canonical_id"],
                    derivation_rule="exact normalized concept lookup in frozen generic alias group",
                    target_field=target_field,
                ))
    return _dedupe(output)


def _broader_terms(target: dict[str, Any], authorities: dict[str, Any]) -> list[dict[str, str]]:
    literals = [
        target["object"],
        target["measurement_target"],
        target["measurement_property_endpoint"],
    ]
    normalized_literals = {normalize_term(value) for value in literals}
    matches = []
    for record in _authorized_records(authorities, "broader_concept_relations"):
        narrower = {normalize_term(value) for value in record.get("narrower_terms", [])}
        if normalized_literals & narrower:
            matches.append(record)
    broader_values = {
        normalize_term(record.get("broader_term", "")): record for record in matches
    }
    broader_values.pop("", None)
    if len(broader_values) > 1:
        raise QueryBindingAuthorityError("multiple authorized broader concepts matched target")
    if not broader_values:
        return []
    record = next(iter(broader_values.values()))
    return [_term(
        record["broader_term"],
        provenance_kind="AUTHORIZED_BROADER_CONCEPT",
        source_authority=record["source_authority"],
        canonical_id=record["canonical_id"],
        derivation_rule="exact narrower-to-broader relation in frozen generic hierarchy",
        target_field="measurement_property_endpoint",
    )]


def bind_scientific_target(
    target: dict[str, Any],
    authorities: dict[str, Any],
    *,
    target_source_hash: str,
) -> dict[str, Any]:
    """Bind a ScientificPropositionTargetV1 without inventing query vocabulary."""
    missing = [name for name in REQUIRED_TARGET_FIELDS if name not in target]
    if missing:
        raise QueryBindingError(f"missing ScientificPropositionTargetV1 fields: {missing}")
    if target.get("artifact_schema_version") != "ScientificPropositionTargetV1":
        raise QueryBindingError("unsupported target schema")
    if not isinstance(target["context_qualifiers"], list):
        raise QueryBindingError("context_qualifiers must be a list")

    subject_literal = _term(
        target["subject"], provenance_kind="TARGET_LITERAL",
        source_authority="ScientificPropositionTargetV1#subject",
        canonical_id=_literal_id("subject", target["subject"]),
        derivation_rule="verbatim frozen target field", target_field="subject",
    )
    measurement_literals = [
        _term(
            target[field], provenance_kind="TARGET_LITERAL",
            source_authority=f"ScientificPropositionTargetV1#{field}",
            canonical_id=_literal_id(field, target[field]),
            derivation_rule="verbatim frozen target field",
            target_field="measurement_property_endpoint",
        )
        for field in ("measurement_target", "measurement_property_endpoint")
    ]
    relation_literal = _term(
        target["relation_family"], provenance_kind="TARGET_LITERAL",
        source_authority="ScientificPropositionTargetV1#relation_family",
        canonical_id=_literal_id("relation_family", target["relation_family"]),
        derivation_rule="verbatim frozen target field", target_field="relation_family",
    )
    contexts = [
        _term(
            value, provenance_kind="TARGET_LITERAL",
            source_authority="ScientificPropositionTargetV1#context_qualifiers",
            canonical_id=_literal_id("context_qualifiers", value),
            derivation_rule="verbatim frozen target field in frozen list order",
            target_field="context_qualifiers",
        )
        for value in target["context_qualifiers"]
    ]

    relation_aliases = _matching_group_aliases(
        [target["relation_family"]],
        records=_authorized_records(authorities, "relation_alias_groups"),
        provenance_kind="CANONICAL_RELATION_ALIAS",
        target_field="relation_family",
    )
    endpoint_aliases = _matching_group_aliases(
        [target["measurement_target"], target["measurement_property_endpoint"]],
        records=_authorized_records(authorities, "endpoint_alias_groups"),
        provenance_kind="CANONICAL_ENDPOINT_ALIAS",
        target_field="measurement_property_endpoint",
    )
    subject_aliases = _match_entity_aliases(target["subject"], "subject", authorities)
    object_aliases = _match_entity_aliases(target["object"], "object", authorities)
    object_endpoint_aliases = _matching_group_aliases(
        [target["object"]],
        records=_authorized_records(authorities, "endpoint_alias_groups"),
        provenance_kind="CANONICAL_ENDPOINT_ALIAS",
        target_field="object",
    )
    authorized_aliases = _dedupe(subject_aliases + object_aliases + object_endpoint_aliases)

    fields = {
        "subject_terms": _field("subject_terms", [subject_literal], required=True,
                                empty_reason="target subject literal unavailable"),
        "broader_terms": _field(
            "broader_terms", _broader_terms(target, authorities), required=True,
            empty_reason="no frozen generic narrower-to-broader authority matched",
        ),
        "measurement_terms": _field(
            "measurement_terms", measurement_literals + endpoint_aliases, required=True,
            empty_reason="target measurement fields unavailable",
        ),
        "relation_terms": _field(
            "relation_terms", [relation_literal] + relation_aliases, required=True,
            empty_reason="target relation literal unavailable",
        ),
        "authorized_aliases": _field(
            "authorized_aliases", authorized_aliases, required=True,
            empty_reason="family F requires at least one alias from frozen generic authority",
        ),
        "unverified_terms": _field(
            "unverified_terms", [], required=False,
            empty_reason="v2.3-beta.1 forbids unverified terms from satisfying family F",
        ),
        "context_terms": _field(
            "context_terms", contexts, required=True,
            empty_reason="family E requires a frozen target context literal",
        ),
    }
    blocking = [
        name for name, value in fields.items()
        if value["resolution_state"] == UNRESOLVED_REQUIRED
    ]
    return {
        "artifact_schema_version": INPUT_SCHEMA_VERSION,
        "binding_version": BINDING_VERSION,
        "search_plan_version": SEARCH_PLAN_VERSION,
        "target_schema_version": target["artifact_schema_version"],
        "target_source_hash": target_source_hash,
        "target_identity": target.get("scientific_proposition_target_id"),
        "fields": fields,
        "family_f_behavior": "STRUCTURALLY_EMPTY_AND_COMPILATION_INVALID",
        "compilation_ready": not blocking,
        "blocking_fields": blocking,
        "network_calls": 0,
        "provider_calls": 0,
        "llm_calls": 0,
    }


def to_legacy_v22_compiler_inputs(
    target: dict[str, Any],
    binding: dict[str, Any],
    *,
    source_ref: str,
) -> tuple[dict[str, str], dict[str, Any], str]:
    """Return exact legacy inputs, or fail before the v2.2 compiler is called."""
    if not binding.get("compilation_ready"):
        raise QueryBindingUnresolvedError(
            f"query binding unresolved: {binding.get('blocking_fields', [])}"
        )
    fields = binding["fields"]
    aliases: dict[str, list[str]] = {}
    for item in fields["authorized_aliases"]["terms"]:
        if item["authorization_status"] != "AUTHORIZED":
            raise QueryBindingAuthorityError("unauthorized alias reached legacy conversion")
        key = target["subject"] if item["target_field"] == "subject" else target["object"]
        aliases.setdefault(key, []).append(item["term"])
    if not aliases:
        raise QueryBindingUnresolvedError("family F has no authorized alias")
    compiler_target = {
        "subject": target["subject"],
        "object": target["object"],
        "relation_family": target["relation_family"],
    }
    compiler_spec = {
        "broader": fields["broader_terms"]["terms"][0]["term"],
        "measurement_terms": [item["term"] for item in fields["measurement_terms"]["terms"]],
        "measurement_property_endpoint": target["measurement_property_endpoint"],
        "relation_terms": [item["term"] for item in fields["relation_terms"]["terms"]],
        "context_qualifiers": [item["term"] for item in fields["context_terms"]["terms"]],
        "aliases": {key: values for key, values in sorted(aliases.items())},
        "unverified": [],
    }
    return compiler_target, compiler_spec, source_ref


def canonical_binding_sha256(binding: dict[str, Any]) -> str:
    return hashlib.sha256(
        json.dumps(binding, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    ).hexdigest()


__all__ = [
    "ALLOWED_PROVENANCE_KINDS",
    "BINDING_VERSION",
    "EMPTY_AUTHORIZED",
    "FORBIDDEN_PROVENANCE_KINDS",
    "INPUT_SCHEMA_VERSION",
    "QueryBindingAuthorityError",
    "QueryBindingError",
    "QueryBindingUnresolvedError",
    "RESOLVED",
    "SEARCH_PLAN_VERSION",
    "UNRESOLVED_REQUIRED",
    "bind_scientific_target",
    "canonical_binding_sha256",
    "normalize_term",
    "to_legacy_v22_compiler_inputs",
]
