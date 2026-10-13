#!/usr/bin/env python3
"""Execute the one frozen pilot-bound Builder V4 development request."""

from __future__ import annotations

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

from code_engine.construction import handoff_adapter
from scripts.run_search_plan_v24_alpha318b_builder import key as deepseek_key
from scripts.run_search_plan_v24_alpha320c_builder_v4_execution import (
    URL as DEEPSEEK_URL,
    provider_failure_state,
)
from scripts.run_search_plan_v24_alpha320d_deterministic_variant_evaluation_offline import (
    independent_reference_leakage,
    production_leakage_metrics,
    structural_result,
)
from scripts.search_plan_v24_alpha318b_post_builder_prechecks import (
    evidence_sentence,
    private_identity_from_jats,
    validate_builder_response,
)
from scripts.search_plan_v24_alpha320a_v4_localizer import (
    SUCCESS as LOCALIZATION_SUCCESS,
    localize_exact_body_quote,
)


FREEZE = ROOT / "runs/20261012_code_pilot_bound_builder_v4_request_freeze_offline"
FREEZE_MARKER = "code_pilot_bound_builder_v4_request_freeze_sha256"
FREEZE_ROOT = "0ebf44c361fc9e2cde04b7562b5e559c2ee0c25602383083cb62471b3fde307e"
REQUEST_SHA256 = "88fd33cea837ed688368ac8b3fe057c7b2e1021453fd85d627ca115642770b25"
DOCUMENT_SHA256 = "5b6750308b2cfdf496200f21383399ae27431c75923c1d7af18cca5a24476c8f"
PROMPT_SHA256 = "6af5b7f3cd8b23cc65e4ee9c3e85eb955d760f7f06e88a48722be213454d7592"
OUTPUT_SCHEMA_SHA256 = "e6b65571708d196b9fb7a4b8c4af71f46e8680b4b078a6ebedd9ece28658f1c1"

ADAPTER = ROOT / "runs/20261012_code_minimal_immutable_handoff_to_construction_adapter_offline"
ADAPTER_MARKER = "code_minimal_immutable_handoff_to_construction_adapter_sha256"
ADAPTER_ROOT = "d8a05a63f48f0fa71c319c25d4f0cf622127cbcee866465e01b7228181f709ea"
SMOKE = ROOT / "runs/20261012_code_post_pilot_scientific_handoff_smoke_offline"
SMOKE_MARKER = "code_post_pilot_scientific_handoff_smoke_sha256"
SMOKE_ROOT = "53a79c029ae6a3b7127ccf3a1e1cd0c7df63c60d94638e7a4debc3471108a902"
PILOT = ROOT / "runs/20261012_search_plan_v24_dev_alpha3_22f_first_controlled_live_pilot"
PILOT_MARKER = "search_plan_v24_dev_alpha3_22f_first_controlled_live_pilot_sha256"
PILOT_ROOT = "fd24d7ff2303259ba674823f01403ac2b694082ed5e8e6035f76ff084300230c"
BUILDER = ROOT / "runs/20261004_search_plan_v24_dev_alpha3_20f_final_builder_v4_contract_freeze_offline"
BUILDER_MARKER = "search_plan_v24_dev_alpha3_20f_sha256"
BUILDER_ROOT = "cc76b168c80634510168a759815dbf7ab905d5e67292b3393a6b9c6a537847c6"

OUT = ROOT / "runs/20261012_code_first_pilot_bound_builder_v4_development_execution"
ROOT_MARKER = "code_first_pilot_bound_builder_v4_development_execution_sha256"
FINAL_FILES = {
    "summary.json", "execution_manifest.json", "provider_response.json",
    "builder_validation.json", "proposition_diagnostics.json",
    "historical_preservation.json", ROOT_MARKER,
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


def write_raw(path: Path, raw: bytes, *, private: bool = False) -> str:
    with path.open("xb") as handle:
        handle.write(raw)
        handle.flush()
        os.fsync(handle.fileno())
    path.chmod(0o600 if private else 0o644)
    return sha(raw)


def write_json(path: Path, value: Any, *, private: bool = False) -> str:
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2).encode("utf-8") + b"\n"
    return write_raw(path, raw, private=private)


def root_hash(directory: Path, marker: str) -> str:
    return handoff_adapter.root_hash(directory, marker)


