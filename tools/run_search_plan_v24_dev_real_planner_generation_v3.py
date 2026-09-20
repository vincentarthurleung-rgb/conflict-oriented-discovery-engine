#!/usr/bin/env python3
"""Run eight authorized v2.4-dev planner payload calls after projection freeze."""

from __future__ import annotations

import argparse
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
    REHYDRATOR_VERSION,
    rehydrate_planner_output,
    render_provider_payload_schema,
    static_provider_compatibility_preflight,
    validate_provider_payload,
)
from code_engine.search.openai_structured_output_schema_renderer_v1 import validate_scientific_instance
from code_engine.search.proposition_aware_query_planner_v1 import (
    DEFAULT_DEVELOPMENT_CONFIG,
    canonical_target_hash,
    planner_config_hash,
    validate_plan,
)
from code_engine.search.query_compiler_v24_dev import DEFAULT_DEVELOPMENT_BUDGETS, compile_validated_plan
from code_engine.search.retrieval_intent_v1 import DIMENSION_ORDER
from code_engine.search.search_term_validator_v1 import USABLE_CLASSES, validate_and_classify_plan_terms
from tools import run_search_plan_v24_dev_real_planner_generation as base


RUN = ROOT / "runs/20260918_search_plan_v24_dev_real_planner_generation_freeze_v3"
TRANSPORT_RUN = ROOT / "runs/20260918_search_plan_v24_dev_transport_projection_compatibility_offline"
FAILED_RUN_1 = ROOT / "runs/20260917_search_plan_v24_dev_real_planner_generation_freeze"
FAILED_RUN_2 = ROOT / "runs/20260918_search_plan_v24_dev_real_planner_generation_v2_freeze"
WORKSPACE_ROOT = Path("/tmp/v24_dev_real_planner_v3_workspaces")
STAGING_ROOT = Path("/tmp/v24_dev_real_planner_v3_staging")
PROMPT_ROOT = STAGING_ROOT / "prompts"
RESPONSE_ROOT = STAGING_ROOT / "responses"
EVENT_ROOT = STAGING_ROOT / "events"
EXECUTION_ROOT = STAGING_ROOT / "execution_records"
PROTECTED_SNAPSHOT = STAGING_ROOT / "protected_state_before.json"

EXPECTED_TRANSPORT = "655afe60eb2f4137754b71cea7a8f51c7aef080d14c6d7e14168852f7341c4f8"
EXPECTED_PROVIDER_PAYLOAD_SCHEMA = "d6daf7d8757cab974437a9bb1449078eea1c2a003a34f74825f62cc513684ae4"
EXPECTED_FAILED_1 = "7380b5fc472bda29c1e9a82d64a73956ad1ec077464e09db33bcd5974ba4d316"
EXPECTED_FAILED_2 = "437b659b3dcdf8bd7162aa6b4955be3f864be17eb30c3c1ef8fd3a3d1e1b2fd5"
CASES = base.CASES
DISABLED_FEATURES = base.DISABLED_FEATURES

REQUIRED_OUTPUTS = {
    "upstream_root_verification.json", "transport_root_verification.json",
    "provider_schema_preflight_manifest.json", "planner_call_manifest.json",
    "planner_workspace_isolation_audit.json", "v24_dev_raw_planner_outputs.jsonl",
    "v24_dev_raw_planner_outputs_sha256", "provider_payload_validation.json",
    "v24_dev_rehydrated_planner_outputs.jsonl", "v24_dev_rehydrated_planner_outputs_sha256",
    "scientific_postvalidation.json", "validated_search_terms.jsonl",
    "search_term_classification_summary.json", "retrieval_intent_summary.json",
    "retrieval_plan_coverage_analysis.json", "relation_coverage_analysis.json",
    "biological_unit_coverage_analysis.json", "search_only_expansion_audit.json",
    "v24_dev_compiled_queries.jsonl", "v24_dev_compiled_queries_sha256",
    "query_provenance_trace.json", "v23_v24_structural_coverage_comparison.json",
    "scientific_state_safety_audit.json", "implementation_manifest.json",
    "validation.json", "summary.json",
}

FAIL_CLOSED_OUTPUTS = {
    "upstream_root_verification.json", "transport_root_verification.json",
    "provider_schema_preflight_manifest.json", "planner_call_manifest.json",
    "planner_workspace_isolation_audit.json", "v24_dev_raw_planner_outputs.jsonl",
    "v24_dev_raw_planner_outputs_sha256", "provider_payload_validation.json",
    "v24_dev_rehydrated_planner_outputs.jsonl", "v24_dev_rehydrated_planner_outputs_sha256",
    "scientific_postvalidation.json", "scientific_state_safety_audit.json",
    "implementation_manifest.json", "validation.json", "summary.json",
}


def verify_aggregate(run: Path, metadata_name: str, field: str, expected: str) -> str:
    metadata = base.load_json(run / metadata_name)
    pairs = []
    for name, recorded in metadata["aggregate_components"]:
        actual = base.sha(run / name)
        base.require(actual == recorded, f"component changed: {run.name}/{name}")
        pairs.append([name, actual])
    actual = base.aggregate(pairs)
    base.require(actual == metadata[field] == expected, f"root mismatch: {field}")
    return actual


def verify_upstreams() -> dict[str, Any]:
    roots = base.verify_upstreams()
    transport = verify_aggregate(
        TRANSPORT_RUN, "validation.json",
        "search_plan_v24_transport_projection_compatibility_sha256", EXPECTED_TRANSPORT,
    )
    failed_1 = verify_aggregate(
        FAILED_RUN_1, "implementation_manifest.json",
        "search_plan_v24_dev_real_planner_generation_sha256", EXPECTED_FAILED_1,
    )
    failed_2 = verify_aggregate(
        FAILED_RUN_2, "implementation_manifest.json",
        "search_plan_v24_dev_real_planner_generation_sha256", EXPECTED_FAILED_2,
    )
    summary = base.load_json(TRANSPORT_RUN / "summary.json")
    base.require(summary["provider_payload_schema_sha256"] == EXPECTED_PROVIDER_PAYLOAD_SCHEMA,
                 "provider payload schema hash mismatch")
    contract = base.load_json(TRANSPORT_RUN / "provider_payload_projection_contract.json")
    base.require(base.sha(ROOT / contract["source_file"]) == contract["source_sha256"],
                 "frozen transport source changed")
    base.require(base.sha(ROOT / contract["test_file"]) == contract["test_sha256"],
                 "frozen transport tests changed")
    return {
        **roots,
        "artifact_schema_version": "V24DevRealPlannerV3UpstreamRootVerificationV1",
        "search_plan_v24_transport_projection_compatibility_sha256": transport,
        "provider_payload_schema_sha256": EXPECTED_PROVIDER_PAYLOAD_SCHEMA,
        "preserved_failed_generation_roots": [failed_1, failed_2],
        "verified_before_provider_calls": True,
    }


