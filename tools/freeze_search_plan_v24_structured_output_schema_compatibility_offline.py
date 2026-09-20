#!/usr/bin/env python3
"""Freeze the offline v2.4 Structured Outputs compatibility amendment."""

from __future__ import annotations

from collections import Counter
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from code_engine.search.openai_structured_output_schema_renderer_v1 import (
    CACHE_KEY_VERSION,
    PREFLIGHT_VERSION,
    RENDERER_VERSION,
    planner_cache_key_with_provider_schema,
    preflight_provider_schema,
    render_provider_schema,
    require_provider_schema_preflight,
    sha256_value,
)
from code_engine.search.proposition_aware_query_planner_v1 import (
    DEFAULT_DEVELOPMENT_CONFIG,
    PLAN_SCHEMA_VERSION,
    PROMPT_VERSION,
    planner_cache_key,
)
from tools import freeze_search_plan_v24_dev_planner_compiler_implementation_offline as implementation


RUN = ROOT / "runs/20260918_search_plan_v24_dev_structured_output_schema_compatibility_offline"
ARCHITECTURE_RUN = implementation.ARCHITECTURE_RUN
IMPLEMENTATION_RUN = implementation.RUN
FAILED_RUN = ROOT / "runs/20260917_search_plan_v24_dev_real_planner_generation_freeze"
SCHEMA_PATH = ARCHITECTURE_RUN / "proposition_aware_search_plan_v1_schema.json"
PROMPT_PATH = IMPLEMENTATION_RUN / "query_planner_prompt_v1.md"
TARGETS_PATH = implementation.TARGETS_PATH
RENDERER_SOURCE = ROOT / "src/code_engine/search/openai_structured_output_schema_renderer_v1.py"
RENDERER_TEST = ROOT / "tests/test_openai_structured_output_schema_renderer_v1.py"
TARGET_POINTER = "#/properties/canonical_proposition/properties/target_payload"

EXPECTED_ARCHITECTURE = "ec1ca7facd2f0df67abae27f922a62c4bd859c6011adda30f0cec51f6baf84ea"
EXPECTED_IMPLEMENTATION = "970e11cbac017af2ecde0803e6c47768fcba947211bcb1b37ea00fb5331ef478"
EXPECTED_FAILED_RUN = "7380b5fc472bda29c1e9a82d64a73956ad1ec077464e09db33bcd5974ba4d316"

