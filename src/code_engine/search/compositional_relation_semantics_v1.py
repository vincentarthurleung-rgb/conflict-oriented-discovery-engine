"""Deterministic compositional relation semantics for Search Plan v2.4 alpha3.2.

This module consumes the frozen Planner V3 lexical payload.  It does not alter
provider output, establish scientific identity, call a model, or perform
retrieval.  A relation core must be valid before ordinary proposition context
may be externalized into a compiled query.
"""

from __future__ import annotations

import re
from typing import Any

from code_engine.search.alpha1_relation_searchonly_v1 import _anchors, normalize
from code_engine.search.alpha2_linked_relation_v1 import _contains_surface
from code_engine.search.planner_v3_contract import (
    PlannerV3ContractError, allocate_artifact_id_v1,
    deterministic_target_role_frame_v1, intent_semantic_transform_v1,
    validate_planner_proposal_v3,
)
from code_engine.search.proposition_aware_query_planner_v1 import sha256_value
from code_engine.search.retrieval_intent_v1 import INTENT_ORDER

RELATION_CORE_VERSION = "RelationCoreV1"
QUERY_CONTEXT_VERSION = "QueryContextConstraintV1"
COMPOSITION_VERSION = "CompositionalResponseSemanticsV1"
ORIENTATION_VERSION = "ResponseOrientationV1"
DIRECTION_VERSION = "DirectionCompositionV1"
SURFACE_VERSION = "SemanticSurfaceContainmentV3"
UNIT_VERSION = "CompositeBiologicalUnitCompatibilityV1"
BINDING_VERSION = "RelationBindingAssessmentV3"
COVERAGE_VERSION = "FinalQueryCoverageV1"
PLAN_VERSION = "ValidatedPlannerPlanAlpha3_2"
COMPILER_VERSION = "DeterministicQueryCompilerV24DevAlpha3_2"

RELATION_INTERNAL_ROLE_MATRIX = {
    "PRIMARY_INTERVENTION": "INTERNAL",
    "PRIMARY_INTERVENTION_ACTION": "INTERNAL_WHEN_SCIENTIFICALLY_DEFINING",
    "RESPONSE_TARGET": "INTERNAL",
    "RESPONSE_PROPERTY": "INTERNAL",
    "THERAPY": "INTERNAL_FOR_THERAPY_RESPONSE",
    "CONDITIONING_TREATMENT": "INTERNAL_FOR_NESTED_TREATMENT",
    "ENDPOINT_DEFINING_LOCALIZATION": "INTERNAL",
    "BIOLOGICAL_UNIT_CONTEXT": "QUERY_CONTEXT_NORMALLY",
    "DISEASE_CONTEXT": "QUERY_CONTEXT_NORMALLY",
    "GENOTYPE_CONTEXT": "QUERY_CONTEXT_NORMALLY",
    "SPECIES_CONTEXT": "QUERY_CONTEXT_NORMALLY",
    "ORDINARY_TIME_CONTEXT": "QUERY_CONTEXT_NORMALLY",
    "NON_ENDPOINT_LOCALIZATION": "QUERY_CONTEXT_NORMALLY",
}


class CompositionalRelationError(ValueError):
    """A deterministic alpha3.2 relation or compiler invariant failed."""


def _unique(values: list[str]) -> list[str]:
    return list(dict.fromkeys(v for v in values if isinstance(v, str) and v.strip()))


def _alias_parts(values: list[str]) -> list[str]:
    return _unique([part.strip() for value in values
                    for part in re.split(r"\s*/\s*", value) if part.strip()])


def _singular_tokens(value: str) -> list[str]:
    result = []
    for token in normalize(value).split():
        if token.endswith("ies") and len(token) > 4:
            token = token[:-3] + "y"
        elif token.endswith("s") and not token.endswith("ss") and len(token) > 3:
            token = token[:-1]
        result.append(token)
    return result


def _sequence_span(haystack: list[str], needle: list[str]) -> tuple[int, int] | None:
    for index in range(len(haystack) - len(needle) + 1):
        if haystack[index:index + len(needle)] == needle:
            return index, index + len(needle)
    return None


def _contains_any(value: str, surfaces: list[str]) -> bool:
    return any(_contains_surface(value, part) for part in _alias_parts(surfaces))


