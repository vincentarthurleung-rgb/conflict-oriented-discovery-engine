"""Independent A--F query builders for Search Plan v2.3-beta.2.

The executable query construction is an extraction of the frozen v2.2 family
logic.  The explicit semantic difference is that inapplicable optional family
slots do not emit queries; family G and unverified family-F fallbacks do not
exist in this compiler.
"""

from __future__ import annotations

import hashlib
from typing import Any, Callable

from code_engine.search.query_family_applicability_v1 import (
    APPLICABILITY_VERSION,
    APPLICABLE,
    FAMILY_ARCHITECTURES,
    FAMILY_ORDER,
    case_compilation_status,
    evaluate_query_family_applicability,
)
from code_engine.search.scientific_target_query_binding_v1_1 import BINDING_VERSION


COMPILER_VERSION = "SearchPlanQueryCompilerV23Beta2"
SEARCH_PLAN_VERSION = "v2.3-beta.2"


def _value(binding: dict[str, Any], field: str) -> list[dict[str, str]]:
    return binding["fields"][field]["value"]


def _annotation(
    item: dict[str, str],
    authority_class: str,
    target_field: str,
    source_ref: str | None,
    *,
    unverified: bool | None = None,
) -> dict[str, Any]:
    if unverified is None:
        unverified = authority_class not in {"required_search_anchor", "authorized_alias"} and source_ref is None
    return {
        "term": item["term"],
        "authority_class": authority_class,
        "target_field": target_field,
        "authority_source_ref": source_ref,
        "planning_only_unverified_expansion": unverified,
        "authorizes_proposition_identity": authority_class in {"required_search_anchor", "authorized_alias"},
        "binding_term_provenance": item,
    }


def _query(
    case_id: str,
    family_id: str,
    terms: list[dict[str, Any]],
    *,
    overconstraint_risk: str = "low",
    overconstraint_rationale: str = "",
) -> dict[str, Any]:
    query_string = " AND ".join(f'"{item["term"]}"' for item in terms)
    return {
        "query_id": f"{case_id}_{family_id.lower()}",
        "query_string": query_string,
        "query_hash": hashlib.sha256(query_string.encode("utf-8")).hexdigest(),
        "term_annotations": terms,
        "term_provenance": [item["binding_term_provenance"] for item in terms],
        "overconstraint_risk": overconstraint_risk,
        "overconstraint_rationale": overconstraint_rationale,
        "execution_status": "not_executed_offline_freeze",
        "compiler_version": COMPILER_VERSION,
        "binding_version": BINDING_VERSION,
        "applicability_version": APPLICABILITY_VERSION,
    }


def compile_family_a(case_id: str, binding: dict[str, Any], source_ref: str) -> dict[str, Any]:
    subject = _value(binding, "subject_terms")[0]
    object_ = _value(binding, "object_terms")[0]
    return _query(case_id, "A", [
        _annotation(subject, "required_search_anchor", "subject", source_ref),
        _annotation(object_, "required_search_anchor", "object", source_ref),
    ])


def compile_family_b(case_id: str, binding: dict[str, Any], source_ref: str) -> dict[str, Any]:
    subject = _value(binding, "subject_terms")[0]
    broader = _value(binding, "broader_terms")[0]
    return _query(case_id, "B", [
        _annotation(subject, "required_search_anchor", "subject", source_ref),
        _annotation(broader, "recall_expansion_only", "measurement_property_endpoint", None),
    ])


def compile_family_c(case_id: str, binding: dict[str, Any], source_ref: str) -> dict[str, Any]:
    subject = _value(binding, "subject_terms")[0]
    object_ = _value(binding, "object_terms")[0]
    relation = _value(binding, "relation_terms")[0]
    return _query(case_id, "C", [
        _annotation(subject, "required_search_anchor", "subject", source_ref),
        _annotation(object_, "required_search_anchor", "object", source_ref),
        _annotation(relation, "relation_expansion_only", "relation_family", source_ref),
    ])


def compile_family_d(case_id: str, binding: dict[str, Any], source_ref: str) -> dict[str, Any]:
    subject = _value(binding, "subject_terms")[0]
    measurement = _value(binding, "measurement_terms")[0]
    target_literals = {
        item["normalized_term"]
        for field in ("subject_terms", "object_terms", "relation_terms")
        for item in _value(binding, field)[:1]
    }
    measure_source = source_ref if measurement["normalized_term"] in target_literals else None
    return _query(case_id, "D", [
        _annotation(subject, "required_search_anchor", "subject", source_ref),
        _annotation(measurement, "measurement_expansion_only", "measurement_property_endpoint", measure_source),
    ])