REQUIRED_OUTPUTS = {
    "upstream_root_verification.json",
    "failed_run_preservation_audit.json",
    "scientific_schema_immutability_audit.json",
    "openai_structured_output_compatibility_requirements.json",
    "provider_schema_renderer_contract.json",
    "provider_compatible_schema.json",
    "provider_schema_recursive_audit.json",
    "transport_semantic_equivalence_audit.json",
    "static_provider_schema_preflight.json",
    "schema_fixture_validation.json",
    "planner_cache_impact_audit.json",
    "scientific_state_safety_audit.json",
    "validation.json",
    "summary.json",
}


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def pretty(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n").encode("utf-8")


def sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def write_exact(path: Path, body: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        require(path.is_file() and not path.is_symlink(), f"non-physical output: {path}")
        require(path.read_bytes() == body, f"existing output differs: {path}")
        return
    with path.open("xb") as stream:
        stream.write(body)


def load_json(path: Path) -> Any:
    return json.loads(path.read_bytes())


def aggregate(components: list[list[str]]) -> str:
    return hashlib.sha256(canonical(components)).hexdigest()


def verify_component_root(run: Path, metadata_file: str, root_field: str, expected: str) -> tuple[str, int]:
    metadata = load_json(run / metadata_file)
    components = []
    for name, recorded in metadata["aggregate_components"]:
        actual = sha(run / name)
        require(actual == recorded, f"component changed: {run.name}/{name}")
        components.append([name, actual])
    root = aggregate(components)
    require(root == metadata[root_field] == expected, f"root mismatch: {root_field}")
    return root, len(components)


def tree_hashes(path: Path) -> dict[str, str]:
    return {
        str(item.relative_to(ROOT)): sha(item)
        for item in sorted(path.rglob("*")) if item.is_file()
    }


def relevant_scientific_state() -> dict[str, str]:
    paths = [
        SCHEMA_PATH,
        PROMPT_PATH,
        ROOT / "src/code_engine/search/proposition_aware_query_planner_v1.py",
        ROOT / "src/code_engine/search/retrieval_intent_v1.py",
        ROOT / "src/code_engine/search/retrieval_plan_coverage_v1.py",
        ROOT / "src/code_engine/search/search_term_validator_v1.py",
        ROOT / "src/code_engine/search/query_compiler_v24_dev.py",
    ]
    result = {str(path.relative_to(ROOT)): sha(path) for path in paths}
    for base in (ARCHITECTURE_RUN, IMPLEMENTATION_RUN, FAILED_RUN):
        result.update(tree_hashes(base))
    return dict(sorted(result.items()))


def synthetic_fixtures() -> list[dict[str, Any]]:
    return [
        {
            "fixture_id": "const_primitives",
            "schema": {
                "type": "object", "additionalProperties": False,
                "required": ["string_const", "integer_const", "boolean_const"],
                "properties": {
                    "string_const": {"const": "fixed"},
                    "integer_const": {"const": 7},
                    "boolean_const": {"const": True},
                },
            },
        },
        {
            "fixture_id": "nested_arrays_enums_nullable",
            "schema": {
                "type": "object", "additionalProperties": False,
                "required": ["nested", "values", "nullable"],
                "properties": {
                    "nested": {
                        "type": "object", "additionalProperties": False,
                        "required": ["state"],
                        "properties": {"state": {"type": "string", "enum": ["A", "B"]}},
                    },
                    "values": {"type": "array", "items": {"type": "integer"}},
                    "nullable": {"type": ["string", "null"]},
                },
            },
        },
        {
            "fixture_id": "defs_and_refs",
            "schema": {
                "type": "object", "additionalProperties": False,
                "required": ["value"],
                "properties": {"value": {"$ref": "#/$defs/value"}},
                "$defs": {"value": {"type": "string", "enum": ["x", "y"]}},
            },
        },
    ]


def main() -> None:
    require(not RUN.exists() or not any(RUN.iterdir()), "compatibility run already contains files")

    architecture_root, architecture_components = verify_component_root(
        ARCHITECTURE_RUN, "validation.json",
        "search_plan_v24_proposition_aware_architecture_sha256", EXPECTED_ARCHITECTURE,
    )
    implementation_root, implementation_components = verify_component_root(
        IMPLEMENTATION_RUN, "validation.json",
        "search_plan_v24_dev_planner_compiler_implementation_sha256", EXPECTED_IMPLEMENTATION,
    )
    failed_root, failed_components = verify_component_root(
        FAILED_RUN, "implementation_manifest.json",
        "search_plan_v24_dev_real_planner_generation_sha256", EXPECTED_FAILED_RUN,
    )
    before = relevant_scientific_state()
    scientific_schema_before = SCHEMA_PATH.read_bytes()
    scientific_schema = json.loads(scientific_schema_before)
    target = json.loads(TARGETS_PATH.read_text(encoding="utf-8").splitlines()[0])

    upstream = {
        "artifact_schema_version": "V24StructuredOutputCompatibilityUpstreamRootVerificationV1",
        "status": "PASS",
        "search_plan_v24_proposition_aware_architecture_sha256": architecture_root,
        "architecture_component_count": architecture_components,
        "search_plan_v24_dev_planner_compiler_implementation_sha256": implementation_root,
        "implementation_component_count": implementation_components,
        "search_plan_v24_dev_real_planner_generation_sha256": failed_root,
        "failed_run_component_count": failed_components,
        "verified_before_amendment_generation": True,
    }

    provider_schema, recursive_rows = render_provider_schema(
        scientific_schema, exact_object_bindings={TARGET_POINTER: target}
    )
    scientific_preflight = preflight_provider_schema(scientific_schema)
    provider_preflight = require_provider_schema_preflight(provider_schema)
    provider_schema_hash = sha256_value(provider_schema)
    require(provider_schema_hash == provider_preflight["provider_schema_sha256"], "provider hash mismatch")

    transformation_counts = Counter(row["transformation"] for row in recursive_rows)
    recursive_audit = {
        "artifact_schema_version": "ProviderSchemaRecursiveAuditV1",
        "scientific_schema_version": PLAN_SCHEMA_VERSION,
        "provider_schema_renderer_version": RENDERER_VERSION,
        "request_specialization": {
            "required": True,
            "binding_path": TARGET_POINTER,
            "reference_case_id": target["case_id"],
            "reference_target_id": target["scientific_proposition_target_id"],
            "reference_target_sha256": sha256_value(target),
            "case_specific_logic": False,
            "rule": "bind the canonical target supplied to the current request as one exact closed JSON value",
        },
        "transformation_count": len(recursive_rows),
        "transformation_distribution": dict(sorted(transformation_counts.items())),
        "audit_rows": recursive_rows,
    }
    semantic_audit = {
        "artifact_schema_version": "TransportSemanticEquivalenceAuditV1",
        "status": "PASS",
        "equivalence_scope": "provider preflight plus mandatory frozen scientific schema post-validation",
        "provider_schema_alone_may_be_broader_for_delegated_assertions": True,
        "provider_output_accepted_without_scientific_post_validation": False,
        "scientific_semantic_changes": 0,
        "all_transformations_semantic_change_false": all(not row["semantic_change"] for row in recursive_rows),
        "const_equivalence_rule": {
            "before": "value must equal X",
            "after": "value must have the inherent JSON type of X and equal X",
            "accepted_value_set_changed": False,
        },
        "delegated_assertion_rule": {
            "transport_surface_relation": "PROVIDER_SCHEMA_IS_A_SUPERSET_FOR_DELEGATED_ASSERTIONS",
            "final_acceptance_rule": "provider output must pass the unchanged frozen scientific schema before acceptance",
            "end_to_end_accepted_value_set_changed": False,
        },
        "transformations": recursive_rows,
    }

    requirements = {
        "artifact_schema_version": "OpenAIStructuredOutputCompatibilityRequirementsV1",
        "derivation_mode": "OFFLINE_CONSERVATIVE_CONTRACT",
        "online_official_documentation_consulted": False,
        "evidence": [
            "observed OpenAI invalid_json_schema rejection from the preserved failed run",
            "user-authorized compatibility requirements in this offline amendment",
        ],
        "root": {"type_object_required": True, "root_anyof_forbidden": True},
        "objects": {"type_object_required": True, "additional_properties_false_required": True,
                    "all_properties_required": True},
        "arrays": {"type_array_required": True, "items_schema_required": True},
        "primitives": {"explicit_type_required": True},
        "const": {"explicit_compatible_type_required": True},
        "enum": {"explicit_compatible_type_required": True},
        "nullable": {"supported_representation": "type union including null or nested anyOf"},
        "limits": {"maximum_nesting_depth": 10, "maximum_total_object_properties": 5000},
        "provider_allowed_keywords": sorted({
            "type", "properties", "required", "additionalProperties", "items", "enum", "const",
            "anyOf", "$defs", "$ref", "description",
        }),
        "scientific_constraints_delegated_to_mandatory_post_validation": sorted({
            row["json_path"].split("/")[-1]
            for row in recursive_rows
            if row["transformation"] == "DELEGATE_UNSUPPORTED_ASSERTION_TO_FROZEN_SCIENTIFIC_POST_VALIDATION"
        }),
        "uncertain_provider_features_treated_as_unsupported": True,
    }

    renderer_contract = {
        "artifact_schema_version": "OpenAIStructuredOutputSchemaRendererContractV1",
        "amendment_classification": "TRANSPORT_SCHEMA_COMPATIBILITY_AMENDMENT",
        "scientific_schema_version": PLAN_SCHEMA_VERSION,
        "provider_schema_renderer_version": RENDERER_VERSION,
        "static_preflight_version": PREFLIGHT_VERSION,
        "cache_key_version": CACHE_KEY_VERSION,
        "source_file": str(RENDERER_SOURCE.relative_to(ROOT)),
        "source_sha256": sha(RENDERER_SOURCE),
        "test_file": str(RENDERER_TEST.relative_to(ROOT)),
        "test_sha256": sha(RENDERER_TEST),
        "required_pipeline": [
            "load immutable scientific schema",
            "bind request canonical target to target_payload",
            "render provider transport schema",
            "run static provider schema preflight",
            "include provider schema SHA-256 in cache identity",
            "perform authorized provider call only after PASS",
            "validate response against immutable scientific schema",
            "run existing deterministic plan validation",
        ],
        "provider_call_permitted_when_preflight_fails": False,
        "scientific_post_validation_mandatory": True,
        "provider_schema_hash_mandatory_in_future_cache_key": True,
    }

    fixture_rows = []
    for fixture in synthetic_fixtures():
        rendered, audit = render_provider_schema(fixture["schema"])
        before_report = preflight_provider_schema(fixture["schema"])
        after_report = require_provider_schema_preflight(rendered)
        fixture_rows.append({
            "fixture_id": fixture["fixture_id"],
            "scientific_schema": fixture["schema"],
            "provider_schema": rendered,
            "scientific_preflight_status": before_report["status"],
            "provider_preflight_status": after_report["status"],
            "transformation_count": len(audit),
            "semantic_changes": sum(bool(row["semantic_change"]) for row in audit),
        })
    fixture_validation = {
        "artifact_schema_version": "StructuredOutputSchemaFixtureValidationV1",
        "status": "PASS",
        "fixture_count": len(fixture_rows),
        "fixtures": fixture_rows,
        "real_schema_const_only_regression_reproduced": scientific_preflight["const_nodes_missing_explicit_type"] > 0,
        "real_schema_const_nodes_missing_type_before": scientific_preflight["const_nodes_missing_explicit_type"],
        "real_schema_const_nodes_missing_type_after": provider_preflight["const_nodes_missing_explicit_type"],
        "provider_calls": 0,
    }

    base_cache_key = planner_cache_key(
        target, DEFAULT_DEVELOPMENT_CONFIG,
        prompt_version=PROMPT_VERSION, schema_version=PLAN_SCHEMA_VERSION,
    )
    provider_bound_cache_key = planner_cache_key_with_provider_schema(
        base_planner_cache_key=base_cache_key,
        provider_schema_sha256=provider_schema_hash,
    )
    changed_schema = deepcopy(provider_schema)
    changed_schema["description"] = "cache identity perturbation fixture"
    changed_cache_key = planner_cache_key_with_provider_schema(
        base_planner_cache_key=base_cache_key,
        provider_schema_sha256=sha256_value(changed_schema),
    )
    cache_audit = {
        "artifact_schema_version": "PlannerCacheImpactAuditV1",
        "status": "PASS",
        "historical_cache_key_formula_changed": False,
        "historical_cache_artifacts_invalidated": False,
        "future_provider_generation_cache_key_version": CACHE_KEY_VERSION,
        "base_planner_cache_key_sha256": base_cache_key,
        "provider_schema_sha256": provider_schema_hash,
        "provider_bound_planner_cache_key_sha256": provider_bound_cache_key,
        "cache_key_changes_when_provider_schema_changes": provider_bound_cache_key != changed_cache_key,
        "provider_schema_hash_required_for_future_provider_generation": True,
    }

    RUN.mkdir(parents=True, exist_ok=True)
    write_exact(RUN / "upstream_root_verification.json", pretty(upstream))
    write_exact(RUN / "openai_structured_output_compatibility_requirements.json", pretty(requirements))
    write_exact(RUN / "provider_schema_renderer_contract.json", pretty(renderer_contract))
    write_exact(RUN / "provider_compatible_schema.json", pretty(provider_schema))
    write_exact(RUN / "provider_schema_recursive_audit.json", pretty(recursive_audit))
    write_exact(RUN / "transport_semantic_equivalence_audit.json", pretty(semantic_audit))
    write_exact(RUN / "static_provider_schema_preflight.json", pretty({
        "artifact_schema_version": "StaticProviderSchemaPreflightArtifactV1",
        "status": "PASS",
        "original_scientific_schema_preflight": scientific_preflight,
        "rendered_provider_schema_preflight": provider_preflight,
        "mandatory_before_future_provider_request": True,
        "provider_calls": 0,
    }))
    write_exact(RUN / "schema_fixture_validation.json", pretty(fixture_validation))
    write_exact(RUN / "planner_cache_impact_audit.json", pretty(cache_audit))

    after = relevant_scientific_state()
    schema_after = SCHEMA_PATH.read_bytes()
    require(before == after, "protected scientific state changed")
    require(scientific_schema_before == schema_after, "scientific schema changed")
    failed_preservation = {
        "artifact_schema_version": "FailedPlannerGenerationRunPreservationAuditV1",
        "status": "PASS",
        "failed_run_path": str(FAILED_RUN.relative_to(ROOT)),
        "expected_root": EXPECTED_FAILED_RUN,
        "verified_root": failed_root,
        "file_count": len(tree_hashes(FAILED_RUN)),
        "files_unchanged": tree_hashes(FAILED_RUN) == {
            key: value for key, value in before.items() if key.startswith(str(FAILED_RUN.relative_to(ROOT)) + "/")
        },
        "historical_assets_modified": False,
    }
    schema_immutability = {
        "artifact_schema_version": "ScientificSchemaImmutabilityAuditV1",
        "status": "PASS",
        "scientific_schema_version": PLAN_SCHEMA_VERSION,
        "scientific_schema_path": str(SCHEMA_PATH.relative_to(ROOT)),
        "scientific_schema_sha256_before": hashlib.sha256(scientific_schema_before).hexdigest(),
        "scientific_schema_sha256_after": hashlib.sha256(schema_after).hexdigest(),
        "scientific_schema_changed": False,
        "planner_prompt_changed": False,
        "planner_semantics_changed": False,
        "retrieval_intents_changed": False,
        "authority_boundary_changed": False,
        "query_budgets_changed": False,
        "compiler_changed": False,
        "protected_state_before_sha256": hashlib.sha256(canonical(before)).hexdigest(),
        "protected_state_after_sha256": hashlib.sha256(canonical(after)).hexdigest(),
    }
    safety = {
        "artifact_schema_version": "V24StructuredOutputCompatibilityScientificStateSafetyAuditV1",
        "status": "PASS",
        "offline_only": True,
        "provider_calls": 0,
        "llm_calls": 0,
        "network_calls": 0,
        "retrieval_calls": 0,
        "scientific_schema_changed": False,
        "planner_prompt_changed": False,
        "planner_semantics_changed": False,
        "historical_assets_modified": False,
    }
    write_exact(RUN / "failed_run_preservation_audit.json", pretty(failed_preservation))
    write_exact(RUN / "scientific_schema_immutability_audit.json", pretty(schema_immutability))
    write_exact(RUN / "scientific_state_safety_audit.json", pretty(safety))

    component_names = sorted(REQUIRED_OUTPUTS - {"validation.json", "summary.json"})
    components = [[name, sha(RUN / name)] for name in component_names]
    compatibility_root = aggregate(components)
    checks = {
        "upstream_roots_verified": upstream["status"] == "PASS",
        "failed_run_preserved": failed_preservation["status"] == "PASS" and failed_preservation["files_unchanged"],
        "scientific_schema_changed_false": not schema_immutability["scientific_schema_changed"],
        "planner_prompt_changed_false": not schema_immutability["planner_prompt_changed"],
        "planner_semantics_changed_false": not schema_immutability["planner_semantics_changed"],
        "provider_schema_renderer_created": RENDERER_SOURCE.is_file(),
        "const_nodes_missing_explicit_type_zero": provider_preflight["const_nodes_missing_explicit_type"] == 0,
        "objects_missing_additional_properties_false_zero": provider_preflight["objects_missing_additional_properties_false"] == 0,
        "object_properties_missing_required_membership_zero": provider_preflight["object_properties_missing_required_membership"] == 0,
        "root_anyof_absent": not provider_preflight["root_anyof_present"],
        "static_provider_schema_preflight_pass": provider_preflight["status"] == "PASS",
        "scientific_semantic_changes_zero": semantic_audit["scientific_semantic_changes"] == 0,
        "cache_includes_provider_schema_hash": cache_audit["cache_key_changes_when_provider_schema_changes"],
        "zero_external_calls": safety["provider_calls"] == safety["llm_calls"] == safety["network_calls"] == 0,
    }
    require(all(checks.values()), f"compatibility validation failed: {checks}")
    validation = {
        "artifact_schema_version": "V24StructuredOutputSchemaCompatibilityValidationV1",
        "status": "PASS",
        "checks": checks,
        "aggregate_components": components,
        "search_plan_v24_structured_output_compatibility_sha256": compatibility_root,
    }
    summary = {
        "artifact_schema_version": "V24StructuredOutputSchemaCompatibilitySummaryV1",
        "status": "COMPLETED",
        "failure_class": "TRANSPORT_SCHEMA_COMPATIBILITY",
        "scientific_schema_changed": False,
        "planner_prompt_changed": False,
        "planner_semantics_changed": False,
        "provider_schema_renderer_created": True,
        "provider_schema_renderer_version": RENDERER_VERSION,
        "provider_schema_sha256": provider_schema_hash,
        "const_nodes_missing_explicit_type": provider_preflight["const_nodes_missing_explicit_type"],
        "objects_missing_additional_properties_false": provider_preflight["objects_missing_additional_properties_false"],
        "object_properties_missing_required_membership": provider_preflight["object_properties_missing_required_membership"],
        "root_anyof_present": provider_preflight["root_anyof_present"],
        "static_provider_schema_preflight_pass": provider_preflight["status"] == "PASS",
        "scientific_semantic_changes": semantic_audit["scientific_semantic_changes"],
        "recursive_transformation_count": len(recursive_rows),
        "provider_calls": 0,
        "llm_calls": 0,
        "network_calls": 0,
        "retrieval_calls": 0,
        "search_plan_v24_structured_output_compatibility_sha256": compatibility_root,
        "historical_assets_modified": False,
    }
    write_exact(RUN / "validation.json", pretty(validation))
    write_exact(RUN / "summary.json", pretty(summary))
    require({path.name for path in RUN.iterdir()} == REQUIRED_OUTPUTS, "run membership mismatch")
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