def verify_root(directory: Path, marker: str, expected: str) -> dict[str, Any]:
    actual = root_hash(directory, marker)
    recorded = (directory / marker).read_text(encoding="ascii").strip()
    require(actual == recorded == expected, "FROZEN_ROOT_MISMATCH:" + directory.name)
    return {"artifact_path": directory.relative_to(ROOT).as_posix(),
            "root_marker": marker, "sha256": actual, "verified": True}


def ref(path: Path, expected: str | None = None) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), "ARTIFACT_MISSING_OR_SYMLINK:" + str(path))
    actual = sha(path.read_bytes())
    if expected is not None:
        require(actual == expected, "ARTIFACT_HASH_MISMATCH:" + str(path))
    return {"artifact_path": path.relative_to(ROOT).as_posix(), "sha256": actual}


def verify_preflight() -> dict[str, Any]:
    require(not OUT.exists(), "OUTPUT_ALREADY_EXISTS_NO_REINFERENCE")
    roots = {
        "request_freeze": verify_root(FREEZE, FREEZE_MARKER, FREEZE_ROOT),
        "construction_adapter": verify_root(ADAPTER, ADAPTER_MARKER, ADAPTER_ROOT),
        "post_pilot_smoke": verify_root(SMOKE, SMOKE_MARKER, SMOKE_ROOT),
        "controlled_live_pilot": verify_root(PILOT, PILOT_MARKER, PILOT_ROOT),
        "builder_v4_contract": verify_root(BUILDER, BUILDER_MARKER, BUILDER_ROOT),
    }
    request_manifest_path = FREEZE / "builder_request_manifest.json"
    request_manifest = read_json(request_manifest_path)
    request = request_manifest.get("request")
    require(type(request) is dict and sha(canonical(request)) ==
            request_manifest.get("request_sha256") == REQUEST_SHA256,
            "FROZEN_REQUEST_SHA256_MISMATCH")
    require(request_manifest.get("request_count") == 1 and
            request_manifest.get("execution_authorized") is False and
            request_manifest.get("construction_document_sha256") == DOCUMENT_SHA256 and
            request_manifest.get("prompt_sha256") == PROMPT_SHA256 and
            request_manifest.get("expected_response_schema_artifact_sha256") ==
                OUTPUT_SCHEMA_SHA256,
            "FROZEN_REQUEST_MANIFEST_BINDING_MISMATCH")
    require(request == {
        "model": "deepseek-flash",
        "thinking": {"type": "enabled"},
        "reasoning_effort": "high",
        "response_format": {"type": "json_object"},
        "messages": request["messages"],
    } and len(request["messages"]) == 2 and
            request["messages"][0]["role"] == "system" and
            request["messages"][1]["role"] == "user" and
            not any(key in request for key in
                    ("temperature", "top_p", "max_tokens", "max_output_tokens", "stream")),
            "FROZEN_PROVIDER_PAYLOAD_SHAPE_MISMATCH")

    binding = read_json(FREEZE / "builder_contract_binding.json")
    validation = read_json(FREEZE / "request_validation.json")
    require(binding["builder_v4"]["prompt"]["sha256"] == PROMPT_SHA256 and
            binding["builder_v4"]["output_schema"]["sha256"] == OUTPUT_SCHEMA_SHA256 and
            binding["builder_v4"]["provider"] == "DeepSeek" and
            binding["builder_v4"]["model"] == "deepseek-flash" and
            binding["retry_semantics"]["automatic_retry"] is False and
            binding["retry_semantics"]["known_no_inference_transport_retry_enabled"] is False and
            binding["cache_semantics"]["cache_reuse_allowed"] is False and
            validation["status"] == "PASS" and validation["checks"][
                "all_anchors_within_model_visible_body"] is True,
            "FROZEN_BUILDER_CONTRACT_OR_VALIDATION_MISMATCH")

    source_manifest_path = ADAPTER / "source_manifest.json"
    source_manifest = read_json(source_manifest_path)
    envelope = source_manifest.get("verified_construction_input")
    token_authority = source_manifest.get("opaque_source_token_authority")
    require(type(envelope) is dict and type(token_authority) is dict and
            (source_manifest_path.stat().st_mode & 0o777) == 0o600,
            "PRIVATE_SOURCE_AUTHORITY_MISSING")
    document = envelope.get("construction_document")
    token = token_authority.get("opaque_source_token")
    require(type(document) is dict and type(token) is str,
            "DOCUMENT_OR_OPAQUE_TOKEN_MISSING")
    handoff_adapter.validate_construction_document(document, token)
    require(sha(canonical(document)) == envelope.get("construction_document_sha256") ==
            DOCUMENT_SHA256 and len(document["body_text"]) == 60000 and
            request_manifest.get("opaque_source_token_sha256") == sha(token.encode("utf-8")),
            "DOCUMENT_OR_TOKEN_HASH_MISMATCH")
    provenance = envelope["controller_private_provenance"]
    require(provenance["pilot_root_sha256"] == PILOT_ROOT and
            provenance["handoff_sha256"] ==
                "d7ff77546c41dc910483483e7ae74f550c7100c421c30be42fe64e55480ce84f" and
            provenance["opaque_source_token"] == token and
            token_authority["visibility"] ==
                "CONTROLLER_PRIVATE_NOT_MODEL_VISIBLE_WITH_SOURCE_MAPPING",
            "PILOT_HANDOFF_OR_TOKEN_AUTHORITY_MISMATCH")
    require(request["messages"][1]["content"].startswith("Source token: " + token + "\n") and
            request["messages"][1]["content"].count("Body: " + document["body_text"]) == 1 and
            request["messages"][1]["content"].count("Abstract: " +
                document["abstract_text"]) == 1,
            "FROZEN_REQUEST_INPUT_BINDING_MISMATCH")
    private_identity = token_authority["binding"]
    require(all(private_identity[field] not in request["messages"][1]["content"]
                for field in ("pmid", "pmcid", "doi")),
            "MODEL_VISIBLE_BIBLIOGRAPHIC_IDENTITY_LEAKAGE")

    schema_wrapper_path = (ROOT / binding["builder_v4"]["output_schema"]["artifact_path"])
    schema_wrapper = read_json(schema_wrapper_path)
    schema = schema_wrapper.get("schema")
    require(type(schema) is dict and schema_wrapper.get("schema_version") ==
            "BuilderOutputSchemaV4", "BUILDER_OUTPUT_SCHEMA_INVALID")
    schema_json = canonical(schema).decode("utf-8")
    require(request["messages"][1]["content"].endswith(
            "Output schema: " + schema_json + "\n"), "OUTPUT_SCHEMA_NOT_BOUND_TO_REQUEST")

    normalized_ref = provenance["normalized_jats_reference"]
    normalized_path = Path(normalized_ref["artifact_path"])
    normalized_path = normalized_path if normalized_path.is_absolute() else ROOT / normalized_path
    require(sha(normalized_path.read_bytes()) == normalized_ref["sha256"],
            "NORMALIZED_JATS_HASH_MISMATCH")
    private_jats_identity = private_identity_from_jats(
        normalized_path.read_bytes(), private_identity["pmid"], private_identity["pmcid"],
        private_identity["doi"])
    require(bool(private_jats_identity.get("title_1")), "PRIVATE_TITLE_UNAVAILABLE")

    return {
        "roots": roots,
        "request_manifest_ref": ref(request_manifest_path),
        "request": request,
        "request_id": request_manifest["request_id"],
        "request_sha256": REQUEST_SHA256,
        "document": document,
        "document_sha256": DOCUMENT_SHA256,
        "token": token,
        "token_sha256": sha(token.encode("utf-8")),
        "schema": schema,
        "private_title": private_jats_identity["title_1"],
        "normalized_jats_ref": ref(normalized_path),
        "binding_ref": ref(FREEZE / "builder_contract_binding.json"),
        "validation_ref": ref(FREEZE / "request_validation.json"),
    }


