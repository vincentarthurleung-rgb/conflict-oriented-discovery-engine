#!/usr/bin/env python3
"""Project the sealed v3 planner failure into the protocol-named run directory."""

from __future__ import annotations

import json
from pathlib import Path
import shutil
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from code_engine.search.openai_planner_payload_transport_v2 import (
    REHYDRATOR_VERSION,
    rehydrate_planner_output,
    render_provider_payload_schema,
)
from code_engine.search.proposition_aware_query_planner_v1 import DEFAULT_DEVELOPMENT_CONFIG
from tools import run_search_plan_v24_dev_real_planner_generation as base
from tools import run_search_plan_v24_dev_real_planner_generation_v3 as v3


SOURCE = ROOT / "runs/20260918_search_plan_v24_dev_real_planner_generation_freeze_v3"
DEST = ROOT / "runs/20260918_search_plan_v24_dev_real_planner_generation_v3"
EXPECTED_SOURCE_ROOT = "57a1de64ea969c8404e3a7d25b19bdf99cf01c871b2c1294efdb202929cd5b00"

COPIED = {
    "upstream_root_verification.json",
    "transport_root_verification.json",
    "provider_schema_preflight_manifest.json",
    "planner_call_manifest.json",
    "planner_workspace_isolation_audit.json",
    "v24_dev_raw_planner_outputs.jsonl",
    "v24_dev_raw_planner_outputs_sha256",
    "provider_payload_validation.json",
    "v24_dev_rehydrated_planner_outputs.jsonl",
    "v24_dev_rehydrated_planner_outputs_sha256",
    "scientific_postvalidation.json",
    "scientific_state_safety_audit.json",
}

GENERATED = {
    "prior_failed_runs_preservation_audit.json",
    "rehydration_validation.json",
    "implementation_manifest.json",
    "validation.json",
    "summary.json",
    "search_plan_v24_dev_real_planner_generation_v3_sha256",
}

MISSING_DUE_FAIL_CLOSED = {
    "retrieval_intent_summary.json",
    "validated_search_terms.jsonl",
    "search_term_classification_summary.json",
    "retrieval_plan_coverage_analysis.json",
    "relation_coverage_analysis.json",
    "biological_unit_coverage_analysis.json",
    "search_only_expansion_audit.json",
    "v24_dev_compiled_queries.jsonl",
    "v24_dev_compiled_queries_sha256",
    "query_provenance_trace.json",
    "human_readable_query_plan_review.md",
    "v23_v24_structural_coverage_comparison.json",
}


def verify_source() -> dict[str, Any]:
    manifest = base.load_json(SOURCE / "implementation_manifest.json")
    pairs = []
    for name, recorded in manifest["aggregate_components"]:
        actual = base.sha(SOURCE / name)
        base.require(actual == recorded, f"source component changed: {name}")
        pairs.append([name, actual])
    actual_root = base.aggregate(pairs)
    base.require(actual_root == manifest["search_plan_v24_dev_real_planner_generation_v3_sha256"],
                 "source aggregate mismatch")
    base.require(actual_root == EXPECTED_SOURCE_ROOT, "unexpected source failure root")
    summary = base.load_json(SOURCE / "summary.json")
    base.require(summary["status"] == "FAILED_CLOSED", "source is not failed closed")
    base.require(summary["provider_requests_attempted"] == 8, "source request count mismatch")
    base.require(summary["provider_calls_completed"] == 8, "source completion count mismatch")
    base.require(summary["scientific_postvalidation_failures"] == 7,
                 "source postvalidation count mismatch")
    return {"source_root": actual_root, "source_summary": summary}


def copy_physical(name: str) -> None:
    source = SOURCE / name
    target = DEST / name
    base.require(source.is_file() and not source.is_symlink(), f"invalid source file: {name}")
    if target.exists():
        base.require(target.is_file() and not target.is_symlink(), f"invalid existing copy: {name}")
        base.require(base.sha(target) == base.sha(source), f"existing copy differs: {name}")
        return
    shutil.copyfile(source, target)
    base.require(target.is_file() and not target.is_symlink(), f"non-physical copy: {name}")
    base.require(base.sha(target) == base.sha(source), f"copy differs: {name}")


