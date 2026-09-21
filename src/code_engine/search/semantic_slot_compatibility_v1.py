"""Generic alpha2.2 separation of semantic slots from searchable identity anchors.

This module does not grant scientific identity or change the frozen alpha2
planner, prompt, search-only rules, relation binder, or compiler.
"""

from __future__ import annotations

from copy import deepcopy
import re
from typing import Any

from code_engine.search.alpha1_relation_searchonly_v1 import (
    ENDPOINT_LEXICON, _anchors, normalize, singular_tokens,
)
from code_engine.search.alpha2_linked_relation_v1 import (
    PLANNER_PROPOSAL_PAYLOAD_V2_SCHEMA, SUFFICIENT_ANCHORS,
    _contains_surface, _surface_direction, _target_direction, _validate_local_schema,
    search_anchor_compatibility, validate_planner_proposal_v2,
)

SEMANTIC_SLOT_VERSION = "SemanticSlotCompatibilityV1"
ANCHOR_VERSION = "SearchAnchorCompatibilityV1_1"
SEMANTIC_DIMENSIONS = frozenset({"relation", "direction", "endpoint_property", "evidence_mode"})
SURFACE_DIMENSIONS = frozenset({"subject", "object_measurement_target", "biological_unit",
                                "therapy", "disease", "genotype", "nested_treatment"})
SUFFICIENT_SEMANTIC = frozenset({"EXACT_SEMANTIC_MATCH", "AUTHORIZED_SEMANTIC_VARIANT",
                                  "COMPATIBLE_RELATION_PARAPHRASE", "COMPATIBLE_DIRECTION"})
SUFFICIENT_SURFACE = SUFFICIENT_ANCHORS | frozenset({"CANONICAL_ANCHOR_IN_COMPOSITE_SURFACE",
                                                     "SAFE_MORPHOLOGICAL_SURFACE_VARIANT"})
FIELD_OWNERSHIP = {
    "subject": "ENTITY_SURFACE_ANCHOR",
    "object_measurement_target": "ENDPOINT_TARGET_SURFACE_ANCHOR",
    "biological_unit": "BIOLOGICAL_UNIT_SURFACE_ANCHOR",
    "therapy": "THERAPY_SURFACE_ANCHOR",
    "disease": "DISEASE_SURFACE_ANCHOR",
    "genotype": "GENOTYPE_SURFACE_ANCHOR",
    "nested_treatment": "CONDITIONING_CONTEXT_SURFACE_ANCHOR",
    "endpoint_property": "ENDPOINT_PROPERTY_SEMANTIC_SLOT",
    "relation": "RELATION_SEMANTIC_SLOT",
    "direction": "DIRECTION_SEMANTIC_SLOT",
    "evidence_mode": "EVIDENCE_MODE_SEMANTIC_SLOT",
}


class SemanticSlotCompatibilityError(ValueError):
    """A semantic slot or surface was sent to the wrong deterministic gate."""


def _result(dimension: str, proposed: str, state: str, rule: str, target_values: list[str]) -> dict[str, Any]:
    return {"artifact_schema_version": SEMANTIC_SLOT_VERSION,
            "dimension": dimension, "proposed_surface": proposed,
            "target_semantic_values": target_values, "state": state,
            "rule_id": rule, "canonical_identity_promoted": False,
            "scientific_truth_established": False}


def _semantic_target_values(target: dict[str, Any], dimension: str) -> list[str]:
    if dimension == "relation":
        values = [target.get("relation_family"), target.get("canonical_relation_family")]
    elif dimension == "direction":
        values = [target.get("canonical_proposition_orientation"), _target_direction(target)]
    elif dimension == "endpoint_property":
        values = [target.get("measurement_property_endpoint")]
    elif dimension == "evidence_mode":
        values = [target.get("required_evidence_mode")]
    else:
        raise SemanticSlotCompatibilityError(f"not a semantic slot: {dimension}")
    return list(dict.fromkeys(str(value) for value in values if value is not None and str(value).strip()))


def _endpoint_family(value: str) -> str | None:
    text = normalize(value)
    if "flux" in text:
        return "dynamic_autophagic_flux"
    if "phospho" in text:
        return "phosphorylation"
    if "secret" in text or "releas" in text:
        return "secretion_release"
    if "nuclear" in text:
        return "nuclear_localization"
    if any(stem in text for stem in ("sensitiv", "sensitiz", "resistan", "ic50")):
        return "drug_response"
    return None


def _endpoint_variant(proposed: str, target_value: str) -> bool:
    family = _endpoint_family(target_value)
    if family is None:
        return False
    proposed_norm = normalize(proposed)
    if family == "dynamic_autophagic_flux" and "flux" not in proposed_norm and "turnover" not in proposed_norm \
            and "dynamic autophagic degradation" not in proposed_norm:
        return False
    return any(normalize(variant) in proposed_norm for variant in ENDPOINT_LEXICON["families"][family])