def validate_response(content: str | None, finish_reason: str | None,
                      state: dict[str, Any]) -> dict[str, Any]:
    result: dict[str, Any] = {
        "schema_status": "NOT_EVALUATED",
        "terminal_state": "COMPLETED_SCHEMA_INVALID",
        "schema_validation_passed": False,
        "source_token_binding_valid": None,
        "raw_candidate_count": 0,
        "parsed": None,
        "schema_reason": None,
    }
    try:
        if not isinstance(content, str):
            raise ValueError("BUILDER_V4_RESPONSE_NO_TEXT_CONTENT")
        if finish_reason != "stop":
            raise ValueError("BUILDER_V4_RESPONSE_INCOMPLETE_FINISH:" + str(finish_reason))
        parsed = validate_builder_response(content.encode("utf-8"), state["token"],
                                           state["schema"])
    except ValueError as exc:
        result["schema_status"] = "BUILDER_V4_RESPONSE_INVALID"
        result["schema_reason"] = str(exc)
        try:
            echo = json.loads(content).get("source_record_token") if content else None
            result["source_token_binding_valid"] = echo == state["token"]
        except (ValueError, AttributeError, TypeError):
            result["source_token_binding_valid"] = None
        return result
    count = len(parsed["candidates"])
    result.update({
        "schema_status": "BUILDER_V4_SCHEMA_VALID",
        "terminal_state": "COMPLETED_SCHEMA_VALID_ZERO" if count == 0 else
                          "COMPLETED_SCHEMA_VALID_NONZERO",
        "schema_validation_passed": True,
        "source_token_binding_valid": True,
        "raw_candidate_count": count,
        "parsed": parsed,
    })
    return result


