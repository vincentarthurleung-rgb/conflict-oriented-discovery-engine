"""Offline authority-split contracts for Search Plan v2.4 development.

The model proposes retrieval semantics only.  Deterministic code owns term
classification, authority references, coverage, request identity, and compiler
inputs.  This module performs no provider, network, or retrieval access.
"""

from __future__ import annotations

from copy import deepcopy
import hashlib
import json
import re
from typing import Any

from code_engine.search.openai_structured_output_schema_renderer_v1 import (
    validate_scientific_instance,
)
from code_engine.search.proposition_aware_query_planner_v1 import (
    PLAN_SCHEMA_VERSION,
    canonical_bytes,
    canonical_target_hash,
    sha256_value,
)
from code_engine.search.retrieval_intent_v1 import (
    DIMENSION_ORDER, INTENT_ORDER, MINIMUM_REQUIRED_DIMENSIONS,
)
from code_engine.search.retrieval_plan_coverage_v1 import COVERAGE_VERSION, validate_blueprint_coverage


PROPOSAL_VERSION = "PlannerProposalPayloadV1"
RECEIPT_VERSION = "SearchTermValidationReceiptV1"
VALIDATED_PLAN_VERSION = "ValidatedPropositionAwareSearchPlanV1"
AUTHORITY_SPLIT_VALIDATOR_VERSION = "SearchTermValidatorV1AuthoritySplit"
AUTHORITY_SPLIT_COVERAGE_VERSION = "DeterministicRetrievalPlanCoverageV1"
AUTHORITY_SPLIT_CACHE_VERSION = "PlannerAuthoritySplitCacheIdentityV1"
CLASSIFICATIONS = (
    "AUTHORIZED_EQUIVALENT", "SEARCH_ONLY_EXPANSION", "UNRESOLVED", "REJECTED",
)
USABLE_CLASSIFICATIONS = frozenset({"AUTHORIZED_EQUIVALENT", "SEARCH_ONLY_EXPANSION"})
FORBIDDEN_MODEL_AUTHORITY_FIELDS = frozenset({
    "authority_reference", "proposal_class", "deterministic_classification",
    "validation_reason", "validator_version", "authority_state_hash",
})


class AuthoritySplitContractError(ValueError):
    """Raised when an authority-split artifact violates its frozen boundary."""


def _object(properties: dict[str, Any]) -> dict[str, Any]:
    return {
        "type": "object",
        "additionalProperties": False,
        "properties": properties,
        "required": list(properties),
    }


TEXT = {"type": "string"}
NULLABLE_TEXT = {"type": ["string", "null"]}
NULLABLE_TEXT_OR_ARRAY = {"type": ["string", "array", "null"], "items": TEXT}
TEXT_ARRAY = {"type": "array", "items": TEXT}

TERM_PROPOSAL_SCHEMA = _object({
    "term_id": TEXT,
    "term": TEXT,
})

CONCEPT_PROPOSAL_SCHEMA = _object({
    "concept_id": TEXT,
    "concept_type": {"type": "string", "enum": list(DIMENSION_ORDER)},
    "canonical_anchor": NULLABLE_TEXT_OR_ARRAY,
    "proposed_terms": {"type": "array", "items": TERM_PROPOSAL_SCHEMA},
})

BLUEPRINT_PROPOSAL_SCHEMA = _object({
    "blueprint_id": TEXT,
    "concept_ids": TEXT_ARRAY,
})

INTENT_PROPOSAL_SCHEMA = _object({
    "intent_id": TEXT,
    "intent_type": {"type": "string", "enum": list(INTENT_ORDER)},
    "applicability": {"type": "string", "enum": ["APPLICABLE", "NOT_APPLICABLE"]},
    "applicability_rationale": TEXT,
    "scientific_rationale": TEXT,
    "required_dimensions": {"type": "array", "items": {"type": "string", "enum": list(DIMENSION_ORDER)}},
    "optional_dimensions": {"type": "array", "items": {"type": "string", "enum": list(DIMENSION_ORDER)}},
    "biological_unit_context": _object({
        "target_value": NULLABLE_TEXT,
        "planning_state": {"type": "string", "enum": ["PRESENT", "ABSENT", "UNRESOLVED", "NOT_APPLICABLE"]},
        "separate_from_entity_identity": {"type": "boolean", "enum": [True]},
    }),
    "search_concepts": {"type": "array", "items": CONCEPT_PROPOSAL_SCHEMA},
    "candidate_query_blueprints": {"type": "array", "items": BLUEPRINT_PROPOSAL_SCHEMA},
})