def compile_family_e(case_id: str, binding: dict[str, Any], source_ref: str) -> dict[str, Any]:
    subject = _value(binding, "subject_terms")[0]
    object_ = _value(binding, "object_terms")[0]
    context = _value(binding, "context_terms")[0]
    return _query(
        case_id,
        "E",
        [
            _annotation(subject, "required_search_anchor", "subject", source_ref),
            _annotation(object_, "required_search_anchor", "object", source_ref),
            _annotation(context, "context_expansion_only", "context_qualifiers", source_ref),
        ],
        overconstraint_risk="medium",
        overconstraint_rationale="Three simultaneous concepts may miss cross-context mechanistic studies; retain only as a complementary family.",
    )


def compile_family_f(case_id: str, binding: dict[str, Any], source_ref: str) -> dict[str, Any]:
    alias = _value(binding, "authorized_aliases")[0]
    subject = _value(binding, "subject_terms")[0]
    object_ = _value(binding, "object_terms")[0]
    alias_annotation = _annotation(alias, "authorized_alias", alias["target_field"], source_ref)
    if alias["target_field"] == "subject":
        terms = [alias_annotation, _annotation(object_, "required_search_anchor", "object", source_ref)]
    else:
        terms = [alias_annotation, _annotation(subject, "required_search_anchor", "subject", source_ref)]
    return _query(case_id, "F", terms)


BUILDERS: dict[str, Callable[[str, dict[str, Any], str], dict[str, Any]]] = {
    "A": compile_family_a,
    "B": compile_family_b,
    "C": compile_family_c,
    "D": compile_family_d,
    "E": compile_family_e,
    "F": compile_family_f,
}

SCIENTIFIC_JUSTIFICATIONS = {
    "A": "High-specificity exact frozen subject/object pairing.",
    "B": "Recall bridge; the broader term does not redefine the exact endpoint.",
    "C": "Retrieve papers expressing the frozen relation with explicit relational language.",
    "D": "Retrieve evidence using measurement-language likely to expose the endpoint.",
    "E": "Context-stratified recall family; context is not imposed on every query.",
    "F": "Use only alternative surfaces explicitly present in frozen generic authority.",
}


def compile_modular_queries(
    case_id: str,
    binding: dict[str, Any],
    *,
    source_ref: str,
) -> dict[str, Any]:
    """Emit six family slots and queries only for APPLICABLE slots."""
    applicability = evaluate_query_family_applicability(binding)
    slots = []
    query_strings: list[str] = []
    for status in applicability:
        family_id = status["family_id"]
        compiled = None
        if status["applicability"] == APPLICABLE:
            compiled = BUILDERS[family_id](case_id, binding, source_ref)
            query_strings.append(compiled["query_string"])
        slots.append({
            **status,
            "query_family_id": f"{case_id}:{family_id}",
            "scientific_justification": SCIENTIFIC_JUSTIFICATIONS[family_id],
            "compiled_query": compiled,
        })
    if [slot["family_id"] for slot in slots] != list(FAMILY_ORDER):
        raise RuntimeError("modular compiler did not preserve A-F order")
    if len(query_strings) != len(set(query_strings)):
        raise ValueError(f"duplicate applicable queries generated for {case_id}")
    status = case_compilation_status(binding, applicability)
    if status == "VALID" and slots[0]["compiled_query"] is None:
        raise RuntimeError("valid case lacks executable family A")
    return {
        "artifact_schema_version": "ModularQueryCompilationV23Beta2",
        "search_plan_version": SEARCH_PLAN_VERSION,
        "compiler_version": COMPILER_VERSION,
        "binding_version": binding["binding_version"],
        "applicability_version": APPLICABILITY_VERSION,
        "case_id": case_id,
        "case_compilation_status": status,
        "family_slot_count": len(slots),
        "executable_query_count": sum(slot["compiled_query"] is not None for slot in slots),
        "family_slots": slots,
        "family_g_emitted": False,
        "unverified_lexical_fallback_used": False,
    }


__all__ = [
    "BUILDERS",
    "COMPILER_VERSION",
    "compile_family_a",
    "compile_family_b",
    "compile_family_c",
    "compile_family_d",
    "compile_family_e",
    "compile_family_f",
    "compile_modular_queries",
]
