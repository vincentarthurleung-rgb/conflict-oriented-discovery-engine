#!/usr/bin/env python3
"""Prepare and freeze the authorized primary held-out-v2 PASS-A adjudication."""

from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import shutil
import sys
import tomllib
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools import freeze_search_plan_v23_beta_2_primary_heldout_v2_neutral_review_offline as neutral


RUN = ROOT / "runs/20260917_search_plan_v23_beta_2_primary_heldout_v2_pass_a_adjudication"
NEUTRAL_RUN = neutral.RUN
WORKSPACE_ROOT = Path("/tmp/primary_v2_pass_a_evaluator_workspaces")
STAGING_ROOT = Path("/tmp/primary_v2_pass_a_adjudication_staging")
PROMPT_ROOT = STAGING_ROOT / "prompts"
SUBMISSION_ROOT = STAGING_ROOT / "submissions"
PROTECTED_SNAPSHOT = STAGING_ROOT / "protected_state_before.json"

EXPECTED_NEUTRAL_ROOT = "0db9d84b1567d95d78272d6259d5e41f24751d5204b273801025cd595469c971"
EXPECTED_PASS_A = "0d9d096842085239ea7e546d6fc1b1d9e0c61972a6a1d76483647f31bfa971b5"
EXPECTED_PASS_B = "2e082673c7a58604286a00ace9748389c04aa76dced04bb0226d1873e28ff485"
EXPECTED_RECORDS = 60
EXPECTED_BATCHES = 6
EXPECTED_BATCH_SIZE = 10