def _endpoint_family(value: str) -> str | None:
    text = normalize(value)
    if "phospho" in text:
        return "PHOSPHORYLATION"
    if "secret" in text or "extracellular release" in text or "released" in text:
        return "SECRETION"
    if "nuclear" in text and any(x in text for x in ("accumul", "localiz", "translocat", "nuclear")):
        return "ACCUMULATION"
    if "flux" in text or "turnover" in text or "dynamic autophagic degradation" in text:
        return "FLUX"
    if "resistan" in text and (
            "sensitiv" not in text or
            any(marker in text for marker in ("restored resistance", "increased resistance"))):
        return "RESISTANCE"
    if "sensitiv" in text or "sensitiz" in text or "response" in text or "cytotoxic" in text:
        return "SENSITIVITY"
    if any(x in text for x in ("surface", "expression", "protein abundance")):
        return "ABUNDANCE"
    return None


def _polarity(direction: str, endpoint_family: str, intent_type: str,
              expected: dict[str, Any]) -> str | None:
    direction = direction.upper()
    if endpoint_family == "SENSITIVITY":
        if direction in {"INCREASE", "SENSITIZE"}:
            return "UP"
        if direction == "DECREASE":
            return "DOWN"
        if direction == "RESIST" and "RESIST" in expected["allowed_directions"]:
            return "DOWN"
    elif endpoint_family == "RESISTANCE":
        if direction in {"INCREASE", "RESIST", "REQUIRE", "RESCUE"}:
            return "UP"
        if direction in {"DECREASE", "SENSITIZE"}:
            return "DOWN"
    elif direction in {"INCREASE", "ACTIVATE", "RESCUE"}:
        return "UP"
    elif direction in {"DECREASE", "INHIBIT"}:
        return "DOWN"
    elif direction == "REQUIRE" and intent_type == "NECESSITY":
        return "PRESERVED"
    return None


def direction_composition_v1(*, raw_direction: str, endpoint_property: str,
                             intent_type: str,
                             expected_semantics: dict[str, Any]) -> dict[str, Any]:
    """Compose direction only inside its endpoint and intent semantics."""
    family = _endpoint_family(endpoint_property)
    polarity = _polarity(raw_direction, family or "", intent_type, expected_semantics)
    state = "COMPOSED" if family and polarity else "UNRESOLVED"
    orientation = f"{family}_{polarity}" if state == "COMPOSED" else None
    return {
        "artifact_schema_version": DIRECTION_VERSION,
        "response_orientation": {
            "artifact_schema_version": ORIENTATION_VERSION,
            "endpoint_family": family,
            "polarity": polarity,
            "orientation": orientation,
        },
        "state": state,
        "raw_direction": raw_direction,
        "intent_type": intent_type,
        "endpoint_property": endpoint_property,
        "global_lexical_equivalence_used": False,
        "scientific_identity_promoted": False,
    }


def _phrase_orientation(phrase: str, endpoint_family: str | None) -> str | None:
    text = normalize(phrase)
    if endpoint_family == "SENSITIVITY":
        if "sensitiz" in text or (
                any(x in text for x in ("increase", "enhanc")) and
                any(x in text for x in ("sensitiv", "response"))):
            return "SENSITIVITY_UP"
        if any(x in text for x in ("decrease", "reduce")) and "sensitiv" in text:
            return "SENSITIVITY_DOWN"
    if endpoint_family == "RESISTANCE":
        if "resistan" in text and any(x in text for x in (
                "required", "maintain", "increase", "rescue", "restor")):
            return "RESISTANCE_UP"
        if any(x in text for x in ("reduced resistance", "decreased resistance")):
            return "RESISTANCE_DOWN"
    markers = {
        "PHOSPHORYLATION": ("phospho",),
        "SECRETION": ("secret", "release", "extracellular"),
        "ACCUMULATION": ("nuclear",),
        "FLUX": ("flux", "turnover"),
        "ABUNDANCE": ("surface", "protein expression", "protein abundance"),
    }
    if endpoint_family in markers and any(x in text for x in markers[endpoint_family]):
        if any(x in text for x in ("decrease", "suppress", "reduce", "inhibit")):
            return f"{endpoint_family}_DOWN"
        if any(x in text for x in ("increase", "induce", "enhance", "accumul", "stimulat")):
            return f"{endpoint_family}_UP"
        if "required" in text:
            return f"{endpoint_family}_PRESERVED"
    return None