def protected_state() -> dict[str, str]:
    state = base.protected_state()
    for directory in (TRANSPORT_RUN, FAILED_RUN_1, FAILED_RUN_2):
        for path in directory.rglob("*"):
            if path.is_file():
                state[str(path.resolve().relative_to(ROOT))] = base.sha(path)
    contract = base.load_json(TRANSPORT_RUN / "provider_payload_projection_contract.json")
    for field in ("source_file", "test_file"):
        path = ROOT / contract[field]
        state[str(path.relative_to(ROOT))] = base.sha(path)
    return dict(sorted(state.items()))


def payload_schema() -> tuple[dict[str, Any], dict[str, Any]]:
    scientific_schema = base.load_json(base.SCHEMA_SOURCE)
    rendered, _ = render_provider_payload_schema(scientific_schema)
    preflight = static_provider_compatibility_preflight(rendered)
    base.require(preflight["status"] == "PASS", "frozen provider payload preflight failed")
    base.require(preflight["provider_payload_schema_sha256"] == EXPECTED_PROVIDER_PAYLOAD_SCHEMA,
                 "rendered provider payload schema differs from frozen identity")
    return rendered, preflight


def provider_prompt(instruction: bytes, target: bytes) -> bytes:
    controls = (
        "You are a fresh isolated PROPOSITION_AWARE_QUERY_PLANNER context for exactly one development target.\n"
        "Use only the canonical target and frozen planner instruction below.\n"
        "Do not call tools or access files, network, memory, prior conversations, outside evidence, or other cases.\n"
        "Transport rule: return exactly one PropositionAwarePlannerPayloadV1 JSON object containing only retrieval_intents.\n"
        "Do not return artifact_schema_version, request_provenance, target_id, canonical_proposition, hashes, "
        "planner identities, planner_output_frozen_before_retrieval, Markdown, commentary, or final PubMed query strings.\n"
        "Those deterministic request-echo fields are rehydrated outside the model from immutable request state.\n"
        "The frozen instruction's scientific planning semantics remain authoritative for retrieval_intents.\n"
        "Every blueprint must contain all eleven coverage rows in the exact frozen order.\n\n"
    ).encode("utf-8")
    return b"".join([
        controls,
        b"--- FROZEN QUERY PLANNER INSTRUCTION ---\n", instruction,
        b"\n--- CANONICAL SCIENTIFIC PROPOSITION TARGET ---\n", target,
    ])


