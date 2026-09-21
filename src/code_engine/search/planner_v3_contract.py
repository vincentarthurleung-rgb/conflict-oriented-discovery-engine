"""Minimal Planner V3 semantic contract for Search Plan v2.4 development.

The provider owns retrieval semantics and lexical proposals only.  Every opaque
identifier, canonical role binding, applicability decision, authority decision,
validation receipt, and compiler decision is deterministic and local.

This module is prospective and offline-safe.  It does not contain provider or
retrieval execution code and does not modify the frozen Planner V2 contract.
"""

from __future__ import annotations

from copy import deepcopy
import hashlib
import re
from typing import Any

from code_engine.search.alpha1_relation_searchonly_v1 import _anchors, normalize
from code_engine.search.alpha2_linked_relation_v1 import (
    DIRECTIONS, SUFFICIENT_ANCHORS, _contains_surface, _target_direction,
    _validate_local_schema, search_anchor_compatibility,
)
from code_engine.search.context_role_ontology_v1 import (
    conditioning_context_applicability, context_role_mapping,
    therapy_context_applicability,
)
from code_engine.search.proposition_aware_query_planner_v1 import (
    canonical_target_hash, sha256_value,
)
from code_engine.search.retrieval_intent_v1 import INTENT_ORDER, applicable_intent_types
from code_engine.search.semantic_slot_compatibility_v1 import (
    SUFFICIENT_SEMANTIC, semantic_slot_compatibility,
)

PAYLOAD_VERSION = "PlannerProposalPayloadV3"
LINK_VERSION = "LinkedRelationProposalV2"
ROLE_FRAME_VERSION = "DeterministicTargetRoleFrameV1"
APPLICABILITY_VERSION = "RetrievalIntentApplicabilityV2"
TRANSFORM_VERSION = "IntentSemanticTransformV1"
EXPECTED_VERSION = "ExpectedRetrievalSemanticsV1"
ALLOCATOR_VERSION = "PlannerArtifactIdAllocatorV1"
REHYDRATOR_VERSION = "PlannerRoleRehydratorV1"
SURFACE_VERSION = "SemanticSurfaceContainmentV2"
VALIDATED_INTENT_VERSION = "ValidatedPlannerIntentV3"
VALIDATED_PLAN_VERSION = "ValidatedPlannerPlanV3"
COMPILER_VERSION = "DeterministicQueryCompilerV24DevPlannerV3"
PROMPT_VERSION = "PlannerPromptV3"
CACHE_VERSION = "DeepSeekPlannerCacheIdentityV3"

PROMPT_TEXT_V3 = """You are PROPOSITION_AWARE_QUERY_PLANNER. Return one JSON object that
matches PlannerProposalPayloadV3. Understand the immutable proposition and choose
only useful retrieval intents from the supplied applicable intent types. Generate
linked actor-to-response retrieval language, preserve endpoint semantics and the
provided canonical role surfaces when possible, and provide useful lexical
alternatives. Do not invent scientific equivalence. You propose retrieval language,
not scientific truth, identity, authority, applicability, validation, or relevance.
Do not emit IDs, references, namespaces, canonical-target echoes, hashes, coverage,
or compiler results. The deterministic system owns all of those fields.
"""


class PlannerV3ContractError(ValueError):
    """Fail-closed Planner V3 schema, role, or compiler-boundary violation."""


def _object(fields: dict[str, Any]) -> dict[str, Any]:
    return {"type": "object", "additionalProperties": False,
            "properties": fields, "required": list(fields)}


_TEXT = {"type": "string"}
_OPTIONAL_TEXT = {"type": ["string", "null"]}
SEARCH_CONCEPT_PROPOSAL_V3_SCHEMA = _object({
    "semantic_role": {"type": "string", "enum": [
        "PRIMARY_INTERVENTION", "PRIMARY_INTERVENTION_ACTION", "RESPONSE_TARGET",
        "RESPONSE_PROPERTY", "BIOLOGICAL_UNIT_CONTEXT", "CONDITIONING_TREATMENT",
        "THERAPY", "DISEASE_CONTEXT", "GENOTYPE_CONTEXT", "EVIDENCE_MODE",
    ]},
    "proposed_terms": {"type": "array", "items": _TEXT},
})
LINKED_RELATION_PROPOSAL_V2_SCHEMA = _object({
    "subject_surface": _TEXT,
    "subject_action_surface": _TEXT,
    "relation_surface": _TEXT,
    "direction": {"type": "string", "enum": list(DIRECTIONS)},
    "response_surface": _TEXT,
    "endpoint_property_surface": _TEXT,
    "linked_relation_phrase": _TEXT,
    "biological_unit_surface": _OPTIONAL_TEXT,
    "conditioning_treatment_surface": _OPTIONAL_TEXT,
    "therapy_surface": _OPTIONAL_TEXT,
    "disease_surface": _OPTIONAL_TEXT,
    "genotype_surface": _OPTIONAL_TEXT,
    "evidence_mode_surface": _OPTIONAL_TEXT,
    "planner_rationale": _TEXT,
})
PLANNER_PROPOSAL_PAYLOAD_V3_SCHEMA = _object({
    "retrieval_intents": {"type": "array", "items": _object({
        "intent_type": {"type": "string", "enum": list(INTENT_ORDER)},
        "retrieval_rationale": _TEXT,
        "linked_relation_proposals": {
            "type": "array", "items": LINKED_RELATION_PROPOSAL_V2_SCHEMA,
        },
        "search_concept_proposals": {
            "type": "array", "items": SEARCH_CONCEPT_PROPOSAL_V3_SCHEMA,
        },
    })},
})