def semantic_surface_containment_v3(*, phrase: str, role: str,
                                    proposed_surfaces: list[str],
                                    canonical_surfaces: list[str],
                                    endpoint_family: str | None = None,
                                    expected_orientation: str | None = None) -> dict[str, Any]:
    """Validate bounded role-level coverage, never fuzzy or identity-level similarity."""
    surfaces = _alias_parts(_unique(proposed_surfaces + canonical_surfaces))
    matched = [surface for surface in surfaces if _contains_surface(phrase, surface)]
    semantic = False
    if role == "RESPONSE_PROPERTY" and endpoint_family:
        semantic = _endpoint_family(phrase) == endpoint_family or any(
            _endpoint_family(surface) == endpoint_family and _contains_surface(phrase, surface)
            for surface in surfaces)
    elif role == "RESPONSE_ORIENTATION" and expected_orientation:
        semantic = _phrase_orientation(phrase, endpoint_family) == expected_orientation
    state = "CONTAINED" if matched or semantic else "NOT_CONTAINED"
    return {
        "artifact_schema_version": SURFACE_VERSION,
        "role": role,
        "state": state,
        "matched_surfaces": matched,
        "semantic_family_match": semantic,
        "whole_composite_string_required": False,
        "fuzzy_equivalence_used": False,
        "canonical_identity_promoted": False,
    }


def composite_biological_unit_compatibility_v1(
        proposed_surface: str | None, canonical_surfaces: list[str], *,
        target: dict[str, Any]) -> dict[str, Any]:
    """Permit only safe number morphology or a validated intervention-state wrapper."""
    proposed = str(proposed_surface or "")
    tokens = _singular_tokens(proposed)
    matches = []
    for anchor in _alias_parts(canonical_surfaces):
        needle = _singular_tokens(anchor)
        span = _sequence_span(tokens, needle) if needle else None
        if span:
            matches.append((anchor, span))
    modifier_class = None
    state = "INCOMPATIBLE"
    if matches:
        anchor, (start, end) = matches[0]
        modifiers = tokens[:start] + tokens[end:]
        if not modifiers:
            state = "COMPATIBLE"
            modifier_class = "SAFE_GRAMMATICAL_MORPHOLOGY"
        else:
            modifier_text = " ".join(modifiers)
            subject_anchors = _alias_parts(_anchors(target, "subject"))
            intervention_markers = {
                "depleted", "depletion", "knockdown", "knockout", "inhibited",
                "inhibition", "deficient", "deficiency", "loss", "null",
            }
            subject_present = _contains_any(modifier_text, subject_anchors)
            state_marker_present = any(marker in modifiers for marker in intervention_markers)
            if subject_present and state_marker_present:
                state = "COMPATIBLE"
                modifier_class = "VALIDATED_PRIMARY_INTERVENTION_STATE"
    return {
        "artifact_schema_version": UNIT_VERSION,
        "state": state,
        "proposed_surface": proposed_surface,
        "canonical_surfaces": canonical_surfaces,
        "matched_canonical_anchor": matches[0][0] if matches else None,
        "modifier_class": modifier_class,
        "arbitrary_modifier_stripping": False,
        "canonical_identity_promoted": False,
    }


