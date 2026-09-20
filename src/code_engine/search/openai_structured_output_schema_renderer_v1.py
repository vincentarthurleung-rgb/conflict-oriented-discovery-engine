"""Deterministic OpenAI Structured Outputs rendering and offline preflight.

The frozen scientific JSON Schema remains authoritative.  The provider schema
is a transport projection: unsupported assertion keywords are enforced again
by :func:`validate_scientific_instance` after generation, before a value can be
accepted as a scientific plan.
"""

from __future__ import annotations

from copy import deepcopy
import hashlib
import json
import re
from typing import Any, Iterable


RENDERER_VERSION = "openai_structured_output_renderer_v1_1"
PREFLIGHT_VERSION = "OpenAIStructuredOutputSchemaPreflightV1"
CACHE_KEY_VERSION = "PlannerCacheKeyWithProviderSchemaV1"

JSON_TYPES = frozenset({"object", "array", "string", "number", "integer", "boolean", "null"})
ANNOTATION_KEYWORDS = frozenset({"$schema", "$id", "title", "description", "default", "examples", "readOnly", "writeOnly"})
DETERMINISTIC_POST_VALIDATION_KEYWORDS = frozenset({
    "minLength", "maxLength", "pattern",
    "minimum", "maximum", "exclusiveMinimum", "exclusiveMaximum", "multipleOf",
    "minItems", "maxItems", "uniqueItems", "contains", "minContains", "maxContains",
    "minProperties", "maxProperties", "patternProperties", "propertyNames",
    "allOf", "not", "if", "then", "else", "dependentRequired", "dependentSchemas",
})
UNTRANSLATABLE_KEYWORDS = frozenset({"format"})
PROVIDER_ALLOWED_KEYWORDS = frozenset({
    "type", "properties", "required", "additionalProperties", "items", "enum", "const",
    "anyOf", "$defs", "$ref", "description",
})


class ProviderSchemaRenderError(ValueError):
    """Raised when a semantics-preserving provider rendering is impossible."""


class ProviderSchemaPreflightError(ValueError):
    """Raised when a provider-facing schema fails the deterministic gate."""


class ScientificSchemaValidationError(ValueError):
    """Raised when a provider value violates the frozen scientific schema."""


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def sha256_value(value: Any) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


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
    raise ProviderSchemaRenderError(f"unsupported JSON value type: {type(value).__name__}")


def _type_accepts(type_spec: Any, value: Any) -> bool:
    allowed = {type_spec} if isinstance(type_spec, str) else set(type_spec or [])
    actual = _json_type(value)
    return actual in allowed or (actual == "integer" and "number" in allowed)


def _pointer(parts: Iterable[str]) -> str:
    encoded = [str(part).replace("~", "~0").replace("/", "~1") for part in parts]
    return "#" + "".join("/" + part for part in encoded)


def _audit(path: tuple[str, ...], before: Any, after: Any, transformation: str,
           *, enforcement: str = "PROVIDER_SCHEMA", note: str = "") -> dict[str, Any]:
    return {
        "json_path": _pointer(path),
        "scientific_schema_fragment": before,
        "provider_schema_fragment": after,
        "transformation": transformation,
        "semantic_change": False,
        "semantic_equivalence_basis": enforcement,
        "note": note,
    }


def _exact_schema(value: Any) -> dict[str, Any]:
    """Build a closed schema for one exact JSON value."""
    value_type = _json_type(value)
    result: dict[str, Any] = {"type": value_type, "const": deepcopy(value)}
    if value_type == "object":
        result["properties"] = {key: _exact_schema(item) for key, item in sorted(value.items())}
        result["required"] = sorted(value)
        result["additionalProperties"] = False
    elif value_type == "array":
        schemas: list[dict[str, Any]] = []
        seen: set[bytes] = set()
        for item in value:
            candidate = _exact_schema(item)
            identity = canonical_bytes(candidate)
            if identity not in seen:
                schemas.append(candidate)
                seen.add(identity)
        if not schemas:
            result["items"] = {"type": list(sorted(JSON_TYPES))}
        elif len(schemas) == 1:
            result["items"] = schemas[0]
        else:
            result["items"] = {"anyOf": schemas}
    return result