def _evidence_mode_core(value: str) -> str | None:
    text = normalize(value)
    if not ("current study" in text or "current study" == text):
        return None
    for family, patterns in (
        ("PERTURBATIONAL", ("perturb", "intervention")),
        ("FUNCTIONAL", ("functional",)),
        ("CAUSAL", ("causal",)),
        ("OBSERVATIONAL", ("observational",)),
    ):
        if any(pattern in text for pattern in patterns) and "evidence" in text:
            return family
    return None


def semantic_slot_compatibility(dimension: str, proposed: str, target: dict[str, Any]) -> dict[str, Any]:
    """Compare a retrieval-semantic slot against the immutable proposition."""
    if dimension not in SEMANTIC_DIMENSIONS:
        raise SemanticSlotCompatibilityError("entity/context dimensions cannot use semantic-slot compatibility")
    values = _semantic_target_values(target, dimension)
    if not isinstance(proposed, str) or not proposed.strip():
        return _result(dimension, str(proposed or ""), "UNDER_SPECIFIED", "SEMANTIC_SLOT_ABSENT", values)
    text = normalize(proposed)
    if any(text == normalize(value) for value in values):
        return _result(dimension, proposed, "EXACT_SEMANTIC_MATCH", "EXACT_FROZEN_TARGET_SEMANTIC_VALUE", values)
    if not values:
        return _result(dimension, proposed, "UNRESOLVED", "TARGET_SEMANTIC_SLOT_UNAVAILABLE", values)
    if dimension == "relation":
        target_direction = _target_direction(target)
        proposed_direction = _surface_direction(proposed)
        if target_direction and proposed_direction and target_direction == proposed_direction:
            return _result(dimension, proposed, "COMPATIBLE_RELATION_PARAPHRASE",
                           "FROZEN_GENERIC_RELATION_DIRECTION_FAMILY", values)
        if target_direction and proposed_direction and target_direction != proposed_direction:
            return _result(dimension, proposed, "INCOMPATIBLE", "RELATION_DIRECTION_CONFLICT", values)
    elif dimension == "direction":
        target_direction = _target_direction(target)
        proposed_direction = _surface_direction(proposed)
        if target_direction and proposed_direction and target_direction == proposed_direction:
            return _result(dimension, proposed, "COMPATIBLE_DIRECTION", "FROZEN_TARGET_DIRECTION_CATEGORY", values)
        if target_direction and proposed_direction and target_direction != proposed_direction:
            return _result(dimension, proposed, "INCOMPATIBLE", "OPPOSITE_DIRECTION", values)
    elif dimension == "endpoint_property":
        if any(_endpoint_variant(proposed, value) for value in values):
            return _result(dimension, proposed, "AUTHORIZED_SEMANTIC_VARIANT",
                           "FROZEN_GENERIC_ENDPOINT_LEXICON", values)
    elif dimension == "evidence_mode":
        target_core = _evidence_mode_core(values[0])
        proposed_core = _evidence_mode_core(proposed)
        if target_core and target_core == proposed_core:
            return _result(dimension, proposed, "AUTHORIZED_SEMANTIC_VARIANT",
                           "FROZEN_EVIDENCE_MODE_CORE_WITH_TARGET_LINK_SEPARATE", values)
        if target_core and proposed_core and target_core != proposed_core:
            return _result(dimension, proposed, "INCOMPATIBLE", "EVIDENCE_MODE_FAMILY_CONFLICT", values)
    return _result(dimension, proposed, "UNDER_SPECIFIED", "NO_GENERIC_SEMANTIC_SLOT_COMPATIBILITY", values)


def search_anchor_compatibility_v1_1(surface: str, target: dict[str, Any], dimension: str) -> dict[str, Any]:
    """Search-surface coverage, never canonical entity/biological-unit identity."""
    if dimension not in SURFACE_DIMENSIONS:
        raise SemanticSlotCompatibilityError("semantic slot cannot use entity alias lookup")
    anchors = _anchors(target, dimension)
    state = search_anchor_compatibility(surface, anchors)
    rule = "FROZEN_SEARCH_ANCHOR_COMPATIBILITY"
    if state not in SUFFICIENT_SURFACE and anchors and isinstance(surface, str):
        if dimension in {"subject", "object_measurement_target"} and not re.search(
            r"\b(?:not|without|except|versus|vs|or)\b", normalize(surface)
        ) and any(_contains_surface(surface, anchor) for anchor in anchors):
            state = "CANONICAL_ANCHOR_IN_COMPOSITE_SURFACE"
            rule = "FULL_CANONICAL_ENTITY_ANCHOR_CONTAINED_FOR_SEARCH_ONLY"
        elif dimension in {"biological_unit", "disease", "genotype", "nested_treatment"} and any(
            singular_tokens(surface) == singular_tokens(anchor) for anchor in anchors
        ):
            state = "SAFE_MORPHOLOGICAL_SURFACE_VARIANT"
            rule = "GENERIC_FULL_SURFACE_MORPHOLOGY_FOR_SEARCH_ONLY"
    return {"artifact_schema_version": ANCHOR_VERSION, "dimension": dimension,
            "proposed_surface": surface, "target_surfaces": anchors,
            "state": state, "rule_id": rule,
            "canonical_identity_promoted": False,
            "sufficient_for_search_anchor": state in SUFFICIENT_SURFACE}


