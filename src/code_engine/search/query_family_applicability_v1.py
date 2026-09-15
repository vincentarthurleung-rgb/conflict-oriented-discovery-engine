"""Family-slot applicability for the v2.3-beta.2 modular query compiler."""

from __future__ import annotations

from typing import Any

from code_engine.search.scientific_target_query_binding_v1_1 import (
    EMPTY_AUTHORIZED,
    RESOLVED,
    UNRESOLVED_CORE,
)


APPLICABILITY_VERSION = "QueryFamilyApplicabilityV1"
APPLICABLE = "APPLICABLE"
NOT_APPLICABLE = "NOT_APPLICABLE"
INVALID_REQUIRED_INPUT = "INVALID_REQUIRED_INPUT"

FAMILY_ARCHITECTURES = {
    "A": "exact_entity_endpoint",
    "B": "broader_endpoint_recall_family",
    "C": "relation_terminology",
    "D": "measurement_terminology",
    "E": "disease_context_expansion",
    "F": "authorized_alias_variants",
}
FAMILY_ORDER = tuple(FAMILY_ARCHITECTURES)


def _state(binding: dict[str, Any], field: str) -> str:
    return binding["fields"][field]["status"]


def _slot(
    family_id: str,
    *,
    applicability: str,
    reason_codes: list[str],
    required_authorities: list[str],
    available_authorities: list[str],
    missing_authorities: list[str],
) -> dict[str, Any]:
    return {
        "family_id": family_id,
        "family_order": FAMILY_ORDER.index(family_id) + 1,
        "architecture": FAMILY_ARCHITECTURES[family_id],
        "applicability": applicability,
        "reason_codes": reason_codes,
        "required_authorities": required_authorities,
        "available_authorities": available_authorities,
        "missing_authorities": missing_authorities,
        "scientific_score": None,
    }


def _core_slot(
    family_id: str,
    binding: dict[str, Any],
    required_fields: tuple[str, ...],
    *,
    reason: str,
) -> dict[str, Any]:
    missing = [field for field in required_fields if _state(binding, field) == UNRESOLVED_CORE]
    if missing:
        return _slot(
            family_id,
            applicability=INVALID_REQUIRED_INPUT,
            reason_codes=[f"UNRESOLVED_CORE_{field.upper()}" for field in missing],
            required_authorities=list(required_fields),
            available_authorities=[field for field in required_fields if field not in missing],
            missing_authorities=missing,
        )
    return _slot(
        family_id,
        applicability=APPLICABLE,
        reason_codes=[reason],
        required_authorities=list(required_fields),
        available_authorities=list(required_fields),
        missing_authorities=[],
    )