def build_rehydration_validation() -> dict[str, Any]:
    raw_rows = base.load_jsonl(DEST / "v24_dev_raw_planner_outputs.jsonl")
    calls = base.load_json(DEST / "planner_call_manifest.json")["calls"]
    calls_by_case = {row["case_id"]: row for row in calls}
    targets = base.targets_by_case()
    scientific_schema = base.load_json(base.SCHEMA_SOURCE)
    provider_schema, _ = render_provider_payload_schema(scientific_schema)
    results = []
    for raw in raw_rows:
        case_id = raw["case_id"]
        call = calls_by_case[case_id]
        errors = []
        plan = None
        try:
            plan = rehydrate_planner_output(
                raw["structured_parsed_payload"],
                canonical_target=targets[case_id],
                request_reference=call["request_reference"],
                planner_config=DEFAULT_DEVELOPMENT_CONFIG,
                prompt_sha256=call["frozen_planner_prompt_sha256"],
                scientific_schema_sha256=call["scientific_schema_sha256"],
                provider_payload_schema=provider_schema,
            )
        except Exception as exc:
            errors.append(f"{type(exc).__name__}: {exc}")
        target_unchanged = bool(
            plan is not None
            and plan["target_id"] == targets[case_id]["scientific_proposition_target_id"]
            and plan["canonical_proposition"]["target_sha256"] == call["target_sha256"]
            and plan["canonical_proposition"]["target_payload"] == targets[case_id]
        )
        results.append({
            "case_id": case_id,
            "deterministic_rehydration_completed": plan is not None and not errors,
            "canonical_target_unchanged": target_unchanged,
            "model_controlled_deterministic_echo_fields": 0,
            "errors": errors,
        })
    return {
        "artifact_schema_version": "V24DevRehydrationValidationV1",
        "status": "PASS" if all(row["deterministic_rehydration_completed"]
                                  and row["canonical_target_unchanged"] for row in results) else "FAIL",
        "rehydrator_version": REHYDRATOR_VERSION,
        "provider_payload_count": len(raw_rows),
        "valid_rehydrated_plans": sum(row["deterministic_rehydration_completed"] for row in results),
        "rehydration_invariant_failures": sum(not row["deterministic_rehydration_completed"]
                                              for row in results),
        "model_target_mutations": sum(not row["canonical_target_unchanged"] for row in results),
        "results": results,
        "note": "Scientific schema validation is recorded separately and failed closed for seven plans.",
    }


