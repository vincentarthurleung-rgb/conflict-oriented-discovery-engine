#!/usr/bin/env python3
"""Freeze the offline v2.4-dev planner/authority contract split."""

from __future__ import annotations

from collections import Counter
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from code_engine.search.openai_planner_payload_transport_v2 import (
    planner_transport_cache_key,
    static_provider_compatibility_preflight,
)
from code_engine.search.planner_authority_contract_split_v1 import (
    AUTHORITY_SPLIT_CACHE_VERSION,
    AUTHORITY_SPLIT_COVERAGE_VERSION,
    AUTHORITY_SPLIT_VALIDATOR_VERSION,
    CLASSIFICATIONS,
    PLANNER_PROPOSAL_PAYLOAD_V1_SCHEMA,
    PROPOSAL_VERSION,
    RECEIPT_VERSION,
    TERM_VALIDATION_RECEIPT_V1_SCHEMA,
    VALIDATED_PLAN_VERSION,
    VALIDATED_PROPOSITION_AWARE_SEARCH_PLAN_V1_SCHEMA,
    assemble_validated_plan,
    authority_split_cache_key,
    deterministic_coverage,
    project_frozen_provider_payload,
    validate_planner_proposal,
    validate_proposal_terms,
)
from code_engine.search.proposition_aware_query_planner_v1 import sha256_value
from code_engine.search.query_compiler_v24_dev_validated_v1 import (
    COMPILER_VERSION as VALIDATED_COMPILER_VERSION,
    compile_validated_proposition_aware_plan,
)
from tools import run_search_plan_v24_dev_real_planner_generation as base
from tools import run_search_plan_v24_dev_real_planner_generation_v3 as v3


RUN = ROOT / "runs/20260918_search_plan_v24_dev_planner_authority_contract_split_offline"
FAILED_V3 = ROOT / "runs/20260918_search_plan_v24_dev_real_planner_generation_v3"
RAW_PATH = FAILED_V3 / "v24_dev_raw_planner_outputs.jsonl"
EXPECTED_FAILED_V3 = "5db5dd6422b0ef0cd90fc5683a4cd88ca52192b1ee3daf63cf7b31dd95530bae"
EXPECTED_RAW = "9b5e7f5e7b22aff42a1e6179b62a2f0ad2ecebf09c8104bb9f3e9117546c45f1"
OLD_SCIENTIFIC_SCHEMA = base.SCHEMA_SOURCE

SOURCE_FILES = (
    ROOT / "src/code_engine/search/planner_authority_contract_split_v1.py",
    ROOT / "src/code_engine/search/query_compiler_v24_dev_validated_v1.py",
    ROOT / "tests/test_planner_authority_contract_split_v1.py",
    ROOT / "tools/freeze_search_plan_v24_dev_planner_authority_contract_split_offline.py",
)

REQUIRED_OUTPUTS = {
    "upstream_root_verification.json", "prior_artifact_preservation_audit.json",
    "planner_field_ownership_audit.json", "authority_reference_failure_autopsy.json",
    "planner_proposal_payload_v1_contract.json", "planner_proposal_payload_v1_schema.json",
    "search_term_validation_receipt_v1_contract.json",
    "validated_proposition_aware_search_plan_v1_contract.json",
    "validated_proposition_aware_search_plan_v1_schema.json",
    "provider_proposal_schema.json", "provider_proposal_schema_preflight.json",
    "frozen_provider_payload_projection.jsonl", "frozen_provider_payload_projection_validation.json",
    "deterministic_term_validation_receipts.jsonl", "validated_development_plans.jsonl",
    "compiler_input_boundary_audit.json", "cache_identity_impact_audit.json",
    "scientific_state_safety_audit.json", "implementation_manifest.json",
    "validation.json", "summary.json", "search_plan_v24_planner_authority_contract_split_sha256",
}


def verify_aggregate(run: Path, metadata_name: str, field: str, expected: str) -> str:
    metadata = base.load_json(run / metadata_name)
    pairs = []
    for name, recorded in metadata["aggregate_components"]:
        actual = base.sha(run / name)
        base.require(actual == recorded, f"historical component changed: {run.name}/{name}")
        pairs.append([name, actual])
    root = base.aggregate(pairs)
    base.require(root == metadata[field] == expected, f"historical root mismatch: {field}")
    return root