def render_provider_schema(
    scientific_schema: dict[str, Any],
    *,
    exact_object_bindings: dict[str, dict[str, Any]] | None = None,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Render a provider schema while retaining scientific post-validation.

    ``exact_object_bindings`` maps JSON pointers in the scientific schema to
    request-local object values.  Open objects cannot be represented by the
    closed Structured Outputs object subset without such a binding.
    """
    bindings = exact_object_bindings or {}
    audit: list[dict[str, Any]] = []

    def visit(node: Any, path: tuple[str, ...]) -> Any:
        if isinstance(node, list):
            return [visit(item, path + (str(index),)) for index, item in enumerate(node)]
        if not isinstance(node, dict):
            return deepcopy(node)

        pointer = _pointer(path)
        if pointer in bindings:
            before = deepcopy(node)
            after = _exact_schema(bindings[pointer])
            audit.append(_audit(
                path, before, after, "BIND_OPEN_OBJECT_TO_REQUEST_EXACT_VALUE",
                enforcement="REQUEST_EXACT_BINDING_PLUS_FROZEN_SCIENTIFIC_POST_VALIDATION",
                note="The scientific validator already requires the canonical target to equal the request target.",
            ))
            return after

        result: dict[str, Any] = {}
        for key, value in node.items():
            key_path = path + (key,)
            if key in UNTRANSLATABLE_KEYWORDS:
                raise ProviderSchemaRenderError(
                    f"cannot preserve unsupported assertion {key!r} at {_pointer(key_path)}"
                )
            if key in ANNOTATION_KEYWORDS or key.startswith("x-"):
                audit.append(_audit(
                    key_path, value, None, "REMOVE_NON_VALIDATING_ANNOTATION",
                    enforcement="JSON_SCHEMA_ANNOTATION_HAS_NO_ACCEPTANCE_EFFECT",
                ))
                continue
            if key in DETERMINISTIC_POST_VALIDATION_KEYWORDS:
                audit.append(_audit(
                    key_path, value, None, "DELEGATE_UNSUPPORTED_ASSERTION_TO_FROZEN_SCIENTIFIC_POST_VALIDATION",
                    enforcement="MANDATORY_FROZEN_SCIENTIFIC_SCHEMA_POST_VALIDATION",
                    note="Provider transport may be broader; end-to-end accepted values remain unchanged.",
                ))
                continue
            result[key] = visit(value, key_path)

        if "const" in result and "type" not in result:
            inferred = _json_type(result["const"])
            result["type"] = inferred
            audit.append(_audit(
                path, node, result, "ADD_EXPLICIT_TYPE_TO_CONST",
                enforcement="CONST_VALUE_ALREADY_HAS_THE_ADDED_JSON_TYPE",
                note=f"Before and after both accept only the same {result['const']!r} value.",
            ))

        if "enum" in result and "type" not in result:
            enum_types = sorted({_json_type(value) for value in result["enum"]})
            result["type"] = enum_types[0] if len(enum_types) == 1 else enum_types
            audit.append(_audit(
                path, node, result, "ADD_EXPLICIT_TYPE_TO_ENUM",
                enforcement="ENUM_VALUES_ALREADY_HAVE_THE_ADDED_JSON_TYPES",
            ))

        is_object = result.get("type") == "object" or "properties" in result
        if is_object:
            result["type"] = "object"
            properties = result.get("properties")
            if not isinstance(properties, dict):
                raise ProviderSchemaRenderError(
                    f"open object at {pointer} requires an exact_object_bindings entry"
                )
            expected_required = list(properties)
            if result.get("required") != expected_required:
                before = deepcopy(result.get("required"))
                result["required"] = expected_required
                audit.append(_audit(
                    path + ("required",), before, expected_required,
                    "REQUIRE_ALL_PROVIDER_OBJECT_PROPERTIES",
                    enforcement="SCIENTIFIC_SCHEMA_ALREADY_REQUIRES_THE_SAME_FIELDS_OR_EXACT_BINDING",
                ))
            if result.get("additionalProperties") is not False:
                before = deepcopy(result.get("additionalProperties"))
                result["additionalProperties"] = False
                audit.append(_audit(
                    path + ("additionalProperties",), before, False,
                    "CLOSE_PROVIDER_OBJECT",
                    enforcement="SCIENTIFIC_SCHEMA_ALREADY_FORBIDS_EXTRA_FIELDS_OR_EXACT_BINDING",
                ))

        if result.get("type") == "array" and not isinstance(result.get("items"), dict):
            raise ProviderSchemaRenderError(f"array at {pointer} lacks a valid items schema")
        return result

    rendered = visit(deepcopy(scientific_schema), ())
    require_provider_schema_preflight(rendered)
    return rendered, audit


def _resolve_ref(root: dict[str, Any], reference: str) -> dict[str, Any]:
    if not reference.startswith("#/"):
        raise ScientificSchemaValidationError(f"only local refs are supported: {reference}")
    node: Any = root
    for token in reference[2:].split("/"):
        token = token.replace("~1", "/").replace("~0", "~")
        node = node[token]
    if not isinstance(node, dict):
        raise ScientificSchemaValidationError(f"ref does not resolve to a schema: {reference}")
    return node


def validate_scientific_instance(instance: Any, schema: dict[str, Any]) -> None:
    """Validate the frozen schema subset used by PropositionAwareSearchPlanV1."""
    root = schema

    def check(value: Any, node: dict[str, Any], path: str) -> None:
        if "$ref" in node:
            check(value, _resolve_ref(root, node["$ref"]), path)
            return
        if "type" in node and not _type_accepts(node["type"], value):
            raise ScientificSchemaValidationError(f"{path}: incompatible type")
        if "const" in node and value != node["const"]:
            raise ScientificSchemaValidationError(f"{path}: const mismatch")
        if "enum" in node and value not in node["enum"]:
            raise ScientificSchemaValidationError(f"{path}: enum mismatch")
        if "anyOf" in node:
            successes = 0
            for branch in node["anyOf"]:
                try:
                    check(value, branch, path)
                    successes += 1
                except ScientificSchemaValidationError:
                    pass
            if successes == 0:
                raise ScientificSchemaValidationError(f"{path}: no anyOf branch matched")
        if "not" in node:
            try:
                check(value, node["not"], path)
            except ScientificSchemaValidationError:
                pass
            else:
                raise ScientificSchemaValidationError(f"{path}: not schema matched")
        for branch in node.get("allOf", []):
            check(value, branch, path)
        if "if" in node:
            try:
                check(value, node["if"], path)
                condition = True
            except ScientificSchemaValidationError:
                condition = False
            selected = node.get("then") if condition else node.get("else")
            if selected is not None:
                check(value, selected, path)
        if isinstance(value, str):
            if len(value) < node.get("minLength", 0):
                raise ScientificSchemaValidationError(f"{path}: minLength")
            if "maxLength" in node and len(value) > node["maxLength"]:
                raise ScientificSchemaValidationError(f"{path}: maxLength")
            if "pattern" in node and re.search(node["pattern"], value) is None:
                raise ScientificSchemaValidationError(f"{path}: pattern")
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            if "minimum" in node and value < node["minimum"]:
                raise ScientificSchemaValidationError(f"{path}: minimum")
            if "maximum" in node and value > node["maximum"]:
                raise ScientificSchemaValidationError(f"{path}: maximum")
            if "exclusiveMinimum" in node and value <= node["exclusiveMinimum"]:
                raise ScientificSchemaValidationError(f"{path}: exclusiveMinimum")
            if "exclusiveMaximum" in node and value >= node["exclusiveMaximum"]:
                raise ScientificSchemaValidationError(f"{path}: exclusiveMaximum")
            if "multipleOf" in node:
                quotient = value / node["multipleOf"]
                if abs(quotient - round(quotient)) > 1e-12:
                    raise ScientificSchemaValidationError(f"{path}: multipleOf")
        if isinstance(value, list):
            if len(value) < node.get("minItems", 0):
                raise ScientificSchemaValidationError(f"{path}: minItems")
            if "maxItems" in node and len(value) > node["maxItems"]:
                raise ScientificSchemaValidationError(f"{path}: maxItems")
            if node.get("uniqueItems") and len({canonical_bytes(item) for item in value}) != len(value):
                raise ScientificSchemaValidationError(f"{path}: uniqueItems")
            if "items" in node:
                for index, item in enumerate(value):
                    check(item, node["items"], f"{path}/{index}")
            if "contains" in node:
                matches = 0
                for index, item in enumerate(value):
                    try:
                        check(item, node["contains"], f"{path}/{index}")
                        matches += 1
                    except ScientificSchemaValidationError:
                        pass
                minimum = node.get("minContains", 1)
                maximum = node.get("maxContains")
                if matches < minimum or (maximum is not None and matches > maximum):
                    raise ScientificSchemaValidationError(f"{path}: contains")
        if isinstance(value, dict):
            properties = node.get("properties", {})
            if len(value) < node.get("minProperties", 0):
                raise ScientificSchemaValidationError(f"{path}: minProperties")
            if "maxProperties" in node and len(value) > node["maxProperties"]:
                raise ScientificSchemaValidationError(f"{path}: maxProperties")
            missing = set(node.get("required", [])) - set(value)
            if missing:
                raise ScientificSchemaValidationError(f"{path}: missing required {sorted(missing)}")
            if node.get("additionalProperties") is False:
                extra = set(value) - set(properties)
                if extra:
                    raise ScientificSchemaValidationError(f"{path}: additional properties {sorted(extra)}")
            for key, child in properties.items():
                if key in value:
                    check(value[key], child, f"{path}/{key}")
            for pattern, child in node.get("patternProperties", {}).items():
                for key, item in value.items():
                    if re.search(pattern, key):
                        check(item, child, f"{path}/{key}")
            if "propertyNames" in node:
                for key in value:
                    check(key, node["propertyNames"], f"{path}/{key}")
            for trigger, dependencies in node.get("dependentRequired", {}).items():
                if trigger in value:
                    absent = set(dependencies) - set(value)
                    if absent:
                        raise ScientificSchemaValidationError(f"{path}: dependentRequired {sorted(absent)}")
            for trigger, dependent_schema in node.get("dependentSchemas", {}).items():
                if trigger in value:
                    check(value, dependent_schema, path)

    check(instance, schema, "#")


def preflight_provider_schema(schema: dict[str, Any]) -> dict[str, Any]:
    """Return a deterministic fail-closed Structured Outputs compatibility report."""
    errors: list[dict[str, str]] = []
    counts = {
        "const_nodes_missing_explicit_type": 0,
        "enum_nodes_missing_explicit_type": 0,
        "objects_missing_additional_properties_false": 0,
        "object_properties_missing_required_membership": 0,
        "arrays_missing_valid_items": 0,
        "unsupported_keyword_occurrences": 0,
    }
    property_count = 0
    maximum_depth = 0

    def error(path: tuple[str, ...], code: str, message: str) -> None:
        errors.append({"json_path": _pointer(path), "code": code, "message": message})

    def walk(node: Any, path: tuple[str, ...], data_depth: int) -> None:
        nonlocal property_count, maximum_depth
        if not isinstance(node, dict):
            error(path, "SCHEMA_NODE_NOT_OBJECT", "schema node must be an object")
            return
        maximum_depth = max(maximum_depth, data_depth)
        for key in node:
            if key not in PROVIDER_ALLOWED_KEYWORDS:
                counts["unsupported_keyword_occurrences"] += 1
                error(path + (key,), "UNSUPPORTED_KEYWORD", f"unsupported provider keyword: {key}")
        if "const" in node and "type" not in node:
            counts["const_nodes_missing_explicit_type"] += 1
            error(path, "CONST_MISSING_TYPE", "const requires an explicit compatible type")
        if "const" in node and "type" in node and not _type_accepts(node["type"], node["const"]):
            error(path, "CONST_TYPE_MISMATCH", "const value is incompatible with type")
        if "enum" in node and "type" not in node:
            counts["enum_nodes_missing_explicit_type"] += 1
            error(path, "ENUM_MISSING_TYPE", "enum requires an explicit compatible type")
        if "enum" in node and "type" in node:
            for value in node["enum"]:
                if not _type_accepts(node["type"], value):
                    error(path, "ENUM_TYPE_MISMATCH", "enum value is incompatible with type")
        type_spec = node.get("type")
        type_values = {type_spec} if isinstance(type_spec, str) else set(type_spec or [])
        invalid_types = type_values - JSON_TYPES
        if invalid_types:
            error(path + ("type",), "INVALID_TYPE", f"unknown JSON types: {sorted(invalid_types)}")
        if "object" in type_values or "properties" in node:
            properties = node.get("properties")
            if not isinstance(properties, dict):
                error(path, "OBJECT_PROPERTIES_MISSING", "object requires properties")
                properties = {}
            if node.get("additionalProperties") is not False:
                counts["objects_missing_additional_properties_false"] += 1
                error(path, "OBJECT_NOT_CLOSED", "object requires additionalProperties=false")
            required = node.get("required")
            if not isinstance(required, list):
                required = []
                error(path, "OBJECT_REQUIRED_MISSING", "object requires a required array")
            missing = set(properties) - set(required)
            counts["object_properties_missing_required_membership"] += len(missing)
            for key in sorted(missing):
                error(path + ("properties", key), "PROPERTY_NOT_REQUIRED", "every property must be required")
            property_count += len(properties)
            for key, child in properties.items():
                walk(child, path + ("properties", key), data_depth + 1)
        if "array" in type_values:
            if not isinstance(node.get("items"), dict):
                counts["arrays_missing_valid_items"] += 1
                error(path, "ARRAY_ITEMS_MISSING", "array requires an items schema")
            else:
                walk(node["items"], path + ("items",), data_depth + 1)
        for key in ("anyOf",):
            if key in node:
                if not isinstance(node[key], list) or not node[key]:
                    error(path + (key,), "INVALID_COMBINATOR", f"{key} must be a non-empty array")
                else:
                    for index, child in enumerate(node[key]):
                        walk(child, path + (key, str(index)), data_depth)
        if "$defs" in node:
            if not isinstance(node["$defs"], dict):
                error(path + ("$defs",), "INVALID_DEFS", "$defs must be an object")
            else:
                for key, child in node["$defs"].items():
                    walk(child, path + ("$defs", key), data_depth)
        if "$ref" in node:
            try:
                _resolve_ref(schema, node["$ref"])
            except (KeyError, ScientificSchemaValidationError) as exc:
                error(path + ("$ref",), "INVALID_REF", str(exc))

    root_anyof = "anyOf" in schema
    if schema.get("type") != "object":
        errors.append({"json_path": "#", "code": "ROOT_NOT_OBJECT", "message": "root type must be object"})
    if root_anyof:
        errors.append({"json_path": "#", "code": "ROOT_ANYOF", "message": "root anyOf is not supported"})
    walk(schema, (), 1)
    if maximum_depth > 10:
        errors.append({"json_path": "#", "code": "MAX_DEPTH_EXCEEDED", "message": f"depth {maximum_depth} exceeds 10"})
    if property_count > 5000:
        errors.append({"json_path": "#", "code": "PROPERTY_LIMIT_EXCEEDED", "message": f"property count {property_count} exceeds 5000"})
    return {
        "artifact_schema_version": PREFLIGHT_VERSION,
        "status": "PASS" if not errors else "FAIL",
        "provider_schema_sha256": sha256_value(schema),
        "root_type_object": schema.get("type") == "object",
        "root_anyof_present": root_anyof,
        "maximum_nesting_depth": maximum_depth,
        "total_object_properties": property_count,
        **counts,
        "errors": errors,
    }


def require_provider_schema_preflight(schema: dict[str, Any]) -> dict[str, Any]:
    result = preflight_provider_schema(schema)
    if result["status"] != "PASS":
        raise ProviderSchemaPreflightError(json.dumps(result["errors"], sort_keys=True))
    return result


def planner_cache_key_with_provider_schema(
    *, base_planner_cache_key: str, provider_schema_sha256: str
) -> str:
    for label, value in (("base_planner_cache_key", base_planner_cache_key),
                         ("provider_schema_sha256", provider_schema_sha256)):
        if not isinstance(value, str) or re.fullmatch(r"[0-9a-f]{64}", value) is None:
            raise ValueError(f"{label} must be a lowercase SHA-256")
    return sha256_value({
        "cache_key_version": CACHE_KEY_VERSION,
        "base_planner_cache_key": base_planner_cache_key,
        "provider_schema_sha256": provider_schema_sha256,
    })


__all__ = [
    "CACHE_KEY_VERSION", "PREFLIGHT_VERSION", "RENDERER_VERSION",
    "ProviderSchemaPreflightError", "ProviderSchemaRenderError",
    "ScientificSchemaValidationError", "planner_cache_key_with_provider_schema",
    "preflight_provider_schema", "render_provider_schema",
    "require_provider_schema_preflight", "sha256_value", "validate_scientific_instance",
]