def evaluate_query_family_applicability(binding: dict[str, Any]) -> list[dict[str, Any]]:
    """Return exactly six A--F family-status records in canonical order."""
    slots = []
    slots.append(_core_slot(
        "A", binding, ("subject_terms", "object_terms"),
        reason="EXACT_CORE_LITERALS_AVAILABLE",
    ))

    subject_missing = _state(binding, "subject_terms") == UNRESOLVED_CORE
    broader_state = _state(binding, "broader_terms")
    if subject_missing:
        slots.append(_slot(
            "B", applicability=INVALID_REQUIRED_INPUT,
            reason_codes=["UNRESOLVED_CORE_SUBJECT_TERMS"],
            required_authorities=["subject_terms", "authorized_broader_concept"],
            available_authorities=[] if broader_state != RESOLVED else ["authorized_broader_concept"],
            missing_authorities=["subject_terms"],
        ))
    elif broader_state == EMPTY_AUTHORIZED:
        slots.append(_slot(
            "B", applicability=NOT_APPLICABLE,
            reason_codes=["NO_AUTHORIZED_BROADER_CONCEPT"],
            required_authorities=["subject_terms", "authorized_broader_concept"],
            available_authorities=["subject_terms"],
            missing_authorities=["authorized_broader_concept"],
        ))
    else:
        slots.append(_slot(
            "B", applicability=APPLICABLE,
            reason_codes=["AUTHORIZED_BROADER_CONCEPT_AVAILABLE"],
            required_authorities=["subject_terms", "authorized_broader_concept"],
            available_authorities=["subject_terms", "authorized_broader_concept"],
            missing_authorities=[],
        ))

    slots.append(_core_slot(
        "C", binding, ("subject_terms", "object_terms", "relation_terms"),
        reason="RELATION_LITERAL_AVAILABLE",
    ))
    slots.append(_core_slot(
        "D", binding, ("subject_terms", "measurement_terms"),
        reason="MEASUREMENT_LITERAL_AVAILABLE",
    ))

    e_core_missing = [
        field for field in ("subject_terms", "object_terms")
        if _state(binding, field) == UNRESOLVED_CORE
    ]
    context_state = _state(binding, "context_terms")
    if e_core_missing:
        slots.append(_slot(
            "E", applicability=INVALID_REQUIRED_INPUT,
            reason_codes=[f"UNRESOLVED_CORE_{field.upper()}" for field in e_core_missing],
            required_authorities=["subject_terms", "object_terms", "authorized_context_literal"],
            available_authorities=[] if context_state != RESOLVED else ["authorized_context_literal"],
            missing_authorities=e_core_missing,
        ))
    elif context_state == EMPTY_AUTHORIZED:
        slots.append(_slot(
            "E", applicability=NOT_APPLICABLE,
            reason_codes=["NO_AUTHORIZED_CONTEXT_LITERAL"],
            required_authorities=["subject_terms", "object_terms", "authorized_context_literal"],
            available_authorities=["subject_terms", "object_terms"],
            missing_authorities=["authorized_context_literal"],
        ))
    else:
        slots.append(_slot(
            "E", applicability=APPLICABLE,
            reason_codes=["AUTHORIZED_CONTEXT_LITERAL_AVAILABLE"],
            required_authorities=["subject_terms", "object_terms", "authorized_context_literal"],
            available_authorities=["subject_terms", "object_terms", "authorized_context_literal"],
            missing_authorities=[],
        ))

    f_core_missing = [
        field for field in ("subject_terms", "object_terms")
        if _state(binding, field) == UNRESOLVED_CORE
    ]
    alias_state = _state(binding, "authorized_aliases")
    if f_core_missing:
        slots.append(_slot(
            "F", applicability=INVALID_REQUIRED_INPUT,
            reason_codes=[f"UNRESOLVED_CORE_{field.upper()}" for field in f_core_missing],
            required_authorities=["subject_terms", "object_terms", "authorized_alias"],
            available_authorities=[] if alias_state != RESOLVED else ["authorized_alias"],
            missing_authorities=f_core_missing,
        ))
    elif alias_state == EMPTY_AUTHORIZED:
        slots.append(_slot(
            "F", applicability=NOT_APPLICABLE,
            reason_codes=["NO_AUTHORIZED_ALIAS"],
            required_authorities=["subject_terms", "object_terms", "authorized_alias"],
            available_authorities=["subject_terms", "object_terms"],
            missing_authorities=["authorized_alias"],
        ))
    else:
        slots.append(_slot(
            "F", applicability=APPLICABLE,
            reason_codes=["AUTHORIZED_ALIAS_AVAILABLE"],
            required_authorities=["subject_terms", "object_terms", "authorized_alias"],
            available_authorities=["subject_terms", "object_terms", "authorized_alias"],
            missing_authorities=[],
        ))

    if [slot["family_id"] for slot in slots] != list(FAMILY_ORDER):
        raise RuntimeError("family applicability order is not A-F")
    return slots


def case_compilation_status(binding: dict[str, Any], slots: list[dict[str, Any]]) -> str:
    by_id = {slot["family_id"]: slot for slot in slots}
    if binding.get("unresolved_core_fields") or by_id["A"]["applicability"] != APPLICABLE:
        return "INVALID_CORE_BINDING"
    if any(slot["applicability"] == INVALID_REQUIRED_INPUT for slot in slots):
        return "INVALID_CORE_BINDING"
    return "VALID"


__all__ = [
    "APPLICABILITY_VERSION",
    "APPLICABLE",
    "FAMILY_ARCHITECTURES",
    "FAMILY_ORDER",
    "INVALID_REQUIRED_INPUT",
    "NOT_APPLICABLE",
    "case_compilation_status",
    "evaluate_query_family_applicability",
]