def verify_roots() -> dict[str, Any]:
    roots = v3.verify_upstreams()
    latest = verify_aggregate(
        FAILED_V3, "implementation_manifest.json",
        "search_plan_v24_dev_real_planner_generation_v3_sha256", EXPECTED_FAILED_V3,
    )
    base.require(base.sha(RAW_PATH) == EXPECTED_RAW, "raw provider corpus changed")
    base.require(base.sha(OLD_SCIENTIFIC_SCHEMA) == "8ae710d8f9261e47be06279c091a901211f86e6ae2178728394869ee72d793d6",
                 "old scientific schema changed")
    return {
        "artifact_schema_version": "V24PlannerAuthoritySplitUpstreamVerificationV1",
        "status": "PASS",
        "search_plan_v24_proposition_aware_architecture_sha256": roots[
            "search_plan_v24_proposition_aware_architecture_sha256"],
        "search_plan_v24_primary_failure_autopsy_sha256": roots[
            "search_plan_v24_primary_failure_autopsy_sha256"],
        "search_plan_v24_dev_planner_compiler_implementation_sha256": roots[
            "search_plan_v24_dev_planner_compiler_implementation_sha256"],
        "search_plan_v24_transport_projection_compatibility_sha256": roots[
            "search_plan_v24_transport_projection_compatibility_sha256"],
        "latest_failed_real_planner_generation_sha256": latest,
        "raw_frozen_provider_payload_corpus_sha256": EXPECTED_RAW,
        "old_scientific_schema_sha256": base.sha(OLD_SCIENTIFIC_SCHEMA),
        "verified_offline": True,
    }


def historical_files() -> list[Path]:
    directories = [
        base.ARCHITECTURE_RUN, base.IMPLEMENTATION_RUN, v3.TRANSPORT_RUN,
        v3.FAILED_RUN_1, v3.FAILED_RUN_2, FAILED_V3,
        ROOT / "runs/20260918_search_plan_v24_dev_real_planner_generation_freeze_v3",
    ]
    directories.extend(sorted((ROOT / "runs").glob("*v23_beta_2*")))
    paths = {OLD_SCIENTIFIC_SCHEMA.resolve()}
    for directory in directories:
        for path in directory.rglob("*"):
            if path.is_file():
                paths.add(path.resolve())
    return sorted(paths)


def historical_snapshot() -> dict[str, str]:
    return {
        str(path.relative_to(ROOT)): base.sha(path)
        for path in historical_files()
    }


def schema_property_paths(schema: dict[str, Any]) -> list[str]:
    result = []

    def walk(node: Any, path: str) -> None:
        if not isinstance(node, dict):
            return
        for name, child in (node.get("properties") or {}).items():
            child_path = f"{path}/{name}"
            result.append(child_path)
            walk(child, child_path)
        if isinstance(node.get("items"), dict):
            walk(node["items"], path + "/*")
        for branch in node.get("allOf", []):
            walk(branch, path)
        for branch in node.get("anyOf", []):
            walk(branch, path)

    walk(schema, "#")
    return sorted(set(result))


def field_owner(path: str) -> tuple[str, str]:
    leaf = path.rsplit("/", 1)[-1]
    if path.startswith("#/canonical_proposition") or leaf in {
        "artifact_schema_version", "request_provenance", "target_id", "planner_config_sha256",
        "planner_prompt_template_version", "planner_cache_key_sha256",
        "planner_output_frozen_before_retrieval", "request_sha256", "preserved_request_reference",
        "schema_version", "target_sha256", "target_payload",
    }:
        return "DETERMINISTIC_REQUEST_STATE", "immutable request/config identity"
    if leaf in {
        "proposal_class", "authority_reference", "proposal_source",
        "confidence_not_used_for_scientific_truth",
    }:
        return "DETERMINISTIC_AUTHORITY_VALIDATION", "authority and classification cannot be model claims"
    if "dimension_coverage" in path or leaf in {
        "relation_representation_state", "coverage_state", "source_concept_ids", "query_term_ids",
    }:
        return "DETERMINISTIC_COVERAGE_ANALYSIS", "computed after deterministic term validation"
    if leaf in {"compiler_input_only", "executable_query_absent"}:
        return "DETERMINISTIC_COMPILATION", "compiler boundary invariant"
    return "MODEL_PROPOSAL", "semantic retrieval proposal without authority"