PLANNER_PROPOSAL_PAYLOAD_V1_SCHEMA = _object({
    "retrieval_intents": {"type": "array", "items": INTENT_PROPOSAL_SCHEMA},
})

TERM_VALIDATION_RECEIPT_V1_SCHEMA = _object({
    "artifact_schema_version": {"type": "string", "enum": [RECEIPT_VERSION]},
    "term_id": TEXT,
    "term": TEXT,
    "concept_id": TEXT,
    "concept_type": {"type": "string", "enum": list(DIMENSION_ORDER)},
    "deterministic_classification": {"type": "string", "enum": list(CLASSIFICATIONS)},
    "authority_reference": NULLABLE_TEXT,
    "validation_reason": TEXT,
    "validator_version": {"type": "string", "enum": [AUTHORITY_SPLIT_VALIDATOR_VERSION]},
    "input_term_hash": TEXT,
    "authority_state_hash": TEXT,
    "receipt_sha256": TEXT,
})

COVERAGE_ROW_SCHEMA = _object({
    "dimension": {"type": "string", "enum": list(DIMENSION_ORDER)},
    "coverage_state": {"type": "string", "enum": ["REPRESENTED", "UNDERREPRESENTED", "OMITTED", "NOT_APPLICABLE"]},
    "source_concept_ids": TEXT_ARRAY,
    "query_term_ids": TEXT_ARRAY,
    "rationale": TEXT,
})

COVERAGE_RECORD_SCHEMA = _object({
    "intent_id": TEXT,
    "blueprint_id": TEXT,
    "dimension_coverage": {"type": "array", "items": COVERAGE_ROW_SCHEMA},
    "relation_representation_state": {
        "type": "string", "enum": ["REPRESENTED", "RELATION_UNDERREPRESENTED", "NOT_APPLICABLE"],
    },
})

VALIDATED_PROPOSITION_AWARE_SEARCH_PLAN_V1_SCHEMA = _object({
    "artifact_schema_version": {"type": "string", "enum": [VALIDATED_PLAN_VERSION]},
    "request_provenance": _object({
        "request_sha256": TEXT,
        "preserved_request_reference": TEXT,
    }),
    "target_id": TEXT,
    "canonical_proposition": _object({
        "schema_version": {"type": "string", "enum": ["ScientificPropositionTargetV1"]},
        "target_sha256": TEXT,
        "target_payload": {"type": "object"},
    }),
    "planner_config_sha256": TEXT,
    "planner_prompt_template_version": TEXT,
    "planner_cache_key_sha256": TEXT,
    "planner_proposal_payload": PLANNER_PROPOSAL_PAYLOAD_V1_SCHEMA,
    "planner_proposal_sha256": TEXT,
    "term_validation_receipts": {"type": "array", "items": TERM_VALIDATION_RECEIPT_V1_SCHEMA},
    "term_validation_receipts_sha256": TEXT,
    "retrieval_plan_coverage": {"type": "array", "items": COVERAGE_RECORD_SCHEMA},
    "retrieval_plan_coverage_sha256": TEXT,
    "validated_before_compilation": {"type": "boolean", "enum": [True]},
})