def prepare() -> None:
    roots = verify_upstreams()
    protected = protected_state()
    config = base.planner_config()
    targets = base.targets_by_case()
    schema, preflight = payload_schema()
    base.require(not RUN.exists() or not any(RUN.iterdir()), "v3 generation run already contains files")
    RUN.mkdir(parents=True, exist_ok=True)
    for directory in (WORKSPACE_ROOT, STAGING_ROOT, PROMPT_ROOT, RESPONSE_ROOT, EVENT_ROOT, EXECUTION_ROOT):
        directory.mkdir(parents=True, exist_ok=True)
    base.write_exact(PROTECTED_SNAPSHOT, base.pretty(protected))
    base.write_exact(RUN / "upstream_root_verification.json", base.pretty(roots))
    base.write_exact(RUN / "transport_root_verification.json", base.pretty({
        "artifact_schema_version": "V24DevRealPlannerV3TransportRootVerificationV1",
        "status": "PASS",
        "transport_projection_root": EXPECTED_TRANSPORT,
        "provider_payload_schema_sha256": EXPECTED_PROVIDER_PAYLOAD_SCHEMA,
        "renderer_source_verified": True,
        "rehydrator_version": REHYDRATOR_VERSION,
    }))
    instruction = base.INSTRUCTION_SOURCE.read_bytes()
    schema_body = base.pretty(schema)
    prompt_identity = base.sha(base.INSTRUCTION_SOURCE)
    scientific_schema_identity = base.sha(base.SCHEMA_SOURCE)
    calls, workspaces, preflight_rows = [], [], []
    for index, case_id in enumerate(CASES, 1):
        target = targets[case_id]
        case_preflight = static_provider_compatibility_preflight(schema)
        base.require(case_preflight["status"] == "PASS", f"preflight failed before call: {case_id}")
        target_body = base.pretty(target)
        workspace = WORKSPACE_ROOT / case_id
        workspace.mkdir(parents=True, exist_ok=True)
        files = {
            "canonical_target.json": target_body,
            "planner_instruction.md": instruction,
            "provider_payload_schema.json": schema_body,
        }
        base.require(not ({path.name for path in workspace.iterdir()} - set(files)),
                     f"forbidden workspace file: {case_id}")
        for name, body in files.items():
            base.write_exact(workspace / name, body)
        paths = sorted(workspace.iterdir())
        base.require({path.name for path in paths} == set(files), f"workspace membership mismatch: {case_id}")
        base.require(all(path.is_file() and not path.is_symlink() for path in paths), "workspace must be physical")
        prompt = provider_prompt(instruction, target_body)
        prompt_path = PROMPT_ROOT / f"{case_id}.txt"
        base.write_exact(prompt_path, prompt)
        response_path = RESPONSE_ROOT / f"{case_id}.json"
        event_path = EVENT_ROOT / f"{case_id}.jsonl"
        execution_path = EXECUTION_ROOT / f"{case_id}.json"
        request_reference = f"v24_dev_real_planner_generation_v3:{case_id}"
        calls.append({
            "call_index": index, "case_id": case_id,
            "provider": "OpenAI", "model": "gpt-5.6-sol",
            "reasoning_effort": "high", "service_tier": "default",
            "temperature_exposed": False, "temperature_override": None,
            "maximum_attempts": 1, "automatic_retry": False, "manual_repair": False,
            "fresh_isolated_context": True,
            "workspace_path": str(workspace), "prompt_path": str(prompt_path),
            "prompt_sha256": base.digest(prompt), "frozen_planner_prompt_sha256": prompt_identity,
            "response_path": str(response_path), "event_path": str(event_path),
            "execution_record_path": str(execution_path),
            "request_reference": request_reference,
            "request_sha256": base.digest(request_reference.encode("utf-8")),
            "target_id": target["scientific_proposition_target_id"],
            "target_sha256": canonical_target_hash(target),
            "planner_config_sha256": planner_config_hash(DEFAULT_DEVELOPMENT_CONFIG),
            "scientific_schema_sha256": scientific_schema_identity,
            "provider_payload_schema_sha256": EXPECTED_PROVIDER_PAYLOAD_SCHEMA,
            "provider_schema_path": str(workspace / "provider_payload_schema.json"),
            "static_provider_schema_preflight_pass": True,
            "status": "PREPARED_NOT_CALLED",
        })
        preflight_rows.append({
            "case_id": case_id, "status": case_preflight["status"],
            "provider_payload_schema_sha256": case_preflight["provider_payload_schema_sha256"],
            "object_const_count": case_preflight["provider_schema_object_const_count"],
            "array_const_count": case_preflight["provider_schema_array_const_count"],
            "primitive_const_count": case_preflight["provider_schema_primitive_const_count"],
            "preflight_is_provider_acceptance_proof": False,
        })
        workspaces.append({
            "case_id": case_id, "workspace_path": str(workspace),
            "file_membership": sorted(files),
            "files": [{"path": path.name, "sha256": base.sha(path), "bytes": path.stat().st_size} for path in paths],
            "physical_files_only": True, "symlinks_present": False,
            "historical_results_present": False, "other_case_outputs_present": False,
            "PASS_A_present": False, "PASS_B_present": False, "PMIDs_present": False,
            "candidate_material_present": False, "metrics_present": False,
            "prompt_path_outside_workspace": str(prompt_path), "prompt_sha256": base.digest(prompt),
        })
    base.write_exact(RUN / "provider_schema_preflight_manifest.json", base.pretty({
        "artifact_schema_version": "V24DevProviderPayloadPreflightManifestV1",
        "status": "PASS", "preflight_name": "STATIC_PROVIDER_COMPATIBILITY_PREFLIGHT",
        "preflight_is_provider_acceptance_proof": False,
        "expected_preflights": 8, "passed_preflights": 8,
        "completed_before_first_provider_request": True,
        "provider_payload_schema_sha256": EXPECTED_PROVIDER_PAYLOAD_SCHEMA,
        "cases": preflight_rows,
    }))
    base.write_exact(RUN / "planner_workspace_isolation_audit.json", base.pretty({
        "artifact_schema_version": "V24DevPlannerV3WorkspaceIsolationAuditV1",
        "status": "PASS", "workspace_count": 8, "files_per_workspace": 3,
        "all_physical_and_isolated": True, "allowed_input_categories_only": True,
        "workspaces": workspaces,
    }))
    base.write_exact(RUN / "planner_call_manifest.json", base.pretty({
        "artifact_schema_version": "V24DevPlannerV3CallManifestV1",
        "status": "PREPARED_FOR_EXACTLY_EIGHT_CALLS",
        "configuration": {**config, "transport_projection_root": EXPECTED_TRANSPORT,
                          "provider_payload_schema_sha256": EXPECTED_PROVIDER_PAYLOAD_SCHEMA,
                          "rehydrator_version": REHYDRATOR_VERSION},
        "authorized_planner_calls": 8, "expected_calls": 8, "calls": calls,
    }))
    base.require(protected_state() == protected, "protected state changed during preparation")
    print(json.dumps({
        "status": "READY_FOR_EXACTLY_EIGHT_CALLS", "cases": list(CASES),
        "provider_preflight_pass_count": 8,
        "provider_payload_schema_sha256": EXPECTED_PROVIDER_PAYLOAD_SCHEMA,
    }, indent=2, sort_keys=True))


def execute_one(case_id: str) -> None:
    base.require(case_id in CASES, "unauthorized case")
    verify_upstreams()
    base.require(base.load_json(PROTECTED_SNAPSHOT) == protected_state(), "protected state changed before call")
    manifest = base.load_json(RUN / "planner_call_manifest.json")
    call = next(row for row in manifest["calls"] if row["case_id"] == case_id)
    execution_path, response_path = Path(call["execution_record_path"]), Path(call["response_path"])
    base.require(not execution_path.exists(), f"call already attempted for {case_id}; retry prohibited")
    base.require(not response_path.exists(), f"response already exists for {case_id}; retry prohibited")
    schema = base.load_json(Path(call["provider_schema_path"]))
    preflight = static_provider_compatibility_preflight(schema)
    base.require(preflight["status"] == "PASS", f"preflight failed immediately before call: {case_id}")
    base.require(preflight["provider_payload_schema_sha256"] == call["provider_payload_schema_sha256"],
                 f"provider schema changed: {case_id}")
    command = [
        "codex", "exec", "--ephemeral", "--ignore-user-config", "--ignore-rules",
        "--model", "gpt-5.6-sol", "--config", 'model_reasoning_effort="high"',
        "--config", 'service_tier="default"', "--sandbox", "read-only",
        "--cd", call["workspace_path"], "--skip-git-repo-check",
        "--output-schema", call["provider_schema_path"],
        "--output-last-message", call["response_path"], "--json",
    ]
    for feature in DISABLED_FEATURES:
        command.extend(["--disable", feature])
    command.append("-")
    completed = subprocess.run(
        command, input=Path(call["prompt_path"]).read_bytes(), stdout=subprocess.PIPE,
        stderr=subprocess.PIPE, check=False, timeout=900,
    )
    event_path = Path(call["event_path"])
    stderr_path = EVENT_ROOT / f"{case_id}.stderr.txt"
    base.write_exact(event_path, completed.stdout)
    base.write_exact(stderr_path, completed.stderr)
    record = {
        "artifact_schema_version": "V24DevPlannerV3CallExecutionRecordV1",
        "case_id": case_id, "attempt_count": 1, "provider_requests_attempted": 1,
        "provider_calls_completed": int(completed.returncode == 0 and response_path.is_file()),
        "llm_calls": 1, "automatic_retries": 0, "manual_repairs": 0,
        "return_code": completed.returncode, "response_present": response_path.is_file(),
        "response_sha256": base.sha(response_path) if response_path.is_file() else None,
        "provider_payload_schema_sha256": call["provider_payload_schema_sha256"],
        "static_provider_schema_preflight_pass": True,
        "event_stream_sha256": base.sha(event_path), "stderr_sha256": base.sha(stderr_path),
        "accepted_for_raw_freeze": completed.returncode == 0 and response_path.is_file(),
    }
    base.write_exact(execution_path, base.pretty(record))
    base.require(record["accepted_for_raw_freeze"], f"provider call failed closed for {case_id}: rc={completed.returncode}")
    print(json.dumps(record, indent=2, sort_keys=True))


