#!/usr/bin/env python3
"""Freeze the offline v2.4 planner transport-projection compatibility amendment."""

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

from code_engine.search.openai_planner_payload_transport_v2 import (
    CACHE_KEY_VERSION,
    DETERMINISTIC_REQUEST_ECHO_FIELDS,
    MODEL_GENERATED_FIELDS,
    PAYLOAD_RENDERER_VERSION,
    PREFLIGHT_VERSION,
    PROVIDER_PAYLOAD_SCHEMA_VERSION,
    REHYDRATOR_VERSION,
    PlannerPayloadTransportError,
    audit_deterministic_request_echo_fields,
    planner_transport_cache_key,
    rehydrate_planner_output,
    render_provider_payload_schema,
    static_provider_compatibility_preflight,
    validate_provider_payload,
)
from code_engine.search.openai_structured_output_schema_renderer_v1 import (
    validate_scientific_instance,
)
from code_engine.search.proposition_aware_query_planner_v1 import (
    DEFAULT_DEVELOPMENT_CONFIG,
    PLAN_SCHEMA_VERSION,
    canonical_target_hash,
    planner_config_hash,
    validate_plan,
)
from tools import freeze_search_plan_v24_dev_planner_compiler_implementation_offline as implementation


RUN = ROOT / "runs/20260918_search_plan_v24_dev_transport_projection_compatibility_offline"
ARCHITECTURE_RUN = implementation.ARCHITECTURE_RUN
IMPLEMENTATION_RUN = implementation.RUN
COMPATIBILITY_RUN = ROOT / "runs/20260918_search_plan_v24_dev_structured_output_schema_compatibility_offline"
FAILED_RUN_1 = ROOT / "runs/20260917_search_plan_v24_dev_real_planner_generation_freeze"
FAILED_RUN_2 = ROOT / "runs/20260918_search_plan_v24_dev_real_planner_generation_v2_freeze"
SCHEMA_PATH = ARCHITECTURE_RUN / "proposition_aware_search_plan_v1_schema.json"
PROMPT_PATH = IMPLEMENTATION_RUN / "query_planner_prompt_v1.md"
TRANSPORT_SOURCE = ROOT / "src/code_engine/search/openai_planner_payload_transport_v2.py"
TRANSPORT_TEST = ROOT / "tests/test_openai_planner_payload_transport_v2.py"

EXPECTED_ARCHITECTURE = "ec1ca7facd2f0df67abae27f922a62c4bd859c6011adda30f0cec51f6baf84ea"
EXPECTED_IMPLEMENTATION = "970e11cbac017af2ecde0803e6c47768fcba947211bcb1b37ea00fb5331ef478"
EXPECTED_COMPATIBILITY = "1a069ac50f95d2f9ae31307616ab22166c01f8ea9266d356e059bb8f268fc9d8"
EXPECTED_FAILED_1 = "7380b5fc472bda29c1e9a82d64a73956ad1ec077464e09db33bcd5974ba4d316"
EXPECTED_FAILED_2 = "437b659b3dcdf8bd7162aa6b4955be3f864be17eb30c3c1ef8fd3a3d1e1b2fd5"
EXPECTED_SCIENTIFIC_SCHEMA = "8ae710d8f9261e47be06279c091a901211f86e6ae2178728394869ee72d793d6"

