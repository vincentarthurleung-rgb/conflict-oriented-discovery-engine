"""Exactly-one-call DeepSeek Planner V3 development smoke for heldout_v2_108.

The alpha3 prompt, schema, target-role frame, applicability, validators, role
rehydrator, and compiler are verified before the request.  The exact model
content is fsync'd before parsing.  There is no retry, repair, fallback, or
literature retrieval path.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
from typing import Any

from code_engine.extraction.deepseek_client import (
    DeepSeekClient, DeepSeekExtractionError, build_deepseek_request_payload,
)
from code_engine.search.planner_v3_contract import (
    PLANNER_PROPOSAL_PAYLOAD_V3_SCHEMA, PROMPT_TEXT_V3,
    compile_validated_planner_v3, deterministic_target_role_frame_v1,
    planner_cache_identity_v3, planner_role_rehydrate_v1,
    request_specific_provider_schema, retrieval_intent_applicability_v2,
    static_provider_schema_preflight, validate_planner_proposal_v3,
)
from code_engine.search.proposition_aware_query_planner_v1 import (
    canonical_bytes, canonical_target_hash, sha256_value,
)
from tools.freeze_search_plan_v24_dev_alpha2_2_semantic_slot_compatibility_offline import targets_by_case
from tools.run_search_plan_v24_dev_alpha2_1_smoke_101 import load_key, verify_root

ROOT = Path(__file__).resolve().parents[1]
RUN = ROOT / "runs/20260922_search_plan_v24_dev_alpha3_deepseek_planner_v3_smoke_108"
ALPHA3 = ROOT / "runs/20260920_search_plan_v24_dev_alpha3_minimal_planner_contract_offline"
ALPHA3_ROOT = "96990556e92d197345416a000b4cba88e250afa4456499f498ec89891a95c61f"
CASE_ID = "heldout_v2_108"
MODEL = "deepseek-v4-pro"
ROOT_FILE = "search_plan_v24_dev_alpha3_deepseek_smoke_108_sha256"


def require(ok: bool, message: str) -> None:
    if not ok:
        raise ValueError(message)


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def write_bytes(path: Path, data: bytes) -> None:
    require(not path.exists() and not path.is_symlink(), f"refusing overwrite: {path}")
    with path.open("xb") as handle:
        handle.write(data)
        handle.flush()
        os.fsync(handle.fileno())


def write_json(path: Path, value: Any) -> None:
    write_bytes(path, (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8"))


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    write_bytes(path, b"".join(
        json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8") + b"\n"
        for row in rows))


def freeze_root(status: str) -> str:
    components = [[path.name, digest(path.read_bytes())] for path in sorted(RUN.iterdir())
                  if path.is_file() and path.name not in {"validation.json", ROOT_FILE}]
    root = sha256_value(components)
    write_json(RUN / "validation.json", {
        "artifact_schema_version": "SearchPlanV24DevAlpha3DeepSeekSmoke108ValidationV1",
        "status": status, "aggregate_components": components,
        ROOT_FILE: root, "provider_requests_maximum": 1,
        "automatic_retries": 0, "repair_calls": 0, "openai_calls": 0,
        "network_literature_calls": 0, "retrieval_calls": 0,
    })
    write_bytes(RUN / ROOT_FILE, (root + "\n").encode("utf-8"))
    return root


def make_request(target: dict[str, Any], role_frame: dict[str, Any],
                 applicability: dict[str, Any], schema: dict[str, Any]) -> tuple[list[dict[str, str]], dict[str, Any], bytes]:
    scientific_boundary = {
        "primary_proposition_meaning": target["primary_proposition_meaning"],
        "scientific_boundaries": target["scientific_boundaries"],
        "acceptable_endpoint_evidence": target["acceptable_endpoint_evidence"],
        "insufficient_evidence": target["insufficient_evidence"],
    }
    user = (
        "Return exactly one JSON object matching the model-only schema. "
        "Generate only minimal semantic and lexical Planner V3 content.\n"
        "IMMUTABLE SCIENTIFIC BOUNDARY:\n" + canonical_bytes(scientific_boundary).decode("utf-8") +
        "\nDETERMINISTIC TARGET ROLE FRAME (read-only; do not echo IDs or refs):\n" +
        canonical_bytes({"role_surfaces": role_frame["role_surfaces"],
                         "target_direction": role_frame["target_direction"],
                         "target_relation_family": role_frame["target_relation_family"],
                         "conditioning_treatment_applicability": role_frame[
                             "conditioning_treatment_applicability"],
                         "therapy_applicability": role_frame["therapy_applicability"]}).decode("utf-8") +
        "\nALLOWED INTENT TYPES (choose a useful subset):\n" +
        canonical_bytes(applicability["applicable_intent_types"]).decode("utf-8") +
        "\nMODEL-ONLY REQUEST-SPECIFIC JSON SCHEMA:\n" + canonical_bytes(schema).decode("utf-8")
    )
    messages = [{"role": "system", "content": PROMPT_TEXT_V3},
                {"role": "user", "content": user}]
    request = build_deepseek_request_payload(
        messages, model=MODEL, temperature=None, top_p=None,
        thinking_mode="enabled", reasoning_effort="high")
    body = json.dumps(request).encode("utf-8")
    return messages, request, body


def preflight() -> dict[str, Any]:
    require(not RUN.exists(), "smoke run already exists; rerun is forbidden")
    upstream = verify_root(ALPHA3, ALPHA3_ROOT)
    target = targets_by_case()[CASE_ID]
    require(target["case_id"] == CASE_ID and target["artifact_schema_version"] == "ScientificPropositionTargetV1",
            "frozen case-108 target unavailable")
    role_frame = deterministic_target_role_frame_v1(target)
    applicability = retrieval_intent_applicability_v2(target)
    schema = request_specific_provider_schema(target)
    preflight_record = static_provider_schema_preflight(schema)
    require(preflight_record["passed"], "Planner V3 request-specific schema preflight failed")

    prompt_file = (ALPHA3 / "planner_prompt_v3.md").read_text(encoding="utf-8")
    require(prompt_file == PROMPT_TEXT_V3.rstrip() + "\n", "frozen Planner Prompt V3 differs from runtime")
    frozen_schema = json.loads((ALPHA3 / "planner_proposal_payload_v3_schema.json").read_text(encoding="utf-8"))
    require(frozen_schema == PLANNER_PROPOSAL_PAYLOAD_V3_SCHEMA, "frozen PlannerProposalPayloadV3 differs from runtime")
    provider_set = json.loads((ALPHA3 / "deepseek_planner_v3_provider_schema.json").read_text(encoding="utf-8"))
    require(provider_set["request_specific_schema_sha256"][CASE_ID] == sha256_value(schema),
            "case-108 provider schema hash mismatch")
    require(provider_set["request_specific_intent_enums"][CASE_ID] == applicability["applicable_intent_types"],
            "case-108 intent enum mismatch")
    frozen_frames = json.loads((ALPHA3 / "deterministic_target_role_frame_v1_contract.json").read_text(
        encoding="utf-8"))["development_frames"]
    require(frozen_frames[CASE_ID] == role_frame, "case-108 target role frame changed")
    frozen_applicability = json.loads((ALPHA3 / "retrieval_intent_applicability_v2_contract.json").read_text(
        encoding="utf-8"))["development_applicability"]
    require(frozen_applicability[CASE_ID] == applicability, "case-108 intent applicability changed")

    messages, request, body = make_request(target, role_frame, applicability, schema)
    require(request["model"] == MODEL and request["thinking"] == {"type": "enabled"}
            and request["reasoning_effort"] == "high", "DeepSeek reasoning configuration mismatch")
    require("temperature" not in request and "top_p" not in request,
            "temperature/top-p must be omitted in thinking mode")
    require(request["response_format"] == {"type": "json_object"}, "JSON-object transport disabled")
    require(bool(load_key()), "DeepSeek credential unavailable; provider call not attempted")
    return {
        "upstream": upstream, "target": target, "target_role_frame": role_frame,
        "intent_applicability": applicability, "provider_schema": schema,
        "provider_schema_preflight": preflight_record, "messages": messages,
        "request": request, "request_body": body,
        "target_sha256": canonical_target_hash(target),
        "prompt_sha256": sha256_value(PROMPT_TEXT_V3),
        "proposal_schema_sha256": sha256_value(PLANNER_PROPOSAL_PAYLOAD_V3_SCHEMA),
        "provider_schema_sha256": sha256_value(schema),
        "planner_cache_identity": planner_cache_identity_v3(target, provider_schema=schema),
        "request_body_sha256": digest(body),
        "runner_sha256": digest(Path(__file__).read_bytes()),
    }


def fail_closed(summary: dict[str, Any], *, filename: str, detail: dict[str, Any]) -> None:
    write_json(RUN / filename, detail)
    write_json(RUN / "summary.json", summary)
    root = freeze_root("FAIL_CLOSED")
    print(json.dumps({"root": root, "summary": summary}, ensure_ascii=False, sort_keys=True), flush=True)


def execute(state: dict[str, Any]) -> None:
    key = load_key()
    require(bool(key), "DeepSeek credential disappeared after preflight")
    require(digest(Path(__file__).read_bytes()) == state["runner_sha256"],
            "runner changed after preflight")
    verify_root(ALPHA3, ALPHA3_ROOT)
    _, repeated_request, repeated_body = make_request(
        state["target"], state["target_role_frame"], state["intent_applicability"], state["provider_schema"])
    require(repeated_request == state["request"] and repeated_body == state["request_body"],
            "request bytes changed after preflight")

    RUN.mkdir(parents=True, exist_ok=False)
    write_json(RUN / "upstream_root_verification.json", {
        "search_plan_v24_dev_alpha3_sha256": ALPHA3_ROOT, **state["upstream"]})
    write_json(RUN / "frozen_request_preflight.json", {
        "case_id": CASE_ID, "provider": "deepseek", "model": MODEL,
        "thinking": "enabled", "reasoning_effort": "high",
        "temperature_omitted": True, "top_p_omitted": True,
        "maximum_provider_requests": 1, "maximum_inference_attempts": 1,
        "automatic_retry": False, "repair_call": False, "openai_fallback": False,
        "target_sha256": state["target_sha256"], "prompt_sha256": state["prompt_sha256"],
        "proposal_schema_sha256": state["proposal_schema_sha256"],
        "provider_schema_sha256": state["provider_schema_sha256"],
        "planner_cache_identity": state["planner_cache_identity"],
        "request_body_sha256": state["request_body_sha256"],
        "provider_schema_preflight": state["provider_schema_preflight"],
    })
    write_json(RUN / "deterministic_request_state.json", {
        "case_id": CASE_ID, "target_role_frame": state["target_role_frame"],
        "intent_applicability": state["intent_applicability"],
        "model_controls_target_role_frame": False, "model_controls_applicability": False,
    })
    write_bytes(RUN / "provider_request_body.json", state["request_body"])
    write_json(RUN / "request_attempt_marker.json", {
        "case_id": CASE_ID, "provider_requests_committed": 1,
        "inference_attempts_committed": 1, "maximum_attempts": 1,
        "request_body_sha256": state["request_body_sha256"],
        "no_retry": True, "no_repair": True, "no_fallback": True,
    })
    raw_path = RUN / "raw_model_content.txt"

    def freeze_raw(raw: bytes) -> None:
        write_bytes(raw_path, raw)

    try:
        client = DeepSeekClient(api_key=key, max_retries=0)
        result = client.extract_json_result(
            state["messages"], model=MODEL, temperature=None, top_p=None,
            thinking_mode="enabled", reasoning_effort="high",
            raw_response_sink=freeze_raw)
    except DeepSeekExtractionError as exc:
        summary = {
            "status": "FAIL_CLOSED_PROVIDER_TRANSPORT", "case_id": CASE_ID,
            "provider_requests_attempted": 1, "inference_attempts": 1,
            "raw_model_content_frozen": raw_path.is_file(), "retry_count": 0,
            "repair_calls": 0, "openai_calls": 0, "compiled_query_count": 0,
        }
        fail_closed(summary, filename="provider_failure.json", detail={
            "error_kind": exc.error_kind, "status_code": exc.status_code,
            "attempts": exc.attempts, "finish_reason": exc.finish_reason,
            "error_message_redacted": str(exc).replace(str(key), "[REDACTED]"),
            "raw_model_content_sha256": digest(raw_path.read_bytes()) if raw_path.is_file() else None,
            "provider_metadata": exc.provider_metadata, "retry_count": 0,
        })
        return
    except Exception as exc:
        summary = {
            "status": "FAIL_CLOSED_TRANSPORT_RUNTIME", "case_id": CASE_ID,
            "provider_requests_attempted": 1, "inference_attempts": 1,
            "raw_model_content_frozen": raw_path.is_file(), "retry_count": 0,
            "repair_calls": 0, "openai_calls": 0, "compiled_query_count": 0,
        }
        fail_closed(summary, filename="transport_runtime_failure.json", detail={
            "error_type": type(exc).__name__,
            "error_message_redacted": str(exc).replace(str(key), "[REDACTED]"),
            "raw_model_content_sha256": digest(raw_path.read_bytes()) if raw_path.is_file() else None,
            "retry_count": 0,
        })
        return

    require(raw_path.is_file() and raw_path.read_bytes() == result.raw_response.encode("utf-8"),
            "raw provider content was not durably frozen before parsing")
    write_json(RUN / "provider_response_metadata.json", {
        "provider": "deepseek", "model": MODEL, "finish_reason": result.finish_reason,
        "attempt_count": result.attempt_count, "usage": result.usage,
        "provider_metadata": result.provider_metadata, "parser_warnings": result.warnings,
        "raw_model_content_sha256": digest(raw_path.read_bytes()),
        "raw_frozen_before_deterministic_validation": True,
    })
    if result.attempt_count != 1 or result.finish_reason != "stop" or result.warnings:
        summary = {
            "status": "FAIL_CLOSED_PROVIDER_OUTPUT", "case_id": CASE_ID,
            "provider_requests_attempted": 1, "inference_attempts": 1,
            "raw_model_content_frozen": True, "retry_count": 0,
            "repair_calls": 0, "openai_calls": 0, "compiled_query_count": 0,
        }
        fail_closed(summary, filename="provider_output_failure.json", detail={
            "finish_reason": result.finish_reason, "attempt_count": result.attempt_count,
            "parser_warnings": result.warnings, "raw_output_preserved": True,
        })
        return
    write_json(RUN / "parsed_provider_payload.json", result.payload)

    allowed = state["intent_applicability"]["applicable_intent_types"]
    try:
        validate_planner_proposal_v3(result.payload, allowed_intent_types=allowed)
    except Exception as exc:
        summary = {
            "status": "FAIL_CLOSED_PLANNER_V3_VALIDATION", "case_id": CASE_ID,
            "provider_requests_attempted": 1, "inference_attempts": 1,
            "raw_model_content_frozen": True, "retry_count": 0,
            "repair_calls": 0, "openai_calls": 0, "compiled_query_count": 0,
        }
        fail_closed(summary, filename="planner_v3_validation_failure.json", detail={
            "error_type": type(exc).__name__, "error": str(exc),
            "raw_output_preserved": True, "rerun_allowed": False,
        })
        return

    try:
        validated = planner_role_rehydrate_v1(result.payload, target=state["target"])
    except Exception as exc:
        summary = {
            "status": "FAIL_CLOSED_DETERMINISTIC_REHYDRATION", "case_id": CASE_ID,
            "provider_requests_attempted": 1, "inference_attempts": 1,
            "raw_model_content_frozen": True, "retry_count": 0,
            "repair_calls": 0, "openai_calls": 0, "compiled_query_count": 0,
        }
        fail_closed(summary, filename="deterministic_rehydration_failure.json", detail={
            "error_type": type(exc).__name__, "error": str(exc),
            "raw_output_preserved": True, "rerun_allowed": False,
        })
        return
    write_json(RUN / "validated_planner_v3.json", validated)
    gate_rows = []
    for intent in validated["intents"]:
        for relation in intent["linked_relations"]:
            gate_rows.append({
                "intent_id": intent["intent_id"], "intent_type": intent["intent_type"],
                "blueprint_id": relation["blueprint_id"],
                "validation_state": relation["validation_state"],
                "checks": relation["checks"],
                "failed_checks": [name for name, passed in relation["checks"].items() if not passed],
                "authority_classification": "SEARCH_ONLY_EXPANSION" if
                    relation["validation_state"] == "STRUCTURALLY_BOUND" else "UNRESOLVED",
                "canonical_identity_promoted": False,
            })
    write_jsonl(RUN / "relation_binding_receipts.jsonl", gate_rows)
    coverage = [{
        "intent_id": intent["intent_id"], "intent_type": intent["intent_type"],
        "candidate_count": len(intent["linked_relations"]),
        "structurally_bound_count": intent["structurally_bound_relation_count"],
        "coverage_state": "REPRESENTED" if intent["structurally_bound_relation_count"] else "UNDERREPRESENTED",
    } for intent in validated["intents"]]
    write_json(RUN / "deterministic_coverage.json", {
        "artifact_schema_version": "PlannerV3DeterministicCoverageV1",
        "case_id": CASE_ID, "intent_coverage": coverage,
        "coverage_model_generated": False,
    })
    if not validated["all_proposals_valid"] or any(
            row["validation_state"] != "STRUCTURALLY_BOUND" for row in gate_rows):
        summary = {
            "status": "FAIL_CLOSED_RELATION_BINDING", "case_id": CASE_ID,
            "provider_requests_attempted": 1, "inference_attempts": 1,
            "raw_model_content_frozen": True, "planner_v3_payload_valid": True,
            "relation_candidate_count": len(gate_rows),
            "structurally_bound_relation_count": sum(
                row["validation_state"] == "STRUCTURALLY_BOUND" for row in gate_rows),
            "retry_count": 0, "repair_calls": 0, "openai_calls": 0,
            "compiled_query_count": 0,
        }
        fail_closed(summary, filename="relation_binding_failure.json", detail={
            "failed_relations": [row for row in gate_rows
                                 if row["validation_state"] != "STRUCTURALLY_BOUND"],
            "raw_output_preserved": True, "rerun_allowed": False,
        })
        return

    try:
        compilation = compile_validated_planner_v3(validated)
    except Exception as exc:
        summary = {
            "status": "FAIL_CLOSED_COMPILER", "case_id": CASE_ID,
            "provider_requests_attempted": 1, "inference_attempts": 1,
            "raw_model_content_frozen": True, "planner_v3_payload_valid": True,
            "retry_count": 0, "repair_calls": 0, "openai_calls": 0,
            "compiled_query_count": 0,
        }
        fail_closed(summary, filename="compiler_failure.json", detail={
            "error_type": type(exc).__name__, "error": str(exc),
            "raw_output_preserved": True, "rerun_allowed": False,
        })
        return
    write_json(RUN / "offline_query_compilation.json", compilation)
    write_jsonl(RUN / "compiled_queries.jsonl", compilation["compiled_queries"])
    summary = {
        "artifact_schema_version": "SearchPlanV24DevAlpha3DeepSeekSmoke108SummaryV1",
        "status": "COMPLETED", "case_id": CASE_ID,
        "provider": "deepseek", "model": MODEL,
        "provider_requests_attempted": 1, "inference_attempts": 1,
        "raw_model_content_frozen": True,
        "raw_model_content_sha256": digest(raw_path.read_bytes()),
        "planner_v3_payload_valid": True,
        "retrieval_intent_count": len(result.payload["retrieval_intents"]),
        "relation_candidate_count": len(gate_rows),
        "structurally_bound_relation_count": len(gate_rows),
        "compiled_query_count": compilation["compiled_query_count"],
        "model_generated_opaque_id_count": validated["model_generated_opaque_id_count"],
        "model_generated_canonical_ref_count": validated["model_generated_canonical_ref_count"],
        "model_generated_applicability_decision_count": validated[
            "model_generated_applicability_decision_count"],
        "model_generated_authority_decision_count": validated[
            "model_generated_authority_decision_count"],
        "retry_count": 0, "repair_calls": 0, "openai_calls": 0,
        "network_literature_calls": 0, "retrieval_calls": 0,
        "candidate_records_seen": 0, "historical_assets_modified": False,
        "prompt_modified": False, "schema_modified": False,
        "validator_modified": False, "compiler_modified": False,
        "planner_v3_empirical_smoke_completed": True,
    }
    write_json(RUN / "summary.json", summary)
    root = freeze_root("PASS")
    print(json.dumps({"root": root, "summary": summary}, ensure_ascii=False, sort_keys=True), flush=True)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args()
    state = preflight()
    if not args.execute:
        print(json.dumps({
            "preflight": "PASS", "case_id": CASE_ID,
            "provider": "deepseek", "model": MODEL,
            "request_body_sha256": state["request_body_sha256"],
            "provider_schema_sha256": state["provider_schema_sha256"],
            "maximum_provider_requests": 1, "provider_calls": 0,
        }, sort_keys=True))
        return
    execute(state)


if __name__ == "__main__":
    main()