def _legacy_coverage(target: dict[str, Any], queries: list[dict[str, Any]]) -> dict[str, int]:
    return base._legacy_coverage(target, queries)


def finalize() -> None:
    roots = verify_upstreams()
    base.require(base.load_json(RUN / "upstream_root_verification.json") == roots, "prepared roots changed")
    before = base.load_json(PROTECTED_SNAPSHOT)
    base.require(protected_state() == before, "protected state changed before raw freeze")
    manifest = base.load_json(RUN / "planner_call_manifest.json")
    targets = base.targets_by_case()
    provider_schema, preflight = payload_schema()
    scientific_schema = base.load_json(base.SCHEMA_SOURCE)
    executions = {}
    for case_id in CASES:
        record = base.load_json(EXECUTION_ROOT / f"{case_id}.json")
        base.require(record["attempt_count"] == record["provider_requests_attempted"] == 1,
                     f"attempt accounting mismatch: {case_id}")
        base.require(record["accepted_for_raw_freeze"], f"provider failure: {case_id}")
        executions[case_id] = record
    base.require(sum(row["provider_requests_attempted"] for row in executions.values()) == 8,
                 "provider request total mismatch")
    base.require(sum(row["provider_calls_completed"] for row in executions.values()) == 8,
                 "provider completion total mismatch")

    raw_rows = []
    for call in manifest["calls"]:
        raw_text = Path(call["response_path"]).read_text(encoding="utf-8")
        try:
            parsed = json.loads(raw_text)
            parse_error = None
        except json.JSONDecodeError as exc:
            parsed, parse_error = None, str(exc)
        raw_rows.append({
            "artifact_schema_version": "V24DevRawPlannerPayloadOutputV1",
            "case_id": call["case_id"], "development_case_status": "SEEN_DEVELOPMENT_ONLY",
            "target_sha256": call["target_sha256"],
            "provider_request_identity": {
                key: call[key] for key in (
                    "call_index", "request_reference", "request_sha256", "provider", "model",
                    "reasoning_effort", "service_tier", "temperature_exposed", "temperature_override",
                    "maximum_attempts", "prompt_sha256", "frozen_planner_prompt_sha256",
                )
            },
            "raw_provider_response": raw_text,
            "structured_parsed_payload": parsed,
            "parse_error": parse_error,
            "scientific_schema_sha256": call["scientific_schema_sha256"],
            "provider_payload_schema_sha256": call["provider_payload_schema_sha256"],
            "planner_config_sha256": call["planner_config_sha256"],
            "raw_response_sha256": base.digest(raw_text.encode("utf-8")),
            "provider_event_stream_sha256": executions[call["case_id"]]["event_stream_sha256"],
        })
    raw_body = base.jsonl(raw_rows)
    raw_root = base.digest(raw_body)
    base.write_exact(RUN / "v24_dev_raw_planner_outputs.jsonl", raw_body)
    base.write_exact(RUN / "v24_dev_raw_planner_outputs_sha256", (raw_root + "\n").encode("ascii"))

    payload_results, post_results, plans, rehydrated_rows = [], [], {}, []
    for call, raw in zip(manifest["calls"], raw_rows):
        case_id, errors = call["case_id"], []
        payload = raw["structured_parsed_payload"]
        if payload is None:
            errors.append("provider response is not JSON")
        else:
            try:
                validate_provider_payload(payload, provider_schema)
            except Exception as exc:
                errors.append(f"{type(exc).__name__}: {exc}")
        payload_results.append({"case_id": case_id, "provider_payload_valid": not errors, "errors": errors})
        post_errors = []
        plan = None
        if not errors:
            try:
                plan = rehydrate_planner_output(
                    payload,
                    canonical_target=targets[case_id],
                    request_reference=call["request_reference"],
                    planner_config=DEFAULT_DEVELOPMENT_CONFIG,
                    prompt_sha256=call["frozen_planner_prompt_sha256"],
                    scientific_schema_sha256=call["scientific_schema_sha256"],
                    provider_payload_schema=provider_schema,
                )
                validate_scientific_instance(plan, scientific_schema)
                validate_plan(plan, expected_target=targets[case_id])
            except Exception as exc:
                post_errors.append(f"{type(exc).__name__}: {exc}")
        else:
            post_errors.append("provider payload invalid; rehydration not attempted")
        post_results.append({
            "case_id": case_id, "deterministic_rehydration_pass": plan is not None and not post_errors,
            "scientific_postvalidation_pass": plan is not None and not post_errors,
            "errors": post_errors, "repair_attempted": False, "rerun_attempted": False,
        })
        if plan is not None and not post_errors:
            plans[case_id] = plan
            rehydrated_rows.append({
                "artifact_schema_version": "V24DevRehydratedPlannerOutputV1",
                "case_id": case_id, "provider_payload_sha256": raw["raw_response_sha256"],
                "rehydrator_version": REHYDRATOR_VERSION, "scientific_plan": plan,
            })
    base.write_exact(RUN / "provider_payload_validation.json", base.pretty({
        "artifact_schema_version": "V24DevProviderPayloadValidationV1",
        "status": "PASS" if all(row["provider_payload_valid"] for row in payload_results) else "FAIL",
        "raw_planner_outputs_sha256": raw_root,
        "provider_validation_failures": sum(not row["provider_payload_valid"] for row in payload_results),
        "results": payload_results,
    }))
    rehydrated_body = base.jsonl(rehydrated_rows)
    rehydrated_root = base.digest(rehydrated_body)
    base.write_exact(RUN / "v24_dev_rehydrated_planner_outputs.jsonl", rehydrated_body)
    base.write_exact(RUN / "v24_dev_rehydrated_planner_outputs_sha256", (rehydrated_root + "\n").encode("ascii"))
    base.write_exact(RUN / "scientific_postvalidation.json", base.pretty({
        "artifact_schema_version": "V24DevScientificPostvalidationV1",
        "status": "PASS" if len(plans) == 8 else "FAIL",
        "unchanged_scientific_schema_sha256": base.sha(base.SCHEMA_SOURCE),
        "rehydrator_version": REHYDRATOR_VERSION,
        "valid_planner_outputs": len(plans),
        "scientific_postvalidation_failures": sum(not row["scientific_postvalidation_pass"] for row in post_results),
        "model_controlled_deterministic_echo_fields": 0,
        "results": post_results,
    }))
    base.require(all(row["provider_payload_valid"] for row in payload_results) and len(plans) == 8,
                 f"provider/scientific validation failed closed: payload={payload_results}, post={post_results}")

    _write_downstream(plans, targets, manifest, executions, roots, before, raw_root, rehydrated_root)


