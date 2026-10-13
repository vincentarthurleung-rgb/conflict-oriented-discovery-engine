#!/usr/bin/env python3
"""Execute exactly one frozen pilot-bound Quality V2 development request."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.run_search_plan_v24_alpha318b_builder import key as deepseek_key
from scripts.search_plan_v24_alpha317d_preregister_quality_v2_offline import (
    CRITERIA,
    quality_result,
    validate_response,
)


FREEZE = ROOT / "runs/20261012_code_pilot_bound_quality_v2_request_freeze_offline"
FREEZE_MARKER = "code_pilot_bound_quality_v2_request_freeze_sha256"
FREEZE_ROOT = "833635c0728ae885f900a5554b771b91e5ce4ea917e2d4b34aeb649d4159f326"
REQUEST_SHA256 = "b7d3715884ee6f3a8344fdf78f72973e60bb20260da8227789a802583719c1b9"
MODEL = "deepseek-flash"
PROVIDER = "DeepSeek"
URL = "https://api.deepseek.com/v1/chat/completions"

OUT = ROOT / "runs/20261013_code_pilot_bound_quality_v2_development_execution"
ROOT_MARKER = "code_pilot_bound_quality_v2_development_execution_sha256"
FINAL_FILES = {
    "summary.json",
    "execution_manifest.json",
    "provider_response.json",
    "quality_validation.json",
    "candidate_quality_results.json",
    "historical_preservation.json",
    ROOT_MARKER,
}


def require(condition: bool, reason: str) -> None:
    if not condition:
        raise RuntimeError(reason)


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def canonical(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":")).encode("utf-8")


def read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_bytes())
    require(type(value) is dict, "JSON_OBJECT_REQUIRED:" + str(path))
    return value


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def digest(path: Path) -> str:
    require(path.is_file() and not path.is_symlink(),
            "ARTIFACT_MISSING_OR_SYMLINK:" + str(path))
    return sha(path.read_bytes())


def root_hash(directory: Path, marker: str) -> str:
    require(directory.is_dir() and not directory.is_symlink(),
            "ROOT_DIRECTORY_INVALID:" + str(directory))
    require(not any(path.is_symlink() for path in directory.rglob("*")),
            "FROZEN_SYMLINK_FORBIDDEN:" + str(directory))
    files = sorted(path for path in directory.rglob("*")
                   if path.is_file() and path.name != marker)
    return sha(canonical([[path.relative_to(directory).as_posix(), digest(path)]
                          for path in files]))


def verify_root(record: dict[str, Any]) -> dict[str, Any]:
    path = ROOT / record["artifact_path"]
    actual = root_hash(path, record["root_marker"])
    recorded = (path / record["root_marker"]).read_text(
        encoding="ascii").strip()
    require(actual == recorded == record["sha256"],
            "FROZEN_ROOT_MISMATCH:" + record["artifact_path"])
    return {
        "artifact_path": record["artifact_path"],
        "root_marker": record["root_marker"],
        "sha256": actual,
        "verified": True,
    }


def verify_component(record: dict[str, Any]) -> dict[str, Any]:
    path = ROOT / record["artifact_path"]
    actual = digest(path)
    require(actual == record["sha256"],
            "CONTRACT_COMPONENT_HASH_MISMATCH:" + record["artifact_path"])
    return {"artifact_path": record["artifact_path"], "sha256": actual,
            "verified": True}


def write_raw(path: Path, raw: bytes, *, private: bool = False) -> str:
    with path.open("xb") as handle:
        handle.write(raw)
        handle.flush()
        os.fsync(handle.fileno())
    path.chmod(0o600 if private else 0o644)
    return sha(raw)


def write_json(path: Path, value: Any, *, private: bool = False) -> str:
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True,
                     indent=2).encode("utf-8") + b"\n"
    return write_raw(path, raw, private=private)


def verify_preflight() -> dict[str, Any]:
    require(not OUT.exists(), "OUTPUT_ALREADY_EXISTS_NO_REINFERENCE")
    actual_freeze = root_hash(FREEZE, FREEZE_MARKER)
    recorded_freeze = (FREEZE / FREEZE_MARKER).read_text(
        encoding="ascii").strip()
    require(actual_freeze == recorded_freeze == FREEZE_ROOT,
            "QUALITY_REQUEST_FREEZE_ROOT_MISMATCH")

    manifest_path = FREEZE / "quality_request_manifest.json"
    require((manifest_path.stat().st_mode & 0o777) == 0o600,
            "FROZEN_REQUEST_MANIFEST_NOT_PRIVATE")
    manifest = read_json(manifest_path)
    request = manifest.get("request")
    require(type(request) is dict and
            sha(canonical(request)) == manifest.get("request_sha256") == REQUEST_SHA256,
            "FROZEN_REQUEST_SHA256_MISMATCH")
    require(manifest.get("request_id") ==
            "code_pilot_quality_v2_development_request_001" and
            manifest.get("quality_logical_request_count") == 1 and
            manifest.get("source_group_count") == 1 and
            manifest.get("builder_candidate_count") == 3 and
            manifest.get("candidate_set_preserved") is True and
            manifest.get("candidate_filtering_or_substitution") is False and
            manifest.get("execution_authorized") is False,
            "FROZEN_REQUEST_MANIFEST_UNIVERSE_MISMATCH")
    require(set(request) == {"model", "thinking", "reasoning_effort",
                             "response_format", "stream", "messages"} and
            request["model"] == MODEL and
            request["thinking"] == {"type": "enabled"} and
            request["reasoning_effort"] == "high" and
            request["response_format"] == {"type": "json_object"} and
            request["stream"] is False and
            type(request["messages"]) is list and len(request["messages"]) == 2 and
            request["messages"][0].get("role") == "system" and
            request["messages"][1].get("role") == "user",
            "FROZEN_PROVIDER_REQUEST_CONFIGURATION_MISMATCH")

    binding = read_json(FREEZE / "quality_contract_binding.json")
    validation = read_json(FREEZE / "request_validation.json")
    require(validation.get("status") == "PASS" and
            validation.get("check_count") == validation.get("pass_count") == 27 and
            all(validation.get("checks", {}).values()) and
            validation.get("quality_request_sha256") == REQUEST_SHA256,
            "FROZEN_REQUEST_VALIDATION_MISMATCH")
    require(binding["provider_projection"] == {
        "frozen_operational_model": MODEL,
        "historical_protocol_model": "deepseek-v4-pro",
        "only_request_delta": "top-level model",
        "provider": PROVIDER,
        "reasoning_effort": "high",
        "response_format": {"type": "json_object"},
        "stream": False,
        "thinking": {"type": "enabled"},
    } and binding["request_grouping"]["logical_request_count"] == 1 and
            binding["request_grouping"]["candidate_count_in_group"] == 3 and
            binding["retry_semantics"]["automatic_retry"] is False and
            binding["retry_semantics"][
                "known_no_inference_transport_retry_enabled"] is False and
            binding["retry_semantics"][
                "one_scientific_inference_attempt_per_source_group"] is True and
            binding["retry_semantics"][
                "scientific_repair_or_second_opinion"] is False,
            "QUALITY_PROVIDER_GROUPING_OR_RETRY_CONTRACT_MISMATCH")

    roots = {name: verify_root(record) for name, record in
             binding["authoritative_roots"].items()}
    components = {name: verify_component(record) for name, record in
                  binding["contract_components"].items()}
    schema_wrapper = read_json(ROOT / binding["contract_components"][
        "output_schema"]["artifact_path"])
    schema = schema_wrapper.get("schema")
    require(type(schema) is dict and manifest.get("expected_response_schema") == schema,
            "QUALITY_OUTPUT_SCHEMA_MISMATCH")

    payload = manifest.get("quality_payload")
    require(type(payload) is dict and payload.get("source_group_id") ==
            manifest.get("source_group_id") and
            type(payload.get("candidate_packets")) is list and
            len(payload["candidate_packets"]) == 3,
            "QUALITY_PAYLOAD_GROUP_OR_COUNT_MISMATCH")
    packets = payload["candidate_packets"]
    candidate_ids = [packet.get("candidate_id") for packet in packets]
    require(all(type(value) is str for value in candidate_ids) and
            len(set(candidate_ids)) == 3,
            "QUALITY_CANDIDATE_IDENTITY_INVALID")

    quality_order = manifest.get("quality_request_canonical_packet_order")
    original_order = manifest.get("original_builder_candidate_order")
    require(type(quality_order) is list and len(quality_order) == 3 and
            type(original_order) is list and len(original_order) == 3 and
            [row["candidate_id"] for row in quality_order] == candidate_ids and
            {row["candidate_id"] for row in original_order} == set(candidate_ids) and
            [row["quality_packet_position"] for row in quality_order] == [0, 1, 2] and
            {row["original_builder_array_position"] for row in quality_order} ==
                {0, 1, 2},
            "QUALITY_CANDIDATE_ORDER_BINDING_MISMATCH")
    for packet, row in zip(packets, quality_order):
        require(sha(canonical(packet)) == row["packet_sha256"] and
                sha(canonical(packet["evidence"])) == row["evidence_sha256"] and
                sha(packet["evidence"]["bounded_local_context"].encode("utf-8")) ==
                    row["bounded_local_context_sha256"],
                "QUALITY_PACKET_HASH_MISMATCH:" + packet["candidate_id"])

    serialized = canonical(request).decode("utf-8")
    require(manifest.get("private_source_token_present_in_model_visible_payload") is False and
            manifest.get("private_anchor_ids_present_in_model_visible_payload") is False and
            manifest.get("bibliographic_identity_present_in_model_visible_payload") is False and
            not any(row["anchor_id"] in serialized for row in original_order),
            "MODEL_VISIBLE_PRIVATE_IDENTITY_LEAKAGE")

    expected_ids = set(candidate_ids)
    visible_evidence = {
        packet["candidate_id"]: packet["evidence"]["exact_evidence_span"] + "\n" +
        packet["evidence"]["bounded_local_context"]
        for packet in packets
    }
    original_by_id = {row["candidate_id"]: row for row in original_order}
    quality_by_id = {row["candidate_id"]: row for row in quality_order}
    return {
        "freeze_root": actual_freeze,
        "manifest": manifest,
        "request": request,
        "request_sha256": REQUEST_SHA256,
        "schema": schema,
        "payload": payload,
        "candidate_ids": expected_ids,
        "visible_evidence": visible_evidence,
        "original_by_id": original_by_id,
        "quality_by_id": quality_by_id,
        "roots": roots,
        "components": components,
        "request_manifest_sha256": digest(manifest_path),
        "contract_binding_sha256": digest(FREEZE / "quality_contract_binding.json"),
        "request_validation_sha256": digest(FREEZE / "request_validation.json"),
    }


def execute_once(state: dict[str, Any], secret: str) -> dict[str, Any]:
    OUT.mkdir()
    started_at = utc_now()
    started_epoch = time.time()
    predispatch = {
        "schema_version": "CODEPilotQualityV2AttemptStartV1",
        "request_id": state["manifest"]["request_id"],
        "request_sha256": state["request_sha256"],
        "source_group_id": state["payload"]["source_group_id"],
        "candidate_ids_sorted": sorted(state["candidate_ids"]),
        "provider": PROVIDER,
        "model": MODEL,
        "attempt_number": 1,
        "started_at_utc": started_at,
        "started_unix_time": started_epoch,
        "committed_before_network": True,
        "maximum_provider_attempts": 1,
        "automatic_retry": False,
        "repair_call_authorized": False,
    }
    predispatch_raw = json.dumps(predispatch, ensure_ascii=False, sort_keys=True,
                                 indent=2).encode("utf-8") + b"\n"
    working = OUT / ".predispatch_attempt_start.json"
    predispatch_sha = write_raw(working, predispatch_raw, private=True)

    request_bytes = canonical(state["request"])
    require(sha(request_bytes) == REQUEST_SHA256,
            "REQUEST_MUTATED_BEFORE_DISPATCH")
    response: httpx.Response | None = None
    transport_error: dict[str, str] | None = None
    try:
        with httpx.Client(timeout=httpx.Timeout(connect=20.0, read=900.0,
                                                 write=120.0, pool=20.0)) as client:
            response = client.post(URL, headers={
                "Authorization": "Bearer " + secret,
                "Content-Type": "application/json",
            }, content=request_bytes)
    except Exception as exc:  # Preserve authentic terminal transport evidence.
        transport_error = {
            "error_type": type(exc).__name__,
            "error_message": str(exc).replace(secret, "[REDACTED]"),
        }

    finished_at = utc_now()
    finished_epoch = time.time()
    if response is None:
        unavailable = {
            "schema_version": "CODEProviderResponseUnavailableV1",
            "raw_provider_response_available": False,
            "transport_error": transport_error,
        }
        raw = canonical(unavailable) + b"\n"
        response_sha = write_raw(OUT / "provider_response.json", raw, private=True)
        return {
            "predispatch": predispatch,
            "predispatch_raw": predispatch_raw,
            "predispatch_sha256": predispatch_sha,
            "started_at_utc": started_at,
            "finished_at_utc": finished_at,
            "started_unix_time": started_epoch,
            "finished_unix_time": finished_epoch,
            "http_status": None,
            "elapsed_seconds": None,
            "response_sha256": response_sha,
            "response_byte_count": len(raw),
            "envelope": None,
            "envelope_parse_error": None,
            "transport_error": transport_error,
            "provider_response_id": None,
            "provider_model": None,
            "usage": None,
            "cost": None,
            "finish_reason": None,
            "content": None,
        }

    raw = response.content
    response_sha = write_raw(OUT / "provider_response.json", raw, private=True)
    envelope: dict[str, Any] | None = None
    parse_error: dict[str, str] | None = None
    try:
        candidate = response.json()
        require(type(candidate) is dict, "PROVIDER_ENVELOPE_OBJECT_REQUIRED")
        envelope = candidate
    except (ValueError, RuntimeError) as exc:
        parse_error = {"error_type": type(exc).__name__,
                       "error_message": str(exc)}

    content: str | None = None
    finish_reason: str | None = None
    if envelope is not None and response.status_code == 200:
        try:
            choices = envelope["choices"]
            require(type(choices) is list and len(choices) == 1,
                    "PROVIDER_CHOICES_INVALID")
            content = choices[0]["message"]["content"]
            finish_reason = choices[0]["finish_reason"]
            require(type(content) is str and type(finish_reason) is str,
                    "PROVIDER_CONTENT_OR_FINISH_INVALID")
        except (KeyError, TypeError, IndexError, RuntimeError) as exc:
            parse_error = {"error_type": type(exc).__name__,
                           "error_message": str(exc)}

    return {
        "predispatch": predispatch,
        "predispatch_raw": predispatch_raw,
        "predispatch_sha256": predispatch_sha,
        "started_at_utc": started_at,
        "finished_at_utc": finished_at,
        "started_unix_time": started_epoch,
        "finished_unix_time": finished_epoch,
        "http_status": response.status_code,
        "elapsed_seconds": response.elapsed.total_seconds(),
        "response_sha256": response_sha,
        "response_byte_count": len(raw),
        "envelope": envelope,
        "envelope_parse_error": parse_error,
        "transport_error": None,
        "provider_response_id": envelope.get("id") if envelope else None,
        "provider_model": envelope.get("model") if envelope else None,
        "usage": envelope.get("usage") if envelope else None,
        "cost": envelope.get("cost") if envelope else None,
        "finish_reason": finish_reason,
        "content": content,
    }


def quality_state(criteria: dict[str, str]) -> str:
    checked = quality_result(criteria)
    if checked["failed_criteria"]:
        return "QUALITY_FAIL"
    if checked["unresolved_criteria"]:
        return "QUALITY_UNRESOLVED"
    return "QUALITY_PASS"


def finalize(state: dict[str, Any], execution: dict[str, Any]) -> dict[str, Any]:
    http_ok = execution["http_status"] == 200
    model_identity_verified = http_ok and execution["provider_model"] == MODEL
    envelope_valid = (http_ok and execution["envelope"] is not None and
                      execution["envelope_parse_error"] is None and
                      type(execution["content"]) is str and
                      type(execution["finish_reason"]) is str)
    execution_pass = bool(model_identity_verified and envelope_valid)

    returned_positions: dict[str, int] = {}
    parsed_response: dict[str, Any] | None = None
    records: list[dict[str, Any]] = []
    schema_error: str | None = None
    if execution_pass:
        try:
            require(execution["finish_reason"] == "stop",
                    "QUALITY_RESPONSE_INCOMPLETE_FINISH:" +
                    str(execution["finish_reason"]))
            candidate = json.loads(execution["content"])
            require(type(candidate) is dict,
                    "QUALITY_RESPONSE_CONTENT_OBJECT_REQUIRED")
            parsed_response = candidate
            raw_judgments = candidate.get("judgments")
            if type(raw_judgments) is list:
                for position, record in enumerate(raw_judgments):
                    if type(record) is dict and type(record.get("candidate_id")) is str:
                        cid = record["candidate_id"]
                        require(cid not in returned_positions,
                                "DUPLICATE_RETURNED_CANDIDATE_ID")
                        returned_positions[cid] = position
            records = validate_response(
                candidate,
                state["payload"]["source_group_id"],
                state["candidate_ids"],
                state["visible_evidence"],
                state["schema"],
            )
        except (ValueError, RuntimeError, TypeError) as exc:
            schema_error = str(exc)
            records = []

    deterministic_valid = execution_pass and schema_error is None and len(records) == 3
    candidate_results = []
    if deterministic_valid:
        for record in records:  # Canonical ID order from frozen validator.
            cid = record["candidate_id"]
            result = quality_result(record["criteria"])
            original = state["original_by_id"][cid]
            quality_binding = state["quality_by_id"][cid]
            candidate_results.append({
                "candidate_id": cid,
                "identity_binding_method": "OPAQUE_CANDIDATE_ID_EXACT_MATCH",
                "returned_array_position_observed_not_used_for_binding":
                    returned_positions[cid],
                "quality_packet_position": quality_binding[
                    "quality_packet_position"],
                "original_builder_array_position": original[
                    "original_array_position"],
                "candidate_payload_sha256": original["candidate_payload_sha256"],
                "criteria": record["criteria"],
                "quality_state": quality_state(record["criteria"]),
                "failed_criteria": result["failed_criteria"],
                "unresolved_criteria": result["unresolved_criteria"],
                "evidence_support_reference": record[
                    "evidence_support_reference"],
                "reason_contract": (
                    "Provider-returned criterion states plus the exact validated "
                    "candidate-local evidence reference; no controller scientific "
                    "reinterpretation."
                ),
            })

    validation_artifact = {
        "schema_version": "CODEPilotQualityV2DeterministicValidationV1",
        "execution_status": "EXECUTION_PASS" if execution_pass else
                            "EXECUTION_FAILURE",
        "deterministic_validation_status": "PASS" if deterministic_valid else
                                           "FAIL" if execution_pass else
                                           "NOT_EVALUATED",
        "http_status_200": http_ok,
        "model_identity_verified": model_identity_verified,
        "actual_provider_model": execution["provider_model"],
        "finish_reason": execution["finish_reason"],
        "finish_reason_complete": execution["finish_reason"] == "stop",
        "response_schema_valid": deterministic_valid,
        "response_validation_failure": schema_error,
        "source_group_identity_exact": bool(
            parsed_response and parsed_response.get("source_group_id") ==
            state["payload"]["source_group_id"]),
        "candidate_identity_exact_set": bool(
            deterministic_valid and set(returned_positions) ==
            state["candidate_ids"]),
        "candidate_binding_method": "OPAQUE_CANDIDATE_ID_EXACT_SET_NOT_ARRAY_POSITION",
        "expected_candidate_ids_sorted": sorted(state["candidate_ids"]),
        "returned_candidate_ids_sorted": sorted(returned_positions),
        "returned_array_positions_retained_as_observation_only": returned_positions,
        "judgment_count": len(records),
        "all_ten_criteria_present_and_enum_valid": deterministic_valid and
            all(set(record["criteria"]) == set(CRITERIA) for record in records),
        "candidate_local_evidence_references_validated": deterministic_valid,
        "controller_scientific_reinterpretation": False,
        "automatic_retry_used": False,
        "repair_call_used": False,
    }
    validation_sha = write_json(OUT / "quality_validation.json",
                                validation_artifact)

    results_artifact = {
        "schema_version": "CODEPilotQualityV2CandidateResultsV1",
        "development_role": "SEEN_DATA_DEVELOPMENT_EVALUATION",
        "source_group_id": state["payload"]["source_group_id"],
        "candidate_count": len(candidate_results),
        "records_canonical_order": "candidate_id",
        "candidate_records": candidate_results,
        "quality_scores_computed": False,
        "ranking_computed": False,
        "fresh_primary_evidence": False,
    }
    results_sha = write_json(OUT / "candidate_quality_results.json",
                             results_artifact, private=True)

    failure = None
    if not execution_pass:
        failure = {
            "terminal_state": "QUALITY_PROVIDER_EXECUTION_AMBIGUOUS"
            if execution["http_status"] is None else
            "QUALITY_PROVIDER_RESPONSE_UNUSABLE",
            "http_status": execution["http_status"],
            "transport_error": execution["transport_error"],
            "provider_envelope_parse_error": execution[
                "envelope_parse_error"],
            "model_identity_verified": model_identity_verified,
        }
    elif not deterministic_valid:
        failure = {
            "terminal_state": "QUALITY_RESPONSE_INVALID",
            "failure_reason": schema_error,
            "completed_invalid_response_preserved_without_reinference": True,
        }

    execution_manifest = {
        "schema_version": "CODEPilotBoundQualityV2DevelopmentExecutionManifestV1",
        "request_id": state["manifest"]["request_id"],
        "request_freeze_root_sha256": state["freeze_root"],
        "frozen_request": {
            "artifact_path": str((FREEZE / "quality_request_manifest.json").relative_to(ROOT)),
            "file_sha256": state["request_manifest_sha256"],
            "request_sha256": state["request_sha256"],
        },
        "request_payload_regenerated": False,
        "request_payload_modified": False,
        "source_group_id": state["payload"]["source_group_id"],
        "candidate_ids_sorted": sorted(state["candidate_ids"]),
        "provider": PROVIDER,
        "requested_model": MODEL,
        "actual_provider_model": execution["provider_model"],
        "model_identity_verified": model_identity_verified,
        "thinking": {"type": "enabled"},
        "reasoning_effort": "high",
        "logical_quality_requests": 1,
        "provider_attempts": 1,
        "technical_retries": 0,
        "additional_generations": 0,
        "model_substitutions": 0,
        "predispatch_commit": {
            "sha256": execution["predispatch_sha256"],
            "byte_count": len(execution["predispatch_raw"]),
            "record": execution["predispatch"],
        },
        "started_at_utc": execution["started_at_utc"],
        "finished_at_utc": execution["finished_at_utc"],
        "started_unix_time": execution["started_unix_time"],
        "finished_unix_time": execution["finished_unix_time"],
        "http_status": execution["http_status"],
        "elapsed_seconds": execution["elapsed_seconds"],
        "provider_response": {
            "artifact_path": "provider_response.json",
            "sha256": execution["response_sha256"],
            "byte_count": execution["response_byte_count"],
            "raw_bytes_preserved_before_parsing": True,
            "file_mode": "0600",
            "provider_response_id": execution["provider_response_id"],
            "finish_reason": execution["finish_reason"],
        },
        "usage_reported": execution["usage"] is not None,
        "usage": execution["usage"],
        "provider_cost_reported": execution["cost"] is not None,
        "provider_cost": execution["cost"],
        "execution_or_validation_failure": failure,
        "api_credentials_persisted": False,
        "private_source_mapping_model_visible": False,
    }
    manifest_sha = write_json(OUT / "execution_manifest.json",
                              execution_manifest, private=True)

    roots_after = {
        name: verify_root(record)
        for name, record in read_json(FREEZE / "quality_contract_binding.json")[
            "authoritative_roots"].items()
    }
    components_after = {
        name: verify_component(record)
        for name, record in read_json(FREEZE / "quality_contract_binding.json")[
            "contract_components"].items()
    }
    frozen_request_unchanged = (
        sha(canonical(read_json(FREEZE / "quality_request_manifest.json")[
            "request"])) == REQUEST_SHA256 and
        root_hash(FREEZE, FREEZE_MARKER) == FREEZE_ROOT
    )
    preservation = {
        "schema_version": "CODEPilotQualityV2HistoricalPreservationV1",
        "authoritative_roots_before": state["roots"],
        "authoritative_roots_after": roots_after,
        "contract_components_before": state["components"],
        "contract_components_after": components_after,
        "authoritative_roots_unchanged": state["roots"] == roots_after,
        "contract_components_unchanged": state["components"] == components_after,
        "frozen_request_unchanged": frozen_request_unchanged,
        "builder_reexecuted": False,
        "literature_requests": 0,
        "fresh_primary_started": False,
        "pilot_source_remains_seen_development_evidence": True,
        "scientific_policy_changed": False,
        "historical_assets_modified": False,
        "network_calls": 1,
        "llm_calls": 1,
        "quality_calls": 1,
    }
    require(preservation["authoritative_roots_unchanged"] and
            preservation["contract_components_unchanged"] and
            preservation["frozen_request_unchanged"],
            "HISTORICAL_PRESERVATION_FAILURE")
    preservation_sha = write_json(OUT / "historical_preservation.json",
                                  preservation)

    quality_counts = {
        value: sum(record["quality_state"] == value
                   for record in candidate_results)
        for value in ("QUALITY_PASS", "QUALITY_FAIL", "QUALITY_UNRESOLVED")
    }
    recommendation = (
        "STOP_PILOT_BOUND_QUALITY_V2_DEVELOPMENT_EVALUATION_COMPLETE"
        if deterministic_valid else
        "AUDIT_PILOT_BOUND_QUALITY_V2_INVALID_RESPONSE_OFFLINE_OR_STOP"
        if execution_pass else
        "AUDIT_PILOT_BOUND_QUALITY_V2_EXECUTION_FAILURE_OFFLINE_OR_STOP"
    )
    summary = {
        "schema_version": "CODEPilotBoundQualityV2DevelopmentExecutionSummaryV1",
        "quality_execution_status": "PASS" if execution_pass else "FAIL",
        "quality_validation_status": "PASS" if deterministic_valid else
                                     "FAIL" if execution_pass else "NOT_EVALUATED",
        "frozen_request_verified": True,
        "request_sha256": state["request_sha256"],
        "logical_quality_requests": 1,
        "provider_attempts": 1,
        "technical_retries": 0,
        "model_identity_verified": model_identity_verified,
        "provider_response_id": execution["provider_response_id"],
        "usage_reported": execution["usage"] is not None,
        "provider_cost_reported": execution["cost"] is not None,
        "candidate_judgment_count": len(candidate_results),
        "quality_state_counts": quality_counts,
        "identity_binding_method": "OPAQUE_CANDIDATE_ID_EXACT_SET_NOT_ARRAY_POSITION",
        "execution_manifest_sha256": manifest_sha,
        "provider_response_sha256": execution["response_sha256"],
        "quality_validation_sha256": validation_sha,
        "candidate_quality_results_sha256": results_sha,
        "historical_preservation_sha256": preservation_sha,
        "builder_reexecuted": False,
        "literature_requests": 0,
        "fresh_primary_started": False,
        "scientific_policy_changed": False,
        "historical_assets_modified": False,
        "network_calls": 1,
        "llm_calls": 1,
        "quality_calls": 1,
        "next_stage_recommendation": recommendation,
        "root_marker": ROOT_MARKER,
        "root_hash_algorithm": (
            "SHA256(compact canonical JSON of sorted "
            "[relative_path,SHA256(file)] pairs; root marker excluded; no final LF "
            "in hashed JSON)"
        ),
    }
    write_json(OUT / "summary.json", summary)

    working = OUT / ".predispatch_attempt_start.json"
    require(working.read_bytes() == execution["predispatch_raw"],
            "PREDISPATCH_COMMIT_CHANGED")
    working.unlink()
    require({path.name for path in OUT.iterdir() if path.is_file()} ==
            FINAL_FILES - {ROOT_MARKER},
            "UNEXPECTED_FINAL_FILE_SET_BEFORE_MARKER")
    final_root = root_hash(OUT, ROOT_MARKER)
    write_raw(OUT / ROOT_MARKER, (final_root + "\n").encode("ascii"))
    require(root_hash(OUT, ROOT_MARKER) == final_root,
            "FINAL_EXECUTION_ROOT_RECOMPUTATION_FAILED")
    require((OUT / "provider_response.json").stat().st_mode & 0o777 == 0o600 and
            (OUT / "execution_manifest.json").stat().st_mode & 0o777 == 0o600 and
            (OUT / "candidate_quality_results.json").stat().st_mode & 0o777 == 0o600,
            "PRIVATE_ARTIFACT_FILE_MODE_INVALID")
    return {**summary, "execution_root_sha256": final_root,
            "candidate_records": candidate_results}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--preflight-only", action="store_true")
    args = parser.parse_args()
    state = verify_preflight()
    secret = deepseek_key()
    require(bool(secret), "DEEPSEEK_CREDENTIAL_UNAVAILABLE")
    if args.preflight_only:
        print(json.dumps({
            "status": "PASS",
            "freeze_root_sha256": state["freeze_root"],
            "request_sha256": state["request_sha256"],
            "logical_quality_requests": 1,
            "candidate_count": len(state["candidate_ids"]),
            "credential_available": True,
            "network_calls": 0,
        }, sort_keys=True), flush=True)
        return
    execution = execute_once(state, secret)
    result = finalize(state, execution)
    print(json.dumps({
        "quality_execution_status": result["quality_execution_status"],
        "quality_validation_status": result["quality_validation_status"],
        "provider_attempts": result["provider_attempts"],
        "candidate_judgment_count": result["candidate_judgment_count"],
        "quality_state_counts": result["quality_state_counts"],
        "execution_root_sha256": result["execution_root_sha256"],
    }, sort_keys=True), flush=True)


if __name__ == "__main__":
    main()
