"""Role-scoped intervention polarity and response-orientation evidence.

Alpha3.3 keeps actor intervention state distinct from endpoint response
orientation.  It consumes frozen Planner V3 proposals and the alpha3.2
deterministic contracts without modifying either historical component.
"""

from __future__ import annotations

import re
from typing import Any

from code_engine.search.compositional_relation_semantics_v1 import (
    COMPILER_VERSION as ALPHA3_2_COMPILER_VERSION,
    _contains_any, assess_relation_binding_v3, direction_composition_v1,
    final_query_coverage_v1,
)
from code_engine.search.planner_v3_contract import (
    intent_semantic_transform_v1, validate_planner_proposal_v3,
)
from code_engine.search.proposition_aware_query_planner_v1 import sha256_value
from code_engine.search.retrieval_intent_v1 import INTENT_ORDER

INTERVENTION_POLARITY_VERSION = "InterventionActionPolarityV1"
RESPONSE_EVIDENCE_VERSION = "ResponseOrientationEvidenceV1"
PARSER_VERSION = "RoleScopedPolarityParserV1"
RELATION_CORE_VERSION = "RelationCoreV1_1"
BINDING_VERSION = "RelationBindingAssessmentV3_1"
PLAN_VERSION = "ValidatedPlannerPlanAlpha3_3"
COMPILER_VERSION = "DeterministicQueryCompilerV24DevAlpha3_3"

SCOPE_PRIMARY = "PRIMARY_INTERVENTION_ACTION_SCOPE"
SCOPE_RELATION = "RELATION_SCOPE"
SCOPE_RESPONSE = "RESPONSE_SCOPE"
SCOPE_ENDPOINT = "ENDPOINT_SCOPE"
SCOPE_THERAPY = "THERAPY_RESPONSE_SCOPE"
SCOPE_CONDITIONING = "CONDITIONING_TREATMENT_SCOPE"
SCOPE_CONTEXT = "CONTEXT_SCOPE"

_ACTION_PATTERNS = (
    ("DELETE_OR_LOSS", r"\b(?:delet(?:e|ed|ion)|loss|lost|knockout|deficien(?:t|cy)|null)\b"),
    ("KNOCKDOWN_OR_REDUCE", r"\b(?:knockdown|deplet(?:e|ed|ion)|silenc(?:e|ed|ing)|reduc(?:e|ed|tion))\b"),
    ("OVEREXPRESS_OR_INCREASE", r"\b(?:overexpress(?:ion|ed)?|upregulat(?:e|ed|ion)|increased function)\b"),
    ("INHIBIT", r"\b(?:inhibit(?:s|ed|ion)?|suppress(?:es|ed|ion)?)\b"),
    ("ACTIVATE", r"\b(?:activat(?:e|es|ed|ion)|agonis(?:t|m))\b"),
    ("EXPOSE_OR_STIMULATE", r"\b(?:expos(?:e|ed|ure)|stimulat(?:e|es|ed|ion)|treat(?:ed|ment))\b"),
    ("BLOCK", r"\b(?:block(?:s|ed|ade)?|neutraliz(?:e|ed|ation))\b"),
)

_RESPONSE_PATTERNS = (
    ("UP", r"\b(?:increase(?:s|d)?|enhanc(?:e|es|ed)|elevat(?:e|es|ed)|promot(?:e|es|ed)|stimulat(?:e|es|ed)|more sensitive|sensitiz(?:e|es|ed|ing))\b"),
    ("DOWN", r"\b(?:decrease(?:s|d)?|reduc(?:e|es|ed)|lower(?:s|ed)?|suppress(?:es|ed)?|inhibit(?:s|ed)?|less sensitive)\b"),
    ("REQUIRE", r"\b(?:require(?:s|d)?|necessary|essential)\b"),
    ("RESCUE", r"\b(?:rescu(?:e|es|ed)|restor(?:e|es|ed|ation)|re-expression|add-back)\b"),
    ("RESIST", r"\b(?:resist(?:s|ed|ance)|refractory)\b"),
)