def compositional_response_semantics_v1(*, link: dict[str, Any],
                                        target: dict[str, Any],
                                        intent_type: str,
                                        expected_semantics: dict[str, Any]) -> dict[str, Any]:
    """Assess response meaning across therapy, endpoint, direction, and phrase roles."""
    frame = deterministic_target_role_frame_v1(target)
    endpoint = link["endpoint_property_surface"]
    proposal_direction = direction_composition_v1(
        raw_direction=link["direction"], endpoint_property=endpoint,
        intent_type=intent_type, expected_semantics=expected_semantics)
    orientation = proposal_direction["response_orientation"]["orientation"]
    family = proposal_direction["response_orientation"]["endpoint_family"]
    phrase = link["linked_relation_phrase"]
    therapy_required = expected_semantics["therapy_required"]
    therapy = semantic_surface_containment_v3(
        phrase=phrase, role="THERAPY",
        proposed_surfaces=[str(link.get("therapy_surface") or "")],
        canonical_surfaces=frame["role_surfaces"]["THERAPY"])
    endpoint_row = semantic_surface_containment_v3(
        phrase=phrase, role="RESPONSE_PROPERTY",
        proposed_surfaces=[endpoint],
        canonical_surfaces=frame["role_surfaces"]["RESPONSE_PROPERTY"],
        endpoint_family=family)
    orientation_row = semantic_surface_containment_v3(
        phrase=phrase, role="RESPONSE_ORIENTATION", proposed_surfaces=[],
        canonical_surfaces=[], endpoint_family=family,
        expected_orientation=orientation)
    endpoint_text = normalize(endpoint)
    licensed_inverse_pair = (
        orientation == "RESISTANCE_UP"
        and "increased resistance" in endpoint_text
        and "decreased sensitivity" in endpoint_text
        and _phrase_orientation(phrase, "SENSITIVITY") == "SENSITIVITY_DOWN"
    ) or (
        orientation == "SENSITIVITY_UP"
        and "increased sensitivity" in endpoint_text
        and "decreased resistance" in endpoint_text
        and _phrase_orientation(phrase, "RESISTANCE") == "RESISTANCE_DOWN"
    )
    if licensed_inverse_pair and orientation_row["state"] != "CONTAINED":
        orientation_row = {**orientation_row, "state": "CONTAINED",
                           "semantic_family_match": True,
                           "explicit_endpoint_inverse_pair_license": True}
    response_target_surfaces = frame["role_surfaces"]["RESPONSE_TARGET"]
    response = semantic_surface_containment_v3(
        phrase=phrase, role="RESPONSE_TARGET",
        proposed_surfaces=[link["response_surface"]],
        canonical_surfaces=response_target_surfaces)
    response_anchor_compatible = _contains_any(
        link["response_surface"], response_target_surfaces)
    # For therapy-response endpoints the response target is compositionally
    # represented by therapy + endpoint + orientation, not a monolithic string.
    composite_response = therapy_required and therapy["state"] == "CONTAINED" \
        and endpoint_row["state"] == "CONTAINED" and orientation_row["state"] == "CONTAINED"
    compatible = proposal_direction["state"] == "COMPOSED" \
        and endpoint_row["state"] == "CONTAINED" \
        and orientation_row["state"] == "CONTAINED" \
        and ((response["state"] == "CONTAINED" and response_anchor_compatible)
             or composite_response) \
        and (not therapy_required or therapy["state"] == "CONTAINED")
    return {
        "artifact_schema_version": COMPOSITION_VERSION,
        "state": "COMPATIBLE" if compatible else "UNDERREPRESENTED",
        "response_orientation": proposal_direction["response_orientation"],
        "direction_composition": proposal_direction,
        "therapy_containment": therapy,
        "response_target_containment": response,
        "response_target_anchor_compatible": response_anchor_compatible,
        "endpoint_containment": endpoint_row,
        "orientation_containment": orientation_row,
        "composite_response_satisfied": composite_response,
        "monolithic_response_string_required": False,
        "global_lexical_equivalence_used": False,
    }


def _subject_compatible(surface: str, target: dict[str, Any]) -> bool:
    return _contains_any(surface, _anchors(target, "subject"))


def _conditioning_in_phrase(phrase: str, anchors: list[str]) -> bool:
    if _contains_any(phrase, anchors):
        return True
    text = normalize(phrase)
    for anchor in anchors:
        actor = normalize(anchor)
        for suffix in (" stimulation", " treatment", " exposure"):
            actor = actor.removesuffix(suffix)
        if actor and _contains_surface(phrase, actor) and any(
                marker in text for marker in ("induced", "stimulated", "treated", "exposed")):
            return True
    return False


def _context_constraint(role: str, surface: str | None, canonical: list[str],
                        *, phrase: str, target: dict[str, Any]) -> dict[str, Any]:
    if not canonical:
        return {"role": role, "required": False, "state": "NOT_APPLICABLE",
                "surface": surface, "canonical_surfaces": canonical,
                "present_in_relation_phrase": False}
    if role == "BIOLOGICAL_UNIT_CONTEXT":
        compatibility = composite_biological_unit_compatibility_v1(
            surface, canonical, target=target)
        compatible = compatibility["state"] == "COMPATIBLE"
    else:
        compatibility = None
        compatible = bool(surface) and _contains_any(str(surface), canonical)
    present = bool(surface) and _contains_surface(phrase, str(surface))
    return {"role": role, "required": True,
            "state": "COMPATIBLE" if compatible else "INCOMPATIBLE",
            "surface": surface, "canonical_surfaces": canonical,
            "present_in_relation_phrase": present,
            "compatibility_receipt": compatibility}


