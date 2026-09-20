"""Transport-only planner payload projection and deterministic rehydration.

The provider generates only ``retrieval_intents``.  Request identity and the
canonical scientific target never enter the provider output surface; they are
rehydrated from immutable request inputs before unchanged scientific validation.
"""

from __future__ import annotations

from copy import deepcopy
import hashlib
import json
import re
from typing import Any

from code_engine.search.openai_structured_output_schema_renderer_v1 import (
    ScientificSchemaValidationError,
    sha256_value,
    validate_scientific_instance,
)
from code_engine.search.proposition_aware_query_planner_v1 import (
    PLAN_SCHEMA_VERSION,
    PROMPT_VERSION,
    QueryPlannerConfigV1,
    canonical_target_hash,
    planner_config_hash,
)


PROVIDER_PAYLOAD_SCHEMA_VERSION = "PropositionAwarePlannerPayloadV1"
PAYLOAD_RENDERER_VERSION = "OpenAIPlannerPayloadSchemaRendererV2"
REHYDRATOR_VERSION = "DeterministicPlannerOutputRehydratorV1"
PREFLIGHT_VERSION = "StaticProviderCompatibilityPreflightV2"
CACHE_KEY_VERSION = "PlannerTransportCacheKeyV2"

DETERMINISTIC_REQUEST_ECHO_FIELDS = (
    "artifact_schema_version",
    "request_provenance",
    "target_id",
    "canonical_proposition",
    "planner_config_sha256",
    "planner_prompt_template_version",
    "planner_cache_key_sha256",
    "planner_output_frozen_before_retrieval",
)
MODEL_GENERATED_FIELDS = ("retrieval_intents",)
JSON_TYPES = frozenset({"object", "array", "string", "number", "integer", "boolean", "null"})
ALLOWED_PROVIDER_KEYWORDS = frozenset({
    "type", "properties", "required", "additionalProperties", "items", "enum",
    "anyOf", "$defs", "$ref", "description",
})
ANNOTATION_KEYWORDS = frozenset({"$schema", "$id", "title", "default", "examples", "readOnly", "writeOnly"})
DELEGATED_ASSERTIONS = frozenset({
    "minLength", "maxLength", "pattern", "minimum", "maximum", "exclusiveMinimum",
    "exclusiveMaximum", "multipleOf", "minItems", "maxItems", "uniqueItems", "contains",
    "minContains", "maxContains", "minProperties", "maxProperties", "patternProperties",
    "propertyNames", "allOf", "not", "if", "then", "else", "dependentRequired",
    "dependentSchemas",
})
FAIL_CLOSED_KEYWORDS = frozenset({"format"})


class PlannerPayloadTransportError(ValueError):
    """Raised when payload rendering, validation, or rehydration fails closed."""


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def _pointer(parts: tuple[str, ...]) -> str:
    return "#" + "".join("/" + part.replace("~", "~0").replace("/", "~1") for part in parts)


def _json_type(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, int):
        return "integer"
    if isinstance(value, float):
        return "number"
    if isinstance(value, str):
        return "string"
    if isinstance(value, list):
        return "array"
    if isinstance(value, dict):
        return "object"
    raise PlannerPayloadTransportError(f"unsupported JSON value type: {type(value).__name__}")


def _type_accepts(type_spec: Any, value: Any) -> bool:
    allowed = {type_spec} if isinstance(type_spec, str) else set(type_spec or [])
    actual = _json_type(value)
    return actual in allowed or (actual == "integer" and "number" in allowed)


def _sha_text(value: str, label: str) -> str:
    if not isinstance(value, str) or re.fullmatch(r"[0-9a-f]{64}", value) is None:
        raise PlannerPayloadTransportError(f"{label} must be a lowercase SHA-256")
    return value