def diagnose(parsed: dict[str, Any] | None, state: dict[str, Any]) -> dict[str, Any]:
    if parsed is None:
        return {"candidate_records": [], "raw_proposition_count": 0,
                "valid_proposition_count": 0, "invalid_proposition_count": 0,
                "reviewable_proposition_count": 0, "unsupported_anchor_count": 0,
                "evidence_anchor_coverage_count": 0,
                "deterministic_validation_status": "NOT_EVALUATED_AFTER_SCHEMA_FAILURE"}
    records = []
    for position, candidate in enumerate(parsed["candidates"]):
        payload_sha = sha(canonical(candidate))
        quote = candidate["construction_evidence_span"]["exact_text"]
        localized = localize_exact_body_quote(
            quote, state["document"]["body_text"], state["document"]["paragraphs"])
        record: dict[str, Any] = {
            "raw_array_position": position,
            "candidate_payload_sha256": payload_sha,
            "exact_text_sha256": sha(quote.encode("utf-8")),
            "localization": localized,
            "structural": {"structural_state": "NOT_EVALUATED_AFTER_GROUNDING_FAILURE",
                           "failure_reasons": [],
                           "semantic_scientific_fidelity_established": False},
            "lexical_leakage": {"final_leakage_state":
                                "NOT_EVALUATED_AFTER_GROUNDING_OR_STRUCTURE_FAILURE"},
            "deterministic_candidate_state": "INVALID",
            "scientific_correctness": "NOT_EVALUATED",
            "rejection_reasons": [],
        }
        if localized["development_v4_localization_state"] != LOCALIZATION_SUCCESS:
            record["rejection_reasons"].append(localized[
                "development_v4_localization_state"])
            records.append(record)
            continue
        start = localized["body_document_start_offset"]
        end = localized["body_document_end_offset"]
        require(state["document"]["body_text"][start:end] == quote,
                "LOCALIZATION_ROUND_TRIP_FAILURE")
        structural = structural_result(candidate, state["schema"])
        record["structural"] = structural
        if structural["structural_state"] != "STRUCTURALLY_COMPLETE":
            record["rejection_reasons"].extend(structural["failure_reasons"])
            records.append(record)
            continue
        sentence = evidence_sentence(state["document"]["body_text"], start, end)
        leakage = production_leakage_metrics(candidate["neutral_proposition"],
                                             state["private_title"], sentence)
        independent = independent_reference_leakage(candidate["neutral_proposition"],
                                                    state["private_title"], sentence)
        require(leakage == independent, "LEXICAL_LEAKAGE_REPLAY_MISMATCH")
        record["lexical_leakage"] = leakage
        if leakage["final_leakage_state"] != "LEXICAL_LEAKAGE_PASSED":
            record["rejection_reasons"].append(leakage["final_leakage_state"])
            records.append(record)
            continue
        record["deterministic_candidate_state"] = "VALID_REQUIRES_SCIENTIFIC_REVIEW"
        records.append(record)
    raw_count = len(records)
    valid_count = sum(r["deterministic_candidate_state"] ==
                      "VALID_REQUIRES_SCIENTIFIC_REVIEW" for r in records)
    invalid_count = raw_count - valid_count
    unsupported = sum(r["localization"]["development_v4_localization_state"] !=
                      LOCALIZATION_SUCCESS for r in records)
    coverage = raw_count - unsupported
    return {
        "candidate_records": records,
        "raw_proposition_count": raw_count,
        "valid_proposition_count": valid_count,
        "invalid_proposition_count": invalid_count,
        "reviewable_proposition_count": valid_count,
        "reviewable_count_definition": "Deterministically valid candidates remain scientifically NOT_EVALUATED until separately authorized independent review.",
        "unsupported_anchor_count": unsupported,
        "evidence_anchor_coverage_count": coverage,
        "deterministic_validation_status": "PASS" if invalid_count == 0 else "FAIL",
    }