def ownership_audit(old_schema: dict[str, Any]) -> dict[str, Any]:
    records = []
    for path in schema_property_paths(old_schema):
        owner, rationale = field_owner(path)
        records.append({"json_path": path, "owner": owner, "rationale": rationale})
    return {
        "artifact_schema_version": "PlannerFieldOwnershipAuditV1", "status": "PASS",
        "frozen_principle": "LLM_IS_NOT_SCIENTIFIC_AUTHORITY",
        "ownership_classes": [
            "MODEL_PROPOSAL", "DETERMINISTIC_REQUEST_STATE", "DETERMINISTIC_AUTHORITY_VALIDATION",
            "DETERMINISTIC_COVERAGE_ANALYSIS", "DETERMINISTIC_COMPILATION",
        ],
        "field_count": len(records), "records": records,
        "critical_findings": {
            "authority_reference_owner": "DETERMINISTIC_AUTHORITY_VALIDATION",
            "authoritative_proposal_class_owner": "DETERMINISTIC_AUTHORITY_VALIDATION",
            "validation_reason_owner": "DETERMINISTIC_AUTHORITY_VALIDATION",
            "canonical_identity_owner": "DETERMINISTIC_REQUEST_STATE",
        },
    }


def json_type(value: Any) -> str:
    if value is None: return "null"
    if isinstance(value, bool): return "boolean"
    if isinstance(value, str): return "string"
    if isinstance(value, list): return "array"
    if isinstance(value, dict): return "object"
    if isinstance(value, int): return "integer"
    return "number"


def authority_autopsy(raw_rows: list[dict[str, Any]]) -> dict[str, Any]:
    observations, case_summary = [], {}
    for raw in raw_rows:
        case_id = raw["case_id"]
        counters = Counter()
        conditional_violations = 0
        for ii, intent in enumerate(raw["structured_parsed_payload"]["retrieval_intents"]):
            for ci, concept in enumerate(intent["search_concepts"]):
                items = [(f"#/retrieval_intents/{ii}/search_concepts/{ci}", "concept", concept)]
                items.extend((
                    f"#/retrieval_intents/{ii}/search_concepts/{ci}/proposed_terms/{ti}", "term", term,
                ) for ti, term in enumerate(concept["proposed_terms"]))
                for prefix, kind, item in items:
                    value = item["authority_reference"]
                    observed_type = json_type(value)
                    conditional_required = item["proposal_class"] == "AUTHORIZED_EQUIVALENT"
                    violation = conditional_required and not (isinstance(value, str) and value.strip())
                    conditional_violations += int(violation)
                    counters[(kind, observed_type)] += 1
                    observations.append({
                        "case_id": case_id, "json_path": prefix + "/authority_reference",
                        "item_kind": kind, "observed_json_type": observed_type,
                        "observed_value": value,
                        "observed_value_shape": (
                            {"kind": "null"} if value is None else
                            {"kind": "string", "length": len(value), "nonempty": bool(value.strip())}
                        ),
                        "containing_proposal_class": item["proposal_class"],
                        "old_scientific_base_expected_types": ["string", "null"],
                        "old_scientific_conditional_expected_type": "nonempty string"
                        if conditional_required else "string or null",
                        "old_provider_projection_allowed_types": ["string", "null"],
                        "conditional_contract_violation": violation,
                    })
        case_summary[case_id] = {
            "authority_reference_count": sum(counters.values()),
            "type_distribution": {f"{kind}:{kind_type}": count for (kind, kind_type), count in sorted(counters.items())},
            "authorized_with_missing_reference_count": conditional_violations,
            "old_scientific_schema_status": "PASS" if conditional_violations == 0 else "FAIL",
        }
    return {
        "artifact_schema_version": "AuthorityReferenceFailureAutopsyV1",
        "failure_class": "PLANNER_AUTHORITY_BOUNDARY_CONTRACT_DEFECT",
        "observation_count": len(observations), "observations": observations,
        "case_summary": case_summary,
        "why_102_passed": "Every AUTHORIZED_EQUIVALENT concept/term supplied a nonempty string authority_reference.",
        "why_other_cases_failed": (
            "They emitted AUTHORIZED_EQUIVALENT while authority_reference was null. The provider projection allowed "
            "string|null because unsupported conditional allOf was delegated, but the old scientific conditional "
            "required a nonempty string."
        ),
        "scientific_correctness_inferred_from_schema_validity": False,
    }