def audit_deterministic_request_echo_fields(scientific_schema: dict[str, Any]) -> dict[str, Any]:
    properties = scientific_schema.get("properties")
    required = scientific_schema.get("required")
    if not isinstance(properties, dict) or not isinstance(required, list):
        raise PlannerPayloadTransportError("scientific root must define properties and required")
    expected = set(DETERMINISTIC_REQUEST_ECHO_FIELDS) | set(MODEL_GENERATED_FIELDS)
    if set(properties) != expected or set(required) != expected:
        raise PlannerPayloadTransportError("scientific root fields differ from the frozen projection contract")
    records = []
    for field in properties:
        deterministic = field in DETERMINISTIC_REQUEST_ECHO_FIELDS
        records.append({
            "field": field,
            "classification": "DETERMINISTIC_REQUEST_ECHO" if deterministic else "MODEL_GENERATED_PAYLOAD",
            "provider_payload_included": not deterministic,
            "deterministic_source": {
                "artifact_schema_version": "frozen scientific schema identity",
                "request_provenance": "request reference and its deterministic SHA-256",
                "target_id": "immutable ScientificPropositionTargetV1.scientific_proposition_target_id",
                "canonical_proposition": "immutable ScientificPropositionTargetV1 and canonical hash",
                "planner_config_sha256": "frozen planner configuration",
                "planner_prompt_template_version": "frozen planner configuration",
                "planner_cache_key_sha256": "target/config/prompt/scientific-schema/provider-schema/rehydrator binding",
                "planner_output_frozen_before_retrieval": "frozen protocol constant true",
                "retrieval_intents": None,
            }[field],
        })
    return {
        "deterministic_request_echo_fields": list(DETERMINISTIC_REQUEST_ECHO_FIELDS),
        "model_generated_fields": list(MODEL_GENERATED_FIELDS),
        "records": records,
    }