def _matches(value: str, patterns: tuple[tuple[str, str], ...]) -> list[dict[str, str]]:
    rows = []
    for semantic, pattern in patterns:
        for match in re.finditer(pattern, value, flags=re.IGNORECASE):
            rows.append({"token": match.group(0), "normalized_semantic": semantic})
    return rows


def intervention_action_polarity_v1(link: dict[str, Any]) -> dict[str, Any]:
    """Classify what is done to the actor, never what happens to response."""
    surfaces = [str(link.get("subject_surface") or ""),
                str(link.get("subject_action_surface") or "")]
    evidence = []
    for field, value in zip(("subject_surface", "subject_action_surface"), surfaces, strict=True):
        evidence.extend({**row, "source_field": field, "scope": SCOPE_PRIMARY}
                        for row in _matches(value, _ACTION_PATTERNS))
    values = list(dict.fromkeys(row["normalized_semantic"] for row in evidence))
    state = values[0] if len(values) == 1 else "OTHER" if values else "UNRESOLVED"
    return {"artifact_schema_version": INTERVENTION_POLARITY_VERSION,
            "state": state, "evidence": evidence,
            "controls_response_orientation": False}


def role_scoped_polarity_parser_v1(link: dict[str, Any]) -> dict[str, Any]:
    """Assign polarity-bearing evidence to explicit semantic-role scopes."""
    role_fields = (
        (SCOPE_PRIMARY, "subject_surface", _ACTION_PATTERNS),
        (SCOPE_PRIMARY, "subject_action_surface", _ACTION_PATTERNS),
        (SCOPE_RELATION, "subject_action_surface", _RESPONSE_PATTERNS),
        (SCOPE_RELATION, "relation_surface", _RESPONSE_PATTERNS),
        (SCOPE_RESPONSE, "response_surface", _RESPONSE_PATTERNS),
        (SCOPE_ENDPOINT, "endpoint_property_surface", _RESPONSE_PATTERNS),
        (SCOPE_THERAPY, "therapy_surface", _RESPONSE_PATTERNS),
        (SCOPE_CONDITIONING, "conditioning_treatment_surface", _ACTION_PATTERNS),
        (SCOPE_CONTEXT, "biological_unit_surface", _ACTION_PATTERNS),
        (SCOPE_CONTEXT, "disease_surface", _ACTION_PATTERNS),
        (SCOPE_CONTEXT, "genotype_surface", _ACTION_PATTERNS),
    )
    evidence = []
    for scope, field, patterns in role_fields:
        value = str(link.get(field) or "")
        evidence.extend({**row, "source_field": field, "scope": scope}
                        for row in _matches(value, patterns))
    # Direction is already a typed proposal field, not a lexical bag.
    evidence.append({"token": link["direction"], "normalized_semantic": link["direction"],
                     "source_field": "direction", "scope": SCOPE_RELATION})
    phrase_tokens = _matches(link["linked_relation_phrase"], _ACTION_PATTERNS + _RESPONSE_PATTERNS)
    assigned = []
    for row in phrase_tokens:
        token = row["token"]
        scopes = [scope for scope, field, _ in role_fields
                  if token.casefold() in str(link.get(field) or "").casefold()]
        assigned.append({**row, "source_field": "linked_relation_phrase",
                         "scope": scopes[0] if scopes else "UNRESOLVED_PHRASE_SCOPE",
                         "matched_explicit_role_scopes": scopes})
    return {"artifact_schema_version": PARSER_VERSION,
            "field_scoped_evidence": evidence,
            "phrase_token_assignments": assigned,
            "global_polarity_bag_active": False,
            "intervention_polarity_distinct_from_response_orientation": True}


def _response_relation_evidence(link: dict[str, Any]) -> list[dict[str, str]]:
    # relation_surface is a typed Planner V3 semantic role. Its independent
    # semantic-containment gate remains enforced by the inherited alpha3.2
    # relation core, so response evidence does not need brittle literal phrase
    # substring matching. subject_action_surface is deliberately excluded.
    surface = str(link.get("relation_surface") or "")
    rows = [{**row, "source_field": "relation_surface", "scope": SCOPE_RELATION}
            for row in _matches(surface, _RESPONSE_PATTERNS)]
    # Planner V3 permits a grammatically relational verb in
    # subject_action_surface (for example "sensitizes" or "rescues").  Admit
    # only response tokens that are not themselves intervention-action tokens.
    # Thus "inhibition" and "stimulation" can never become response evidence
    # through this fallback.
    action_surface = str(link.get("subject_action_surface") or "")
    action_tokens = {row["token"].casefold() for row in _matches(action_surface, _ACTION_PATTERNS)}
    rows.extend({**row, "source_field": "subject_action_surface", "scope": SCOPE_RELATION,
                 "grammatical_relation_fallback": True}
                for row in _matches(action_surface, _RESPONSE_PATTERNS)
                if row["token"].casefold() not in action_tokens)
    return rows