def main() -> None:
    source = verify_source()
    roots = v3.verify_upstreams()
    if DEST.exists():
        base.require({path.name for path in DEST.iterdir()} <= COPIED | GENERATED,
                     "protocol-named run directory contains an unexpected file")
        base.require(all(path.is_file() and not path.is_symlink() for path in DEST.iterdir()),
                     "protocol-named run directory contains a non-physical file")
    DEST.mkdir(parents=True, exist_ok=True)
    for name in sorted(COPIED):
        copy_physical(name)

    prior_audit = {
        "artifact_schema_version": "V24DevPriorFailedRunsPreservationAuditV1",
        "status": "PASS",
        "first_failed_generation_root": v3.EXPECTED_FAILED_1,
        "second_failed_generation_root": v3.EXPECTED_FAILED_2,
        "first_failed_generation_unchanged": True,
        "second_failed_generation_unchanged": True,
        "overwritten": False,
        "resumed": False,
        "reinterpreted": False,
    }
    rehydration = build_rehydration_validation()
    base.require(rehydration["status"] == "PASS", "deterministic rehydration audit failed")
    base.write_exact(DEST / "prior_failed_runs_preservation_audit.json", base.pretty(prior_audit))
    base.write_exact(DEST / "rehydration_validation.json", base.pretty(rehydration))

    component_names = sorted((COPIED | {
        "prior_failed_runs_preservation_audit.json", "rehydration_validation.json",
    }))
    components = [[name, base.sha(DEST / name)] for name in component_names]
    run_root = base.aggregate(components)
    raw_root = (DEST / "v24_dev_raw_planner_outputs_sha256").read_text(encoding="ascii").strip()
    partial_rehydrated_root = (DEST / "v24_dev_rehydrated_planner_outputs_sha256").read_text(
        encoding="ascii").strip()
    postvalidation = base.load_json(DEST / "scientific_postvalidation.json")
    safety = base.load_json(DEST / "scientific_state_safety_audit.json")

    implementation = {
        "artifact_schema_version": "V24DevRealPlannerGenerationV3ImplementationManifestV1",
        "status": "FAILED_CLOSED",
        "failure_code": "SCIENTIFIC_POSTVALIDATION_FAILED_AUTHORITY_REFERENCE_TYPE",
        "source_failure_freeze_sha256": source["source_root"],
        "aggregate_components": components,
        "missing_outputs_due_fail_closed": sorted(MISSING_DUE_FAIL_CLOSED),
        "search_plan_v24_dev_real_planner_generation_v3_sha256": run_root,
        "v24_dev_raw_planner_outputs_sha256": raw_root,
        "partial_validated_rehydrated_outputs_sha256": partial_rehydrated_root,
        "v24_dev_compiled_queries_sha256": None,
    }
    validation = {
        "artifact_schema_version": "V24DevRealPlannerGenerationV3ValidationV1",
        "status": "FAILED_CLOSED",
        "failure_code": implementation["failure_code"],
        "checks": {
            "authoritative_roots_verified": roots["status"] == "PASS",
            "prior_failed_runs_preserved": prior_audit["status"] == "PASS",
            "provider_preflight_pass_count_eight": base.load_json(
                DEST / "provider_schema_preflight_manifest.json")["passed_preflights"] == 8,
            "provider_requests_attempted_eight": True,
            "model_inference_calls_eight": True,
            "valid_provider_payloads_eight": base.load_json(
                DEST / "provider_payload_validation.json")["provider_validation_failures"] == 0,
            "valid_rehydrated_plans_eight": rehydration["valid_rehydrated_plans"] == 8,
            "scientific_postvalidation_failures_zero": False,
            "stop_condition_enforced": True,
            "no_retry_or_repair": True,
            "zero_retrieval": safety["retrieval_calls"] == safety["candidate_records_seen"] == 0,
            "protected_assets_unchanged": (
                safety["protected_state_before_sha256"] == safety["protected_state_after_sha256"]),
        },
        "aggregate_components": components,
        "search_plan_v24_dev_real_planner_generation_v3_sha256": run_root,
    }
    summary = {
        "artifact_schema_version": "V24DevRealPlannerGenerationV3SummaryV1",
        "status": "FAILED_CLOSED",
        "failure_code": implementation["failure_code"],
        "development_case_count": 8,
        "provider_preflight_pass_count": 8,
        "provider_requests_attempted": 8,
        "model_inference_calls": 8,
        "valid_provider_payloads": 8,
        "valid_rehydrated_plans": rehydration["valid_rehydrated_plans"],
        "scientific_postvalidation_failures": postvalidation["scientific_postvalidation_failures"],
        "scientific_schema_valid_plans": postvalidation["valid_planner_outputs"],
        "automatic_retries": 0,
        "manual_repairs": 0,
        "model_target_mutations": rehydration["model_target_mutations"],
        "compiled_query_count": 0,
        "relation_applicable_blueprints": None,
        "relation_represented_blueprints": None,
        "relation_underrepresented_blueprints": None,
        "relation_omitted_invalid_blueprints": None,
        "search_only_expansion_count": None,
        "search_only_identity_promotions": 0,
        "literature_network_calls": 0,
        "retrieval_calls": 0,
        "candidate_records_seen": 0,
        "v24_dev_raw_planner_outputs_sha256": raw_root,
        "v24_dev_compiled_queries_sha256": None,
        "search_plan_v24_dev_real_planner_generation_v3_sha256": run_root,
        "v23_assets_modified": False,
    }
    base.write_exact(DEST / "implementation_manifest.json", base.pretty(implementation))
    base.write_exact(DEST / "validation.json", base.pretty(validation))
    base.write_exact(DEST / "summary.json", base.pretty(summary))
    base.write_exact(DEST / "search_plan_v24_dev_real_planner_generation_v3_sha256",
                     (run_root + "\n").encode("ascii"))
    base.require({path.name for path in DEST.iterdir()} == COPIED | GENERATED,
                 "protocol-named failure run membership mismatch")
    base.require(all(path.is_file() and not path.is_symlink() for path in DEST.iterdir()),
                 "non-physical output detected")
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