def _nonempty(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise AuthoritySplitContractError(f"{label} must be a non-empty string")
    return value


def _sha(value: Any, label: str) -> str:
    text = _nonempty(value, label)
    if re.fullmatch(r"[0-9a-f]{64}", text) is None:
        raise AuthoritySplitContractError(f"{label} must be a lowercase SHA-256")
    return text


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


def project_frozen_provider_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """Remove all model-supplied authority and coverage assertions."""
    if set(payload) != {"retrieval_intents"} or not isinstance(payload["retrieval_intents"], list):
        raise AuthoritySplitContractError("frozen provider payload root is not the expected projection")
    intents = []
    for intent in payload["retrieval_intents"]:
        concepts = []
        for concept in intent["search_concepts"]:
            concepts.append({
                "concept_id": concept["concept_id"],
                "concept_type": concept["concept_type"],
                "canonical_anchor": concept["canonical_value"],
                "proposed_terms": [
                    {"term_id": term["term_id"], "term": term["term"]}
                    for term in concept["proposed_terms"]
                ],
            })
        blueprints = [
            {"blueprint_id": row["blueprint_id"], "concept_ids": deepcopy(row["concept_ids"])}
            for row in intent["candidate_query_blueprints"]
        ]
        intents.append({
            "intent_id": intent["intent_id"],
            "intent_type": intent["intent_type"],
            "applicability": intent["applicability"],
            "applicability_rationale": intent["applicability_rationale"],
            "scientific_rationale": intent["scientific_rationale"],
            "required_dimensions": deepcopy(intent["required_dimensions"]),
            "optional_dimensions": deepcopy(intent["optional_dimensions"]),
            "biological_unit_context": deepcopy(intent["biological_unit_context"]),
            "search_concepts": concepts,
            "candidate_query_blueprints": blueprints,
        })
    result = {"retrieval_intents": intents}
    if _walk_keys(result) & FORBIDDEN_MODEL_AUTHORITY_FIELDS:
        raise AuthoritySplitContractError("authority-owned field survived projection")
    return result


def validate_planner_proposal(payload: dict[str, Any], *, target: dict[str, Any]) -> dict[str, Any]:
    """Validate semantic proposal structure without granting authority."""
    try:
        validate_scientific_instance(payload, PLANNER_PROPOSAL_PAYLOAD_V1_SCHEMA)
    except Exception as exc:
        raise AuthoritySplitContractError(str(exc)) from exc
    if _walk_keys(payload) & FORBIDDEN_MODEL_AUTHORITY_FIELDS:
        raise AuthoritySplitContractError("planner proposal contains an authority-owned field")
    intents = payload["retrieval_intents"]
    if not intents:
        raise AuthoritySplitContractError("at least one retrieval intent is required")
    global_ids: set[str] = set()
    for intent_index, intent in enumerate(intents):
        label = f"retrieval_intents[{intent_index}]"
        intent_id = _nonempty(intent["intent_id"], f"{label}.intent_id")
        if intent_id in global_ids:
            raise AuthoritySplitContractError("duplicate intent id")
        global_ids.add(intent_id)
        _nonempty(intent["applicability_rationale"], f"{label}.applicability_rationale")
        _nonempty(intent["scientific_rationale"], f"{label}.scientific_rationale")
        required = intent["required_dimensions"]
        optional = intent["optional_dimensions"]
        if len(required) != len(set(required)) or len(optional) != len(set(optional)):
            raise AuthoritySplitContractError("intent dimension lists must be unique")
        if set(required) & set(optional):
            raise AuthoritySplitContractError("required and optional dimensions overlap")
        if not set(MINIMUM_REQUIRED_DIMENSIONS[intent["intent_type"]]).issubset(required):
            raise AuthoritySplitContractError("intent omits minimum required dimensions")
        if intent["biological_unit_context"]["separate_from_entity_identity"] is not True:
            raise AuthoritySplitContractError("biological unit must remain separate from entity identity")
        concept_ids: set[str] = set()
        term_ids: set[str] = set()
        for concept_index, concept in enumerate(intent["search_concepts"]):
            concept_id = _nonempty(concept["concept_id"], f"{label}.search_concepts[{concept_index}].concept_id")
            if concept_id in global_ids:
                raise AuthoritySplitContractError("duplicate concept id")
            global_ids.add(concept_id)
            concept_ids.add(concept_id)
            if isinstance(concept["canonical_anchor"], str):
                _nonempty(concept["canonical_anchor"], "canonical_anchor")
            elif isinstance(concept["canonical_anchor"], list):
                if not concept["canonical_anchor"]:
                    raise AuthoritySplitContractError("canonical_anchor array must not be empty")
                for value in concept["canonical_anchor"]:
                    _nonempty(value, "canonical_anchor item")
            for term in concept["proposed_terms"]:
                term_id = _nonempty(term["term_id"], "term_id")
                _nonempty(term["term"], "term")
                if term_id in global_ids:
                    raise AuthoritySplitContractError("duplicate term id")
                global_ids.add(term_id)
                term_ids.add(term_id)
        for blueprint in intent["candidate_query_blueprints"]:
            blueprint_id = _nonempty(blueprint["blueprint_id"], "blueprint_id")
            if blueprint_id in global_ids:
                raise AuthoritySplitContractError("duplicate blueprint id")
            global_ids.add(blueprint_id)
            if not blueprint["concept_ids"] or not set(blueprint["concept_ids"]).issubset(concept_ids):
                raise AuthoritySplitContractError("blueprint references an unknown or empty concept set")
    return payload


def _normalize(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", str(value).casefold()).strip()


def _unsafe(value: str) -> bool:
    folded = str(value).casefold()
    return (
        not str(value).strip() or len(str(value)) > 240
        or any(ord(char) < 32 for char in str(value))
        or any(token in folded for token in ("http://", "https://", "<script", "drop table"))
        or bool(re.search(r"\b(?:AND|OR|NOT)\b|\[[^]]+\]", str(value)))
    )


def _target_authorities(target: dict[str, Any]) -> dict[tuple[str, str], str]:
    """Build generic exact-match authority solely from immutable target fields."""
    records: list[tuple[str, str, str]] = []

    def add(concept_type: str, pointer: str, value: Any) -> None:
        values = value if isinstance(value, list) else [value]
        for item in values:
            if str(item or "").strip():
                records.append((concept_type, str(item), f"ScientificPropositionTargetV1#{pointer}"))

    for field in ("subject", "canonical_subject", "subject_intervention"):
        add("subject", f"/{field}", target.get(field))
    for field in ("relation_family", "canonical_relation_family"):
        add("relation", f"/{field}", target.get(field))
    for field in ("object", "measurement_target"):
        add("object_measurement_target", f"/{field}", target.get(field))
    add("endpoint_property", "/measurement_property_endpoint", target.get("measurement_property_endpoint"))
    add("endpoint_property", "/acceptable_endpoint_evidence", target.get("acceptable_endpoint_evidence"))
    add("therapy", "/therapy", target.get("therapy"))
    add("direction", "/canonical_proposition_orientation", target.get("canonical_proposition_orientation"))
    add("evidence_mode", "/required_evidence_mode", target.get("required_evidence_mode"))
    contexts = target.get("context_qualifier_dimensions") or {}
    mapping = {
        "biological_unit": "biological_unit", "therapy": "therapy", "disease": "disease",
        "genotype": "genotype", "nested_treatment": "nested_treatment", "treatment": "nested_treatment",
    }
    for key, concept_type in mapping.items():
        add(concept_type, f"/context_qualifier_dimensions/{key}", contexts.get(key))
    result: dict[tuple[str, str], str] = {}
    for concept_type, term, reference in records:
        normalized = _normalize(term)
        if normalized:
            result.setdefault((concept_type, normalized), reference)
    return result


def validate_proposal_terms(
    proposal: dict[str, Any], *, target: dict[str, Any], authorities: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """Issue one deterministic, hash-bound receipt for every proposed term."""
    validate_planner_proposal(proposal, target=target)
    authority_manifest = authorities or {"records": []}
    authority = _target_authorities(target)
    for record in authority_manifest.get("records", []):
        concept_type = record.get("concept_type")
        reference = _nonempty(record.get("authority_reference"), "authority_reference")
        if concept_type not in DIMENSION_ORDER:
            raise AuthoritySplitContractError("authority record has invalid concept type")
        for term in record.get("terms", []):
            normalized = _normalize(term)
            if not normalized:
                raise AuthoritySplitContractError("authority record contains an empty term")
            key = (concept_type, normalized)
            if key in authority and authority[key] != reference:
                raise AuthoritySplitContractError("ambiguous deterministic authority state")
            authority[key] = reference
    authority_state_hash = sha256_value({
        "canonical_target_sha256": canonical_target_hash(target),
        "external_authority_manifest": authority_manifest,
    })
    receipts = []
    for intent in proposal["retrieval_intents"]:
        for concept in intent["search_concepts"]:
            for term in concept["proposed_terms"]:
                normalized = _normalize(term["term"])
                reference = authority.get((concept["concept_type"], normalized))
                if _unsafe(term["term"]):
                    classification, reference, reason = "REJECTED", None, "generic lexical-safety rejection"
                elif not normalized:
                    classification, reference, reason = (
                        "UNRESOLVED", None, "term has no deterministic alphanumeric lexical identity",
                    )
                elif reference:
                    classification, reason = "AUTHORIZED_EQUIVALENT", "exact deterministic immutable-authority match"
                else:
                    classification, reference, reason = (
                        "SEARCH_ONLY_EXPANSION", None,
                        "well-formed retrieval vocabulary without deterministic equivalence authority",
                    )
                material = {
                    "artifact_schema_version": RECEIPT_VERSION,
                    "term_id": term["term_id"], "term": term["term"],
                    "concept_id": concept["concept_id"], "concept_type": concept["concept_type"],
                    "deterministic_classification": classification,
                    "authority_reference": reference, "validation_reason": reason,
                    "validator_version": AUTHORITY_SPLIT_VALIDATOR_VERSION,
                    "input_term_hash": sha256_value({
                        "term_id": term["term_id"], "term": term["term"],
                        "concept_id": concept["concept_id"], "concept_type": concept["concept_type"],
                    }),
                    "authority_state_hash": authority_state_hash,
                }
                material["receipt_sha256"] = sha256_value(material)
                validate_scientific_instance(material, TERM_VALIDATION_RECEIPT_V1_SCHEMA)
                receipts.append(material)
    return receipts


def deterministic_coverage(
    proposal: dict[str, Any], receipts: list[dict[str, Any]], *, target: dict[str, Any],
) -> list[dict[str, Any]]:
    """Compute coverage from selected concepts and deterministic usable terms."""
    validate_planner_proposal(proposal, target=target)
    receipt_by_term = {row["term_id"]: row for row in receipts}
    records = []
    for intent in proposal["retrieval_intents"]:
        concepts = {row["concept_id"]: row for row in intent["search_concepts"]}
        applicable = set(intent["required_dimensions"]) | set(intent["optional_dimensions"])
        for blueprint in intent["candidate_query_blueprints"]:
            selected = [concepts[concept_id] for concept_id in blueprint["concept_ids"]]
            rows = []
            for dimension in DIMENSION_ORDER:
                source = [row for row in selected if row["concept_type"] == dimension]
                source_ids = [row["concept_id"] for row in source]
                term_ids = [
                    term["term_id"] for concept in source for term in concept["proposed_terms"]
                    if receipt_by_term[term["term_id"]]["deterministic_classification"] in USABLE_CLASSIFICATIONS
                ]
                if dimension not in applicable:
                    state, rationale = "NOT_APPLICABLE", "dimension is not required or optional for this intent"
                    source_ids, term_ids = [], []
                elif source_ids and term_ids:
                    state, rationale = "REPRESENTED", "selected concept has deterministically usable retrieval terms"
                elif source_ids:
                    state, rationale = "UNDERREPRESENTED", "selected concept has no deterministically usable retrieval term"
                else:
                    state, rationale = "OMITTED", "no selected concept represents this applicable dimension"
                rows.append({
                    "dimension": dimension, "coverage_state": state,
                    "source_concept_ids": source_ids, "query_term_ids": term_ids,
                    "rationale": rationale,
                })
            relation = rows[DIMENSION_ORDER.index("relation")]
            if not str(target.get("relation_family") or "").strip():
                relation_state = "NOT_APPLICABLE"
            elif relation["coverage_state"] == "REPRESENTED":
                relation_state = "REPRESENTED"
            else:
                relation_state = "RELATION_UNDERREPRESENTED"
            legacy_blueprint = {
                "dimension_coverage": rows,
                "relation_representation_state": relation_state,
            }
            validate_blueprint_coverage(legacy_blueprint, target)
            records.append({
                "intent_id": intent["intent_id"], "blueprint_id": blueprint["blueprint_id"],
                "dimension_coverage": rows, "relation_representation_state": relation_state,
            })
    return records


def authority_split_cache_key(
    *, target_sha256: str, planner_config_sha256: str, prompt_sha256: str,
    proposal_schema_sha256: str, validator_version: str = AUTHORITY_SPLIT_VALIDATOR_VERSION,
    validated_plan_schema_sha256: str,
) -> str:
    material = {
        "cache_identity_version": AUTHORITY_SPLIT_CACHE_VERSION,
        "target_sha256": _sha(target_sha256, "target_sha256"),
        "planner_config_sha256": _sha(planner_config_sha256, "planner_config_sha256"),
        "prompt_sha256": _sha(prompt_sha256, "prompt_sha256"),
        "proposal_schema_sha256": _sha(proposal_schema_sha256, "proposal_schema_sha256"),
        "validator_version": _nonempty(validator_version, "validator_version"),
        "validated_plan_schema_sha256": _sha(validated_plan_schema_sha256, "validated_plan_schema_sha256"),
    }
    return sha256_value(material)


def assemble_validated_plan(
    proposal: dict[str, Any], receipts: list[dict[str, Any]], coverage: list[dict[str, Any]],
    *, target: dict[str, Any], request_reference: str, planner_config_sha256: str,
    planner_prompt_template_version: str, planner_cache_key_sha256: str,
) -> dict[str, Any]:
    validate_planner_proposal(proposal, target=target)
    expected_receipts = validate_proposal_terms(proposal, target=target)
    if canonical_bytes(receipts) != canonical_bytes(expected_receipts):
        raise AuthoritySplitContractError("term receipts do not match deterministic validation")
    expected_coverage = deterministic_coverage(proposal, receipts, target=target)
    if canonical_bytes(coverage) != canonical_bytes(expected_coverage):
        raise AuthoritySplitContractError("coverage does not match deterministic analysis")
    target_sha = canonical_target_hash(target)
    result = {
        "artifact_schema_version": VALIDATED_PLAN_VERSION,
        "request_provenance": {
            "request_sha256": hashlib.sha256(request_reference.encode("utf-8")).hexdigest(),
            "preserved_request_reference": request_reference,
        },
        "target_id": target["scientific_proposition_target_id"],
        "canonical_proposition": {
            "schema_version": "ScientificPropositionTargetV1",
            "target_sha256": target_sha,
            "target_payload": deepcopy(target),
        },
        "planner_config_sha256": _sha(planner_config_sha256, "planner_config_sha256"),
        "planner_prompt_template_version": _nonempty(
            planner_prompt_template_version, "planner_prompt_template_version"),
        "planner_cache_key_sha256": _sha(planner_cache_key_sha256, "planner_cache_key_sha256"),
        "planner_proposal_payload": deepcopy(proposal),
        "planner_proposal_sha256": sha256_value(proposal),
        "term_validation_receipts": deepcopy(receipts),
        "term_validation_receipts_sha256": sha256_value(receipts),
        "retrieval_plan_coverage": deepcopy(coverage),
        "retrieval_plan_coverage_sha256": sha256_value(coverage),
        "validated_before_compilation": True,
    }
    validate_validated_plan(result, expected_target=target)
    return result


def validate_validated_plan(
    plan: dict[str, Any], *, expected_target: dict[str, Any] | None = None,
) -> dict[str, Any]:
    try:
        validate_scientific_instance(plan, VALIDATED_PROPOSITION_AWARE_SEARCH_PLAN_V1_SCHEMA)
    except Exception as exc:
        raise AuthoritySplitContractError(str(exc)) from exc
    target = plan["canonical_proposition"]["target_payload"]
    if canonical_target_hash(target) != plan["canonical_proposition"]["target_sha256"]:
        raise AuthoritySplitContractError("canonical target hash mismatch")
    if expected_target is not None and canonical_bytes(target) != canonical_bytes(expected_target):
        raise AuthoritySplitContractError("validated plan changed canonical target")
    if plan["target_id"] != target["scientific_proposition_target_id"]:
        raise AuthoritySplitContractError("validated plan target id mismatch")
    proposal = plan["planner_proposal_payload"]
    validate_planner_proposal(proposal, target=target)
    if sha256_value(proposal) != plan["planner_proposal_sha256"]:
        raise AuthoritySplitContractError("proposal hash mismatch")
    receipts = plan["term_validation_receipts"]
    if sha256_value(receipts) != plan["term_validation_receipts_sha256"]:
        raise AuthoritySplitContractError("term receipt corpus hash mismatch")
    if canonical_bytes(receipts) != canonical_bytes(validate_proposal_terms(proposal, target=target)):
        raise AuthoritySplitContractError("term receipts are not deterministically reproducible")
    coverage = plan["retrieval_plan_coverage"]
    if sha256_value(coverage) != plan["retrieval_plan_coverage_sha256"]:
        raise AuthoritySplitContractError("coverage hash mismatch")
    if canonical_bytes(coverage) != canonical_bytes(deterministic_coverage(proposal, receipts, target=target)):
        raise AuthoritySplitContractError("coverage is not deterministically reproducible")
    return plan


def materialize_legacy_compiler_inputs(plan: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    """Create a legacy compiler representation only after split-plan validation."""
    validate_validated_plan(plan)
    proposal = plan["planner_proposal_payload"]
    receipt_by_term = {row["term_id"]: row for row in plan["term_validation_receipts"]}
    coverage_by_blueprint = {row["blueprint_id"]: row for row in plan["retrieval_plan_coverage"]}
    intents = []
    counts = {name: 0 for name in CLASSIFICATIONS}
    audit = []
    for intent in proposal["retrieval_intents"]:
        concepts = []
        for concept in intent["search_concepts"]:
            terms = []
            for term in concept["proposed_terms"]:
                receipt = receipt_by_term[term["term_id"]]
                counts[receipt["deterministic_classification"]] += 1
                audit.append({
                    "item_id": term["term_id"], "item_kind": "term",
                    "assigned_class": receipt["deterministic_classification"],
                    "reason": receipt["validation_reason"],
                })
                terms.append({
                    "term_id": term["term_id"], "term": term["term"],
                    "proposal_source": "LLM_PROPOSAL",
                    "proposal_class": receipt["deterministic_classification"],
                    "authority_reference": receipt["authority_reference"],
                    "confidence_not_used_for_scientific_truth": True,
                })
            concepts.append({
                "concept_id": concept["concept_id"], "concept_type": concept["concept_type"],
                "canonical_value": concept["canonical_anchor"], "proposal_source": "LLM_PROPOSAL",
                "proposal_class": "SEARCH_ONLY_EXPANSION", "authority_reference": None,
                "confidence_not_used_for_scientific_truth": True, "proposed_terms": terms,
            })
            counts["SEARCH_ONLY_EXPANSION"] += 1
            audit.append({
                "item_id": concept["concept_id"], "item_kind": "concept",
                "assigned_class": "SEARCH_ONLY_EXPANSION",
                "reason": "non-authoritative model concept anchor retained only for compilation structure",
            })
        blueprints = []
        for blueprint in intent["candidate_query_blueprints"]:
            coverage = coverage_by_blueprint[blueprint["blueprint_id"]]
            blueprints.append({
                "blueprint_id": blueprint["blueprint_id"],
                "concept_ids": deepcopy(blueprint["concept_ids"]),
                "dimension_coverage": deepcopy(coverage["dimension_coverage"]),
                "relation_representation_state": coverage["relation_representation_state"],
                "compiler_input_only": True, "executable_query_absent": True,
            })
        intents.append({**deepcopy(intent), "search_concepts": concepts,
                        "candidate_query_blueprints": blueprints})
    legacy = {
        "artifact_schema_version": PLAN_SCHEMA_VERSION,
        "request_provenance": deepcopy(plan["request_provenance"]),
        "target_id": plan["target_id"],
        "canonical_proposition": deepcopy(plan["canonical_proposition"]),
        "planner_config_sha256": plan["planner_config_sha256"],
        "planner_prompt_template_version": plan["planner_prompt_template_version"],
        "planner_cache_key_sha256": plan["planner_cache_key_sha256"],
        "retrieval_intents": intents,
        "planner_output_frozen_before_retrieval": True,
    }
    plan_hash = sha256_value(legacy)
    receipt = {
        "artifact_schema_version": RECEIPT_VERSION,
        "validator_version": AUTHORITY_SPLIT_VALIDATOR_VERSION,
        "status": "PASS", "validated_plan_sha256": plan_hash,
        "canonical_target_sha256": plan["canonical_proposition"]["target_sha256"],
        "canonical_identity_unchanged": True,
        "classification_counts": counts, "classification_audit": audit,
        "authority_manifest_sha256": plan["term_validation_receipts"][0]["authority_state_hash"]
        if plan["term_validation_receipts"] else sha256_value({"records": []}),
    }
    receipt["receipt_sha256"] = sha256_value(receipt)
    return legacy, receipt


__all__ = [
    "AUTHORITY_SPLIT_CACHE_VERSION", "AUTHORITY_SPLIT_COVERAGE_VERSION",
    "AUTHORITY_SPLIT_VALIDATOR_VERSION", "AuthoritySplitContractError",
    "CLASSIFICATIONS", "FORBIDDEN_MODEL_AUTHORITY_FIELDS",
    "PLANNER_PROPOSAL_PAYLOAD_V1_SCHEMA", "PROPOSAL_VERSION", "RECEIPT_VERSION",
    "TERM_VALIDATION_RECEIPT_V1_SCHEMA", "USABLE_CLASSIFICATIONS",
    "VALIDATED_PLAN_VERSION", "VALIDATED_PROPOSITION_AWARE_SEARCH_PLAN_V1_SCHEMA",
    "assemble_validated_plan", "authority_split_cache_key", "deterministic_coverage",
    "materialize_legacy_compiler_inputs", "project_frozen_provider_payload",
    "validate_planner_proposal", "validate_proposal_terms", "validate_validated_plan",
]