def validate_v2_structure_and_slots(payload: dict[str, Any], target: dict[str, Any]) -> dict[str, Any]:
    """Reuse frozen V2 reference validator after semantic slots are checked separately."""
    _validate_local_schema(payload, PLANNER_PROPOSAL_PAYLOAD_V2_SCHEMA)
    projected = deepcopy(payload)
    semantic_rows = []
    surface_rows = []
    for intent in projected["retrieval_intents"]:
        for concept in intent["search_concepts"]:
            dimension = concept["concept_type"]
            values = concept["canonical_anchor"]
            values = values if isinstance(values, list) else [values]
            for value in values:
                if dimension in SEMANTIC_DIMENSIONS:
                    semantic_rows.append({"intent_id": intent["intent_id"], "concept_id": concept["concept_id"],
                                          **semantic_slot_compatibility(dimension, value, target)})
                else:
                    surface_rows.append({"intent_id": intent["intent_id"], "concept_id": concept["concept_id"],
                                         **search_anchor_compatibility_v1_1(value, target, dimension)})
            # Frozen V2 remains the shape/reference validator. All anchors are
            # checked above by their proper V1.1 surface or semantic owner;
            # no proposed anchor is sent back through its obsolete V1 lookup.
            # The source payload is never changed.
            concept["canonical_anchor"] = None
    validate_planner_proposal_v2(projected, target=target)
    return {"provider_payload_schema_valid": True, "concept_references_valid": True,
            "semantic_slots": semantic_rows, "surface_anchors": surface_rows,
            "semantic_slots_compatible": all(row["state"] in SUFFICIENT_SEMANTIC for row in semantic_rows),
            "surface_anchors_compatible": all(row["sufficient_for_search_anchor"] for row in surface_rows),
            "original_payload_mutated": False}


def audit_linked_relation_candidate(link: dict[str, Any], target: dict[str, Any]) -> dict[str, Any]:
    """Check V2 retrieval-language roles without changing frozen relation binding."""
    phrase = link["linked_relation_phrase"]
    subject = search_anchor_compatibility_v1_1(link["subject_surface_candidate"], target, "subject")
    response = search_anchor_compatibility_v1_1(
        link["response_surface_candidate"], target, "object_measurement_target")
    relation_family = semantic_slot_compatibility("relation", link["relation_family"], target)
    relation_surface = semantic_slot_compatibility("relation", link["relation_surface_candidate"], target)
    direction = semantic_slot_compatibility("direction", link["direction"], target)
    endpoint_property = semantic_slot_compatibility(
        "endpoint_property", link["endpoint_property_surface_candidate"], target)
    endpoint_in_phrase = semantic_slot_compatibility("endpoint_property", phrase, target)
    required_unit = _anchors(target, "biological_unit")
    unit_present = not required_unit or bool(link["biological_unit_context_ref"]) and any(
        " " + singular_tokens(anchor) + " " in " " + singular_tokens(phrase) + " " for anchor in required_unit)
    required_conditioning = _anchors(target, "nested_treatment")
    conditioning_present = not required_conditioning or bool(link["conditioning_context_refs"]) and any(
        _contains_surface(phrase, anchor) for anchor in required_conditioning)
    required_therapy = _anchors(target, "therapy")
    therapy_present = not required_therapy or bool(link["therapy_context_refs"]) and any(
        _contains_surface(phrase, anchor) for anchor in required_therapy)
    checks = {
        "subject_surface_anchor": subject["sufficient_for_search_anchor"],
        "response_surface_anchor": response["sufficient_for_search_anchor"],
        "relation_family_semantic_slot": relation_family["state"] in SUFFICIENT_SEMANTIC,
        "relation_surface_semantic_slot": relation_surface["state"] in SUFFICIENT_SEMANTIC,
        "direction_semantic_slot": direction["state"] in SUFFICIENT_SEMANTIC,
        "endpoint_property_semantic_slot": endpoint_property["state"] in SUFFICIENT_SEMANTIC,
        "linked_phrase_contains_subject": _contains_surface(phrase, link["subject_surface_candidate"]),
        "linked_phrase_contains_response": _contains_surface(phrase, link["response_surface_candidate"]),
        "linked_phrase_contains_relation": _contains_surface(phrase, link["relation_surface_candidate"]),
        "linked_phrase_retains_endpoint_property": endpoint_in_phrase["state"] in SUFFICIENT_SEMANTIC,
        "required_biological_unit_context": unit_present,
        "required_conditioning_context": conditioning_present,
        "required_therapy_context": therapy_present,
    }
    return {"artifact_schema_version": "LinkedRelationCandidateSemanticSlotAuditV1",
            "valid": all(checks.values()), "checks": checks,
            "subject_anchor": subject, "response_anchor": response,
            "relation_family_semantic": relation_family,
            "relation_surface_semantic": relation_surface,
            "direction_semantic": direction,
            "endpoint_property_semantic": endpoint_property,
            "endpoint_in_phrase_semantic": endpoint_in_phrase,
            "canonical_identity_promoted": False}
