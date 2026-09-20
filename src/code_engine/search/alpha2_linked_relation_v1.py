"""Prospective, offline Search Plan v2.4 alpha2 proposal and safety contracts.

Planner text is retrieval vocabulary, never an identity or scientific assertion.
The frozen V1 proposal, receipts, and historical plans are not modified here.
"""

from __future__ import annotations

from copy import deepcopy
import re
from typing import Any

from code_engine.search.alpha1_relation_searchonly_v1 import (
    _anchors, _unsafe, normalize, semantic_eligibility,
)
from code_engine.search.planner_authority_contract_split_v1 import (
    PLANNER_PROPOSAL_PAYLOAD_V1_SCHEMA, FORBIDDEN_MODEL_AUTHORITY_FIELDS,
    _walk_keys,
)
from code_engine.search.retrieval_intent_v1 import MINIMUM_REQUIRED_DIMENSIONS

PROPOSAL_VERSION = "PlannerProposalPayloadV2"
LINK_VERSION = "LinkedRelationCandidateV1"
ANCHOR_VERSION = "SearchAnchorCompatibilityV1"
ELIGIBILITY_VERSION = "SearchOnlyEligibilityV1_1"
BINDING_VERSION = "RelationBindingAssessmentV1_1"
DIRECTIONS = ("INCREASE", "DECREASE", "ACTIVATE", "INHIBIT", "SENSITIZE", "RESIST", "REQUIRE", "RESCUE")
SUFFICIENT_ANCHORS = frozenset({"EXACT_CANONICAL_SURFACE", "AUTHORIZED_ALIAS_SURFACE", "SAFE_ORTHOGRAPHIC_VARIANT"})


class Alpha2ContractError(ValueError):
    """Invalid model proposal or deterministic alpha2 input."""


def _object(fields: dict[str, Any]) -> dict[str, Any]:
    return {"type": "object", "additionalProperties": False, "properties": fields, "required": list(fields)}


_TEXT = {"type": "string"}
_REFS = {"type": "array", "items": _TEXT}
LINKED_RELATION_CANDIDATE_V1_SCHEMA = _object({
    "subject_concept_ref": _TEXT,
    "response_concept_ref": _TEXT,
    "relation_family": _TEXT,
    "direction": {"type": "string", "enum": list(DIRECTIONS)},
    "subject_surface_candidate": _TEXT,
    "relation_surface_candidate": _TEXT,
    "response_surface_candidate": _TEXT,
    "endpoint_property_surface_candidate": _TEXT,
    "linked_relation_phrase": _TEXT,
    "conditioning_context_refs": _REFS,
    "therapy_context_refs": _REFS,
    "biological_unit_context_ref": {"type": ["string", "null"]},
    "planner_rationale": _TEXT,
})
PLANNER_PROPOSAL_PAYLOAD_V2_SCHEMA = deepcopy(PLANNER_PROPOSAL_PAYLOAD_V1_SCHEMA)
_blueprint = PLANNER_PROPOSAL_PAYLOAD_V2_SCHEMA["properties"]["retrieval_intents"]["items"]["properties"]["candidate_query_blueprints"]["items"]
_blueprint["properties"]["linked_relation_candidates"] = {
    "type": "array", "items": LINKED_RELATION_CANDIDATE_V1_SCHEMA,
}
_blueprint["required"].append("linked_relation_candidates")