def execute_once(state: dict[str, Any], secret: str) -> dict[str, Any]:
    OUT.mkdir()
    start_iso = utc_now()
    start_epoch = time.time()
    predispatch = {
        "schema_version": "CODEPilotBuilderV4AttemptStartV1",
        "request_id": state["request_id"],
        "request_sha256": state["request_sha256"],
        "provider": "DeepSeek", "model": "deepseek-flash", "attempt_number": 1,
        "started_at_utc": start_iso, "started_unix_time": start_epoch,
        "committed_before_network": True,
        "maximum_provider_attempts": 1,
        "automatic_retry": False,
    }
    predispatch_raw = json.dumps(predispatch, ensure_ascii=False, sort_keys=True,
                                 indent=2).encode("utf-8") + b"\n"
    working = OUT / ".predispatch_attempt_start.json"
    predispatch_sha = write_raw(working, predispatch_raw, private=True)
    request_bytes = canonical(state["request"])
    require(sha(request_bytes) == REQUEST_SHA256, "REQUEST_MUTATED_BEFORE_DISPATCH")
    response: httpx.Response | None = None
    transport_error: dict[str, Any] | None = None
    try:
        with httpx.Client(timeout=httpx.Timeout(connect=20.0, read=900.0,
                                                 write=120.0, pool=20.0)) as client:
            response = client.post(DEEPSEEK_URL, headers={
                "Authorization": "Bearer " + secret,
                "Content-Type": "application/json",
            }, content=request_bytes)
    except Exception as exc:  # authentic terminal transport evidence
        message = str(exc).replace(secret, "[REDACTED]")
        transport_error = {"error_type": type(exc).__name__, "error_message": message}
    finish_iso = utc_now()
    finish_epoch = time.time()
    if response is None:
        unavailable = {
            "schema_version": "CODEProviderResponseUnavailableV1",
            "raw_provider_response_available": False,
            "transport_error": transport_error,
        }
        response_raw = json.dumps(unavailable, ensure_ascii=False, sort_keys=True,
                                  separators=(",", ":")).encode("utf-8") + b"\n"
        response_sha = write_raw(OUT / "provider_response.json", response_raw, private=True)
        return {
            "predispatch": predispatch, "predispatch_raw": predispatch_raw,
            "predispatch_sha256": predispatch_sha,
            "started_at_utc": start_iso, "finished_at_utc": finish_iso,
            "started_unix_time": start_epoch, "finished_unix_time": finish_epoch,
            "provider_attempts": 1, "http_status": None, "elapsed_seconds": None,
            "response_sha256": response_sha, "response_byte_count": len(response_raw),
            "response": None, "transport_error": transport_error,
            "provider_response_id": None, "provider_model": None,
            "usage": None, "finish_reason": None, "content": None,
        }
    response_raw = response.content
    response_sha = write_raw(OUT / "provider_response.json", response_raw, private=True)
    envelope = None
    parse_error = None
    try:
        envelope = response.json()
        require(type(envelope) is dict, "PROVIDER_ENVELOPE_OBJECT_REQUIRED")
    except (ValueError, RuntimeError) as exc:
        parse_error = {"error_type": type(exc).__name__, "error_message": str(exc)}
    content = None
    finish_reason = None
    if envelope is not None and response.status_code == 200:
        try:
            choices = envelope["choices"]
            require(type(choices) is list and len(choices) == 1,
                    "PROVIDER_CHOICES_INVALID")
            content = choices[0]["message"]["content"]
            finish_reason = choices[0]["finish_reason"]
            require((isinstance(content, str) or content is None) and
                    isinstance(finish_reason, str),
                    "PROVIDER_CONTENT_OR_FINISH_INVALID")
        except (KeyError, TypeError, IndexError, RuntimeError) as exc:
            parse_error = {"error_type": type(exc).__name__, "error_message": str(exc)}
    return {
        "predispatch": predispatch, "predispatch_raw": predispatch_raw,
        "predispatch_sha256": predispatch_sha,
        "started_at_utc": start_iso, "finished_at_utc": finish_iso,
        "started_unix_time": start_epoch, "finished_unix_time": finish_epoch,
        "provider_attempts": 1, "http_status": response.status_code,
        "elapsed_seconds": response.elapsed.total_seconds(),
        "response_sha256": response_sha, "response_byte_count": len(response_raw),
        "response": envelope, "provider_envelope_parse_error": parse_error,
        "transport_error": None,
        "provider_response_id": envelope.get("id") if envelope else None,
        "provider_model": envelope.get("model") if envelope else None,
        "usage": envelope.get("usage") if envelope else None,
        "finish_reason": finish_reason, "content": content,
    }