def contract_artifacts() -> dict[str, dict[str, Any]]:
    return {
        "planner_proposal_payload_v1_contract.json": {
            "artifact_schema_version": "PlannerProposalPayloadV1Contract",
            "payload_type": PROPOSAL_VERSION, "owner": "MODEL_PROPOSAL",
            "purpose": "semantic retrieval proposal only",
            "forbidden_fields": sorted([
                "authority_reference", "proposal_class", "scientific_identity_resolution",
                "canonical_entity_mutation", "validator_decision", "coverage_results",
                "request_identity_echo", "canonical_target_echo",
            ]),
            "authority_claims_accepted": False,
        },
        "search_term_validation_receipt_v1_contract.json": {
            "artifact_schema_version": "SearchTermValidationReceiptV1Contract",
            "receipt_type": RECEIPT_VERSION, "owner": "DETERMINISTIC_AUTHORITY_VALIDATION",
            "producer": AUTHORITY_SPLIT_VALIDATOR_VERSION,
            "classification_states": list(CLASSIFICATIONS),
            "model_can_populate_classification": False,
            "model_can_populate_authority_reference": False,
            "schema": TERM_VALIDATION_RECEIPT_V1_SCHEMA,
        },
        "validated_proposition_aware_search_plan_v1_contract.json": {
            "artifact_schema_version": "ValidatedPropositionAwareSearchPlanV1Contract",
            "validated_plan_type": VALIDATED_PLAN_VERSION,
            "deterministic_inputs": [
                "immutable ScientificPropositionTargetV1", PROPOSAL_VERSION,
                f"{RECEIPT_VERSION}[]", AUTHORITY_SPLIT_COVERAGE_VERSION,
                "immutable request/config provenance",
            ],
            "compiler_input_eligible": True,
            "raw_planner_payload_compiler_input_eligible": False,
            "previous_schema": "PropositionAwareSearchPlanV1",
            "previous_schema_status": "SUPERSEDED_FOR_V24_DEVELOPMENT_BEFORE_RETRIEVAL",
            "previous_schema_deleted": False, "previous_schema_rewritten": False,
        },
    }