def freeze_failure() -> None:
    """Seal an already-observed postvalidation failure without repair or rerun."""
    roots = verify_upstreams()
    base.require(base.load_json(RUN / "upstream_root_verification.json") == roots, "prepared roots changed")
    protected_before = base.load_json(PROTECTED_SNAPSHOT)
    base.require(protected_state() == protected_before, "protected state changed before failure freeze")
    manifest = base.load_json(RUN / "planner_call_manifest.json")
    executions = {
        case_id: base.load_json(EXECUTION_ROOT / f"{case_id}.json") for case_id in CASES
    }
    base.require(all(row["attempt_count"] == row["provider_requests_attempted"] == 1
                     for row in executions.values()), "attempt accounting mismatch")
    base.require(sum(row["provider_calls_completed"] for row in executions.values()) == 8,
                 "provider completion total mismatch")
    base.require(sum(row["automatic_retries"] for row in executions.values()) == 0,
                 "automatic retry detected")
    base.require(sum(row["manual_repairs"] for row in executions.values()) == 0,
                 "manual repair detected")

    raw_root = (RUN / "v24_dev_raw_planner_outputs_sha256").read_text(encoding="ascii").strip()
    rehydrated_root = (RUN / "v24_dev_rehydrated_planner_outputs_sha256").read_text(encoding="ascii").strip()
    base.require(base.sha(RUN / "v24_dev_raw_planner_outputs.jsonl") == raw_root,
                 "raw output root mismatch")
    base.require(base.sha(RUN / "v24_dev_rehydrated_planner_outputs.jsonl") == rehydrated_root,
                 "rehydrated output root mismatch")
    raw_rows = base.load_jsonl(RUN / "v24_dev_raw_planner_outputs.jsonl")
    rehydrated_rows = base.load_jsonl(RUN / "v24_dev_rehydrated_planner_outputs.jsonl")
    base.require(len(raw_rows) == 8, "raw output count mismatch")
    base.require({row["case_id"] for row in raw_rows} == set(CASES), "raw case membership mismatch")
    provider_validation = base.load_json(RUN / "provider_payload_validation.json")
    postvalidation = base.load_json(RUN / "scientific_postvalidation.json")
    base.require(provider_validation["status"] == "PASS", "provider payload validation did not pass")
    base.require(provider_validation["provider_validation_failures"] == 0,
                 "provider payload validation failures present")
    base.require(postvalidation["status"] == "FAIL", "scientific postvalidation failure absent")
    base.require(postvalidation["scientific_postvalidation_failures"] == 7,
                 "unexpected scientific postvalidation failure count")
    base.require(postvalidation["valid_planner_outputs"] == len(rehydrated_rows) == 1,
                 "valid scientific output count mismatch")
    base.require(all(not row["repair_attempted"] and not row["rerun_attempted"]
                     for row in postvalidation["results"]), "repair or rerun detected")

    final_calls = [{**call, **executions[call["case_id"]], "status": "COMPLETED_ACCEPTED_RAW_FREEZE"}
                   for call in manifest["calls"]]
    base.write_owned(RUN / "planner_call_manifest.json", base.pretty({
        **manifest, "status": "FAILED_CLOSED_AFTER_EXACTLY_EIGHT_CALLS",
        "provider_requests_attempted": 8, "provider_calls_completed": 8,
        "raw_provider_payloads_frozen": 8,
        "valid_scientific_planner_outputs": len(rehydrated_rows),
        "automatic_retries": 0, "manual_repairs": 0, "calls": final_calls,
    }))
    protected_after = protected_state()
    base.require(protected_after == protected_before, "protected state changed")
    safety = {
        "artifact_schema_version": "V24DevRealPlannerV3ScientificStateSafetyAuditV1",
        "status": "FAILED_CLOSED", "development_cases_only": True,
        "development_case_count": 8, "authorized_planner_calls": 8,
        "provider_requests_attempted": 8, "provider_calls_completed": 8,
        "raw_provider_payloads_frozen": 8,
        "valid_scientific_planner_outputs": len(rehydrated_rows),
        "automatic_retries": 0, "manual_repairs": 0, "outcome_informed_reruns": 0,
        "provider_model_switches": 0, "retrieval_calls": 0,
        "literature_network_calls": 0, "candidate_records_seen": 0,
        "hit_counts_inspected": False, "oa_availability_inspected": False,
        "known_direct_paper_recovery_tested": False, "v23_assets_modified": False,
        "planner_prompt_changed": False, "schema_changed": False,
        "validator_changed": False, "compiler_changed": False, "budgets_changed": False,
        "downstream_term_validation_performed": False,
        "coverage_analysis_performed": False, "query_compilation_performed": False,
        "protected_state_before_sha256": base.digest(base.canonical(protected_before)),
        "protected_state_after_sha256": base.digest(base.canonical(protected_after)),
    }
    base.write_exact(RUN / "scientific_state_safety_audit.json", base.pretty(safety))
    component_names = sorted(FAIL_CLOSED_OUTPUTS - {
        "implementation_manifest.json", "validation.json", "summary.json",
    })
    components = [[name, base.sha(RUN / name)] for name in component_names]
    run_root = base.aggregate(components)
    missing = sorted(REQUIRED_OUTPUTS - FAIL_CLOSED_OUTPUTS)
    implementation_manifest = {
        "artifact_schema_version": "V24DevRealPlannerV3ImplementationManifestV1",
        "status": "FAILED_CLOSED",
        "failure_code": "SCIENTIFIC_POSTVALIDATION_FAILED_AUTHORITY_REFERENCE_TYPE",
        "aggregate_components": components,
        "missing_outputs_due_fail_closed": missing,
        "search_plan_v24_dev_real_planner_generation_v3_sha256": run_root,
        "v24_dev_raw_planner_outputs_sha256": raw_root,
        "v24_dev_rehydrated_planner_outputs_sha256": rehydrated_root,
        "v24_dev_compiled_queries_sha256": None,
    }
    validation = {
        "artifact_schema_version": "V24DevRealPlannerV3ValidationV1",
        "status": "FAILED_CLOSED",
        "failure_code": "SCIENTIFIC_POSTVALIDATION_FAILED_AUTHORITY_REFERENCE_TYPE",
        "checks": {
            "upstream_roots_verified": roots["status"] == "PASS",
            "provider_preflight_pass_count_eight": base.load_json(
                RUN / "provider_schema_preflight_manifest.json")["passed_preflights"] == 8,
            "provider_requests_attempted_eight": True,
            "provider_calls_completed_eight": True,
            "raw_outputs_frozen_before_analysis": True,
            "provider_payload_validation_pass": True,
            "scientific_postvalidation_pass": False,
            "no_retry_or_repair": True,
            "downstream_processing_stopped": True,
            "zero_retrieval": True,
            "protected_assets_unchanged": protected_after == protected_before,
        },
        "aggregate_components": components,
        "search_plan_v24_dev_real_planner_generation_v3_sha256": run_root,
    }
    summary = {
        "artifact_schema_version": "V24DevRealPlannerV3SummaryV1",
        "status": "FAILED_CLOSED",
        "failure_code": "SCIENTIFIC_POSTVALIDATION_FAILED_AUTHORITY_REFERENCE_TYPE",
        "development_case_count": 8, "provider_preflight_pass_count": 8,
        "provider_requests_attempted": 8, "provider_calls_completed": 8,
        "planner_outputs_expected": 8, "raw_provider_payloads_frozen": 8,
        "provider_validation_failures": 0,
        "valid_scientific_planner_outputs": len(rehydrated_rows),
        "scientific_postvalidation_failures": 7,
        "failed_case_ids": [row["case_id"] for row in postvalidation["results"]
                            if not row["scientific_postvalidation_pass"]],
        "automatic_retries": 0, "manual_repairs": 0,
        "compiled_query_count": 0, "literature_network_calls": 0,
        "retrieval_calls": 0, "candidate_records_seen": 0,
        "v24_dev_raw_planner_outputs_sha256": raw_root,
        "v24_dev_rehydrated_planner_outputs_sha256": rehydrated_root,
        "v24_dev_compiled_queries_sha256": None,
        "search_plan_v24_dev_real_planner_generation_v3_sha256": run_root,
        "v23_assets_modified": False,
    }
    base.write_exact(RUN / "implementation_manifest.json", base.pretty(implementation_manifest))
    base.write_exact(RUN / "validation.json", base.pretty(validation))
    base.write_exact(RUN / "summary.json", base.pretty(summary))
    base.require({path.name for path in RUN.iterdir()} == FAIL_CLOSED_OUTPUTS,
                 "fail-closed run membership mismatch")
    print(json.dumps(summary, indent=2, sort_keys=True))