def finalize(state: dict[str, Any], execution: dict[str, Any]) -> dict[str, Any]:
    response = execution["response"]
    http_ok = execution["http_status"] == 200
    model_identity_verified = http_ok and execution["provider_model"] == "deepseek-flash"
    authentic_inference = (http_ok and response is not None and
                           execution["provider_envelope_parse_error"] is None and
                           isinstance(execution["content"], (str, type(None))) and
                           isinstance(execution["finish_reason"], str))
    execution_pass = authentic_inference and model_identity_verified
    if execution_pass:
        validation = validate_response(execution["content"], execution["finish_reason"], state)
        diagnostics = diagnose(validation["parsed"], state)
    else:
        validation = {
            "schema_status": "NOT_EVALUATED_AFTER_EXECUTION_FAILURE",
            "terminal_state": "EXECUTION_FAILURE",
            "schema_validation_passed": False,
            "source_token_binding_valid": None,
            "raw_candidate_count": 0, "parsed": None,
            "schema_reason": execution.get("provider_envelope_parse_error") or
                             execution.get("transport_error"),
        }
        diagnostics = diagnose(None, state)

    builder_validation_pass = (execution_pass and validation["schema_validation_passed"] and
                               diagnostics["deterministic_validation_status"] == "PASS")
    response_id = execution["provider_response_id"]
    usage = execution["usage"]
    cost = response.get("cost") if isinstance(response, dict) else None
    failure = None
    if not http_ok:
        if execution["http_status"] is not None:
            terminal_state, failure_code = provider_failure_state(
                execution["http_status"], (OUT / "provider_response.json").read_bytes())
            failure = {"terminal_state": terminal_state, "failure_code": failure_code,
                       "http_status": execution["http_status"]}
        else:
            failure = {"terminal_state": "PROVIDER_EXECUTION_AMBIGUOUS",
                       "failure_code": "BUILDER_PROVIDER_EXECUTION_AMBIGUOUS",
                       "transport_error": execution["transport_error"]}
    elif not model_identity_verified:
        failure = {"terminal_state": "PROVIDER_MODEL_IDENTITY_MISMATCH",
                   "failure_code": "BUILDER_PROVIDER_MODEL_IDENTITY_MISMATCH"}
    elif not authentic_inference:
        failure = {"terminal_state": "PROVIDER_EXECUTION_AMBIGUOUS",
                   "failure_code": "BUILDER_PROVIDER_EXECUTION_AMBIGUOUS",
                   "provider_envelope_parse_error": execution[
                       "provider_envelope_parse_error"]}

    execution_manifest = {
        "schema_version": "CODEFirstPilotBoundBuilderV4ExecutionManifestV1",
        "request_id": state["request_id"],
        "frozen_request": state["request_manifest_ref"],
        "request_sha256": state["request_sha256"],
        "construction_document_sha256": state["document_sha256"],
        "provider": "DeepSeek", "requested_model": "deepseek-flash",
        "actual_provider_model": execution["provider_model"],
        "model_identity_verified": model_identity_verified,
        "logical_builder_requests": 1,
        "provider_attempts": execution["provider_attempts"],
        "technical_retries": 0,
        "retry_reasons": [],
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
            "provider_response_id": response_id,
            "finish_reason": execution["finish_reason"],
        },
        "usage_reported": usage is not None,
        "usage": usage,
        "provider_cost_reported": cost is not None,
        "provider_cost": cost,
        "execution_failure": failure,
        "api_credentials_persisted": False,
        "opaque_token_mapping_model_visible": False,
        "request_payload_regenerated": False,
        "request_payload_modified": False,
    }
    manifest_sha = write_json(OUT / "execution_manifest.json", execution_manifest,
                              private=True)

    validation_artifact = {
        "schema_version": "CODEPilotBuilderV4ValidationV1",
        "execution_status": "EXECUTION_PASS" if execution_pass else "EXECUTION_FAILURE",
        "builder_validation_status": "BUILDER_VALIDATION_PASS" if builder_validation_pass
                                     else "BUILDER_VALIDATION_FAIL" if execution_pass
                                     else "NOT_EVALUATED",
        "terminal_state": validation["terminal_state"],
        "schema_status": validation["schema_status"],
        "schema_validation_passed": validation["schema_validation_passed"],
        "schema_failure_reason": validation["schema_reason"],
        "source_token_binding_valid": validation["source_token_binding_valid"],
        "proposition_count": validation["raw_candidate_count"],
        "exact_body_localization_applied": validation["schema_validation_passed"],
        "coordinate_end_semantics": "exclusive",
        "unsupported_anchor_count": diagnostics["unsupported_anchor_count"],
        "all_applicable_deterministic_checks_passed": builder_validation_pass,
        "scientific_correctness_established": False,
        "quality_v2_executed": False,
    }
    validation_sha = write_json(OUT / "builder_validation.json", validation_artifact)

    diagnostics_artifact = {
        "schema_version": "CODEPilotBuilderV4PropositionDiagnosticsV1",
        "development_role": "SEEN_DATA_DEVELOPMENT_OBSERVATIONS",
        "raw_proposition_count": diagnostics["raw_proposition_count"],
        "valid_proposition_count": diagnostics["valid_proposition_count"],
        "invalid_proposition_count": diagnostics["invalid_proposition_count"],
        "reviewable_proposition_count": diagnostics["reviewable_proposition_count"],
        "reviewable_count_definition": diagnostics.get("reviewable_count_definition"),
        "unsupported_anchor_count": diagnostics["unsupported_anchor_count"],
        "evidence_anchor_coverage_count": diagnostics[
            "evidence_anchor_coverage_count"],
        "deterministic_validation_status": diagnostics[
            "deterministic_validation_status"],
        "candidate_records": diagnostics["candidate_records"],
        "scientific_accuracy_claimed": False,
        "scientific_correctness_claimed": False,
        "causal_validity_claimed": False,
        "generalization_claimed": False,
    }
    diagnostics_sha = write_json(OUT / "proposition_diagnostics.json",
                                 diagnostics_artifact, private=True)

    roots_after = {
        "request_freeze": verify_root(FREEZE, FREEZE_MARKER, FREEZE_ROOT),
        "construction_adapter": verify_root(ADAPTER, ADAPTER_MARKER, ADAPTER_ROOT),
        "post_pilot_smoke": verify_root(SMOKE, SMOKE_MARKER, SMOKE_ROOT),
        "controlled_live_pilot": verify_root(PILOT, PILOT_MARKER, PILOT_ROOT),
        "builder_v4_contract": verify_root(BUILDER, BUILDER_MARKER, BUILDER_ROOT),
    }
    preservation = {
        "schema_version": "CODEPilotBuilderV4HistoricalPreservationV1",
        "authoritative_roots_before": state["roots"],
        "authoritative_roots_after": roots_after,
        "authoritative_roots_unchanged": state["roots"] == roots_after,
        "frozen_request_unchanged": sha(canonical(read_json(
            FREEZE / "builder_request_manifest.json")["request"])) == REQUEST_SHA256,
        "construction_adapter_modified": False,
        "builder_prompt_or_policy_modified": False,
        "search_plan_modified": False,
        "acquisition_runtime_modified": False,
        "historical_assets_modified": False,
        "pilot_source_seen_and_future_primary_excluded": True,
        "pubmed_calls": 0, "pmc_calls": 0,
        "builder_logical_requests": 1, "builder_provider_attempts": 1,
        "quality_calls": 0,
    }
    require(preservation["authoritative_roots_unchanged"] and
            preservation["frozen_request_unchanged"], "HISTORICAL_PRESERVATION_FAILURE")
    preservation_sha = write_json(OUT / "historical_preservation.json", preservation)

    recommendation = ("PREREGISTER_SEPARATELY_AUTHORIZED_QUALITY_V2_OR_STOP"
                      if builder_validation_pass and diagnostics[
                          "valid_proposition_count"] > 0
                      else "AUDIT_PILOT_BUILDER_V4_VALIDATION_FAILURE_OFFLINE_OR_STOP"
                      if execution_pass
                      else "AUDIT_PILOT_BUILDER_V4_EXECUTION_FAILURE_OFFLINE_OR_STOP")
    summary = {
        "schema_version": "CODEFirstPilotBoundBuilderV4ExecutionSummaryV1",
        "builder_execution_status": "PASS" if execution_pass else "FAIL",
        "builder_validation_status": "PASS" if builder_validation_pass else
                                     "FAIL" if execution_pass else "NOT_EVALUATED",
        "frozen_request_verified": True,
        "logical_builder_requests": 1,
        "provider_attempts": 1,
        "model_identity_verified": model_identity_verified,
        "provider_response_id": response_id,
        "usage_reported": usage is not None,
        "provider_cost_reported": cost is not None,
        "raw_proposition_count": diagnostics["raw_proposition_count"],
        "valid_proposition_count": diagnostics["valid_proposition_count"],
        "invalid_proposition_count": diagnostics["invalid_proposition_count"],
        "reviewable_proposition_count": diagnostics["reviewable_proposition_count"],
        "unsupported_anchor_count": diagnostics["unsupported_anchor_count"],
        "schema_validation_passed": validation["schema_validation_passed"],
        "execution_manifest_sha256": manifest_sha,
        "provider_response_sha256": execution["response_sha256"],
        "builder_validation_sha256": validation_sha,
        "proposition_diagnostics_sha256": diagnostics_sha,
        "historical_preservation_sha256": preservation_sha,
        "quality_executed": False,
        "fresh_primary_started": False,
        "pubmed_calls": 0, "pmc_calls": 0, "quality_calls": 0,
        "scientific_policy_changed": False,
        "historical_assets_modified": False,
        "next_stage_recommendation": recommendation,
        "root_marker": ROOT_MARKER,
        "root_hash_algorithm": "SHA256(compact canonical JSON of sorted [relative_path,SHA256(file)] pairs; root marker excluded; no final LF in hashed JSON)",
    }
    write_json(OUT / "summary.json", summary)
    working = OUT / ".predispatch_attempt_start.json"
    require(working.read_bytes() == execution["predispatch_raw"],
            "PREDISPATCH_COMMIT_CHANGED")
    working.unlink()
    require({path.name for path in OUT.iterdir() if path.is_file()} ==
            FINAL_FILES - {ROOT_MARKER}, "UNEXPECTED_FINAL_FILE_SET_BEFORE_MARKER")
    final_root = root_hash(OUT, ROOT_MARKER)
    write_raw(OUT / ROOT_MARKER, (final_root + "\n").encode("ascii"))
    require(root_hash(OUT, ROOT_MARKER) == final_root,
            "FINAL_EXECUTION_ROOT_RECOMPUTATION_FAILED")
    require((OUT / "provider_response.json").stat().st_mode & 0o777 == 0o600 and
            (OUT / "execution_manifest.json").stat().st_mode & 0o777 == 0o600 and
            (OUT / "proposition_diagnostics.json").stat().st_mode & 0o777 == 0o600,
            "PRIVATE_ARTIFACT_FILE_MODE_INVALID")
    return {**summary, "execution_root_sha256": final_root}


def main() -> None:
    state = verify_preflight()
    secret = deepseek_key()
    require(bool(secret), "DEEPSEEK_CREDENTIAL_UNAVAILABLE")
    execution = execute_once(state, secret)
    result = finalize(state, execution)
    print(json.dumps({
        "builder_execution_status": result["builder_execution_status"],
        "builder_validation_status": result["builder_validation_status"],
        "provider_attempts": result["provider_attempts"],
        "raw_proposition_count": result["raw_proposition_count"],
        "valid_proposition_count": result["valid_proposition_count"],
        "execution_root_sha256": result["execution_root_sha256"],
    }, sort_keys=True), flush=True)


if __name__ == "__main__":
    main()