def response_orientation_evidence_v1(*, link: dict[str, Any], target: dict[str, Any],
                                     intent_type: str) -> dict[str, Any]:
    """Validate endpoint response direction from typed/relation evidence only."""
    expected = intent_semantic_transform_v1(target, intent_type)
    composition = direction_composition_v1(
        raw_direction=link["direction"],
        endpoint_property=link["endpoint_property_surface"],
        intent_type=intent_type, expected_semantics=expected)
    orientation = composition["response_orientation"]["orientation"]
    relation_evidence = _response_relation_evidence(link)
    direction = link["direction"]
    compatible_semantics = {
        "INCREASE": "UP", "ACTIVATE": "UP", "SENSITIZE": "UP",
        "DECREASE": "DOWN", "INHIBIT": "DOWN", "RESIST": "DOWN",
        "REQUIRE": "REQUIRE", "RESCUE": "RESCUE",
    }.get(direction)
    evidence_matches = any(row["normalized_semantic"] == compatible_semantics
                           for row in relation_evidence)
    # An explicit typed direction is accepted when the phrase contains a
    # directionally matching relation/action surface. Actor-state evidence is
    # intentionally absent from this decision.
    compatible = composition["state"] == "COMPOSED" and evidence_matches
    return {"artifact_schema_version": RESPONSE_EVIDENCE_VERSION,
            "state": "COMPATIBLE" if compatible else "UNDERREPRESENTED",
            "expected_response_orientation": composition["response_orientation"],
            "typed_direction": direction,
            "response_relation_evidence": relation_evidence,
            "explicit_response_relation_precedence": True,
            "actor_action_polarity_used": False,
            "global_polarity_bag_used": False}


def assess_relation_binding_v3_1(*, link: dict[str, Any], target: dict[str, Any],
                                 intent_type: str) -> dict[str, Any]:
    """Replace only alpha3.2's unscoped orientation containment decision."""
    prior = assess_relation_binding_v3(link=link, target=target, intent_type=intent_type)
    evidence = response_orientation_evidence_v1(link=link, target=target, intent_type=intent_type)
    response = dict(prior["compositional_response_semantics"])
    response["role_scoped_orientation_evidence"] = evidence
    response["orientation_containment"] = {
        **response["orientation_containment"],
        "state": "CONTAINED" if evidence["state"] == "COMPATIBLE" else "NOT_CONTAINED",
        "role_scoped": True,
        "actor_action_polarity_used": False,
    }
    compatible = (response["direction_composition"]["state"] == "COMPOSED"
                  and response["endpoint_containment"]["state"] == "CONTAINED"
                  and evidence["state"] == "COMPATIBLE"
                  and ((response["response_target_containment"]["state"] == "CONTAINED"
                        and response["response_target_anchor_compatible"])
                       or response["composite_response_satisfied"])
                  and prior["relation_core"]["checks"]["therapy_internal_when_required"])
    response["state"] = "COMPATIBLE" if compatible else "UNDERREPRESENTED"
    checks = dict(prior["relation_core"]["checks"])
    checks["response_semantics_internal"] = compatible
    core_valid = all(checks.values())
    contexts_valid = prior["query_context_constraints"]["state"] == "VALID"
    bound = core_valid and contexts_valid
    relation_core = {**prior["relation_core"],
                     "artifact_schema_version": RELATION_CORE_VERSION,
                     "state": "VALID" if core_valid else "INVALID",
                     "checks": checks,
                     "intervention_action_polarity": intervention_action_polarity_v1(link),
                     "response_orientation_evidence": evidence,
                     "intervention_polarity_response_orientation_aliased": False,
                     "valid_before_context_externalization": core_valid}
    return {**prior, "artifact_schema_version": BINDING_VERSION,
            "relation_core": relation_core,
            "compositional_response_semantics": response,
            "role_scoped_polarity_parse": role_scoped_polarity_parser_v1(link),
            "state": "STRUCTURALLY_BOUND" if bound else "UNDERREPRESENTED",
            "valid_relation_core_before_context_externalization": core_valid}