def assess_relation_binding_v3(*, link: dict[str, Any], target: dict[str, Any],
                               intent_type: str) -> dict[str, Any]:
    expected = intent_semantic_transform_v1(target, intent_type)
    frame = deterministic_target_role_frame_v1(target)
    phrase = link["linked_relation_phrase"]
    response = compositional_response_semantics_v1(
        link=link, target=target, intent_type=intent_type,
        expected_semantics=expected)
    subject_ok = _subject_compatible(link["subject_surface"], target) and \
        _contains_any(phrase, _anchors(target, "subject"))
    therapy_required = expected["therapy_required"]
    conditioning_required = expected["conditioning_treatment_applicability"] == "REQUIRED"
    therapy_internal = not therapy_required or response["therapy_containment"]["state"] == "CONTAINED"
    conditioning_internal = not conditioning_required or (
        bool(link.get("conditioning_treatment_surface")) and
        _conditioning_in_phrase(phrase, frame["role_surfaces"]["CONDITIONING_TREATMENT"]))
    relation_core_checks = {
        "primary_intervention_internal": subject_ok,
        "response_semantics_internal": response["state"] == "COMPATIBLE",
        "endpoint_property_internal": response["endpoint_containment"]["state"] == "CONTAINED",
        "therapy_internal_when_required": therapy_internal,
        "nested_conditioning_internal_when_required": conditioning_internal,
    }
    relation_core_valid = all(relation_core_checks.values())
    context_fields = (
        ("BIOLOGICAL_UNIT_CONTEXT", "biological_unit_surface", "BIOLOGICAL_UNIT_CONTEXT"),
        ("DISEASE_CONTEXT", "disease_surface", "DISEASE_CONTEXT"),
        ("GENOTYPE_CONTEXT", "genotype_surface", "GENOTYPE_CONTEXT"),
    )
    constraints = [_context_constraint(role, link.get(field), frame["role_surfaces"][frame_role],
                                       phrase=phrase, target=target)
                   for role, field, frame_role in context_fields]
    contexts_valid = all(row["state"] in {"COMPATIBLE", "NOT_APPLICABLE"}
                         for row in constraints)
    bound = relation_core_valid and contexts_valid
    return {
        "artifact_schema_version": BINDING_VERSION,
        "relation_core": {
            "artifact_schema_version": RELATION_CORE_VERSION,
            "state": "VALID" if relation_core_valid else "INVALID",
            "checks": relation_core_checks,
            "primary_actor_surface": link["subject_surface"],
            "intervention_action_surface": link["subject_action_surface"],
            "relation_family": target.get("relation_family"),
            "response_orientation": response["response_orientation"],
            "response_target_surface": link["response_surface"],
            "endpoint_property_surface": link["endpoint_property_surface"],
            "valid_before_context_externalization": relation_core_valid,
        },
        "query_context_constraints": {
            "artifact_schema_version": QUERY_CONTEXT_VERSION,
            "constraints": constraints,
            "state": "VALID" if contexts_valid else "INVALID",
            "context_externalization_created_relation": False,
        },
        "compositional_response_semantics": response,
        "state": "STRUCTURALLY_BOUND" if bound else "UNDERREPRESENTED",
        "valid_relation_core_before_context_externalization": relation_core_valid,
        "canonical_identity_promoted": False,
    }


def _quote_clause(value: str) -> str:
    return f'"{value.replace(chr(34), chr(92) + chr(34))}"[Title/Abstract]'


def final_query_coverage_v1(*, phrase: str, binding: dict[str, Any]) -> dict[str, Any]:
    if binding["relation_core"]["state"] != "VALID":
        return {"artifact_schema_version": COVERAGE_VERSION, "state": "INVALID_RELATION_CORE",
                "compiled_query": None, "missing_constraints": [],
                "compiler_requires_valid_relation_core": True}
    clauses = [_quote_clause(phrase)]
    missing = []
    externalized = []
    for row in binding["query_context_constraints"]["constraints"]:
        if not row["required"]:
            continue
        if row["state"] != "COMPATIBLE" or not row["surface"]:
            missing.append(row["role"])
        elif not row["present_in_relation_phrase"]:
            clauses.append(_quote_clause(str(row["surface"])))
            externalized.append(row["role"])
    state = "COVERED" if not missing else "MISSING_REQUIRED_CONTEXT"
    return {"artifact_schema_version": COVERAGE_VERSION, "state": state,
            "compiled_query": " AND ".join(clauses) if state == "COVERED" else None,
            "missing_constraints": missing, "externalized_constraints": externalized,
            "relation_core_covered": True,
            "compiler_requires_valid_relation_core": True}