def _nonempty(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise Alpha2ContractError(f"{label} must be nonempty")
    return value


def _validate_local_schema(value: Any, schema: dict[str, Any], path: str = "$root") -> None:
    """Provider-neutral local validator for the finite alpha2 JSON Schema subset."""
    types = schema.get("type")
    allowed = types if isinstance(types, list) else [types]
    matches = {"object": lambda item: isinstance(item, dict),
               "array": lambda item: isinstance(item, list),
               "string": lambda item: isinstance(item, str),
               "boolean": lambda item: isinstance(item, bool),
               "null": lambda item: item is None}
    if not any(name in matches and matches[name](value) for name in allowed):
        raise Alpha2ContractError(f"{path}: invalid JSON type")
    if "enum" in schema and value not in schema["enum"]:
        raise Alpha2ContractError(f"{path}: value outside enum")
    if isinstance(value, dict):
        fields = schema.get("properties", {})
        if schema.get("additionalProperties") is not False or set(value) != set(schema.get("required", [])):
            raise Alpha2ContractError(f"{path}: missing or extra provider field")
        for name, child in fields.items():
            _validate_local_schema(value[name], child, f"{path}.{name}")
    elif isinstance(value, list):
        if "items" not in schema:
            raise Alpha2ContractError(f"{path}: array schema lacks items")
        for index, item in enumerate(value):
            _validate_local_schema(item, schema["items"], f"{path}[{index}]")


def _compact(value: str) -> str:
    return re.sub(r"[^a-z0-9]", "", normalize(value))


def _contains_surface(phrase: str, surface: str) -> bool:
    """Whole lexical surface, preserving alpha/beta and numeric suffixes."""
    tokens = normalize(surface).split()
    if not tokens:
        return False
    joined = "".join(tokens)
    phrase_tokens = normalize(phrase).split()
    if len(tokens) == 1:
        return any(token == tokens[0] or _compact(token) == joined for token in phrase_tokens)
    return any(phrase_tokens[i:i + len(tokens)] == tokens for i in range(len(phrase_tokens) - len(tokens) + 1)) or any(
        _compact(token) == joined for token in phrase_tokens
    )


def search_anchor_compatibility(
    surface: str, canonical_surfaces: list[str], *, authorized_aliases: dict[str, str] | None = None,
) -> str:
    """Search-only matching; this function never grants scientific identity."""
    if not isinstance(surface, str) or _unsafe(surface):
        return "INCOMPATIBLE"
    if not canonical_surfaces:
        return "UNRESOLVED"
    if authorized_aliases is not None and not isinstance(authorized_aliases, dict):
        raise Alpha2ContractError("authorized aliases require a deterministic reference map")
    normalized = normalize(surface)
    if any(normalized == normalize(anchor) for anchor in canonical_surfaces):
        return "EXACT_CANONICAL_SURFACE"
    if any(normalized == normalize(alias) and isinstance(reference, str)
           and reference.startswith(("ScientificPropositionTargetV1#", "DeterministicAuthorityManifestV1#"))
           for alias, reference in (authorized_aliases or {}).items()):
        return "AUTHORIZED_ALIAS_SURFACE"
    if any(_compact(surface) == _compact(anchor) and _compact(anchor) for anchor in canonical_surfaces):
        return "SAFE_ORTHOGRAPHIC_VARIANT"
    if any(_contains_surface(anchor, surface) or _contains_surface(surface, anchor) for anchor in canonical_surfaces):
        return "UNDER_SPECIFIED"
    return "UNRESOLVED"


def _relation_applicable(intent: dict[str, Any]) -> bool:
    return intent["applicability"] == "APPLICABLE" and "relation" in (
        intent["required_dimensions"] + intent["optional_dimensions"]
    )


def validate_planner_proposal_v2(payload: dict[str, Any], *, target: dict[str, Any]) -> dict[str, Any]:
    """Validate model-only V2 projection and references; do not infer truth."""
    _validate_local_schema(payload, PLANNER_PROPOSAL_PAYLOAD_V2_SCHEMA)
    forbidden = FORBIDDEN_MODEL_AUTHORITY_FIELDS | {
        "canonical_target", "target_id", "artifact_schema_version", "cache_identity",
        "coverage", "compiler_result", "validator_decision", "authoritative_proposal_class",
    }
    if _walk_keys(payload) & forbidden:
        raise Alpha2ContractError("model payload contains deterministic or authority-owned fields")
    if not payload["retrieval_intents"]:
        raise Alpha2ContractError("at least one intent required")
    if target.get("artifact_schema_version") != "ScientificPropositionTargetV1":
        raise Alpha2ContractError("immutable ScientificPropositionTargetV1 required")
    seen: set[str] = set()
    for intent in payload["retrieval_intents"]:
        _nonempty(intent["intent_id"], "intent_id")
        if intent["intent_id"] in seen:
            raise Alpha2ContractError("duplicate intent ID")
        seen.add(intent["intent_id"])
        required = intent["required_dimensions"]
        optional = intent["optional_dimensions"]
        if (len(required) != len(set(required)) or len(optional) != len(set(optional))
                or set(required) & set(optional)
                or not set(MINIMUM_REQUIRED_DIMENSIONS[intent["intent_type"]]) <= set(required)):
            raise Alpha2ContractError("intent dimension contract violated")
        if intent["biological_unit_context"]["separate_from_entity_identity"] is not True:
            raise Alpha2ContractError("biological unit must stay separate from identity")
        concepts = {c["concept_id"]: c for c in intent["search_concepts"]}
        if len(concepts) != len(intent["search_concepts"]):
            raise Alpha2ContractError("duplicate concept ID")
        for concept in concepts.values():
            _nonempty(concept["concept_id"], "concept_id")
            if concept["concept_id"] in seen:
                raise Alpha2ContractError("duplicate concept ID across intents")
            seen.add(concept["concept_id"])
            dimension = concept["concept_type"]
            anchors = _anchors(target, dimension)
            proposed = concept["canonical_anchor"]
            values = proposed if isinstance(proposed, list) else [proposed]
            if isinstance(proposed, list) and not proposed:
                raise Alpha2ContractError("canonical anchor array is empty")
            if proposed is not None and any(
                value and search_anchor_compatibility(value, anchors) not in SUFFICIENT_ANCHORS
                for value in values
            ):
                raise Alpha2ContractError("model concept canonical anchor differs from immutable target")
            for term in concept["proposed_terms"]:
                _nonempty(term["term"], "proposed term")
                term_id = _nonempty(term["term_id"], "term_id")
                if term_id in seen:
                    raise Alpha2ContractError("duplicate term ID")
                seen.add(term_id)
        for blueprint in intent["candidate_query_blueprints"]:
            blueprint_id = _nonempty(blueprint["blueprint_id"], "blueprint_id")
            if blueprint_id in seen:
                raise Alpha2ContractError("duplicate blueprint ID")
            seen.add(blueprint_id)
            refs = blueprint["concept_ids"]
            if not refs or len(refs) != len(set(refs)) or not set(refs) <= concepts.keys():
                raise Alpha2ContractError("blueprint has unknown or duplicate concept reference")
            links = blueprint["linked_relation_candidates"]
            if _relation_applicable(intent) and not links:
                raise Alpha2ContractError("relation-applicable blueprint requires linked candidate")
            for link in links:
                for name in ("subject_concept_ref", "response_concept_ref"):
                    if link[name] not in refs:
                        raise Alpha2ContractError(f"unknown {name}")
                if concepts[link["subject_concept_ref"]]["concept_type"] != "subject":
                    raise Alpha2ContractError("subject ref has wrong role")
                if concepts[link["response_concept_ref"]]["concept_type"] != "object_measurement_target":
                    raise Alpha2ContractError("response ref has wrong role")
                for name, dimension in (("conditioning_context_refs", "nested_treatment"),
                                        ("therapy_context_refs", "therapy")):
                    if any(ref not in refs or concepts[ref]["concept_type"] != dimension for ref in link[name]):
                        raise Alpha2ContractError(f"invalid {name}")
                unit = link["biological_unit_context_ref"]
                if unit is not None and (unit not in refs or concepts[unit]["concept_type"] != "biological_unit"):
                    raise Alpha2ContractError("invalid biological unit ref")
                for name in ("relation_family", "subject_surface_candidate", "relation_surface_candidate",
                             "response_surface_candidate", "endpoint_property_surface_candidate",
                             "linked_relation_phrase", "planner_rationale"):
                    _nonempty(link[name], name)
    return payload


def search_only_eligibility_v1_1(term: str, dimension: str, target: dict[str, Any]) -> tuple[str, str]:
    """Alpha1 default-deny plus exact full-symbol orthography; no identity promotion."""
    if _unsafe(term):
        return "REJECTED", "LEXICAL_SAFETY_REJECTION"
    state, rule = semantic_eligibility(term, dimension, target)
    if state == "ELIGIBLE":
        return "SEARCH_ONLY_EXPANSION", rule
    if dimension in {"subject", "object_measurement_target", "therapy", "disease", "genotype",
                     "biological_unit", "nested_treatment", "endpoint_property"} and any(
        search_anchor_compatibility(term, [anchor]) == "SAFE_ORTHOGRAPHIC_VARIANT"
        for anchor in _anchors(target, dimension)
    ):
        return "SEARCH_ONLY_EXPANSION", "FULL_CANONICAL_SURFACE_ORTHOGRAPHY"
    return "UNRESOLVED", "NO_GENERIC_SEMANTIC_ELIGIBILITY_RULE"


def _target_direction(target: dict[str, Any]) -> str | None:
    text = normalize(" ".join(str(target.get(key) or "") for key in (
        "canonical_relation_family", "relation_family", "canonical_proposition_orientation")))
    families = (
        ("sensit", "SENSITIZE"), ("resistan", "RESIST"), ("rescu", "RESCUE"),
        ("inhibit", "INHIBIT"), ("suppress", "DECREASE"), ("decreas", "DECREASE"),
        ("reduc", "DECREASE"), ("activat", "ACTIVATE"), ("increas", "INCREASE"),
        ("induc", "INCREASE"), ("requir", "REQUIRE"),
    )
    return next((direction for stem, direction in families if stem in text), None)


def _surface_direction(surface: str) -> str | None:
    text = normalize(surface)
    patterns = (
        (r"sensitiv|sensitiz", "SENSITIZE"), (r"resistan|resistanc", "RESIST"),
        (r"rescu|restor|revers", "RESCUE"), (r"requir|necess", "REQUIRE"),
        (r"inhibit|inhibits|block", "INHIBIT"),
        (r"suppress|decreas|reduc|attenuat", "DECREASE"),
        (r"activat", "ACTIVATE"), (r"increas|enhanc|promot|induc|elevat", "INCREASE"),
    )
    return next((direction for pattern, direction in patterns if re.search(pattern, text)), None)


def assess_linked_relation_v1_1(link: dict[str, Any], target: dict[str, Any], *,
                                authorized_aliases: dict[str, dict[str, str]] | None = None,
                                intent_type: str = "DIRECT_PERTURBATION") -> dict[str, Any]:
    """Conservative structural binding; missing authority never becomes represented."""
    aliases = authorized_aliases or {}
    phrase = link["linked_relation_phrase"]
    checks: dict[str, bool] = {}
    for key, dimension in (("subject", "subject"), ("response", "object_measurement_target"),
                           ("endpoint", "endpoint_property")):
        surface = link[{"subject": "subject_surface_candidate", "response": "response_surface_candidate",
                        "endpoint": "endpoint_property_surface_candidate"}[key]]
        checks[key] = (search_anchor_compatibility(surface, _anchors(target, dimension),
                       authorized_aliases=aliases.get(dimension)) in SUFFICIENT_ANCHORS
                       and _contains_surface(phrase, surface))
    checks["relation_family"] = normalize(link["relation_family"]) == normalize(
        target.get("relation_family") or target.get("canonical_relation_family") or "")
    expected = _target_direction(target)
    if intent_type == "RESCUE":
        expected = "RESCUE"
    elif intent_type == "NECESSITY":
        expected = "REQUIRE"
    elif intent_type == "INVERSE_PERTURBATION":
        expected = {"INCREASE": "DECREASE", "DECREASE": "INCREASE",
                    "ACTIVATE": "INHIBIT", "INHIBIT": "ACTIVATE",
                    "SENSITIZE": "RESIST", "RESIST": "SENSITIZE"}.get(expected)
    surface_direction = _surface_direction(link["relation_surface_candidate"])
    compatible_surfaces = {"INCREASE": {"INCREASE", "ACTIVATE"},
                           "DECREASE": {"DECREASE", "INHIBIT"},
                           "ACTIVATE": {"ACTIVATE", "INCREASE"},
                           "INHIBIT": {"INHIBIT", "DECREASE"}}
    checks["direction"] = (expected is not None and link["direction"] == expected
                           and surface_direction in compatible_surfaces.get(expected, {expected}))
    checks["relation_surface"] = _contains_surface(phrase, link["relation_surface_candidate"])
    for key, dimension, refs in (("nested_treatment", "nested_treatment", "conditioning_context_refs"),
                                 ("therapy", "therapy", "therapy_context_refs")):
        required = _anchors(target, dimension)
        checks[key] = not required or bool(link[refs]) and any(
            _contains_surface(phrase, anchor) for anchor in required
        )
    checks["biological_unit"] = not _anchors(target, "biological_unit") or bool(
        link["biological_unit_context_ref"]
    )
    return {"artifact_schema_version": BINDING_VERSION,
            "state": "STRUCTURALLY_BOUND" if all(checks.values()) else "UNDERREPRESENTED",
            "checks": checks, "canonical_identity_promoted": False}


def linked_relation_search_only_eligibility(link: dict[str, Any], target: dict[str, Any], *,
                                            intent_type: str = "DIRECT_PERTURBATION",
                                            authorized_aliases: dict[str, dict[str, str]] | None = None) -> tuple[str, str]:
    """A V2 linked phrase is search-only only after complete structural binding."""
    if _unsafe(link["linked_relation_phrase"]):
        return "REJECTED", "LEXICAL_SAFETY_REJECTION"
    assessment = assess_linked_relation_v1_1(link, target, intent_type=intent_type,
                                             authorized_aliases=authorized_aliases)
    if assessment["state"] == "STRUCTURALLY_BOUND":
        return "SEARCH_ONLY_EXPANSION", "LINKED_RELATION_ALL_MANDATORY_ROLES_BOUND"
    return "UNRESOLVED", "LINKED_RELATION_MANDATORY_ROLE_UNDERREPRESENTED"