def rehydrate_and_compile_alpha3_3(payload: dict[str, Any], *,
                                  target: dict[str, Any]) -> dict[str, Any]:
    validate_planner_proposal_v3(payload)
    target_hash = sha256_value(target)
    intents = []
    queries = []
    for intent_index, intent in enumerate(payload["retrieval_intents"]):
        relation_rows = []
        for link_index, link in enumerate(intent["linked_relation_proposals"]):
            binding = assess_relation_binding_v3_1(
                link=link, target=target, intent_type=intent["intent_type"])
            coverage = final_query_coverage_v1(
                phrase=link["linked_relation_phrase"], binding=binding)
            relation_rows.append({"source_link_index": link_index,
                                  "source_link_sha256": sha256_value(link),
                                  "relation_binding": binding,
                                  "final_query_coverage": coverage})
            if binding["state"] == "STRUCTURALLY_BOUND" and coverage["state"] == "COVERED":
                query = coverage["compiled_query"]
                identity = {"compiler_version": COMPILER_VERSION, "target_sha256": target_hash,
                            "intent_type": intent["intent_type"], "intent_index": intent_index,
                            "link_index": link_index, "query_string": query}
                query_hash = sha256_value(identity)
                queries.append({"artifact_schema_version": "CompiledPlannerAlpha3_3QueryV1",
                                "query_id": f"v24a33q:{query_hash}", "query_sha256": query_hash,
                                "query_string": query, "intent_type": intent["intent_type"],
                                "intent_index": intent_index, "link_index": link_index,
                                "source_link_sha256": sha256_value(link),
                                "execution_status": "NOT_EXECUTED_DEVELOPMENT_REPLAY"})
        intents.append({"intent_type": intent["intent_type"], "relations": relation_rows,
                        "structurally_bound_relation_count": sum(
                            row["relation_binding"]["state"] == "STRUCTURALLY_BOUND"
                            for row in relation_rows),
                        "compiled_query_count": sum(
                            row["relation_binding"]["state"] == "STRUCTURALLY_BOUND" and
                            row["final_query_coverage"]["state"] == "COVERED"
                            for row in relation_rows)})
    queries.sort(key=lambda row: (INTENT_ORDER.index(row["intent_type"]), row["query_string"]))
    return {"artifact_schema_version": PLAN_VERSION,
            "source_alpha3_2_compiler_version": ALPHA3_2_COMPILER_VERSION,
            "compiler_version": COMPILER_VERSION,
            "target_id": target.get("scientific_proposition_target_id"),
            "target_sha256": target_hash, "payload_sha256": sha256_value(payload),
            "intents": intents,
            "valid_relation_core_count": sum(
                rel["relation_binding"]["relation_core"]["state"] == "VALID"
                for intent in intents for rel in intent["relations"]),
            "structurally_bound_intent_count": sum(
                intent["structurally_bound_relation_count"] > 0 for intent in intents),
            "compiled_query_count": len(queries), "compiled_queries": queries,
            "compiler_requires_valid_relation_core": True,
            "canonical_identity_promotions": 0,
            "provider_calls": 0, "network_calls": 0, "retrieval_calls": 0}


__all__ = [
    "BINDING_VERSION", "COMPILER_VERSION", "INTERVENTION_POLARITY_VERSION",
    "PARSER_VERSION", "PLAN_VERSION", "RELATION_CORE_VERSION", "RESPONSE_EVIDENCE_VERSION",
    "assess_relation_binding_v3_1", "intervention_action_polarity_v1",
    "rehydrate_and_compile_alpha3_3", "response_orientation_evidence_v1",
    "role_scoped_polarity_parser_v1",
]