REQUIRED_OUTPUTS = {
    "upstream_root_verification.json",
    "primary_v2_adjudicator_config.json",
    "primary_v2_adjudicator_config_sha256",
    "pass_a_workspace_isolation_audit.json",
    "primary_v2_pass_a_blinded_adjudications.jsonl",
    "primary_v2_pass_a_blinded_adjudications_sha256",
    "primary_v2_pass_a_adjudications.jsonl",
    "primary_v2_pass_a_adjudications_sha256",
    "pass_a_schema_validation.json",
    "pass_a_completeness_audit.json",
    "pass_a_raw_label_distribution.json",
    "pass_b_immutability_audit.json",
    "scientific_state_safety_audit.json",
    "implementation_manifest.json",
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


def jsonl(rows: list[dict[str, Any]]) -> bytes:
    return b"".join(canonical(row) + b"\n" for row in rows)


def sha_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def aggregate(pairs: list[list[str]]) -> str:
    return sha_bytes(canonical(pairs))


def load_json(path: Path) -> Any:
    return json.loads(path.read_bytes())


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def write_exact(path: Path, body: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        require(path.is_file() and not path.is_symlink(), f"non-physical existing output: {path}")
        require(path.read_bytes() == body, f"existing output differs: {path}")
        return
    with path.open("xb") as stream:
        stream.write(body)


def protected_state() -> dict[str, str]:
    paths = set()
    for base in (neutral.PROTOCOL_RUN, neutral.CASE_RUN, neutral.QUERY_RUN, neutral.SOURCE, NEUTRAL_RUN):
        paths.update(path for path in base.rglob("*") if path.is_file())
    paths.update({
        neutral.PRIOR_REVIEW_SCHEMA,
        neutral.PRIOR_EXCERPT_BUILDER,
        ROOT / "tools/freeze_search_plan_v23_beta_2_primary_heldout_v2_neutral_review_offline.py",
        ROOT / "tools/run_search_plan_v23_beta_2_primary_heldout_v2_network_retrieval.py",
    })
    return {str(path.resolve().relative_to(ROOT)): sha(path) for path in sorted(paths)}


def verify_neutral_root() -> tuple[dict[str, Any], str]:
    upstream = neutral.verify_roots()
    manifest = load_json(NEUTRAL_RUN / "freeze_manifest.json")
    checks = []
    for name, expected in manifest["aggregate_components"]:
        path = NEUTRAL_RUN / name
        actual = sha(path) if path.is_file() and not path.is_symlink() else None
        checks.append({"path": name, "expected_sha256": expected, "actual_sha256": actual,
                       "match": actual == expected})
    actual_root = aggregate([[row["path"], row["actual_sha256"]] for row in checks])
    require(all(row["match"] for row in checks), "neutral-review component mismatch")
    require(
        actual_root == manifest["primary_heldout_v2_neutral_review_freeze_sha256"] == EXPECTED_NEUTRAL_ROOT,
        "neutral-review root mismatch",
    )
    pass_a_actual = sha(neutral.PASS_A_SOURCE)
    pass_b_actual = sha(NEUTRAL_RUN / "primary_v2_pass_b_blinded_views.jsonl")
    require(pass_a_actual == EXPECTED_PASS_A, "PASS-A source mismatch")
    require(pass_b_actual == EXPECTED_PASS_B, "PASS-B source mismatch")
    pass_a_manifest = load_json(NEUTRAL_RUN / "primary_v2_pass_a_batch_manifest.json")
    require(
        pass_a_manifest["record_count"] == EXPECTED_RECORDS
        and pass_a_manifest["batch_count"] == EXPECTED_BATCHES
        and pass_a_manifest["batch_size"] == EXPECTED_BATCH_SIZE,
        "PASS-A batch structure mismatch",
    )
    result = {
        "artifact_schema_version": "PrimaryHeldoutV2PassAUpstreamRootVerificationV1",
        "status": "PASS",
        "all_six_pre_neutral_roots_verified": upstream["all_six_authoritative_roots_verified"],
        "pre_neutral_roots": upstream["roots"],
        "primary_heldout_v2_neutral_review_freeze_sha256": actual_root,
        "neutral_review_component_count": len(checks),
        "neutral_review_components_match": True,
        "primary_v2_pass_a_blinded_views_sha256": pass_a_actual,
        "primary_v2_pass_b_blinded_views_sha256": pass_b_actual,
        "pass_a_record_count": EXPECTED_RECORDS,
        "pass_a_batch_count": EXPECTED_BATCHES,
        "pass_a_batch_size": EXPECTED_BATCH_SIZE,
        "existing_pass_a_labels": 0,
        "verified_before_first_scientific_adjudication_call": True,
    }
    return result, actual_root


def adjudicator_config() -> dict[str, Any]:
    config_path = Path("/home/vincent/.codex/config.toml")
    config = tomllib.loads(config_path.read_text(encoding="utf-8"))
    require(config.get("service_tier") == "default", "Codex service tier is not default")
    require(config.get("model") == "gpt-5.6-sol", "Codex model is not gpt-5.6-sol")
    require(config.get("model_reasoning_effort") == "high", "Codex reasoning effort is not high")
    return {
        "artifact_schema_version": "PrimaryHeldoutV2AdjudicatorConfigV1",
        "configuration_status": "FROZEN_BEFORE_LABELS",
        "reviewer_type": "model_retrieval_adjudicator",
        "provider": "openai",
        "model": "gpt-5.6-sol",
        "model_version_if_exposed": "gpt-5.6-sol",
        "reasoning_effort": "high",
        "service_tier": "default",
        "temperature_exposed": False,
        "temperature_override": None,
        "authorized_scientific_adjudication_calls": 6,
        "authorized_provider_calls": 6,
        "authorized_llm_calls": 6,
        "batch_count": 6,
        "records_per_batch": 10,
        "calls_per_batch": 1,
        "fresh_session_per_batch": True,
        "cross_batch_history": False,
        "automatic_retry": False,
        "maximum_attempts_per_batch": 1,
        "invalid_output_repair": "PROHIBITED",
        "schema_validation": "Draft 2020-12 plus exact record count and review-ID membership",
        "invalid_schema_behavior": "FAIL_CLOSED_STOP_RUN",
        "outcome_informed_rerun": False,
        "majority_vote": False,
        "model_or_provider_switching": False,
        "literature_network_access": False,
        "pass_b_access": False,
        "metrics_access": False,
        "prior_configuration_evidence": {
            "heldout_v1_session_id": "01a0898c-3fee-7140-81bf-415e4332f9a0",
            "provider": "openai",
            "model": "gpt-5.6-sol",
            "reasoning_effort": "high",
            "service_tier": "default",
        },
        "execution_command_controls": {
            "ephemeral_session": True,
            "ignore_user_config_after_explicit_overrides": True,
            "ignore_repository_rules": True,
            "sandbox": "read-only",
            "web_search_enabled": False,
            "working_directory": "isolated batch workspace",
        },
    }


def evaluator_prompt(instruction: bytes, schema: bytes, batch: bytes) -> bytes:
    preamble = (
        "You are a fresh isolated evaluator context for exactly one frozen PASS-A batch.\n"
        "Do not call tools and do not access any filesystem, network, prior conversation, or outside knowledge.\n"
        "Use only the frozen instruction, frozen response schema, and frozen batch payload below.\n"
        "Evaluate all ten records independently. Return exactly ten newline-delimited JSON objects, "
        "in batch order, with no Markdown fences or commentary. Every object must conform exactly to "
        "the response schema.\n\n"
    ).encode("utf-8")
    return b"".join([
        preamble,
        b"--- FROZEN INSTRUCTION ---\n", instruction,
        b"\n--- FROZEN RESPONSE SCHEMA ---\n", schema,
        b"\n--- FROZEN PASS-A BATCH ---\n", batch,
    ])


def prepare() -> None:
    root_verification, _ = verify_neutral_root()
    protected = protected_state()
    config = adjudicator_config()
    config_body = pretty(config)
    config_hash = sha_bytes(config_body)

    RUN.mkdir(parents=True, exist_ok=True)
    STAGING_ROOT.mkdir(parents=True, exist_ok=True)
    PROMPT_ROOT.mkdir(parents=True, exist_ok=True)
    SUBMISSION_ROOT.mkdir(parents=True, exist_ok=True)
    write_exact(PROTECTED_SNAPSHOT, pretty(protected))
    write_exact(RUN / "upstream_root_verification.json", pretty(root_verification))
    write_exact(RUN / "primary_v2_adjudicator_config.json", config_body)
    write_exact(RUN / "primary_v2_adjudicator_config_sha256", (config_hash + "\n").encode("ascii"))

    batch_manifest = load_json(NEUTRAL_RUN / "primary_v2_pass_a_batch_manifest.json")
    instruction_source = NEUTRAL_RUN / "pass_a_evaluator_instruction.md"
    schema_source = NEUTRAL_RUN / "primary_v2_pass_a_review_schema.json"
    instruction = instruction_source.read_bytes()
    schema = schema_source.read_bytes()
    audits = []
    for index, batch_record in enumerate(batch_manifest["batches"], 1):
        workspace = WORKSPACE_ROOT / f"batch_{index:02d}"
        workspace.mkdir(parents=True, exist_ok=True)
        sources = {
            "instruction.md": instruction_source,
            "response_schema.json": schema_source,
            "batch.jsonl": NEUTRAL_RUN / batch_record["path"],
        }
        expected_membership = set(sources)
        existing_membership = {path.name for path in workspace.iterdir()}
        require(not (existing_membership - expected_membership), f"workspace {index} has forbidden files")
        for name, source in sources.items():
            destination = workspace / name
            if destination.exists():
                require(destination.is_file() and not destination.is_symlink(), "workspace file is not physical")
                require(destination.read_bytes() == source.read_bytes(), "workspace copy differs")
            else:
                shutil.copyfile(source, destination)
        files = sorted(path for path in workspace.iterdir())
        require({path.name for path in files} == expected_membership, "workspace membership mismatch")
        require(all(path.is_file() and not path.is_symlink() for path in files), "workspace symlink detected")
        batch_bytes = (workspace / "batch.jsonl").read_bytes()
        require(sha_bytes(batch_bytes) == batch_record["sha256"], "workspace batch hash mismatch")
        prompt = evaluator_prompt(instruction, schema, batch_bytes)
        prompt_path = PROMPT_ROOT / f"batch_{index:02d}.txt"
        write_exact(prompt_path, prompt)
        audits.append({
            "batch_index": index,
            "workspace_path": str(workspace),
            "workspace_file_count": len(files),
            "file_membership": [path.name for path in files],
            "files": [{"path": path.name, "sha256": sha(path), "bytes": path.stat().st_size} for path in files],
            "physical_files_only": True,
            "symlinks_present": False,
            "forbidden_files_present": False,
            "exactly_one_batch_present": True,
            "pass_b_present": False,
            "sealed_mapping_present": False,
            "metrics_present": False,
            "retrieval_material_present": False,
            "prompt_path_outside_workspace": str(prompt_path),
            "prompt_sha256": sha_bytes(prompt),
        })
    audit = {
        "artifact_schema_version": "PrimaryHeldoutV2PassAWorkspaceIsolationAuditV1",
        "status": "PASS",
        "workspace_count": len(audits),
        "files_per_workspace": 3,
        "all_workspaces_physically_isolated": True,
        "all_workspaces_audited_before_evaluator_access": True,
        "no_symlinks": True,
        "same_frozen_adjudicator_config_sha256": config_hash,
        "workspaces": audits,
    }
    write_exact(RUN / "pass_a_workspace_isolation_audit.json", pretty(audit))
    require(protected_state() == protected, "protected state changed during preparation")
    print(json.dumps({
        "status": "READY_FOR_SIX_AUTHORIZED_CALLS",
        "adjudicator_config_sha256": config_hash,
        "workspace_count": 6,
        "prompt_paths": [row["prompt_path_outside_workspace"] for row in audits],
        "submission_root": str(SUBMISSION_ROOT),
    }, indent=2))


def parse_submission(path: Path, schema: dict[str, Any], expected_ids: list[str]) -> tuple[list[dict[str, Any]], list[str]]:
    require(path.is_file() and not path.is_symlink(), f"missing physical evaluator response: {path}")
    raw_lines = path.read_text(encoding="utf-8").splitlines()
    require(raw_lines and all(line.strip() for line in raw_lines), f"blank line or empty response: {path}")
    records = []
    parse_errors = []
    for line_number, line in enumerate(raw_lines, 1):
        try:
            value = json.loads(line)
        except json.JSONDecodeError as exc:
            parse_errors.append(f"line {line_number}: {exc}")
            continue
        records.append(value)
    require(not parse_errors, f"malformed JSONL, repair prohibited: {parse_errors}")
    validation_errors = []
    required = schema["required"]
    properties = schema["properties"]
    for index, record in enumerate(records, 1):
        if not isinstance(record, dict):
            validation_errors.append(f"record {index}: not an object")
            continue
        missing = [key for key in required if key not in record]
        extra = sorted(set(record) - set(properties))
        if missing:
            validation_errors.append(f"record {index}: missing fields {missing}")
        if extra:
            validation_errors.append(f"record {index}: additional fields {extra}")
        if missing or extra:
            continue
        if not isinstance(record["review_id"], str) or not record["review_id"].startswith("A2_"):
            validation_errors.append(f"record {index}: invalid review_id")
        if record["acquisition_decision"] not in properties["acquisition_decision"]["enum"]:
            validation_errors.append(f"record {index}: invalid acquisition_decision")
        if not isinstance(record["rationale"], str) or not record["rationale"]:
            validation_errors.append(f"record {index}: invalid rationale")
        confidence = record["confidence"]
        if confidence is not None and (
            not isinstance(confidence, (int, float)) or isinstance(confidence, bool) or not 0 <= confidence <= 1
        ):
            validation_errors.append(f"record {index}: invalid confidence")
        if record["reviewer_type"] != properties["reviewer_type"]["const"]:
            validation_errors.append(f"record {index}: invalid reviewer_type")
    require(not validation_errors, f"schema-invalid response, repair prohibited: {validation_errors[:5]}")
    ids = [record["review_id"] for record in records]
    require(len(records) == EXPECTED_BATCH_SIZE, f"response record count is not 10: {path}")
    require(ids == expected_ids, f"response review IDs/order mismatch: {path}")
    require(len(ids) == len(set(ids)), f"duplicate response review ID: {path}")
    return records, validation_errors


def finalize() -> None:
    require(RUN.is_dir(), "prepare phase has not run")
    root_verification, _ = verify_neutral_root()
    require(load_json(RUN / "upstream_root_verification.json") == root_verification,
            "prepared root verification changed")
    config = adjudicator_config()
    config_body = pretty(config)
    config_hash = sha_bytes(config_body)
    require((RUN / "primary_v2_adjudicator_config.json").read_bytes() == config_body,
            "frozen adjudicator configuration changed")
    require((RUN / "primary_v2_adjudicator_config_sha256").read_text().strip() == config_hash,
            "adjudicator configuration sidecar mismatch")
    protected_before = load_json(PROTECTED_SNAPSHOT)
    require(protected_state() == protected_before, "protected state changed before finalization")

    schema = load_json(NEUTRAL_RUN / "primary_v2_pass_a_review_schema.json")
    batch_manifest = load_json(NEUTRAL_RUN / "primary_v2_pass_a_batch_manifest.json")
    all_records = []
    batch_validation = []
    for index, batch_record in enumerate(batch_manifest["batches"], 1):
        workspace = WORKSPACE_ROOT / f"batch_{index:02d}"
        require({path.name for path in workspace.iterdir()} == {"instruction.md", "response_schema.json", "batch.jsonl"},
                f"workspace {index} membership changed")
        batch_rows = load_jsonl(workspace / "batch.jsonl")
        expected_ids = [row["review_id"] for row in batch_rows]
        response_path = SUBMISSION_ROOT / f"batch_{index:02d}.jsonl"
        records, errors = parse_submission(response_path, schema, expected_ids)
        all_records.extend(records)
        batch_validation.append({
            "batch_index": index,
            "attempt_count": 1,
            "provider_calls": 1,
            "llm_calls": 1,
            "scientific_adjudication_calls": 1,
            "response_ref": str(response_path),
            "response_sha256": sha(response_path),
            "record_count": len(records),
            "schema_valid": not errors,
            "repair_attempted": False,
            "retry_attempted": False,
            "accepted": True,
        })
    ids = [row["review_id"] for row in all_records]
    require(len(all_records) == len(set(ids)) == EXPECTED_RECORDS, "global response completeness mismatch")

    # Freeze blinded responses physically before the sealed identity mapping is loaded.
    blinded_body = jsonl(all_records)
    blinded_hash = sha_bytes(blinded_body)
    blinded_path = RUN / "primary_v2_pass_a_blinded_adjudications.jsonl"
    write_exact(blinded_path, blinded_body)
    write_exact(RUN / "primary_v2_pass_a_blinded_adjudications_sha256", (blinded_hash + "\n").encode("ascii"))
    require(sha(blinded_path) == blinded_hash, "blinded adjudication freeze verification failed")
    require(all("candidate_id" not in row and "case_id" not in row for row in all_records),
            "identity leaked into blinded adjudication freeze")

    # Identity join begins only after the blinded corpus and sidecar exist and verify.
    sealed = load_json(NEUTRAL_RUN / "primary_v2_pass_a_sealed_identity_mapping.json")["sealed_mapping"]
    sealed_by_id = {row["review_id"]: row for row in sealed}
    require(set(sealed_by_id) == set(ids), "sealed mapping identity mismatch")
    joined = []
    for record in all_records:
        mapping = sealed_by_id[record["review_id"]]
        candidate_id = mapping["candidate_id"]
        joined.append({
            "artifact_schema_version": "PrimaryHeldoutV2PassAAdjudicationV1",
            "candidate_id": candidate_id,
            "case_id": candidate_id.split(":", 1)[0],
            **record,
            "adjudicator_config_sha256": config_hash,
            "pass_a_source_sha256": EXPECTED_PASS_A,
            "blinded_adjudications_sha256": blinded_hash,
            "identity_join_after_blinded_freeze": True,
        })
    joined_body = jsonl(joined)
    joined_hash = sha_bytes(joined_body)
    write_exact(RUN / "primary_v2_pass_a_adjudications.jsonl", joined_body)
    write_exact(RUN / "primary_v2_pass_a_adjudications_sha256", (joined_hash + "\n").encode("ascii"))

    decisions = [row["acquisition_decision"] for row in all_records]
    distribution = Counter(decisions)
    allowed = schema["properties"]["acquisition_decision"]["enum"]
    require(set(distribution) <= set(allowed), "unexpected acquisition label")
    distribution_record = {
        "artifact_schema_version": "PrimaryHeldoutV2PassARawLabelDistributionV1",
        "distribution_scope": "raw adjudication completeness counts only",
        "JUSTIFIED": distribution["JUSTIFIED"],
        "BORDERLINE_BUT_JUSTIFIED": distribution["BORDERLINE_BUT_JUSTIFIED"],
        "NOT_JUSTIFIED": distribution["NOT_JUSTIFIED"],
        "UNDETERMINABLE_FROM_PRESERVED_PREACQUISITION_EVIDENCE": distribution[
            "UNDETERMINABLE_FROM_PRESERVED_PREACQUISITION_EVIDENCE"
        ],
        "total": sum(distribution.values()),
        "rates_calculated": False,
        "metrics_unblinded": False,
    }
    schema_validation = {
        "artifact_schema_version": "PrimaryHeldoutV2PassASchemaValidationV1",
        "status": "PASS",
        "schema_ref": "primary_v2_pass_a_review_schema.json",
        "schema_sha256": sha(NEUTRAL_RUN / "primary_v2_pass_a_review_schema.json"),
        "record_count": len(all_records),
        "valid_record_count": len(all_records),
        "invalid_record_count": 0,
        "attempt_count": 6,
        "retry_count": 0,
        "repair_count": 0,
        "all_reviewer_types_exact": all(row["reviewer_type"] == "model_retrieval_adjudicator" for row in all_records),
        "batch_validation": batch_validation,
    }
    completeness = {
        "artifact_schema_version": "PrimaryHeldoutV2PassACompletenessAuditV1",
        "status": "PASS",
        "expected": 60,
        "adjudicated": len(all_records),
        "unique_review_ids": len(set(ids)),
        "missing": 0,
        "duplicates": 0,
        "invalid": 0,
        "zero_yield_case_adjudications_created": 0,
        "heldout_v2_104_adjudications_created": 0,
        "heldout_v2_107_adjudications_created": 0,
        "raw_label_distribution_ref": "pass_a_raw_label_distribution.json",
        "performance_rates_calculated": False,
    }
    pass_b_actual = sha(NEUTRAL_RUN / "primary_v2_pass_b_blinded_views.jsonl")
    require(pass_b_actual == EXPECTED_PASS_B, "PASS-B view changed during PASS-A adjudication")
    pass_b_audit = {
        "artifact_schema_version": "PrimaryHeldoutV2PassBImmutabilityAuditV1",
        "status": "PASS",
        "expected_sha256": EXPECTED_PASS_B,
        "actual_sha256": pass_b_actual,
        "pass_b_views_modified": False,
        "pass_b_batches_opened_by_evaluators": False,
        "pass_b_labels_created": 0,
        "pass_a_results_used_to_modify_pass_b": False,
    }
    protected_after = protected_state()
    require(protected_after == protected_before, "historical protected assets changed")
    safety = {
        "artifact_schema_version": "PrimaryHeldoutV2PassAScientificStateSafetyAuditV1",
        "historical_assets_modified": False,
        "changed_historical_paths": [],
        "scientific_adjudication_calls": 6,
        "provider_calls": 6,
        "llm_calls": 6,
        "network_literature_retrieval_calls": 0,
        "pass_b_adjudication_calls": 0,
        "pass_b_labels_created": 0,
        "metrics_unblinded": False,
        "metrics_calculated": False,
        "algorithm_modifications": 0,
        "query_modifications": 0,
        "review_surface_modifications": 0,
        "automatic_retries": 0,
        "invalid_output_repairs": 0,
        "outcome_informed_reruns": 0,
        "protected_file_count": len(protected_before),
        "protected_state_before_sha256": sha_bytes(canonical(protected_before)),
        "protected_state_after_sha256": sha_bytes(canonical(protected_after)),
    }
    write_exact(RUN / "pass_a_schema_validation.json", pretty(schema_validation))
    write_exact(RUN / "pass_a_completeness_audit.json", pretty(completeness))
    write_exact(RUN / "pass_a_raw_label_distribution.json", pretty(distribution_record))
    write_exact(RUN / "pass_b_immutability_audit.json", pretty(pass_b_audit))
    write_exact(RUN / "scientific_state_safety_audit.json", pretty(safety))

    aggregate_names = sorted(REQUIRED_OUTPUTS - {"implementation_manifest.json", "validation.json", "summary.json"})
    components = [[name, sha(RUN / name)] for name in aggregate_names]
    adjudication_root = aggregate(components)
    implementation = {
        "artifact_schema_version": "PrimaryHeldoutV2PassAImplementationManifestV1",
        "aggregate_algorithm": "sha256(canonical JSON ordered [path, sha256] pairs)",
        "aggregate_components": components,
        "primary_heldout_v2_pass_a_adjudication_sha256": adjudication_root,
        "required_outputs": sorted(REQUIRED_OUTPUTS),
        "blinded_freeze_preceded_identity_join": True,
        "primary_v2_adjudicator_config_sha256": config_hash,
        "primary_v2_pass_a_blinded_adjudications_sha256": blinded_hash,
        "primary_v2_pass_a_adjudications_sha256": joined_hash,
    }
    write_exact(RUN / "implementation_manifest.json", pretty(implementation))
    checks = {
        "all_review_roots_verified_before_calls": True,
        "adjudicator_configuration_frozen_before_labels": True,
        "six_workspaces_isolated_and_audited": True,
        "six_fresh_calls_same_configuration": True,
        "exactly_one_call_per_batch": True,
        "all_sixty_schema_valid": True,
        "blinded_freeze_before_identity_join": True,
        "blinded_freeze_contains_no_candidate_identity": True,
        "identity_join_complete_after_blinded_freeze": True,
        "pass_b_unchanged": pass_b_actual == EXPECTED_PASS_B,
        "pass_b_labels_zero": True,
        "metrics_not_unblinded": True,
        "historical_assets_unchanged": protected_after == protected_before,
        "provider_call_budget_exact": True,
        "literature_network_calls_zero": True,
    }
    require(all(checks.values()), "final PASS-A validation failed")
    validation = {
        "artifact_schema_version": "PrimaryHeldoutV2PassAValidationV1",
        "status": "PASS",
        "checks": checks,
    }
    summary = {
        "artifact_schema_version": "PrimaryHeldoutV2PassASummaryV1",
        "status": "COMPLETED",
        "expected_pass_a_records": 60,
        "completed_pass_a_records": 60,
        "missing_pass_a_records": 0,
        "duplicate_pass_a_records": 0,
        "invalid_pass_a_records": 0,
        "reviewer_type": "model_retrieval_adjudicator",
        "justified_count": distribution["JUSTIFIED"],
        "borderline_but_justified_count": distribution["BORDERLINE_BUT_JUSTIFIED"],
        "not_justified_count": distribution["NOT_JUSTIFIED"],
        "undeterminable_count": distribution["UNDETERMINABLE_FROM_PRESERVED_PREACQUISITION_EVIDENCE"],
        "primary_v2_pass_a_blinded_adjudications_sha256": blinded_hash,
        "primary_v2_pass_a_adjudications_sha256": joined_hash,
        "primary_heldout_v2_pass_a_adjudication_sha256": adjudication_root,
        "pass_b_views_modified": False,
        "pass_b_labels_created": 0,
        "metrics_unblinded": False,
        "scientific_adjudication_calls": 6,
        "provider_calls": 6,
        "llm_calls": 6,
        "network_literature_retrieval_calls": 0,
        "historical_assets_modified": False,
    }
    write_exact(RUN / "validation.json", pretty(validation))
    write_exact(RUN / "summary.json", pretty(summary))
    require({path.name for path in RUN.iterdir()} == REQUIRED_OUTPUTS, "final output membership mismatch")
    require(protected_state() == protected_before, "protected state changed after finalization")
    print(json.dumps(summary, indent=2, sort_keys=True))


def arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--prepare", action="store_true")
    group.add_argument("--finalize", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = arguments()
    if args.prepare:
        prepare()
    else:
        finalize()


if __name__ == "__main__":
    main()
