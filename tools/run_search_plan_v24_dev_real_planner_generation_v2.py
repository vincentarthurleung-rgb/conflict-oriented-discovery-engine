#!/usr/bin/env python3
"""Run the newly authorized v2.4-dev planner generation after schema amendment."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from code_engine.search.openai_structured_output_schema_renderer_v1 import (
    CACHE_KEY_VERSION,
    RENDERER_VERSION,
    planner_cache_key_with_provider_schema,
    render_provider_schema,
    require_provider_schema_preflight,
    sha256_value,
    validate_scientific_instance,
)
from code_engine.search.proposition_aware_query_planner_v1 import (
    DEFAULT_DEVELOPMENT_CONFIG,
    PLAN_SCHEMA_VERSION,
    PROMPT_VERSION,
    canonical_target_hash,
    planner_cache_key,
    planner_config_hash,
)
from tools import run_search_plan_v24_dev_real_planner_generation as base


RUN = ROOT / "runs/20260918_search_plan_v24_dev_real_planner_generation_v2_freeze"
COMPATIBILITY_RUN = ROOT / "runs/20260918_search_plan_v24_dev_structured_output_schema_compatibility_offline"
FAILED_RUN = ROOT / "runs/20260917_search_plan_v24_dev_real_planner_generation_freeze"
WORKSPACE_ROOT = Path("/tmp/v24_dev_real_planner_v2_workspaces")
STAGING_ROOT = Path("/tmp/v24_dev_real_planner_v2_staging")
PROMPT_ROOT = STAGING_ROOT / "prompts"
RESPONSE_ROOT = STAGING_ROOT / "responses"
EVENT_ROOT = STAGING_ROOT / "events"
EXECUTION_ROOT = STAGING_ROOT / "execution_records"
PROTECTED_SNAPSHOT = STAGING_ROOT / "protected_state_before.json"

EXPECTED_COMPATIBILITY = "1a069ac50f95d2f9ae31307616ab22166c01f8ea9266d356e059bb8f268fc9d8"
EXPECTED_REFERENCE_PROVIDER_SCHEMA = "d5c3d3da384954740c21ee51e3dc733d88bed04ee1a0be3a993207568640e4d0"
EXPECTED_FAILED_RUN = "7380b5fc472bda29c1e9a82d64a73956ad1ec077464e09db33bcd5974ba4d316"
TARGET_POINTER = "#/properties/canonical_proposition/properties/target_payload"
CASES = base.CASES
DISABLED_FEATURES = base.DISABLED_FEATURES

ORIGINAL_VERIFY_UPSTREAMS = base.verify_upstreams
ORIGINAL_PROTECTED_STATE = base.protected_state
ORIGINAL_VALIDATE_PLAN = base.validate_plan


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
    roots = ORIGINAL_VERIFY_UPSTREAMS()
    compatibility = verify_aggregate(
        COMPATIBILITY_RUN, "validation.json",
        "search_plan_v24_structured_output_compatibility_sha256", EXPECTED_COMPATIBILITY,
    )
    failed = verify_aggregate(
        FAILED_RUN, "implementation_manifest.json",
        "search_plan_v24_dev_real_planner_generation_sha256", EXPECTED_FAILED_RUN,
    )
    compatibility_summary = base.load_json(COMPATIBILITY_RUN / "summary.json")
    base.require(compatibility_summary["provider_schema_sha256"] == EXPECTED_REFERENCE_PROVIDER_SCHEMA,
                 "reference provider schema hash mismatch")
    contract = base.load_json(COMPATIBILITY_RUN / "provider_schema_renderer_contract.json")
    base.require(base.sha(ROOT / contract["source_file"]) == contract["source_sha256"],
                 "frozen compatibility renderer source changed")
    base.require(base.sha(ROOT / contract["test_file"]) == contract["test_sha256"],
                 "frozen compatibility renderer tests changed")
    return {
        **roots,
        "artifact_schema_version": "V24DevRealPlannerV2UpstreamRootVerificationV1",
        "search_plan_v24_structured_output_compatibility_sha256": compatibility,
        "provider_schema_canonical_sha256": EXPECTED_REFERENCE_PROVIDER_SCHEMA,
        "preserved_failed_generation_sha256": failed,
        "compatibility_renderer_source_verified": True,
        "verified_before_provider_calls": True,
    }


def protected_state() -> dict[str, str]:
    state = ORIGINAL_PROTECTED_STATE()
    for directory in (COMPATIBILITY_RUN, FAILED_RUN):
        for path in directory.rglob("*"):
            if path.is_file():
                state[str(path.resolve().relative_to(ROOT))] = base.sha(path)
    contract = base.load_json(COMPATIBILITY_RUN / "provider_schema_renderer_contract.json")
    for field in ("source_file", "test_file"):
        path = ROOT / contract[field]
        state[str(path.relative_to(ROOT))] = base.sha(path)
    return dict(sorted(state.items()))


def provider_schema_for_target(target: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    scientific_schema = base.load_json(base.SCHEMA_SOURCE)
    schema, _ = render_provider_schema(
        scientific_schema,
        exact_object_bindings={TARGET_POINTER: target},
    )
    preflight = require_provider_schema_preflight(schema)
    return schema, preflight


def request_identity(case_id: str, target: dict[str, Any]) -> dict[str, str]:
    provider_schema, preflight = provider_schema_for_target(target)
    request_reference = f"v24_dev_real_planner_generation_v2:{case_id}"
    base_key = planner_cache_key(
        target,
        DEFAULT_DEVELOPMENT_CONFIG,
        prompt_version=PROMPT_VERSION,
        schema_version=PLAN_SCHEMA_VERSION,
    )
    provider_hash = preflight["provider_schema_sha256"]
    return {
        "request_reference": request_reference,
        "request_sha256": base.digest(request_reference.encode("utf-8")),
        "target_id": target["scientific_proposition_target_id"],
        "target_sha256": canonical_target_hash(target),
        "planner_config_sha256": planner_config_hash(DEFAULT_DEVELOPMENT_CONFIG),
        "planner_prompt_template_version": PROMPT_VERSION,
        "base_planner_cache_key_sha256": base_key,
        "provider_schema_sha256": provider_hash,
        "planner_cache_key_sha256": planner_cache_key_with_provider_schema(
            base_planner_cache_key=base_key,
            provider_schema_sha256=provider_hash,
        ),
        "provider_schema_renderer_version": RENDERER_VERSION,
        "cache_key_version": CACHE_KEY_VERSION,
    }


def provider_prompt(instruction: bytes, scientific_schema: bytes, target: bytes,
                    identity: dict[str, str]) -> bytes:
    output_identity = {
        key: identity[key] for key in (
            "request_reference", "request_sha256", "target_id", "target_sha256",
            "planner_config_sha256", "planner_prompt_template_version",
            "planner_cache_key_sha256",
        )
    }
    controls = (
        "You are a fresh isolated PROPOSITION_AWARE_QUERY_PLANNER context for exactly one development target.\n"
        "Do not call tools. Do not access files, network, memory, prior conversations, or outside evidence.\n"
        "Use only the frozen instruction, unchanged scientific schema, and canonical target below.\n"
        "Return exactly one JSON object and no Markdown or commentary. Do not emit a final PubMed query string.\n"
        "Copy the canonical target payload without adding, removing, or changing fields.\n"
        "Use these deterministic output identities exactly; they are transport metadata derived only from the allowed inputs:\n"
        + json.dumps(output_identity, sort_keys=True, ensure_ascii=False)
        + "\nThe provider response schema was rendered and locally preflighted before this call. Its hash is "
        + identity["provider_schema_sha256"]
        + ". Do not add this transport-only hash as an output field.\n"
        "Ensure every blueprint has all eleven coverage rows in the exact frozen order.\n\n"
    ).encode("utf-8")
    return b"".join([
        controls,
        b"--- FROZEN PLANNER INSTRUCTION ---\n", instruction,
        b"\n--- UNCHANGED SCIENTIFIC PROPOSITION-AWARE SEARCH PLAN SCHEMA ---\n", scientific_schema,
        b"\n--- CANONICAL SCIENTIFIC PROPOSITION TARGET ---\n", target,
    ])


def configure_base() -> None:
    base.RUN = RUN
    base.WORKSPACE_ROOT = WORKSPACE_ROOT
    base.STAGING_ROOT = STAGING_ROOT
    base.PROMPT_ROOT = PROMPT_ROOT
    base.RESPONSE_ROOT = RESPONSE_ROOT
    base.EVENT_ROOT = EVENT_ROOT
    base.EXECUTION_ROOT = EXECUTION_ROOT
    base.PROTECTED_SNAPSHOT = PROTECTED_SNAPSHOT
    base.verify_upstreams = verify_upstreams
    base.protected_state = protected_state
    base.request_identity = request_identity

    scientific_schema = base.load_json(base.SCHEMA_SOURCE)

    def unchanged_scientific_validation(plan: dict[str, Any], *, expected_target=None):
        validate_scientific_instance(plan, scientific_schema)
        return ORIGINAL_VALIDATE_PLAN(plan, expected_target=expected_target)

    base.validate_plan = unchanged_scientific_validation


def prepare() -> None:
    configure_base()
    roots = verify_upstreams()
    protected = protected_state()
    config = base.planner_config()
    targets = base.targets_by_case()
    base.require(not RUN.exists() or not any(RUN.iterdir()), "v2 generation run already contains files")
    RUN.mkdir(parents=True, exist_ok=True)
    for directory in (WORKSPACE_ROOT, STAGING_ROOT, PROMPT_ROOT, RESPONSE_ROOT, EVENT_ROOT, EXECUTION_ROOT):
        directory.mkdir(parents=True, exist_ok=True)
    base.write_exact(PROTECTED_SNAPSHOT, base.pretty(protected))
    base.write_exact(RUN / "upstream_root_verification.json", base.pretty(roots))

    instruction = base.INSTRUCTION_SOURCE.read_bytes()
    scientific_schema_bytes = base.SCHEMA_SOURCE.read_bytes()
    calls = []
    workspaces = []
    for index, case_id in enumerate(CASES, 1):
        target = targets[case_id]
        provider_schema, preflight = provider_schema_for_target(target)
        identity = request_identity(case_id, target)
        base.require(preflight["status"] == "PASS", f"provider schema preflight failed: {case_id}")
        base.require(identity["provider_schema_sha256"] == preflight["provider_schema_sha256"],
                     f"provider schema identity mismatch: {case_id}")
        if case_id == CASES[0]:
            base.require(identity["provider_schema_sha256"] == EXPECTED_REFERENCE_PROVIDER_SCHEMA,
                         "case 101 did not reproduce frozen reference provider schema")

        workspace = WORKSPACE_ROOT / case_id
        workspace.mkdir(parents=True, exist_ok=True)
        target_body = base.pretty(target)
        files = {
            "canonical_target.json": target_body,
            "planner_instruction.md": instruction,
            "proposition_aware_search_plan_v1_schema.json": scientific_schema_bytes,
            "provider_compatible_schema.json": base.pretty(provider_schema),
        }
        base.require(not ({path.name for path in workspace.iterdir()} - set(files)),
                     f"forbidden existing workspace file: {case_id}")
        for name, body in files.items():
            base.write_exact(workspace / name, body)
        paths = sorted(workspace.iterdir())
        base.require({path.name for path in paths} == set(files), f"workspace membership mismatch: {case_id}")
        base.require(all(path.is_file() and not path.is_symlink() for path in paths),
                     f"workspace must contain physical files: {case_id}")

        prompt = provider_prompt(instruction, scientific_schema_bytes, target_body, identity)
        prompt_path = PROMPT_ROOT / f"{case_id}.txt"
        response_path = RESPONSE_ROOT / f"{case_id}.json"
        event_path = EVENT_ROOT / f"{case_id}.jsonl"
        execution_path = EXECUTION_ROOT / f"{case_id}.json"
        base.write_exact(prompt_path, prompt)
        workspaces.append({
            "case_id": case_id,
            "workspace_path": str(workspace),
            "file_membership": sorted(files),
            "files": [{"path": path.name, "sha256": base.sha(path), "bytes": path.stat().st_size} for path in paths],
            "physical_files_only": True,
            "symlinks_present": False,
            "historical_results_present": False,
            "PASS_A_present": False,
            "PASS_B_present": False,
            "PMIDs_present": False,
            "metrics_present": False,
            "candidate_material_present": False,
            "provider_schema_preflight": preflight,
            "prompt_path_outside_workspace": str(prompt_path),
            "prompt_sha256": base.digest(prompt),
        })
        calls.append({
            "call_index": index,
            "case_id": case_id,
            "provider": "OpenAI",
            "model": "gpt-5.6-sol",
            "reasoning_effort": "high",
            "service_tier": "default",
            "temperature_exposed": False,
            "temperature_override": None,
            "maximum_attempts": 1,
            "automatic_retry": False,
            "manual_repair": False,
            "fresh_isolated_context": True,
            "workspace_path": str(workspace),
            "prompt_path": str(prompt_path),
            "prompt_sha256": base.digest(prompt),
            "response_path": str(response_path),
            "event_path": str(event_path),
            "execution_record_path": str(execution_path),
            **identity,
            "schema_sha256": identity["provider_schema_sha256"],
            "scientific_schema_sha256": base.sha(base.SCHEMA_SOURCE),
            "provider_schema_path": str(workspace / "provider_compatible_schema.json"),
            "static_provider_schema_preflight_pass": True,
            "status": "PREPARED_NOT_CALLED",
        })

    base.write_exact(RUN / "planner_workspace_isolation_audit.json", base.pretty({
        "artifact_schema_version": "V24DevPlannerV2WorkspaceIsolationAuditV1",
        "status": "PASS",
        "workspace_count": 8,
        "files_per_workspace": 4,
        "all_physical_and_isolated": True,
        "allowed_input_categories_only": True,
        "all_provider_schemas_preflight_passed_before_first_call": True,
        "workspaces": workspaces,
    }))
    base.write_exact(RUN / "planner_call_manifest.json", base.pretty({
        "artifact_schema_version": "V24DevPlannerV2CallManifestV1",
        "status": "PREPARED_FOR_EXACTLY_EIGHT_CALLS",
        "configuration": {
            **config,
            "provider_schema_renderer_version": RENDERER_VERSION,
            "cache_key_version": CACHE_KEY_VERSION,
            "scientific_schema_post_validation_required": True,
        },
        "planner_config_sha256": planner_config_hash(DEFAULT_DEVELOPMENT_CONFIG),
        "frozen_prompt_sha256": base.sha(base.INSTRUCTION_SOURCE),
        "unchanged_scientific_schema_sha256": base.sha(base.SCHEMA_SOURCE),
        "compatibility_root": EXPECTED_COMPATIBILITY,
        "reference_provider_schema_sha256": EXPECTED_REFERENCE_PROVIDER_SCHEMA,
        "expected_calls": 8,
        "calls": calls,
    }))
    base.require(protected_state() == protected, "protected state changed during preparation")
    print(json.dumps({
        "status": "READY_FOR_EXACTLY_EIGHT_CALLS",
        "cases": list(CASES),
        "all_provider_schema_preflights_passed": True,
        "provider_schema_hashes": {call["case_id"]: call["provider_schema_sha256"] for call in calls},
    }, indent=2, sort_keys=True))


def execute_one(case_id: str) -> None:
    configure_base()
    base.require(case_id in CASES, "unauthorized development case")
    verify_upstreams()
    base.require(base.load_json(PROTECTED_SNAPSHOT) == protected_state(),
                 "protected state changed before provider call")
    manifest = base.load_json(RUN / "planner_call_manifest.json")
    base.require(all(call["static_provider_schema_preflight_pass"] for call in manifest["calls"]),
                 "not all provider schemas passed preflight before the first call")
    call = next(row for row in manifest["calls"] if row["case_id"] == case_id)
    execution_path = Path(call["execution_record_path"])
    response_path = Path(call["response_path"])
    base.require(not execution_path.exists(), f"provider call already attempted for {case_id}; retry prohibited")
    base.require(not response_path.exists(), f"response already exists for {case_id}; retry prohibited")
    workspace = Path(call["workspace_path"])
    expected_files = {
        "canonical_target.json", "planner_instruction.md",
        "proposition_aware_search_plan_v1_schema.json", "provider_compatible_schema.json",
    }
    base.require({path.name for path in workspace.iterdir()} == expected_files,
                 f"workspace membership changed: {case_id}")
    provider_schema = base.load_json(Path(call["provider_schema_path"]))
    preflight = require_provider_schema_preflight(provider_schema)
    base.require(preflight["provider_schema_sha256"] == call["provider_schema_sha256"],
                 f"provider schema changed after preparation: {case_id}")

    command = [
        "codex", "exec", "--ephemeral", "--ignore-user-config", "--ignore-rules",
        "--model", "gpt-5.6-sol",
        "--config", 'model_reasoning_effort="high"',
        "--config", 'service_tier="default"',
        "--sandbox", "read-only", "--cd", str(workspace), "--skip-git-repo-check",
        "--output-schema", call["provider_schema_path"],
        "--output-last-message", call["response_path"], "--json",
    ]
    for feature in DISABLED_FEATURES:
        command.extend(["--disable", feature])
    command.append("-")
    completed = subprocess.run(
        command,
        input=Path(call["prompt_path"]).read_bytes(),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
        timeout=900,
    )
    event_path = Path(call["event_path"])
    stderr_path = EVENT_ROOT / f"{case_id}.stderr.txt"
    base.write_exact(event_path, completed.stdout)
    base.write_exact(stderr_path, completed.stderr)
    record = {
        "artifact_schema_version": "V24DevPlannerV2CallExecutionRecordV1",
        "case_id": case_id,
        "attempt_count": 1,
        "provider_calls": 1,
        "llm_calls": 1,
        "automatic_retries": 0,
        "manual_repairs": 0,
        "return_code": completed.returncode,
        "response_present": response_path.is_file(),
        "response_sha256": base.sha(response_path) if response_path.is_file() else None,
        "provider_schema_sha256": call["provider_schema_sha256"],
        "static_provider_schema_preflight_pass": True,
        "event_stream_sha256": base.sha(event_path),
        "stderr_sha256": base.sha(stderr_path),
        "accepted_for_raw_freeze": completed.returncode == 0 and response_path.is_file(),
    }
    base.write_exact(execution_path, base.pretty(record))
    base.require(record["accepted_for_raw_freeze"],
                 f"provider call failed closed for {case_id}: rc={completed.returncode}")
    print(json.dumps(record, indent=2, sort_keys=True))


def finalize() -> None:
    configure_base()
    base.finalize()


def freeze_failure() -> None:
    configure_base()
    base.freeze_failure()


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