FORBIDDEN_PROVIDER_FIELDS = frozenset({
    "intent_id", "blueprint_id", "concept_id", "term_id", "subject_concept_ref",
    "response_concept_ref", "conditioning_context_refs", "therapy_context_refs",
    "biological_unit_context_ref", "disease_ref", "genotype_ref", "target_id",
    "canonical_target", "artifact_schema_version", "cache_identity", "applicability",
    "authority", "authority_reference", "deterministic_classification", "coverage",
    "validation_receipt", "compiler_result",
})


def _walk_keys(value: Any) -> set[str]:
    keys: set[str] = set()
    if isinstance(value, dict):
        keys.update(value)
        for child in value.values():
            keys.update(_walk_keys(child))
    elif isinstance(value, list):
        for child in value:
            keys.update(_walk_keys(child))
    return keys


def _nonempty(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise PlannerV3ContractError(f"{label} must be nonempty")
    return value


def validate_planner_proposal_v3(payload: dict[str, Any], *,
                                 allowed_intent_types: list[str] | None = None) -> dict[str, Any]:
    """Validate model semantic/lexical content without granting authority."""
    try:
        _validate_local_schema(payload, PLANNER_PROPOSAL_PAYLOAD_V3_SCHEMA)
    except Exception as exc:
        raise PlannerV3ContractError(str(exc)) from exc
    forbidden = _walk_keys(payload) & FORBIDDEN_PROVIDER_FIELDS
    if forbidden:
        raise PlannerV3ContractError(f"provider owns forbidden fields: {sorted(forbidden)}")
    if not payload["retrieval_intents"]:
        raise PlannerV3ContractError("at least one retrieval intent required")
    allowed = set(allowed_intent_types or INTENT_ORDER)
    seen: set[str] = set()
    for intent_index, intent in enumerate(payload["retrieval_intents"]):
        intent_type = intent["intent_type"]
        if intent_type not in allowed:
            raise PlannerV3ContractError(f"intent is not request-applicable: {intent_type}")
        if intent_type in seen:
            raise PlannerV3ContractError("duplicate intent type")
        seen.add(intent_type)
        _nonempty(intent["retrieval_rationale"], f"intent[{intent_index}].retrieval_rationale")
        if not intent["linked_relation_proposals"]:
            raise PlannerV3ContractError("each selected intent needs linked retrieval language")
        for link_index, link in enumerate(intent["linked_relation_proposals"]):
            for field in ("subject_surface", "subject_action_surface", "relation_surface",
                          "response_surface", "endpoint_property_surface",
                          "linked_relation_phrase", "planner_rationale"):
                _nonempty(link[field], f"intent[{intent_index}].link[{link_index}].{field}")
        for concept in intent["search_concept_proposals"]:
            if not concept["proposed_terms"] or any(
                    not isinstance(term, str) or not term.strip()
                    for term in concept["proposed_terms"]):
                raise PlannerV3ContractError("search concept terms must be nonempty")
    return payload


def _unique(values: list[str]) -> list[str]:
    return list(dict.fromkeys(value for value in values if isinstance(value, str) and value.strip()))


def deterministic_target_role_frame_v1(target: dict[str, Any]) -> dict[str, Any]:
    """Construct canonical role ownership from the immutable target only."""
    mapping = context_role_mapping(target)
    by_role: dict[str, list[str]] = {}
    for row in mapping["roles"]:
        by_role.setdefault(row["role"], []).append(row["surface"])
    conditioning = conditioning_context_applicability(target)
    therapy = therapy_context_applicability(target)
    direction = _response_direction(target)
    if direction is None:
        raise PlannerV3ContractError("target direction is unresolved")
    role_surfaces = {
        "PRIMARY_INTERVENTION": _unique(by_role.get("PRIMARY_INTERVENTION", [])),
        "PRIMARY_INTERVENTION_ACTION": _unique(by_role.get("PRIMARY_INTERVENTION_ACTION", [])),
        "RESPONSE_TARGET": _unique(by_role.get("RESPONSE_TARGET", [])),
        "RESPONSE_PROPERTY": _unique(by_role.get("RESPONSE_PROPERTY", [])),
        "BIOLOGICAL_UNIT_CONTEXT": _unique(by_role.get("BIOLOGICAL_UNIT_CONTEXT", [])),
        "CONDITIONING_TREATMENT": _unique(conditioning["required_surfaces"]),
        "THERAPY": _unique(therapy["required_surfaces"]),
        "DISEASE_CONTEXT": _unique(by_role.get("DISEASE_CONTEXT", [])),
        "GENOTYPE_CONTEXT": _unique(by_role.get("GENOTYPE_CONTEXT", [])),
        "EVIDENCE_MODE": _unique([str(target.get("required_evidence_mode") or "")]),
    }
    return {
        "artifact_schema_version": ROLE_FRAME_VERSION,
        "target_id": target.get("scientific_proposition_target_id"),
        "target_sha256": canonical_target_hash(target),
        "role_surfaces": role_surfaces,
        "target_direction": direction,
        "target_relation_family": str(target.get("relation_family") or
                                      target.get("canonical_relation_family") or ""),
        "conditioning_treatment_applicability": conditioning["state"],
        "therapy_applicability": therapy["state"],
        "authority_source": "IMMUTABLE_SCIENTIFIC_PROPOSITION_TARGET",
        "canonical_identity_promoted": False,
        "model_output_used": False,
    }


def retrieval_intent_applicability_v2(target: dict[str, Any]) -> dict[str, Any]:
    """Freeze request-applicable intent classes before provider inference."""
    applicable = applicable_intent_types(target)
    # The V1 recognizer is conservative. Generic counterfactual/causal intents
    # are structurally allowed when the frozen evidence boundary explicitly
    # names that formulation; this is target semantics, never retrieval outcome.
    evidence = normalize(" ".join([
        str(target.get("required_evidence_mode") or ""),
        " ".join(str(v) for v in target.get("acceptable_endpoint_evidence") or []),
    ]))
    semantic_markers = {
        "INVERSE_PERTURBATION": ("inverse", "loss", "inhibition", "deficiency"),
        "NECESSITY": ("necessity", "required", "essential", "dependency"),
        "RESCUE": ("rescue", "restor", "reversal"),
    }
    selected = set(applicable)
    for intent_type, markers in semantic_markers.items():
        if any(marker in evidence for marker in markers):
            selected.add(intent_type)
    if target.get("therapy") and "sensitiv" in normalize(str(target.get("measurement_property_endpoint") or "")):
        selected.add("THERAPY_SENSITIZATION")
        selected.add("THERAPY_RESISTANCE")
    ordered = [name for name in INTENT_ORDER if name in selected]
    return {
        "artifact_schema_version": APPLICABILITY_VERSION,
        "target_sha256": canonical_target_hash(target),
        "applicable_intent_types": ordered,
        "planner_may_choose_subset": True,
        "adaptive_to_retrieval_outcomes": False,
        "model_applicability_decisions": 0,
    }


_INVERSE = {"INCREASE": "DECREASE", "DECREASE": "INCREASE",
            "ACTIVATE": "INHIBIT", "INHIBIT": "ACTIVATE",
            "SENSITIZE": "RESIST", "RESIST": "SENSITIZE"}


def _response_direction(target: dict[str, Any]) -> str | None:
    """Resolve the response orientation, not the intervention polarity."""
    orientation = normalize(str(target.get("canonical_proposition_orientation") or ""))
    if "->" in orientation:
        text = orientation.rsplit("->", 1)[-1]
    else:
        text = normalize(" ".join(str(target.get(key) or "") for key in (
            "relation_family", "canonical_relation_family")))
    if "sensitiv" in text or "decreased resistance" in text:
        return "SENSITIZE"
    if "increased resistance" in text or "resistance to" in text:
        return "RESIST"
    if any(token in text for token in ("increases", "increased", "increase")):
        return "INCREASE"
    if any(token in text for token in ("decreases", "decreased", "decrease", "suppresses", "reduced")):
        return "DECREASE"
    return _target_direction(target)


def intent_semantic_transform_v1(target: dict[str, Any], intent_type: str) -> dict[str, Any]:
    """Return generic intent-conditioned expectations, not scientific truth."""
    if intent_type not in INTENT_ORDER:
        raise PlannerV3ContractError(f"unknown intent type: {intent_type}")
    frame = deterministic_target_role_frame_v1(target)
    direct = frame["target_direction"]
    direction_rules: dict[str, tuple[str, ...]] = {
        "DIRECT_PERTURBATION": (direct,),
        "INVERSE_PERTURBATION": tuple(v for v in (_INVERSE.get(direct), "RESIST" if direct == "SENSITIZE" else None) if v),
        "NECESSITY": ("REQUIRE", _INVERSE.get(direct) or direct),
        "RESCUE": ("RESCUE",),
        "FUNCTIONAL_CHAIN": (direct,),
        "THERAPY_SENSITIZATION": ("SENSITIZE",),
        "THERAPY_RESISTANCE": ("RESIST",),
        "ENDPOINT_SPECIFIC": (direct,),
        "CONTEXT_SPECIFIC": (direct,),
    }
    mode = {
        "DIRECT_PERTURBATION": "PRESERVE_DIRECT_PROPOSITION",
        "INVERSE_PERTURBATION": "INVERT_PRIMARY_PERTURBATION_AND_RESPONSE_ORIENTATION",
        "NECESSITY": "REQUIREMENT_OR_LOSS_OF_FUNCTION_COUNTERFACTUAL",
        "RESCUE": "RESTORE_STATE_AFTER_PRIMARY_PERTURBATION",
        "FUNCTIONAL_CHAIN": "PRESERVE_ENDPOINT_WITH_INTERMEDIATE_CHAIN",
        "THERAPY_SENSITIZATION": "TARGET_PERTURBATION_INCREASES_THERAPY_RESPONSE",
        "THERAPY_RESISTANCE": "TARGET_STATE_DECREASES_THERAPY_RESPONSE",
        "ENDPOINT_SPECIFIC": "PRESERVE_PROPOSITION_AND_EMPHASIZE_ENDPOINT",
        "CONTEXT_SPECIFIC": "PRESERVE_PROPOSITION_AND_REQUIRE_CONTEXT",
    }[intent_type]
    therapy_required = intent_type in {"THERAPY_SENSITIZATION", "THERAPY_RESISTANCE"} or \
        frame["therapy_applicability"] == "REQUIRED"
    return {
        "artifact_schema_version": EXPECTED_VERSION,
        "transform_version": TRANSFORM_VERSION,
        "intent_type": intent_type,
        "semantic_mode": mode,
        "required_actor_role": "PRIMARY_INTERVENTION",
        "allowed_directions": list(dict.fromkeys(direction_rules[intent_type])),
        "response_target_preserved": True,
        "endpoint_semantic_family_preserved": True,
        "conditioning_treatment_applicability": frame["conditioning_treatment_applicability"],
        "therapy_required": therapy_required,
        "disease_context_required": bool(frame["role_surfaces"]["DISEASE_CONTEXT"]),
        "genotype_context_required": bool(frame["role_surfaces"]["GENOTYPE_CONTEXT"]),
        "biological_unit_required": bool(frame["role_surfaces"]["BIOLOGICAL_UNIT_CONTEXT"]),
        "evidence_mode_injected_deterministically": True,
        "unrelated_actor_substitution_allowed": False,
        "scientific_equivalence_assumed": False,
    }


def allocate_artifact_id_v1(*, target_sha256: str, intent_index: int,
                            intent_type: str, semantic_role: str,
                            normalized_surface: str, ordinal: int = 0) -> str:
    """Allocate a stable opaque ID from deterministic, versioned inputs."""
    identity = {
        "allocator_version": ALLOCATOR_VERSION, "target_sha256": target_sha256,
        "intent_index": intent_index, "intent_type": intent_type,
        "semantic_role": semantic_role, "normalized_surface": normalize(normalized_surface),
        "ordinal": ordinal,
    }
    prefix = {"INTENT": "intent", "BLUEPRINT": "blueprint", "TERM": "term"}.get(
        semantic_role, "concept")
    return f"v3:{prefix}:{sha256_value(identity)[:24]}"


def semantic_surface_containment_v2(phrase: str, proposed_surface: str,
                                    canonical_surfaces: list[str]) -> dict[str, Any]:
    """Check role-wise exact/authorized surfaces without fuzzy equivalence."""
    candidates = _unique([proposed_surface, *canonical_surfaces])
    matched = [surface for surface in candidates if _contains_surface(phrase, surface)]
    # A slash-delimited surface is an alias set, not one required contiguous string.
    alias_parts = _unique([
        part.strip() for surface in candidates for part in re.split(r"\s*/\s*", surface)
        if part.strip()
    ])
    matched_aliases = [surface for surface in alias_parts if _contains_surface(phrase, surface)]
    return {
        "artifact_schema_version": SURFACE_VERSION,
        "state": "CONTAINED" if matched or matched_aliases else "NOT_CONTAINED",
        "matched_surfaces": _unique(matched + matched_aliases),
        "whole_multi_alias_string_required": False,
        "fuzzy_equivalence_used": False,
        "canonical_identity_promoted": False,
    }


def _surface_anchor(surface: str, anchors: list[str]) -> bool:
    if not surface or not anchors:
        return False
    if search_anchor_compatibility(surface, anchors) in SUFFICIENT_ANCHORS or any(
            _contains_surface(surface, anchor) for anchor in anchors):
        return True
    def morphological(value: str) -> str:
        tokens = normalize(value).split()
        return " ".join(token[:-1] if token.endswith("s") and len(token) > 3 else token
                        for token in tokens)
    surface_norm = morphological(surface)
    return any(surface_norm == morphological(part.strip())
               for anchor in anchors for part in re.split(r"\s*/\s*", anchor) if part.strip())


def _bound_role_surface_in_phrase(phrase: str, surface: str, anchors: list[str], role: str) -> bool:
    """Render a role already bound to a frozen anchor; never establish identity."""
    if semantic_surface_containment_v2(phrase, surface, anchors)["state"] == "CONTAINED":
        return True
    if role == "BIOLOGICAL_UNIT_CONTEXT":
        def singular_tokens(value: str) -> list[str]:
            return [token[:-1] if token.endswith("s") and len(token) > 3 else token
                    for token in normalize(value).split()]
        needle = singular_tokens(surface)
        haystack = singular_tokens(phrase)
        if needle and any(haystack[index:index + len(needle)] == needle
                          for index in range(len(haystack) - len(needle) + 1)):
            return True
    if role != "CONDITIONING_TREATMENT":
        return False
    phrase_norm = normalize(phrase)
    for anchor in anchors:
        anchor_norm = normalize(anchor)
        if anchor_norm.endswith(" stimulation"):
            actor = anchor_norm.removesuffix(" stimulation").strip()
            if actor and _contains_surface(phrase, actor) and any(
                    token in phrase_norm for token in ("induced", "stimulated", "stimulation")):
                return True
    return False


def _endpoint_compatible(surface: str, target: dict[str, Any]) -> bool:
    record = semantic_slot_compatibility("endpoint_property", surface, target)
    if record["state"] in SUFFICIENT_SEMANTIC:
        return True
    proposed = normalize(surface)
    target_endpoint = normalize(str(target.get("measurement_property_endpoint") or ""))
    families = (
        (("phospho",), ("phospho",)),
        (("nuclear",), ("nuclear",)),
        (("secret", "release"), ("secret", "release")),
        (("flux", "turnover"), ("flux", "turnover")),
        (("sensitiv", "resistan", "response", "cytotoxic"),
         ("sensitiv", "resistan", "response")),
        (("surface", "protein", "abundance"), ("surface", "protein", "abundance")),
    )
    return any(any(a in proposed for a in left) and any(b in target_endpoint for b in right)
               for left, right in families)


def _endpoint_family_in_phrase(phrase: str, target: dict[str, Any]) -> bool:
    phrase_norm = normalize(phrase)
    endpoint = normalize(str(target.get("measurement_property_endpoint") or ""))
    families = (
        (("phospho",), ("phospho",)),
        (("nuclear",), ("nuclear",)),
        (("secret", "release", "extracellular"), ("secret", "release")),
        (("flux", "turnover"), ("flux", "turnover")),
        (("sensitiv", "resistan", "response", "cytotoxic"),
         ("sensitiv", "resistan", "response")),
        (("surface", "protein", "expression", "abundance"),
         ("surface", "protein", "abundance")),
    )
    return any(any(marker in phrase_norm for marker in phrase_markers)
               and any(marker in endpoint for marker in endpoint_markers)
               for phrase_markers, endpoint_markers in families)


def planner_role_rehydrate_v1(payload: dict[str, Any], *, target: dict[str, Any]) -> dict[str, Any]:
    """Bind proposal fields to known roles and emit validated internal objects.

    Lexical similarity is never used to create a new canonical identity.  A
    proposal either maps to an existing frozen role or fails closed.
    """
    applicability = retrieval_intent_applicability_v2(target)
    validate_planner_proposal_v3(payload, allowed_intent_types=applicability["applicable_intent_types"])
    frame = deterministic_target_role_frame_v1(target)
    target_hash = frame["target_sha256"]
    intents: list[dict[str, Any]] = []
    all_valid = True
    for intent_index, intent in enumerate(payload["retrieval_intents"]):
        expected = intent_semantic_transform_v1(target, intent["intent_type"])
        intent_id = allocate_artifact_id_v1(
            target_sha256=target_hash, intent_index=intent_index,
            intent_type=intent["intent_type"], semantic_role="INTENT",
            normalized_surface=intent["retrieval_rationale"])
        candidates = []
        for link_index, link in enumerate(intent["linked_relation_proposals"]):
            phrase = link["linked_relation_phrase"]
            role_surfaces = frame["role_surfaces"]
            subject_anchor = _surface_anchor(link["subject_surface"], role_surfaces["PRIMARY_INTERVENTION"])
            response_anchors = _unique(role_surfaces["RESPONSE_TARGET"] +
                                       [str(v) for v in target.get("acceptable_endpoint_evidence") or []])
            response_anchor = _surface_anchor(link["response_surface"], response_anchors) or any(
                _contains_surface(link["response_surface"], value) or _contains_surface(value, link["response_surface"])
                for value in response_anchors)
            if not response_anchor and expected["therapy_required"]:
                response_anchor = any(_contains_surface(link["response_surface"], therapy)
                                      for therapy in role_surfaces["THERAPY"]) and \
                    _endpoint_compatible(link["endpoint_property_surface"], target)
            checks = {
                "subject_anchor": subject_anchor,
                "response_anchor": response_anchor,
                "subject_in_phrase": semantic_surface_containment_v2(
                    phrase, link["subject_surface"], role_surfaces["PRIMARY_INTERVENTION"])["state"] == "CONTAINED",
                "response_in_phrase": semantic_surface_containment_v2(
                    phrase, link["response_surface"], response_anchors)["state"] == "CONTAINED",
                "endpoint_semantics": _endpoint_compatible(link["endpoint_property_surface"], target),
                "endpoint_in_phrase": semantic_surface_containment_v2(
                    phrase, link["endpoint_property_surface"],
                    role_surfaces["RESPONSE_PROPERTY"] + [str(v) for v in target.get("acceptable_endpoint_evidence") or []]
                )["state"] == "CONTAINED" or _endpoint_family_in_phrase(phrase, target),
                "intent_conditioned_direction": link["direction"] in expected["allowed_directions"],
            }
            if not checks["response_in_phrase"] and expected["therapy_required"]:
                checks["response_in_phrase"] = any(_contains_surface(phrase, therapy)
                                                    for therapy in role_surfaces["THERAPY"]) and \
                    _endpoint_family_in_phrase(phrase, target)
            context_fields = (
                ("biological_unit_surface", "BIOLOGICAL_UNIT_CONTEXT", expected["biological_unit_required"]),
                ("conditioning_treatment_surface", "CONDITIONING_TREATMENT",
                 expected["conditioning_treatment_applicability"] == "REQUIRED"),
                ("therapy_surface", "THERAPY", expected["therapy_required"]),
                ("disease_surface", "DISEASE_CONTEXT", expected["disease_context_required"]),
                ("genotype_surface", "GENOTYPE_CONTEXT", expected["genotype_context_required"]),
            )
            bound_roles = {}
            for field, role, required in context_fields:
                surface = link[field]
                anchors = role_surfaces[role]
                if required:
                    ok = bool(surface) and _surface_anchor(str(surface), anchors) and \
                        _bound_role_surface_in_phrase(phrase, str(surface), anchors, role)
                else:
                    ok = surface is None or not anchors or _surface_anchor(str(surface), anchors)
                checks[f"{role.lower()}_compatible"] = ok
                bound_roles[role] = {
                    "applicability": "REQUIRED" if required else "NOT_APPLICABLE" if not anchors else "OPTIONAL",
                    "canonical_surfaces": anchors,
                    "proposed_surface": surface,
                    "bound": bool(surface) and _surface_anchor(str(surface), anchors),
                }
            valid = all(checks.values())
            all_valid = all_valid and valid
            blueprint_id = allocate_artifact_id_v1(
                target_sha256=target_hash, intent_index=intent_index,
                intent_type=intent["intent_type"], semantic_role="BLUEPRINT",
                normalized_surface=phrase, ordinal=link_index)
            canonical_refs = {
                role: allocate_artifact_id_v1(
                    target_sha256=target_hash, intent_index=intent_index,
                    intent_type=intent["intent_type"], semantic_role=role,
                    normalized_surface=" | ".join(surfaces), ordinal=link_index)
                for role, surfaces in role_surfaces.items() if surfaces
            }
            candidates.append({
                "artifact_schema_version": "ValidatedLinkedRelationV3",
                "blueprint_id": blueprint_id,
                "source_link_index": link_index,
                "source_link_sha256": sha256_value(link),
                "linked_relation_phrase": phrase,
                "direction": link["direction"],
                "checks": checks,
                "bound_role_state": bound_roles,
                "deterministic_canonical_role_refs": canonical_refs,
                "validation_state": "STRUCTURALLY_BOUND" if valid else "V3_PROJECTION_INSUFFICIENT",
                "canonical_identity_promoted": False,
                "scientific_truth_established": False,
            })
        intents.append({
            "artifact_schema_version": VALIDATED_INTENT_VERSION,
            "intent_id": intent_id,
            "intent_type": intent["intent_type"],
            "expected_retrieval_semantics": expected,
            "linked_relations": candidates,
            "structurally_bound_relation_count": sum(
                row["validation_state"] == "STRUCTURALLY_BOUND" for row in candidates),
            "validation_state": "VALID" if candidates and all(
                row["validation_state"] == "STRUCTURALLY_BOUND" for row in candidates)
                else "PARTIALLY_VALID" if any(row["validation_state"] == "STRUCTURALLY_BOUND" for row in candidates)
                else "V3_PROJECTION_INSUFFICIENT",
        })
    return {
        "artifact_schema_version": VALIDATED_PLAN_VERSION,
        "target_id": target.get("scientific_proposition_target_id"),
        "target_sha256": target_hash,
        "target_role_frame_sha256": sha256_value(frame),
        "planner_payload_sha256": sha256_value(payload),
        "intents": intents,
        "all_proposals_valid": all_valid,
        "has_structurally_bound_relation": any(
            row["structurally_bound_relation_count"] for row in intents),
        "model_generated_opaque_id_count": 0,
        "model_generated_canonical_ref_count": 0,
        "model_generated_applicability_decision_count": 0,
        "model_generated_authority_decision_count": 0,
        "canonical_identity_promotions": 0,
        "rehydrator_version": REHYDRATOR_VERSION,
    }


def compile_validated_planner_v3(plan: dict[str, Any]) -> dict[str, Any]:
    """Compile only deterministic V3 internal objects; raw payloads fail closed."""
    if not isinstance(plan, dict) or plan.get("artifact_schema_version") != VALIDATED_PLAN_VERSION:
        raise PlannerV3ContractError("compiler requires ValidatedPlannerPlanV3; raw Planner V3 is forbidden")
    rows = []
    for intent in plan.get("intents", []):
        if intent.get("artifact_schema_version") != VALIDATED_INTENT_VERSION:
            raise PlannerV3ContractError("compiler received non-validated intent")
        for relation in intent["linked_relations"]:
            if relation["validation_state"] != "STRUCTURALLY_BOUND":
                continue
            phrase = relation["linked_relation_phrase"]
            identity = {
                "compiler_version": COMPILER_VERSION, "target_sha256": plan["target_sha256"],
                "intent_id": intent["intent_id"], "blueprint_id": relation["blueprint_id"],
                "query_string": f'"{phrase.replace(chr(34), chr(92) + chr(34))}"[Title/Abstract]',
            }
            query_hash = sha256_value(identity)
            rows.append({
                "artifact_schema_version": "CompiledPlannerV3QueryV1",
                "query_id": f"v24v3q:{query_hash}",
                "query_sha256": query_hash,
                "query_string": identity["query_string"],
                "intent_id": intent["intent_id"],
                "intent_type": intent["intent_type"],
                "blueprint_id": relation["blueprint_id"],
                "execution_status": "NOT_EXECUTED_DEVELOPMENT_COUNTERFACTUAL",
            })
    rows.sort(key=lambda row: (INTENT_ORDER.index(row["intent_type"]), row["query_id"]))
    return {
        "artifact_schema_version": "PlannerV3QueryCompilationV1",
        "compiler_version": COMPILER_VERSION,
        "input_artifact_schema_version": VALIDATED_PLAN_VERSION,
        "target_id": plan["target_id"],
        "validated_plan_sha256": sha256_value(plan),
        "compiled_query_count": len(rows),
        "compiled_queries": rows,
        "compiler_accepts_raw_planner_v3": False,
        "compiler_accepts_validated_planner_v3": True,
        "network_calls": 0,
        "retrieval_calls": 0,
    }


def request_specific_provider_schema(target: dict[str, Any]) -> dict[str, Any]:
    schema = deepcopy(PLANNER_PROPOSAL_PAYLOAD_V3_SCHEMA)
    schema["properties"]["retrieval_intents"]["items"]["properties"]["intent_type"]["enum"] = \
        retrieval_intent_applicability_v2(target)["applicable_intent_types"]
    return schema


def static_provider_schema_preflight(schema: dict[str, Any] = PLANNER_PROPOSAL_PAYLOAD_V3_SCHEMA) -> dict[str, Any]:
    errors: list[str] = []
    def walk(node: Any, path: str) -> None:
        if not isinstance(node, dict):
            errors.append(f"{path}: non-object schema node")
            return
        kind = node.get("type")
        if kind == "object":
            props = node.get("properties", {})
            if node.get("additionalProperties") is not False or set(node.get("required", [])) != set(props):
                errors.append(f"{path}: object must be closed and fully required")
            if set(props) & FORBIDDEN_PROVIDER_FIELDS:
                errors.append(f"{path}: provider-owned deterministic field")
            for key, child in props.items():
                walk(child, f"{path}.{key}")
        elif kind == "array":
            walk(node.get("items"), path + "[]")
        elif kind not in ("string", ["string", "null"]):
            errors.append(f"{path}: unsupported schema type")
    walk(schema, "$root")
    return {
        "artifact_schema_version": "DeepSeekPlannerV3StaticPreflightV1",
        "passed": not errors,
        "errors": errors,
        "schema_sha256": sha256_value(schema),
        "model_generated_opaque_id_count": 0,
        "model_generated_canonical_ref_count": 0,
        "model_generated_applicability_decision_count": 0,
        "model_generated_authority_decision_count": 0,
        "remote_api_acceptance_verified": False,
        "network_calls": 0,
    }


def planner_cache_identity_v3(target: dict[str, Any], *, provider_schema: dict[str, Any] | None = None) -> str:
    frame = deterministic_target_role_frame_v1(target)
    applicability = retrieval_intent_applicability_v2(target)
    schema = provider_schema or request_specific_provider_schema(target)
    return sha256_value({
        "cache_identity_version": CACHE_VERSION,
        "provider": "deepseek", "model": "deepseek-v4-pro",
        "target_sha256": canonical_target_hash(target),
        "target_role_frame_version": ROLE_FRAME_VERSION,
        "target_role_frame_sha256": sha256_value(frame),
        "retrieval_intent_applicability_version": APPLICABILITY_VERSION,
        "retrieval_intent_applicability_sha256": sha256_value(applicability),
        "intent_semantic_transform_version": TRANSFORM_VERSION,
        "prompt_v3_sha256": sha256_value(PROMPT_TEXT_V3),
        "planner_proposal_payload_v3_schema_sha256": sha256_value(PLANNER_PROPOSAL_PAYLOAD_V3_SCHEMA),
        "provider_schema_sha256": sha256_value(schema),
        "id_allocator_version": ALLOCATOR_VERSION,
        "role_rehydrator_version": REHYDRATOR_VERSION,
        "validator_versions": [SURFACE_VERSION, "SearchAnchorCompatibilityV1_1",
                               "SearchOnlyEligibilityV1_1", "RelationBindingAssessmentV1_2"],
    })


__all__ = [
    "ALLOCATOR_VERSION", "APPLICABILITY_VERSION", "CACHE_VERSION", "COMPILER_VERSION",
    "EXPECTED_VERSION", "FORBIDDEN_PROVIDER_FIELDS", "LINKED_RELATION_PROPOSAL_V2_SCHEMA",
    "LINK_VERSION", "PAYLOAD_VERSION", "PLANNER_PROPOSAL_PAYLOAD_V3_SCHEMA",
    "PROMPT_TEXT_V3", "PROMPT_VERSION", "PlannerV3ContractError", "REHYDRATOR_VERSION",
    "ROLE_FRAME_VERSION", "SURFACE_VERSION", "TRANSFORM_VERSION", "VALIDATED_INTENT_VERSION",
    "VALIDATED_PLAN_VERSION", "allocate_artifact_id_v1", "compile_validated_planner_v3",
    "deterministic_target_role_frame_v1", "intent_semantic_transform_v1",
    "planner_cache_identity_v3", "planner_role_rehydrate_v1", "request_specific_provider_schema",
    "retrieval_intent_applicability_v2", "semantic_surface_containment_v2",
    "static_provider_schema_preflight", "validate_planner_proposal_v3",
]