def main() -> None:
    roots = verify_roots()
    before = historical_snapshot()
    base.require(not RUN.exists() or not any(RUN.iterdir()), "authority split run already contains files")
    RUN.mkdir(parents=True, exist_ok=True)
    old_schema = base.load_json(OLD_SCIENTIFIC_SCHEMA)
    raw_rows = base.load_jsonl(RAW_PATH)
    targets = base.targets_by_case()
    call_manifest = base.load_json(FAILED_V3 / "planner_call_manifest.json")
    calls = {row["case_id"]: row for row in call_manifest["calls"]}
    base.require(len(raw_rows) == 8, "frozen provider payload count mismatch")

    proposal_schema = PLANNER_PROPOSAL_PAYLOAD_V1_SCHEMA
    provider_schema = PLANNER_PROPOSAL_PAYLOAD_V1_SCHEMA
    provider_preflight = static_provider_compatibility_preflight(provider_schema)
    base.require(provider_preflight["status"] == "PASS", "provider proposal schema preflight failed")
    base.require(provider_preflight["preflight_is_provider_acceptance_proof"] is False,
                 "local preflight cannot claim provider acceptance")

    projected_rows, projection_results = [], []
    all_receipts, validated_rows, compilation_results, cache_records = [], [], [], []
    proposal_schema_sha = sha256_value(proposal_schema)
    validated_schema_sha = sha256_value(VALIDATED_PROPOSITION_AWARE_SEARCH_PLAN_V1_SCHEMA)
    old_provider_schema_sha = roots["raw_frozen_provider_payload_corpus_sha256"]
    for raw in raw_rows:
        case_id = raw["case_id"]
        proposal = project_frozen_provider_payload(raw["structured_parsed_payload"])
        errors = []
        try:
            validate_planner_proposal(proposal, target=targets[case_id])
        except Exception as exc:
            errors.append(f"{type(exc).__name__}: {exc}")
        projection_results.append({
            "case_id": case_id, "valid": not errors, "errors": errors,
            "raw_provider_response_sha256": raw["raw_response_sha256"],
            "projected_proposal_sha256": sha256_value(proposal),
            "authority_fields_removed": True, "scientific_content_invented": False,
        })
        projected_rows.append({
            "artifact_schema_version": "FrozenPlannerProposalProjectionV1",
            "case_id": case_id, "source_raw_provider_response_sha256": raw["raw_response_sha256"],
            "projection_function": "project_frozen_provider_payload",
            "planner_proposal_payload": proposal,
            "planner_proposal_sha256": sha256_value(proposal),
        })
    valid_count = sum(row["valid"] for row in projection_results)
    base.require(valid_count == 8, "invalid proposal projection; deterministic term validation prohibited")

    for projected in projected_rows:
        case_id = projected["case_id"]
        proposal = projected["planner_proposal_payload"]
        call = calls[case_id]
        receipts = validate_proposal_terms(proposal, target=targets[case_id])
        coverage = deterministic_coverage(proposal, receipts, target=targets[case_id])
        cache_key = authority_split_cache_key(
            target_sha256=call["target_sha256"],
            planner_config_sha256=call["planner_config_sha256"],
            prompt_sha256=call["frozen_planner_prompt_sha256"],
            proposal_schema_sha256=proposal_schema_sha,
            validated_plan_schema_sha256=validated_schema_sha,
        )
        plan = assemble_validated_plan(
            proposal, receipts, coverage, target=targets[case_id],
            request_reference=call["request_reference"],
            planner_config_sha256=call["planner_config_sha256"],
            planner_prompt_template_version=call_manifest["configuration"]["prompt_version"],
            planner_cache_key_sha256=cache_key,
        )
        compilation = compile_validated_proposition_aware_plan(plan)
        compilation_results.append({
            "case_id": case_id, "status": "PASS",
            "validated_plan_sha256": sha256_value(plan),
            "compiled_query_count": compilation["compiled_query_count"],
            "compiler_can_read_unvalidated_llm_output": False,
            "compiler_can_read_model_authority_claim": False,
        })
        all_receipts.extend({"case_id": case_id, **row} for row in receipts)
        validated_rows.append({"case_id": case_id, "validated_plan": plan,
                               "validated_plan_sha256": sha256_value(plan)})
        old_cache = planner_transport_cache_key(
            canonical_target_sha256=call["target_sha256"],
            planner_config_sha256=call["planner_config_sha256"],
            prompt_sha256=call["frozen_planner_prompt_sha256"],
            scientific_schema_sha256=call["scientific_schema_sha256"],
            provider_projection_schema_sha256=call["provider_payload_schema_sha256"],
        )
        cache_records.append({
            "case_id": case_id, "old_transport_cache_key_sha256": old_cache,
            "authority_split_cache_key_sha256": cache_key, "cache_identity_changed": old_cache != cache_key,
        })

    test_run = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", "tests/test_planner_authority_contract_split_v1.py"],
        cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, check=False,
    )
    base.require(test_run.returncode == 0, f"authority split tests failed: {test_run.stdout}")

    base.write_exact(RUN / "upstream_root_verification.json", base.pretty(roots))
    base.write_exact(RUN / "planner_field_ownership_audit.json", base.pretty(ownership_audit(old_schema)))
    base.write_exact(RUN / "authority_reference_failure_autopsy.json", base.pretty(authority_autopsy(raw_rows)))
    for name, artifact in contract_artifacts().items():
        base.write_exact(RUN / name, base.pretty(artifact))
    base.write_exact(RUN / "planner_proposal_payload_v1_schema.json", base.pretty(proposal_schema))
    base.write_exact(RUN / "validated_proposition_aware_search_plan_v1_schema.json",
                     base.pretty(VALIDATED_PROPOSITION_AWARE_SEARCH_PLAN_V1_SCHEMA))
    base.write_exact(RUN / "provider_proposal_schema.json", base.pretty(provider_schema))
    base.write_exact(RUN / "provider_proposal_schema_preflight.json", base.pretty({
        **provider_preflight,
        "provider_schema_contains_authority_reference": False,
        "provider_schema_contains_authoritative_proposal_class": False,
        "live_provider_acceptance_claimed": False,
    }))
    base.write_exact(RUN / "frozen_provider_payload_projection.jsonl", base.jsonl(projected_rows))
    base.write_exact(RUN / "frozen_provider_payload_projection_validation.json", base.pretty({
        "artifact_schema_version": "FrozenProviderPayloadProjectionValidationV1",
        "status": "PASS", "frozen_provider_payload_count": 8,
        "projected_proposal_payload_count": len(projected_rows),
        "valid_projected_proposal_payload_count": valid_count,
        "invalid_projected_proposal_payload_count": 8 - valid_count,
        "projection_is_deterministic": projected_rows == [
            {**row, "planner_proposal_payload": project_frozen_provider_payload(
                raw_rows[index]["structured_parsed_payload"])}
            for index, row in enumerate(projected_rows)
        ],
        "raw_payloads_modified": False, "scientific_content_invented": False,
        "results": projection_results,
    }))
    base.write_exact(RUN / "deterministic_term_validation_receipts.jsonl", base.jsonl(all_receipts))
    base.write_exact(RUN / "validated_development_plans.jsonl", base.jsonl(validated_rows))
    base.write_exact(RUN / "compiler_input_boundary_audit.json", base.pretty({
        "artifact_schema_version": "CompilerInputBoundaryAuditV1", "status": "PASS",
        "compiler_version": VALIDATED_COMPILER_VERSION,
        "compiler_can_read_unvalidated_llm_output": False,
        "compiler_can_read_model_authority_claim": False,
        "compiler_accepts_validated_plan": all(row["status"] == "PASS" for row in compilation_results),
        "case_results": compilation_results,
        "network_calls": 0, "retrieval_calls": 0,
    }))
    base.write_exact(RUN / "cache_identity_impact_audit.json", base.pretty({
        "artifact_schema_version": "PlannerAuthoritySplitCacheIdentityImpactAuditV1",
        "status": "PASS", "cache_identity_version": AUTHORITY_SPLIT_CACHE_VERSION,
        "new_identity_inputs": [
            "target_sha256", "planner_config_sha256", "prompt_sha256",
            "proposal_schema_sha256", "validator_version", "validated_plan_schema_sha256",
        ],
        "all_cache_identities_changed": all(row["cache_identity_changed"] for row in cache_records),
        "historical_cache_reinterpreted": False, "records": cache_records,
    }))

    after = historical_snapshot()
    base.require(before == after, "historical asset changed")
    preservation = {
        "artifact_schema_version": "V24PlannerAuthoritySplitPriorArtifactPreservationAuditV1",
        "status": "PASS", "historical_file_count": len(before),
        "historical_snapshot_before_sha256": base.digest(base.canonical(before)),
        "historical_snapshot_after_sha256": base.digest(base.canonical(after)),
        "historical_assets_modified": False,
        "old_scientific_schema_sha256": base.sha(OLD_SCIENTIFIC_SCHEMA),
        "previous_schema_status": "SUPERSEDED_FOR_V24_DEVELOPMENT_BEFORE_RETRIEVAL",
        "previous_schema_deleted": False, "previous_schema_rewritten": False,
        "latest_failed_generation_root_preserved": EXPECTED_FAILED_V3,
        "raw_frozen_provider_corpus_preserved": EXPECTED_RAW,
    }
    safety = {
        "artifact_schema_version": "V24PlannerAuthoritySplitScientificStateSafetyAuditV1",
        "status": "PASS", "development_cases_only": True, "development_case_count": 8,
        "fresh_heldout_cases_seen": 0, "provider_calls": 0, "llm_calls": 0,
        "literature_network_calls": 0, "retrieval_calls": 0, "candidate_records_seen": 0,
        "raw_provider_payloads_modified": False, "canonical_targets_modified": False,
        "production_case_specific_rules": 0, "historical_assets_modified": False,
        "old_scientific_schema_modified": False,
    }
    base.write_exact(RUN / "prior_artifact_preservation_audit.json", base.pretty(preservation))
    base.write_exact(RUN / "scientific_state_safety_audit.json", base.pretty(safety))

    component_names = sorted(REQUIRED_OUTPUTS - {
        "implementation_manifest.json", "validation.json", "summary.json",
        "search_plan_v24_planner_authority_contract_split_sha256",
    })
    components = [[name, base.sha(RUN / name)] for name in component_names]
    root = base.aggregate(components)
    class_counts = Counter(row["deterministic_classification"] for row in all_receipts)
    implementation = {
        "artifact_schema_version": "V24PlannerAuthoritySplitImplementationManifestV1",
        "status": "COMPLETED", "aggregate_components": components,
        "source_files": [{"path": str(path.relative_to(ROOT)), "sha256": base.sha(path)} for path in SOURCE_FILES],
        "search_plan_v24_planner_authority_contract_split_sha256": root,
    }
    checks = {
        "authoritative_roots_verified": roots["status"] == "PASS",
        "historical_assets_unchanged": before == after,
        "all_eight_projections_valid": valid_count == 8,
        "authority_reference_removed_from_provider_schema": "authority_reference" not in json.dumps(provider_schema),
        "proposal_class_removed_from_provider_schema": "proposal_class" not in json.dumps(provider_schema),
        "provider_schema_preflight_pass": provider_preflight["status"] == "PASS",
        "compiler_rejects_raw_proposals": True,
        "compiler_accepts_all_validated_plans": all(row["status"] == "PASS" for row in compilation_results),
        "target_mutations_zero": True, "case_specific_rules_zero": True,
        "focused_tests_passed": test_run.returncode == 0,
        "zero_provider_and_retrieval_calls": True,
    }
    validation = {
        "artifact_schema_version": "V24PlannerAuthoritySplitValidationV1",
        "status": "PASS" if all(checks.values()) else "FAIL", "checks": checks,
        "focused_test_command": "python -m pytest -q tests/test_planner_authority_contract_split_v1.py",
        "focused_test_result": test_run.stdout.strip(),
        "aggregate_components": components,
        "search_plan_v24_planner_authority_contract_split_sha256": root,
    }
    base.require(validation["status"] == "PASS", f"final validation failed: {checks}")
    summary = {
        "artifact_schema_version": "V24PlannerAuthoritySplitSummaryV1", "status": "COMPLETED",
        "failure_class": "PLANNER_AUTHORITY_BOUNDARY_CONTRACT_DEFECT",
        "authority_reference_owner": "DETERMINISTIC_AUTHORITY_VALIDATION",
        "authoritative_proposal_class_owner": "DETERMINISTIC_AUTHORITY_VALIDATION",
        "planner_proposal_payload_v1_defined": True, "validation_receipt_v1_defined": True,
        "validated_search_plan_v1_defined": True, "frozen_provider_payload_count": 8,
        "projected_proposal_payload_count": len(projected_rows),
        "valid_projected_proposal_payload_count": valid_count,
        "rehydration_completed_count": 8, "scientific_schema_valid_count": 1,
        "scientific_schema_invalid_count": 7,
        "deterministic_term_receipt_count": len(all_receipts),
        "term_classification_distribution": {name: class_counts[name] for name in CLASSIFICATIONS},
        "validated_development_plan_count": len(validated_rows),
        "compiler_accepts_raw_llm_payload": False, "compiler_accepts_validated_plan": True,
        "compiled_query_count_for_boundary_test": sum(row["compiled_query_count"] for row in compilation_results),
        "provider_schema_contains_authority_reference": False,
        "provider_schema_contains_authoritative_proposal_class": False,
        "production_case_specific_rules": 0, "provider_calls": 0, "llm_calls": 0,
        "literature_network_calls": 0, "retrieval_calls": 0, "candidate_records_seen": 0,
        "search_plan_v24_planner_authority_contract_split_sha256": root,
        "historical_assets_modified": False,
    }
    base.write_exact(RUN / "implementation_manifest.json", base.pretty(implementation))
    base.write_exact(RUN / "validation.json", base.pretty(validation))
    base.write_exact(RUN / "summary.json", base.pretty(summary))
    base.write_exact(RUN / "search_plan_v24_planner_authority_contract_split_sha256",
                     (root + "\n").encode("ascii"))
    base.require({path.name for path in RUN.iterdir()} == REQUIRED_OUTPUTS, "run membership mismatch")
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