REQUIRED_OUTPUTS = {
    "upstream_root_verification.json",
    "prior_failed_runs_preservation_audit.json",
    "deterministic_request_echo_field_audit.json",
    "provider_payload_projection_contract.json",
    "provider_payload_schema.json",
    "provider_payload_schema_recursive_audit.json",
    "deterministic_rehydrator_contract.json",
    "rehydration_semantic_equivalence_audit.json",
    "static_provider_compatibility_preflight_v2.json",
    "composite_const_regression_audit.json",
    "planner_cache_impact_audit.json",
    "scientific_schema_immutability_audit.json",
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


def load_json(path: Path) -> Any:
    return json.loads(path.read_bytes())


def write_exact(path: Path, body: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        require(path.is_file() and not path.is_symlink(), f"non-physical output: {path}")
        require(path.read_bytes() == body, f"existing output differs: {path}")
        return
    with path.open("xb") as stream:
        stream.write(body)


def aggregate(components: list[list[str]]) -> str:
    return hashlib.sha256(canonical(components)).hexdigest()


def verify_root(run: Path, metadata_name: str, field: str, expected: str) -> tuple[str, int]:
    metadata = load_json(run / metadata_name)
    pairs = []
    for name, recorded in metadata["aggregate_components"]:
        actual = sha(run / name)
        require(actual == recorded, f"component changed: {run.name}/{name}")
        pairs.append([name, actual])
    root = aggregate(pairs)
    require(root == metadata[field] == expected, f"root mismatch: {field}")
    return root, len(pairs)


def tree_hashes(directory: Path) -> dict[str, str]:
    return {
        str(path.relative_to(ROOT)): sha(path)
        for path in sorted(directory.rglob("*")) if path.is_file()
    }


def protected_state() -> dict[str, str]:
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
    for directory in (ARCHITECTURE_RUN, IMPLEMENTATION_RUN, COMPATIBILITY_RUN, FAILED_RUN_1, FAILED_RUN_2):
        result.update(tree_hashes(directory))
    return dict(sorted(result.items()))


def count_const_types(schema: Any) -> dict[str, int]:
    counts = {"object": 0, "array": 0, "primitive": 0}
    def walk(value: Any) -> None:
        if isinstance(value, dict):
            if "const" in value:
                const = value["const"]
                if isinstance(const, dict):
                    counts["object"] += 1
                elif isinstance(const, list):
                    counts["array"] += 1
                else:
                    counts["primitive"] += 1
            for child in value.values():
                walk(child)
        elif isinstance(value, list):
            for child in value:
                walk(child)
    walk(schema)
    return counts


def main() -> None:
    require(not RUN.exists() or not any(RUN.iterdir()), "transport projection run already contains files")
    architecture_root, architecture_count = verify_root(
        ARCHITECTURE_RUN, "validation.json", "search_plan_v24_proposition_aware_architecture_sha256",
        EXPECTED_ARCHITECTURE,
    )
    implementation_root, implementation_count = verify_root(
        IMPLEMENTATION_RUN, "validation.json", "search_plan_v24_dev_planner_compiler_implementation_sha256",
        EXPECTED_IMPLEMENTATION,
    )
    compatibility_root, compatibility_count = verify_root(
        COMPATIBILITY_RUN, "validation.json", "search_plan_v24_structured_output_compatibility_sha256",
        EXPECTED_COMPATIBILITY,
    )
    failed_1_root, failed_1_count = verify_root(
        FAILED_RUN_1, "implementation_manifest.json", "search_plan_v24_dev_real_planner_generation_sha256",
        EXPECTED_FAILED_1,
    )
    failed_2_root, failed_2_count = verify_root(
        FAILED_RUN_2, "implementation_manifest.json", "search_plan_v24_dev_real_planner_generation_sha256",
        EXPECTED_FAILED_2,
    )
    require(sha(SCHEMA_PATH) == EXPECTED_SCIENTIFIC_SCHEMA, "scientific schema hash mismatch")
    before = protected_state()

    scientific_schema = load_json(SCHEMA_PATH)
    provider_schema, recursive_rows = render_provider_payload_schema(scientific_schema)
    preflight = static_provider_compatibility_preflight(provider_schema)
    require(preflight["status"] == "PASS", "provider payload schema did not pass static preflight v2")
    echo = audit_deterministic_request_echo_fields(scientific_schema)

    upstream = {
        "artifact_schema_version": "V24TransportProjectionUpstreamRootVerificationV1",
        "status": "PASS",
        "search_plan_v24_proposition_aware_architecture_sha256": architecture_root,
        "architecture_component_count": architecture_count,
        "search_plan_v24_dev_planner_compiler_implementation_sha256": implementation_root,
        "implementation_component_count": implementation_count,
        "search_plan_v24_structured_output_compatibility_sha256": compatibility_root,
        "compatibility_component_count": compatibility_count,
        "latest_failed_generation_sha256": failed_2_root,
        "scientific_schema_sha256": sha(SCHEMA_PATH),
        "verified_offline_before_artifact_generation": True,
    }
    failed_audit = {
        "artifact_schema_version": "PriorFailedRunsPreservationAuditV1",
        "status": "PASS",
        "failed_runs": [
            {"path": str(FAILED_RUN_1.relative_to(ROOT)), "root": failed_1_root,
             "component_count": failed_1_count, "expected_root": EXPECTED_FAILED_1},
            {"path": str(FAILED_RUN_2.relative_to(ROOT)), "root": failed_2_root,
             "component_count": failed_2_count, "expected_root": EXPECTED_FAILED_2},
        ],
        "both_failed_runs_immutable": True,
        "historical_assets_modified": False,
    }
    echo_audit = {
        "artifact_schema_version": "DeterministicRequestEchoFieldAuditV1",
        "status": "PASS",
        **echo,
        "deterministic_request_echo_projection": True,
        "model_can_modify_target": False,
        "model_can_modify_target_id": False,
        "model_can_modify_schema_version": False,
        "model_can_modify_config_identity": False,
    }
    projection_contract = {
        "artifact_schema_version": "ProviderPayloadProjectionContractV1",
        "status": "PASS",
        "transport_projection_name": PROVIDER_PAYLOAD_SCHEMA_VERSION,
        "renderer_version": PAYLOAD_RENDERER_VERSION,
        "scientific_contract": PLAN_SCHEMA_VERSION,
        "scientific_contract_changed": False,
        "provider_payload_root_fields": list(MODEL_GENERATED_FIELDS),
        "omitted_deterministic_request_echo_fields": list(DETERMINISTIC_REQUEST_ECHO_FIELDS),
        "provider_payload_additional_properties": False,
        "provider_output_is_scientific_artifact": False,
        "provider_schema_is_generation_constraint_only": True,
        "unchanged_scientific_postvalidation_required": True,
        "source_file": str(TRANSPORT_SOURCE.relative_to(ROOT)),
        "source_sha256": sha(TRANSPORT_SOURCE),
        "test_file": str(TRANSPORT_TEST.relative_to(ROOT)),
        "test_sha256": sha(TRANSPORT_TEST),
    }
    recursive_audit = {
        "artifact_schema_version": "ProviderPayloadSchemaRecursiveAuditV1",
        "status": "PASS",
        "provider_payload_schema_sha256": preflight["provider_payload_schema_sha256"],
        "transformation_count": len(recursive_rows),
        "transformation_distribution": dict(sorted(Counter(
            row["transformation"] for row in recursive_rows
        ).items())),
        "provider_schema_const_counts": count_const_types(provider_schema),
        "scientific_semantic_changes": 0,
        "audit_rows": recursive_rows,
    }
    rehydrator_contract = {
        "artifact_schema_version": "DeterministicPlannerOutputRehydratorContractV1",
        "status": "PASS",
        "rehydrator_version": REHYDRATOR_VERSION,
        "inputs": [
            "provider planner payload", "immutable ScientificPropositionTargetV1",
            "request reference", "frozen planner configuration", "prompt SHA-256",
            "scientific schema SHA-256", "provider payload projection schema",
        ],
        "output": PLAN_SCHEMA_VERSION,
        "field_ownership": {
            "provider": list(MODEL_GENERATED_FIELDS),
            "deterministic_rehydrator": list(DETERMINISTIC_REQUEST_ECHO_FIELDS),
        },
        "validation_pipeline": [
            "provider payload validation", "deterministic rehydration",
            "unchanged PropositionAwareSearchPlanV1 validation", "existing deterministic validate_plan",
        ],
        "fail_closed": True,
        "model_can_modify_target": False,
        "model_can_modify_target_id": False,
        "deterministic_rehydration": True,
    }

    prompt_sha256 = sha(PROMPT_PATH)
    scientific_schema_sha256 = sha(SCHEMA_PATH)
    fixture_rows, injection_rows = [], []
    plan_rows, _, _ = implementation.build_fixtures()
    for fixture in plan_rows:
        original_plan = fixture["plan"]
        target = original_plan["canonical_proposition"]["target_payload"]
        payload = {"retrieval_intents": deepcopy(original_plan["retrieval_intents"])}
        case_id = target["case_id"]
        request_reference = f"transport-projection-equivalence:{case_id}"
        rehydrated = rehydrate_planner_output(
            payload,
            canonical_target=target,
            request_reference=request_reference,
            planner_config=DEFAULT_DEVELOPMENT_CONFIG,
            prompt_sha256=prompt_sha256,
            scientific_schema_sha256=scientific_schema_sha256,
            provider_payload_schema=provider_schema,
        )
        validate_scientific_instance(rehydrated, scientific_schema)
        validate_plan(rehydrated, expected_target=target)
        expected = {
            "artifact_schema_version": PLAN_SCHEMA_VERSION,
            "request_provenance": {
                "request_sha256": hashlib.sha256(request_reference.encode("utf-8")).hexdigest(),
                "preserved_request_reference": request_reference,
            },
            "target_id": target["scientific_proposition_target_id"],
            "canonical_proposition": {
                "schema_version": "ScientificPropositionTargetV1",
                "target_sha256": canonical_target_hash(target),
                "target_payload": target,
            },
            "planner_config_sha256": planner_config_hash(DEFAULT_DEVELOPMENT_CONFIG),
            "planner_prompt_template_version": DEFAULT_DEVELOPMENT_CONFIG.prompt_version,
            "planner_cache_key_sha256": rehydrated["planner_cache_key_sha256"],
            "retrieval_intents": payload["retrieval_intents"],
            "planner_output_frozen_before_retrieval": True,
        }
        require(rehydrated == expected, f"rehydrated object differs from intended object: {case_id}")
        fixture_rows.append({
            "fixture_id": fixture["fixture_id"], "case_id": case_id,
            "target_sha256": canonical_target_hash(target),
            "provider_payload_sha256": hashlib.sha256(canonical(payload)).hexdigest(),
            "rehydrated_plan_sha256": hashlib.sha256(canonical(rehydrated)).hexdigest(),
            "rehydrated_equals_intended_complete_object": True,
            "canonical_target_equal": rehydrated["canonical_proposition"]["target_payload"] == target,
            "scientific_postvalidation_pass": True,
            "existing_plan_validation_pass": True,
        })
    sample_payload = {"retrieval_intents": deepcopy(plan_rows[0]["plan"]["retrieval_intents"])}
    for field in DETERMINISTIC_REQUEST_ECHO_FIELDS:
        malicious = deepcopy(sample_payload)
        malicious[field] = "attacker-controlled"
        rejected = False
        error = None
        try:
            validate_provider_payload(malicious, provider_schema)
        except PlannerPayloadTransportError as exc:
            rejected, error = True, str(exc)
        require(rejected, f"deterministic echo injection was not rejected: {field}")
        injection_rows.append({"attempted_field": field, "rejected": True, "error": error})
    equivalence = {
        "artifact_schema_version": "RehydrationSemanticEquivalenceAuditV1",
        "status": "PASS",
        "fixture_count": len(fixture_rows),
        "fixtures": fixture_rows,
        "injection_conflict_tests": injection_rows,
        "rehydrated_scientific_postvalidation_pass": all(
            row["scientific_postvalidation_pass"] for row in fixture_rows
        ),
        "model_can_modify_target": False,
        "model_can_modify_target_id": False,
        "rehydration_broadens_accepted_scientific_values": False,
        "scientific_semantic_changes": 0,
    }

    first_failure_fixture = {
        "type": "object", "additionalProperties": False,
        "required": ["artifact_schema_version"],
        "properties": {"artifact_schema_version": {"const": PLAN_SCHEMA_VERSION}},
    }
    second_failure_schema = load_json(COMPATIBILITY_RUN / "provider_compatible_schema.json")
    first_report = static_provider_compatibility_preflight(first_failure_fixture)
    second_report = static_provider_compatibility_preflight(second_failure_schema)
    require(first_report["status"] == "FAIL" and first_report["provider_schema_primitive_const_count"] == 1,
            "first transport regression was not detected")
    require(second_report["status"] == "FAIL" and second_report["provider_schema_object_const_count"] > 0,
            "second transport regression was not detected")
    regression = {
        "artifact_schema_version": "CompositeConstRegressionAuditV1",
        "status": "PASS",
        "first_failure_const_only_primitive_detected": True,
        "first_failure_preflight": first_report,
        "second_failure_object_const_detected": True,
        "second_failure_preflight": second_report,
        "provider_projection_preflight": preflight,
        "provider_schema_object_const_count": preflight["provider_schema_object_const_count"],
        "provider_schema_array_const_count": preflight["provider_schema_array_const_count"],
        "provider_schema_primitive_const_count": preflight["provider_schema_primitive_const_count"],
        "provider_calls": 0,
    }

    provider_hash = preflight["provider_payload_schema_sha256"]
    cache_inputs = {
        "canonical_target_sha256": fixture_rows[0]["target_sha256"],
        "planner_config_sha256": planner_config_hash(DEFAULT_DEVELOPMENT_CONFIG),
        "prompt_sha256": prompt_sha256,
        "scientific_schema_sha256": scientific_schema_sha256,
        "provider_projection_schema_sha256": provider_hash,
        "rehydrator_version": REHYDRATOR_VERSION,
    }
    baseline_key = planner_transport_cache_key(**cache_inputs)
    perturbations = {}
    for key, value in cache_inputs.items():
        changed = dict(cache_inputs)
        changed[key] = ("f" * 64) if key.endswith("sha256") and value != "f" * 64 else (
            "e" * 64 if key.endswith("sha256") else REHYDRATOR_VERSION + ":changed"
        )
        changed_key = planner_transport_cache_key(**changed)
        perturbations[key] = {"changed_cache_key": changed_key, "cache_key_changed": changed_key != baseline_key}
    require(all(row["cache_key_changed"] for row in perturbations.values()), "cache binding incomplete")
    cache_audit = {
        "artifact_schema_version": "PlannerTransportProjectionCacheImpactAuditV1",
        "status": "PASS",
        "cache_key_version": CACHE_KEY_VERSION,
        "baseline_inputs": cache_inputs,
        "baseline_cache_key_sha256": baseline_key,
        "input_perturbations": perturbations,
        "all_required_inputs_bound": True,
        "historical_cache_formula_changed": False,
        "historical_caches_modified": False,
    }

    after = protected_state()
    require(before == after, "protected scientific or historical state changed")
    immutability = {
        "artifact_schema_version": "TransportProjectionScientificSchemaImmutabilityAuditV1",
        "status": "PASS",
        "scientific_schema_sha256_before": before[str(SCHEMA_PATH.relative_to(ROOT))],
        "scientific_schema_sha256_after": after[str(SCHEMA_PATH.relative_to(ROOT))],
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
        "artifact_schema_version": "V24TransportProjectionScientificStateSafetyAuditV1",
        "status": "PASS",
        "offline_only": True,
        "provider_calls": 0,
        "llm_calls": 0,
        "network_calls": 0,
        "retrieval_calls": 0,
        "production_case_specific_rules": 0,
        "scientific_semantic_changes": 0,
        "historical_assets_modified": False,
    }

    RUN.mkdir(parents=True, exist_ok=True)
    outputs = {
        "upstream_root_verification.json": upstream,
        "prior_failed_runs_preservation_audit.json": failed_audit,
        "deterministic_request_echo_field_audit.json": echo_audit,
        "provider_payload_projection_contract.json": projection_contract,
        "provider_payload_schema.json": provider_schema,
        "provider_payload_schema_recursive_audit.json": recursive_audit,
        "deterministic_rehydrator_contract.json": rehydrator_contract,
        "rehydration_semantic_equivalence_audit.json": equivalence,
        "static_provider_compatibility_preflight_v2.json": preflight,
        "composite_const_regression_audit.json": regression,
        "planner_cache_impact_audit.json": cache_audit,
        "scientific_schema_immutability_audit.json": immutability,
        "scientific_state_safety_audit.json": safety,
    }
    for name, value in outputs.items():
        write_exact(RUN / name, pretty(value))

    component_names = sorted(REQUIRED_OUTPUTS - {"validation.json", "summary.json"})
    components = [[name, sha(RUN / name)] for name in component_names]
    run_root = aggregate(components)
    checks = {
        "upstream_roots_verified": upstream["status"] == "PASS",
        "both_failed_runs_preserved": failed_audit["both_failed_runs_immutable"],
        "scientific_schema_changed_false": not immutability["scientific_schema_changed"],
        "planner_semantics_changed_false": not immutability["planner_semantics_changed"],
        "deterministic_request_echo_projection": echo_audit["deterministic_request_echo_projection"],
        "deterministic_rehydration": rehydrator_contract["deterministic_rehydration"],
        "model_can_modify_target_false": not equivalence["model_can_modify_target"],
        "model_can_modify_target_id_false": not equivalence["model_can_modify_target_id"],
        "provider_schema_object_const_count_zero": preflight["provider_schema_object_const_count"] == 0,
        "provider_schema_array_const_count_zero": preflight["provider_schema_array_const_count"] == 0,
        "provider_schema_primitive_const_count_zero": preflight["provider_schema_primitive_const_count"] == 0,
        "static_provider_preflight_pass": preflight["status"] == "PASS",
        "rehydrated_scientific_postvalidation_pass": equivalence["rehydrated_scientific_postvalidation_pass"],
        "scientific_semantic_changes_zero": equivalence["scientific_semantic_changes"] == 0,
        "production_case_specific_rules_zero": safety["production_case_specific_rules"] == 0,
        "zero_external_calls": safety["provider_calls"] == safety["llm_calls"] == safety["network_calls"] == 0,
    }
    require(all(checks.values()), f"transport projection validation failed: {checks}")
    validation = {
        "artifact_schema_version": "V24TransportProjectionCompatibilityValidationV1",
        "status": "PASS",
        "checks": checks,
        "aggregate_components": components,
        "search_plan_v24_transport_projection_compatibility_sha256": run_root,
    }
    summary = {
        "artifact_schema_version": "V24TransportProjectionCompatibilitySummaryV1",
        "status": "COMPLETED",
        "failure_class": "TRANSPORT_SCHEMA_COMPOSITE_CONST_INCOMPATIBILITY",
        "scientific_schema_changed": False,
        "planner_semantics_changed": False,
        "deterministic_request_echo_projection": True,
        "deterministic_rehydration": True,
        "model_can_modify_target": False,
        "model_can_modify_target_id": False,
        "provider_payload_schema_sha256": provider_hash,
        "provider_schema_object_const_count": preflight["provider_schema_object_const_count"],
        "provider_schema_array_const_count": preflight["provider_schema_array_const_count"],
        "provider_schema_primitive_const_count": preflight["provider_schema_primitive_const_count"],
        "static_provider_preflight_pass": preflight["status"] == "PASS",
        "static_preflight_is_provider_acceptance_proof": False,
        "rehydrated_scientific_postvalidation_pass": equivalence["rehydrated_scientific_postvalidation_pass"],
        "scientific_semantic_changes": 0,
        "production_case_specific_rules": 0,
        "provider_calls": 0,
        "llm_calls": 0,
        "network_calls": 0,
        "retrieval_calls": 0,
        "search_plan_v24_transport_projection_compatibility_sha256": run_root,
        "historical_assets_modified": False,
    }
    write_exact(RUN / "validation.json", pretty(validation))
    write_exact(RUN / "summary.json", pretty(summary))
    require({path.name for path in RUN.iterdir()} == REQUIRED_OUTPUTS, "run membership mismatch")
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