def render_provider_payload_schema(
    scientific_schema: dict[str, Any],
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Project the frozen plan schema to model-generated content only."""
    field_audit = audit_deterministic_request_echo_fields(scientific_schema)
    audit: list[dict[str, Any]] = [{
        "json_path": "#/properties/" + field,
        "transformation": "OMIT_DETERMINISTIC_REQUEST_ECHO_FROM_PROVIDER_PAYLOAD",
        "scientific_schema_fragment": scientific_schema["properties"][field],
        "provider_schema_fragment": None,
        "semantic_change": False,
        "equivalence_basis": "field is reconstructed exclusively from immutable request state",
    } for field in field_audit["deterministic_request_echo_fields"]]

    def visit(node: Any, path: tuple[str, ...]) -> Any:
        if isinstance(node, list):
            return [visit(item, path + (str(index),)) for index, item in enumerate(node)]
        if not isinstance(node, dict):
            return deepcopy(node)
        result: dict[str, Any] = {}
        for key, value in node.items():
            key_path = path + (key,)
            if key in FAIL_CLOSED_KEYWORDS:
                raise PlannerPayloadTransportError(
                    f"unsupported assertion cannot be preserved at {_pointer(key_path)}: {key}"
                )
            if key in ANNOTATION_KEYWORDS or key.startswith("x-"):
                audit.append({
                    "json_path": _pointer(key_path), "transformation": "REMOVE_NON_VALIDATING_ANNOTATION",
                    "scientific_schema_fragment": value, "provider_schema_fragment": None,
                    "semantic_change": False, "equivalence_basis": "annotation does not affect accepted values",
                })
                continue
            if key in DELEGATED_ASSERTIONS:
                audit.append({
                    "json_path": _pointer(key_path),
                    "transformation": "DELEGATE_ASSERTION_TO_UNCHANGED_SCIENTIFIC_POST_VALIDATION",
                    "scientific_schema_fragment": value, "provider_schema_fragment": None,
                    "semantic_change": False,
                    "equivalence_basis": "rehydrated output must pass the unchanged scientific schema",
                })
                continue
            result[key] = visit(value, key_path)
        if "const" in result:
            value = result.pop("const")
            value_type = _json_type(value)
            if value_type in {"object", "array"}:
                raise PlannerPayloadTransportError(
                    f"composite const cannot enter provider payload at {_pointer(path)}"
                )
            existing_type = result.get("type")
            if existing_type is not None and not _type_accepts(existing_type, value):
                raise PlannerPayloadTransportError(f"const/type mismatch at {_pointer(path)}")
            result["type"] = existing_type or value_type
            result["enum"] = [value]
            audit.append({
                "json_path": _pointer(path),
                "transformation": "RENDER_PRIMITIVE_CONST_AS_SINGLETON_ENUM",
                "scientific_schema_fragment": node,
                "provider_schema_fragment": deepcopy(result),
                "semantic_change": False,
                "equivalence_basis": "primitive const X and singleton enum [X] accept the same value",
            })
        return result

    retrieval_schema = visit(
        scientific_schema["properties"]["retrieval_intents"],
        ("properties", "retrieval_intents"),
    )
    provider_schema = {
        "type": "object",
        "additionalProperties": False,
        "required": ["retrieval_intents"],
        "properties": {"retrieval_intents": retrieval_schema},
    }
    report = static_provider_compatibility_preflight(provider_schema)
    if report["status"] != "PASS":
        raise PlannerPayloadTransportError(json.dumps(report["errors"], sort_keys=True))
    return provider_schema, audit


def static_provider_compatibility_preflight(schema: dict[str, Any]) -> dict[str, Any]:
    """Conservative local gate; explicitly not proof of provider acceptance."""
    errors: list[dict[str, str]] = []
    counts = {
        "provider_schema_object_const_count": 0,
        "provider_schema_array_const_count": 0,
        "provider_schema_primitive_const_count": 0,
        "objects_missing_additional_properties_false": 0,
        "object_properties_missing_required_membership": 0,
        "arrays_missing_items": 0,
        "unsupported_keyword_occurrences": 0,
    }
    maximum_depth = 0
    property_count = 0

    def fail(path: tuple[str, ...], code: str, message: str) -> None:
        errors.append({"json_path": _pointer(path), "code": code, "message": message})

    def walk(node: Any, path: tuple[str, ...], depth: int) -> None:
        nonlocal maximum_depth, property_count
        if not isinstance(node, dict):
            fail(path, "SCHEMA_NODE_NOT_OBJECT", "schema node must be an object")
            return
        maximum_depth = max(maximum_depth, depth)
        for key in node:
            if key not in ALLOWED_PROVIDER_KEYWORDS:
                counts["unsupported_keyword_occurrences"] += 1
                fail(path + (key,), "UNSUPPORTED_KEYWORD", f"unsupported provider keyword: {key}")
        if "const" in node:
            value_type = _json_type(node["const"])
            count_key = {
                "object": "provider_schema_object_const_count",
                "array": "provider_schema_array_const_count",
            }.get(value_type, "provider_schema_primitive_const_count")
            counts[count_key] += 1
            fail(path, "CONST_NOT_ALLOWED", "provider payload projection uses singleton enum, not const")
        type_spec = node.get("type")
        type_values = {type_spec} if isinstance(type_spec, str) else set(type_spec or [])
        invalid = type_values - JSON_TYPES
        if invalid:
            fail(path + ("type",), "INVALID_TYPE", f"unknown JSON types: {sorted(invalid)}")
        if "enum" in node:
            if not type_values:
                fail(path, "ENUM_MISSING_TYPE", "enum requires an explicit compatible type")
            for value in node["enum"]:
                if type_values and not _type_accepts(type_spec, value):
                    fail(path, "ENUM_TYPE_MISMATCH", "enum value is incompatible with type")
        if "object" in type_values or "properties" in node:
            properties = node.get("properties")
            if not isinstance(properties, dict):
                fail(path, "OBJECT_PROPERTIES_MISSING", "object requires properties")
                properties = {}
            if node.get("additionalProperties") is not False:
                counts["objects_missing_additional_properties_false"] += 1
                fail(path, "OBJECT_NOT_CLOSED", "object requires additionalProperties=false")
            required = node.get("required")
            if not isinstance(required, list):
                required = []
                fail(path, "OBJECT_REQUIRED_MISSING", "object requires a required array")
            missing = set(properties) - set(required)
            counts["object_properties_missing_required_membership"] += len(missing)
            for key in sorted(missing):
                fail(path + ("properties", key), "PROPERTY_NOT_REQUIRED", "every property must be required")
            property_count += len(properties)
            for key, child in properties.items():
                walk(child, path + ("properties", key), depth + 1)
        if "array" in type_values:
            if not isinstance(node.get("items"), dict):
                counts["arrays_missing_items"] += 1
                fail(path, "ARRAY_ITEMS_MISSING", "array requires an items schema")
            else:
                walk(node["items"], path + ("items",), depth + 1)
        if "anyOf" in node:
            branches = node["anyOf"]
            if not isinstance(branches, list) or not branches:
                fail(path + ("anyOf",), "INVALID_ANYOF", "anyOf must be a non-empty array")
            else:
                for index, branch in enumerate(branches):
                    walk(branch, path + ("anyOf", str(index)), depth)
        if "$defs" in node:
            definitions = node["$defs"]
            if not isinstance(definitions, dict):
                fail(path + ("$defs",), "INVALID_DEFS", "$defs must be an object")
            else:
                for key, definition in definitions.items():
                    walk(definition, path + ("$defs", key), depth)
        if "$ref" in node and not isinstance(node["$ref"], str):
            fail(path + ("$ref",), "INVALID_REF", "$ref must be a string")

    root_anyof = "anyOf" in schema
    if schema.get("type") != "object":
        fail((), "ROOT_NOT_OBJECT", "root type must be object")
    if root_anyof:
        fail((), "ROOT_ANYOF", "root anyOf is unsupported")
    walk(schema, (), 1)
    if maximum_depth > 10:
        fail((), "MAX_DEPTH_EXCEEDED", f"depth {maximum_depth} exceeds 10")
    if property_count > 5000:
        fail((), "PROPERTY_LIMIT_EXCEEDED", f"property count {property_count} exceeds 5000")
    return {
        "artifact_schema_version": PREFLIGHT_VERSION,
        "preflight_name": "STATIC_PROVIDER_COMPATIBILITY_PREFLIGHT",
        "preflight_is_provider_acceptance_proof": False,
        "status": "PASS" if not errors else "FAIL",
        "provider_payload_schema_sha256": sha256_value(schema),
        "root_type_object": schema.get("type") == "object",
        "root_anyof_present": root_anyof,
        "maximum_nesting_depth": maximum_depth,
        "total_object_properties": property_count,
        **counts,
        "errors": errors,
    }


def validate_provider_payload(payload: dict[str, Any], provider_schema: dict[str, Any]) -> None:
    report = static_provider_compatibility_preflight(provider_schema)
    if report["status"] != "PASS":
        raise PlannerPayloadTransportError("provider schema failed static preflight")
    try:
        validate_scientific_instance(payload, provider_schema)
    except ScientificSchemaValidationError as exc:
        raise PlannerPayloadTransportError(f"provider payload validation failed: {exc}") from exc


def planner_transport_cache_key(
    *, canonical_target_sha256: str, planner_config_sha256: str,
    prompt_sha256: str, scientific_schema_sha256: str,
    provider_projection_schema_sha256: str,
    rehydrator_version: str = REHYDRATOR_VERSION,
) -> str:
    fields = {
        "canonical_target_sha256": canonical_target_sha256,
        "planner_config_sha256": planner_config_sha256,
        "prompt_sha256": prompt_sha256,
        "scientific_schema_sha256": scientific_schema_sha256,
        "provider_projection_schema_sha256": provider_projection_schema_sha256,
    }
    for label, value in fields.items():
        _sha_text(value, label)
    if not str(rehydrator_version).strip():
        raise PlannerPayloadTransportError("rehydrator_version is required")
    return sha256_value({
        "cache_key_version": CACHE_KEY_VERSION,
        **fields,
        "rehydrator_version": rehydrator_version,
    })


def rehydrate_planner_output(
    provider_payload: dict[str, Any],
    *,
    canonical_target: dict[str, Any],
    request_reference: str,
    planner_config: QueryPlannerConfigV1,
    prompt_sha256: str,
    scientific_schema_sha256: str,
    provider_payload_schema: dict[str, Any],
) -> dict[str, Any]:
    """Create the complete scientific plan without trusting model echo fields."""
    validate_provider_payload(provider_payload, provider_payload_schema)
    target_sha256 = canonical_target_hash(canonical_target)
    config_sha256 = planner_config_hash(planner_config)
    provider_schema_sha256 = sha256_value(provider_payload_schema)
    cache_key = planner_transport_cache_key(
        canonical_target_sha256=target_sha256,
        planner_config_sha256=config_sha256,
        prompt_sha256=_sha_text(prompt_sha256, "prompt_sha256"),
        scientific_schema_sha256=_sha_text(scientific_schema_sha256, "scientific_schema_sha256"),
        provider_projection_schema_sha256=provider_schema_sha256,
    )
    if not isinstance(request_reference, str) or not request_reference.strip():
        raise PlannerPayloadTransportError("request_reference is required")
    return {
        "artifact_schema_version": PLAN_SCHEMA_VERSION,
        "request_provenance": {
            "request_sha256": hashlib.sha256(request_reference.encode("utf-8")).hexdigest(),
            "preserved_request_reference": request_reference,
        },
        "target_id": canonical_target["scientific_proposition_target_id"],
        "canonical_proposition": {
            "schema_version": "ScientificPropositionTargetV1",
            "target_sha256": target_sha256,
            "target_payload": deepcopy(canonical_target),
        },
        "planner_config_sha256": config_sha256,
        "planner_prompt_template_version": planner_config.prompt_version or PROMPT_VERSION,
        "planner_cache_key_sha256": cache_key,
        "retrieval_intents": deepcopy(provider_payload["retrieval_intents"]),
        "planner_output_frozen_before_retrieval": True,
    }


__all__ = [
    "CACHE_KEY_VERSION", "DETERMINISTIC_REQUEST_ECHO_FIELDS", "MODEL_GENERATED_FIELDS",
    "PAYLOAD_RENDERER_VERSION", "PREFLIGHT_VERSION", "PROVIDER_PAYLOAD_SCHEMA_VERSION",
    "REHYDRATOR_VERSION", "PlannerPayloadTransportError",
    "audit_deterministic_request_echo_fields", "planner_transport_cache_key",
    "rehydrate_planner_output", "render_provider_payload_schema",
    "static_provider_compatibility_preflight", "validate_provider_payload",
]