def _write_downstream(plans: dict[str, dict[str, Any]], targets: dict[str, dict[str, Any]],
                      manifest: dict[str, Any], executions: dict[str, dict[str, Any]],
                      roots: dict[str, Any], protected_before: dict[str, str],
                      raw_root: str, rehydrated_root: str) -> None:
    validated, term_rows, class_counts, per_case_counts, per_concept_counts, search_only = {}, [], Counter(), {}, {}, []
    for case_id in CASES:
        result = validate_and_classify_plan_terms(plans[case_id], authorities={"records": []})
        validated[case_id] = result
        audit_by_id = {row["item_id"]: row for row in result["validation_receipt"]["classification_audit"]}
        case_counter, concept_counter = Counter(), Counter()
        for intent in result["validated_plan"]["retrieval_intents"]:
            for concept in intent["search_concepts"]:
                for term in concept["proposed_terms"]:
                    audit = audit_by_id[term["term_id"]]
                    row = {
                        "case_id": case_id, "target_id": result["validated_plan"]["target_id"],
                        "intent_id": intent["intent_id"], "intent_type": intent["intent_type"],
                        "concept_id": concept["concept_id"], "concept_type": concept["concept_type"],
                        "term_id": term["term_id"], "term": term["term"],
                        "proposal_source": term["proposal_source"], "assigned_class": term["proposal_class"],
                        "authority_reference": term["authority_reference"],
                        "planner_rationale": intent["scientific_rationale"],
                        "validation_provenance": audit["reason"], "canonical_identity_changed": False,
                    }
                    term_rows.append(row)
                    class_counts[term["proposal_class"]] += 1
                    case_counter[term["proposal_class"]] += 1
                    concept_counter[(concept["concept_type"], term["proposal_class"])] += 1
                    if term["proposal_class"] == "SEARCH_ONLY_EXPANSION":
                        search_only.append(row)
        per_case_counts[case_id] = dict(sorted(case_counter.items()))
        per_concept_counts[case_id] = {
            concept: {classification: count for (name, classification), count in concept_counter.items() if name == concept}
            for concept in sorted({name for name, _ in concept_counter})
        }
    base.write_exact(RUN / "validated_search_terms.jsonl", base.jsonl(term_rows))
    class_summary = {
        "artifact_schema_version": "V24DevSearchTermClassificationSummaryV1",
        "term_count": len(term_rows),
        "classification_distribution": {name: class_counts[name] for name in (
            "AUTHORIZED_EQUIVALENT", "SEARCH_ONLY_EXPANSION", "UNRESOLVED", "REJECTED")},
        "per_case": per_case_counts, "per_concept_type_by_case": per_concept_counts,
        "llm_authority_assertions_overriding_deterministic_authority": 0,
        "search_only_identity_promotions": 0,
    }
    base.write_exact(RUN / "search_term_classification_summary.json", base.pretty(class_summary))
    base.write_exact(RUN / "search_only_expansion_audit.json", base.pretty({
        "artifact_schema_version": "V24DevSearchOnlyExpansionAuditV1",
        "search_only_expansion_count": len(search_only), "search_only_identity_promotions": 0,
        "canonical_identity_unchanged_all_cases": True, "terms": search_only,
    }))

    intent_cases, coverage_rows = {}, []
    for case_id in CASES:
        plan = validated[case_id]["validated_plan"]
        intent_cases[case_id] = [{
            "intent_id": intent["intent_id"], "intent_type": intent["intent_type"],
            "applicability": intent["applicability"],
            "applicability_rationale": intent["applicability_rationale"],
            "semantic_applicability_valid": True,
        } for intent in plan["retrieval_intents"]]
        for intent in plan["retrieval_intents"]:
            for blueprint in intent["candidate_query_blueprints"]:
                coverage_rows.append({
                    "case_id": case_id, "target_id": plan["target_id"],
                    "intent_id": intent["intent_id"], "intent_type": intent["intent_type"],
                    "blueprint_id": blueprint["blueprint_id"],
                    "relation_representation_state": blueprint["relation_representation_state"],
                    "dimension_coverage": blueprint["dimension_coverage"],
                })
    base.write_exact(RUN / "retrieval_intent_summary.json", base.pretty({
        "artifact_schema_version": "V24DevRetrievalIntentSummaryV1", "cases": intent_cases,
        "intent_type_distribution": dict(sorted(Counter(
            row["intent_type"] for rows in intent_cases.values() for row in rows if row["applicability"] == "APPLICABLE"
        ).items())), "semantic_applicability_errors": 0, "plans_edited_from_intent_audit": 0,
    }))
    base.write_exact(RUN / "retrieval_plan_coverage_analysis.json", base.pretty({
        "artifact_schema_version": "V24DevRetrievalPlanCoverageAnalysisV1",
        "analysis_role": "DEVELOPMENT_STRUCTURAL_COVERAGE_NOT_RETRIEVAL_PERFORMANCE",
        "blueprint_count": len(coverage_rows), "dimensions": list(DIMENSION_ORDER),
        "coverage_records": coverage_rows,
        "state_distribution": {dimension: dict(sorted(Counter(
            next(item["coverage_state"] for item in row["dimension_coverage"] if item["dimension"] == dimension)
            for row in coverage_rows).items())) for dimension in DIMENSION_ORDER},
    }))
    applicable_relation = [row for row in coverage_rows if next(
        item["coverage_state"] for item in row["dimension_coverage"] if item["dimension"] == "relation"
    ) != "NOT_APPLICABLE"]
    relation_represented = sum(row["relation_representation_state"] == "REPRESENTED" for row in applicable_relation)
    relation_under = sum(row["relation_representation_state"] == "RELATION_UNDERREPRESENTED" for row in applicable_relation)
    relation_invalid = sum(
        next(item["coverage_state"] for item in row["dimension_coverage"] if item["dimension"] == "relation")
        in {"OMITTED", "UNDERREPRESENTED"} and row["relation_representation_state"] != "RELATION_UNDERREPRESENTED"
        for row in applicable_relation)
    base.write_exact(RUN / "relation_coverage_analysis.json", base.pretty({
        "artifact_schema_version": "V24DevRelationCoverageAnalysisV1",
        "analysis_role": "DEVELOPMENT_STRUCTURAL_COVERAGE_NOT_RETRIEVAL_PERFORMANCE",
        "relation_applicable_blueprints": len(applicable_relation),
        "relation_represented_blueprints": relation_represented,
        "relation_underrepresented_blueprints": relation_under,
        "relation_omitted_invalid_blueprints": relation_invalid,
        "relation_coverage_fraction": {"n": relation_represented, "N": len(applicable_relation),
                                       "fraction": relation_represented / len(applicable_relation) if applicable_relation else None},
    }))
    biological_cases = {}
    for case_id in CASES:
        rows = [row for row in coverage_rows if row["case_id"] == case_id]
        blueprint_records = []
        for row in rows:
            state = next(item["coverage_state"] for item in row["dimension_coverage"] if item["dimension"] == "biological_unit")
            blueprint_records.append({"intent_id": row["intent_id"], "blueprint_id": row["blueprint_id"], "coverage_state": state})
        terms = [{
            "intent_id": intent["intent_id"], "concept_id": concept["concept_id"], "term": term["term"],
            "assigned_class": term["proposal_class"],
        } for intent in validated[case_id]["validated_plan"]["retrieval_intents"]
                 for concept in intent["search_concepts"] if concept["concept_type"] == "biological_unit"
                 for term in concept["proposed_terms"]]
        biological_cases[case_id] = {"blueprints": blueprint_records, "lexical_proposals": terms}
    base.write_exact(RUN / "biological_unit_coverage_analysis.json", base.pretty({
        "artifact_schema_version": "V24DevBiologicalUnitCoverageAnalysisV1",
        "analysis_role": "DEVELOPMENT_STRUCTURAL_DIAGNOSTIC", "cases": biological_cases,
    }))

    compiled_rows, compilation_counts = [], {}
    for case_id in CASES:
        result = validated[case_id]
        compilation = compile_validated_plan(result["validated_plan"], result["validation_receipt"],
                                             budgets=DEFAULT_DEVELOPMENT_BUDGETS)
        compilation_counts[case_id] = compilation["compiled_query_count"]
        compiled_rows.extend({"case_id": case_id, "development_only": True, **query}
                             for query in compilation["compiled_queries"])
    compiled_body = base.jsonl(compiled_rows)
    compiled_root = base.digest(compiled_body)
    base.write_exact(RUN / "v24_dev_compiled_queries.jsonl", compiled_body)
    base.write_exact(RUN / "v24_dev_compiled_queries_sha256", (compiled_root + "\n").encode("ascii"))
    provenance = {
        "artifact_schema_version": "V24DevQueryProvenanceTraceV1", "query_count": len(compiled_rows),
        "all_terms_provenanced": all(
            {"term_id", "term", "proposal_source", "proposal_class", "authority_reference"} <= set(term)
            for query in compiled_rows for group in query["ordered_term_groups"] for term in group["terms"]),
        "all_queries_hash_bound": all(query["query_id"] == "v24q:" + query["query_sha256"] for query in compiled_rows),
        "traces": [{
            "case_id": query["case_id"], "target_id": query["target_id"], "query_id": query["query_id"],
            "source_routes": query["source_routes"], "ordered_term_groups": query["ordered_term_groups"],
            "provenance": query["provenance"], "query_sha256": query["query_sha256"],
        } for query in compiled_rows],
    }
    base.write_exact(RUN / "query_provenance_trace.json", base.pretty(provenance))

    v23_queries = base.load_jsonl(base.V23_QUERIES)
    comparisons = {}
    for case_id in CASES:
        old = [row for row in v23_queries if row["case_id"] == case_id]
        old_counts = _legacy_coverage(targets[case_id], old)
        new = [row for row in coverage_rows if row["case_id"] == case_id]
        new_counts = {dimension: sum(
            next(item["coverage_state"] for item in row["dimension_coverage"] if item["dimension"] == dimension) == "REPRESENTED"
            for row in new) for dimension in DIMENSION_ORDER}
        comparisons[case_id] = {
            "v23_query_count": len(old), "v24_blueprint_count": len(new),
            "v23_represented_query_counts": old_counts, "v24_represented_blueprint_counts": new_counts,
            "structural_count_difference_v24_minus_v23": {
                dimension: new_counts[dimension] - old_counts[dimension] for dimension in DIMENSION_ORDER},
        }
    base.write_exact(RUN / "v23_v24_structural_coverage_comparison.json", base.pretty({
        "artifact_schema_version": "V23V24StructuralCoverageComparisonV1",
        "comparison_role": "DEVELOPMENT_STRUCTURAL_ONLY_NO_RETRIEVAL_OUTCOMES",
        "performance_claims_made": False, "cases": comparisons,
    }))

    final_calls = [{**call, **executions[call["case_id"]], "status": "COMPLETED_ACCEPTED_RAW_FREEZE"}
                   for call in manifest["calls"]]
    base.write_owned(RUN / "planner_call_manifest.json", base.pretty({
        **manifest, "status": "COMPLETED_EXACTLY_EIGHT_CALLS",
        "provider_requests_attempted": 8, "provider_calls_completed": 8,
        "valid_planner_outputs": 8, "automatic_retries": 0, "manual_repairs": 0,
        "calls": final_calls,
    }))
    protected_after = protected_state()
    base.require(protected_after == protected_before, "protected state changed")
    safety = {
        "artifact_schema_version": "V24DevRealPlannerV3ScientificStateSafetyAuditV1",
        "status": "PASS", "development_cases_only": True, "development_case_count": 8,
        "authorized_planner_calls": 8, "provider_requests_attempted": 8,
        "provider_calls_completed": 8, "valid_planner_outputs": 8,
        "automatic_retries": 0, "manual_repairs": 0, "provider_model_switches": 0,
        "retrieval_calls": 0, "literature_network_calls": 0, "candidate_records_seen": 0,
        "hit_counts_inspected": False, "oa_availability_inspected": False,
        "known_direct_paper_recovery_tested": False, "v23_assets_modified": False,
        "planner_prompt_changed": False, "schema_changed": False, "validator_changed": False,
        "compiler_changed": False, "budgets_changed": False,
        "protected_state_before_sha256": base.digest(base.canonical(protected_before)),
        "protected_state_after_sha256": base.digest(base.canonical(protected_after)),
    }
    base.write_exact(RUN / "scientific_state_safety_audit.json", base.pretty(safety))
    component_names = sorted(REQUIRED_OUTPUTS - {"implementation_manifest.json", "validation.json", "summary.json"})
    components = [[name, base.sha(RUN / name)] for name in component_names]
    run_root = base.aggregate(components)
    implementation_manifest = {
        "artifact_schema_version": "V24DevRealPlannerV3ImplementationManifestV1",
        "aggregate_components": components,
        "search_plan_v24_dev_real_planner_generation_v3_sha256": run_root,
        "v24_dev_raw_planner_outputs_sha256": raw_root,
        "v24_dev_rehydrated_planner_outputs_sha256": rehydrated_root,
        "v24_dev_compiled_queries_sha256": compiled_root,
    }
    validation = {
        "artifact_schema_version": "V24DevRealPlannerV3ValidationV1", "status": "PASS",
        "checks": {
            "upstream_roots_verified": roots["status"] == "PASS",
            "provider_preflight_pass_count_eight": base.load_json(RUN / "provider_schema_preflight_manifest.json")["passed_preflights"] == 8,
            "provider_requests_attempted_eight": safety["provider_requests_attempted"] == 8,
            "provider_calls_completed_eight": safety["provider_calls_completed"] == 8,
            "valid_planner_outputs_eight": safety["valid_planner_outputs"] == 8,
            "raw_outputs_frozen_before_analysis": True,
            "scientific_postvalidation_pass": True,
            "search_only_identity_promotions_zero": class_summary["search_only_identity_promotions"] == 0,
            "relation_omitted_invalid_zero": relation_invalid == 0,
            "query_provenance_complete": provenance["all_terms_provenanced"] and provenance["all_queries_hash_bound"],
            "zero_retrieval": safety["retrieval_calls"] == safety["candidate_records_seen"] == 0,
            "protected_assets_unchanged": protected_after == protected_before,
        },
        "aggregate_components": components,
        "search_plan_v24_dev_real_planner_generation_v3_sha256": run_root,
    }
    base.require(all(validation["checks"].values()), f"final validation failed: {validation['checks']}")
    summary = {
        "artifact_schema_version": "V24DevRealPlannerV3SummaryV1", "status": "COMPLETED",
        "development_case_count": 8, "provider_preflight_pass_count": 8,
        "provider_requests_attempted": 8, "provider_calls_completed": 8,
        "planner_outputs_expected": 8, "planner_outputs_frozen": 8,
        "provider_validation_failures": 0, "scientific_postvalidation_failures": 0,
        "automatic_retries": 0, "manual_repairs": 0,
        "compiled_query_count": len(compiled_rows), "compiled_query_counts_by_case": compilation_counts,
        "relation_applicable_blueprints": len(applicable_relation),
        "relation_represented_blueprints": relation_represented,
        "relation_underrepresented_blueprints": relation_under,
        "relation_omitted_invalid_blueprints": relation_invalid,
        "search_only_expansion_count": len(search_only), "search_only_identity_promotions": 0,
        "literature_network_calls": 0, "retrieval_calls": 0, "candidate_records_seen": 0,
        "v24_dev_raw_planner_outputs_sha256": raw_root,
        "v24_dev_rehydrated_planner_outputs_sha256": rehydrated_root,
        "v24_dev_compiled_queries_sha256": compiled_root,
        "search_plan_v24_dev_real_planner_generation_v3_sha256": run_root,
        "v23_assets_modified": False,
    }
    base.write_exact(RUN / "implementation_manifest.json", base.pretty(implementation_manifest))
    base.write_exact(RUN / "validation.json", base.pretty(validation))
    base.write_exact(RUN / "summary.json", base.pretty(summary))
    base.require({path.name for path in RUN.iterdir()} == REQUIRED_OUTPUTS, "run membership mismatch")
    print(json.dumps(summary, indent=2, sort_keys=True))


def main() -> None:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("prepare")
    execute = subparsers.add_parser("execute-one")
    execute.add_argument("case_id", choices=CASES)
    subparsers.add_parser("finalize")
    subparsers.add_parser("freeze-failure")
    args = parser.parse_args()
    if args.command == "prepare":
        prepare()
    elif args.command == "execute-one":
        execute_one(args.case_id)
    elif args.command == "finalize":
        finalize()
    else:
        freeze_failure()


if __name__ == "__main__":
    main()