def rehydrate_and_compile_alpha3_2(payload: dict[str, Any], *,
                                  target: dict[str, Any]) -> dict[str, Any]:
    """Replay one frozen Planner V3 payload through the alpha3.2 stack."""
    validate_planner_proposal_v3(payload)
    target_hash = sha256_value(target)
    intents = []
    queries = []
    for intent_index, intent in enumerate(payload["retrieval_intents"]):
        relation_rows = []
        for link_index, link in enumerate(intent["linked_relation_proposals"]):
            binding = assess_relation_binding_v3(
                link=link, target=target, intent_type=intent["intent_type"])
            coverage = final_query_coverage_v1(
                phrase=link["linked_relation_phrase"], binding=binding)
            relation_rows.append({
                "source_link_index": link_index,
                "source_link_sha256": sha256_value(link),
                "relation_binding": binding,
                "final_query_coverage": coverage,
            })
            if binding["state"] == "STRUCTURALLY_BOUND" and coverage["state"] == "COVERED":
                query = coverage["compiled_query"]
                identity = {"compiler_version": COMPILER_VERSION,
                            "target_sha256": target_hash,
                            "intent_type": intent["intent_type"],
                            "intent_index": intent_index, "link_index": link_index,
                            "query_string": query}
                query_hash = sha256_value(identity)
                queries.append({
                    "artifact_schema_version": "CompiledPlannerAlpha3_2QueryV1",
                    "query_id": f"v24a32q:{query_hash}",
                    "query_sha256": query_hash,
                    "query_string": query,
                    "intent_type": intent["intent_type"],
                    "execution_status": "NOT_EXECUTED_DEVELOPMENT_REPLAY",
                })
        intents.append({
            "intent_type": intent["intent_type"],
            "relations": relation_rows,
            "structurally_bound_relation_count": sum(
                row["relation_binding"]["state"] == "STRUCTURALLY_BOUND"
                for row in relation_rows),
            "compiled_query_count": sum(
                row["final_query_coverage"]["state"] == "COVERED"
                and row["relation_binding"]["state"] == "STRUCTURALLY_BOUND"
                for row in relation_rows),
        })
    queries.sort(key=lambda row: (INTENT_ORDER.index(row["intent_type"]), row["query_id"]))
    return {
        "artifact_schema_version": PLAN_VERSION,
        "target_id": target.get("scientific_proposition_target_id"),
        "target_sha256": target_hash,
        "payload_sha256": sha256_value(payload),
        "intents": intents,
        "structurally_bound_intent_count": sum(
            row["structurally_bound_relation_count"] > 0 for row in intents),
        "structurally_bound_relation_count": sum(
            row["structurally_bound_relation_count"] for row in intents),
        "compiled_query_count": len(queries),
        "compiled_queries": queries,
        "compiler_version": COMPILER_VERSION,
        "compiler_requires_valid_relation_core": True,
        "canonical_identity_promotions": 0,
        "provider_calls": 0,
        "network_calls": 0,
        "retrieval_calls": 0,
    }


__all__ = [
    "BINDING_VERSION", "COMPILER_VERSION", "COMPOSITION_VERSION", "COVERAGE_VERSION",
    "DIRECTION_VERSION", "ORIENTATION_VERSION", "PLAN_VERSION", "QUERY_CONTEXT_VERSION",
    "RELATION_CORE_VERSION", "RELATION_INTERNAL_ROLE_MATRIX", "SURFACE_VERSION",
    "UNIT_VERSION", "CompositionalRelationError", "assess_relation_binding_v3",
    "composite_biological_unit_compatibility_v1", "compositional_response_semantics_v1",
    "direction_composition_v1", "final_query_coverage_v1", "rehydrate_and_compile_alpha3_2",
    "semantic_surface_containment_v3",
]
