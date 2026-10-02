#!/usr/bin/env python3
"""Execute the 42 byte-frozen alpha3.20C Builder V4 development requests.

No scientific postprocessing is performed here. Every attempted request is
committed before transport and every HTTP response is saved before parsing.
"""

from __future__ import annotations

import hashlib
import json
import os
import time
from collections import Counter
from pathlib import Path

import httpx

from scripts.run_search_plan_v24_alpha318b_builder import key
from scripts.search_plan_v24_alpha318b_post_builder_prechecks import validate_builder_response


ROOT = Path(__file__).resolve().parents[1]
B = ROOT / "runs/20261002_search_plan_v24_dev_alpha3_20b_proposition_abstraction_prompt_freeze_offline"
OUT = ROOT / "runs/20261002_search_plan_v24_dev_alpha3_20c_builder_v4_development_execution"
URL = "https://api.deepseek.com/v1/chat/completions"
B_ROOT = "0c5e11b5e53acda51250fca80a544e39fda06c40e9ac2bff138d96ae7cf42e2d"
REQUEST_SHA = "c548c4f992de2ef67f79f961e42c5ec365af6419b24c7ce28366e6b4e710e1e8"
GROUNDING_SHA = "429a11294f1df2c40564f4249ea9f54ce637824cbca13d3450b7afef83c4717b"
SCHEMA_SHA = "e6b65571708d196b9fb7a4b8c4af71f46e8680b4b078a6ebedd9ece28658f1c1"
PROMPT_SHAS = (
    "6af5b7f3cd8b23cc65e4ee9c3e85eb955d760f7f06e88a48722be213454d7592",
    "c9caae20c72f86499681b1f1f4ead01d72f9ac9e9ff621236c9324a765f82178",
    "5f7afd76594bfdf994e0faa253ad0c44c82e5afc37c679c19af76cf1ec4fee0b",
)
ROOT_MARKER = "search_plan_v24_dev_alpha3_20c_sha256"
STOP_RECOMMENDATION = "AUDIT_ALPHA3_20C_RUNTIME_FAILURE_OFFLINE"
NEXT_RECOMMENDATION = "PREREGISTER_ALPHA3_20D_DETERMINISTIC_VARIANT_EVALUATION"


def require(condition: bool, reason: str) -> None:
    if not condition:
        raise RuntimeError(reason)


def canonical(value: object) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":")).encode("utf-8")


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def digest(path: Path) -> str:
    return sha(path.read_bytes())


def read_json(path: Path) -> dict:
    return json.loads(path.read_bytes())


def read_rows(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()
            if line]


def write_raw(path: Path, raw: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as handle:
        handle.write(raw)
        handle.flush()
        os.fsync(handle.fileno())


def write_json(path: Path, value: object) -> None:
    write_raw(path, canonical(value) + b"\n")


def write_rows(name: str, values: list[dict]) -> None:
    write_raw(OUT / name, b"".join(canonical(value) + b"\n" for value in values))


def file_ref(path: Path) -> dict:
    return {"path": str(path.relative_to(ROOT)), "sha256": digest(path)}


def root_hash(directory: Path, marker: str) -> str:
    require(not any(path.is_symlink() for path in directory.rglob("*")),
            "FROZEN_SYMLINK_FORBIDDEN")
    files = sorted(path for path in directory.rglob("*") if path.is_file()
                   and path.name != marker)
    return sha(canonical([[str(path.relative_to(directory)), digest(path)]
                          for path in files]))


def verify_preflight() -> dict:
    require(not OUT.exists(), "ALPHA320C_OUTPUT_ALREADY_EXISTS_NO_REINFERENCE")
    require((B / "search_plan_v24_dev_alpha3_20b_sha256").read_text().strip() == B_ROOT
            and root_hash(B, "search_plan_v24_dev_alpha3_20b_sha256") == B_ROOT,
            "ALPHA320B_ROOT_MISMATCH")
    combined_path = B / "alpha3_20c_combined_request_manifest.jsonl"
    require(digest(combined_path) == REQUEST_SHA
            and (B / "alpha3_20c_combined_request_manifest_sha256").read_text().strip()
            == REQUEST_SHA, "FROZEN_COMBINED_REQUEST_MANIFEST_MISMATCH")
    for name, expected in (("builder_grounding_contract_v4", GROUNDING_SHA),
                           ("builder_output_schema_v4", SCHEMA_SHA)):
        require(digest(B / (name + ".json")) == expected
                and (B / (name + "_sha256")).read_text().strip() == expected,
                "FROZEN_V4_CONTRACT_MISMATCH:" + name)
    for index, expected in enumerate(PROMPT_SHAS, 1):
        require(digest(B / f"prompt_variant_{index}_full_template.txt") == expected
                and (B / f"prompt_variant_{index}_sha256").read_text().strip()
                == expected, "FROZEN_PROMPT_MISMATCH:" + str(index))
    rows = read_rows(combined_path)
    require(len(rows) == 42 and
            [row["execution_ordinal"] for row in rows] == list(range(1, 43)),
            "FROZEN_REQUEST_COUNT_OR_ORDINAL_MISMATCH")
    require(len({(row["source_ordinal"], row["variant_index"]) for row in rows}) == 42
            and len({row["private_source_token"] for row in rows}) == 14,
            "FROZEN_REQUEST_CELL_UNIVERSE_MISMATCH")
    for index in (1, 2, 3):
        variant_path = B / f"alpha3_20c_variant_{index}_request_manifest.jsonl"
        variant_rows = read_rows(variant_path)
        require(len(variant_rows) == 14
                and variant_rows == [row for row in rows if row["variant_index"] == index],
                "FROZEN_PER_VARIANT_MANIFEST_MISMATCH:" + str(index))
    order = read_json(B / "alpha3_20c_execution_order.json")
    require(order["source_count"] == 14 and order["variant_count"] == 3
            and order["one_fresh_independent_context_per_source_variant"] is True
            and order["execution_ordinals"] == [{
                "execution_ordinal": row["execution_ordinal"],
                "source_ordinal": row["source_ordinal"],
                "variant_index": row["variant_index"],
                "request_sha256": row["request_sha256"]} for row in rows],
            "FROZEN_EXECUTION_ORDER_MISMATCH")
    runtime = read_json(B / "alpha3_20c_runtime_policy.json")
    budget = read_json(B / "alpha3_20c_call_budget.json")
    require(runtime["provider"] == "DeepSeek"
            and runtime["model"] == "deepseek-flash"
            and runtime["api_surface"] == "Chat Completions"
            and runtime["thinking"] == {"type": "enabled"}
            and runtime["reasoning_effort"] == "high"
            and runtime["response_format"] == {"type": "json_object"}
            and runtime["automatic_retry"] is False
            and runtime["known_no_inference_transport_retry_enabled"] is False
            and runtime["fallback_provider_or_model"] is False
            and budget["planned_development_sources"] == 14
            and budget["planned_prompt_variants"] == 3
            and budget["planned_development_builder_scientific_inference_events"] == 42
            and budget["maximum_one_scientific_inference_per_source_variant"] is True,
            "FROZEN_RUNTIME_OR_BUDGET_MISMATCH")
    schema = read_json(B / "builder_output_schema_v4.json")["schema"]
    variant_authority = read_json(B / "master_prompt_variant_authority.json")
    controller_ids = [entry["controller_variant_id"] for entry in
                   variant_authority["mapping"]]
    variant_ids = [entry["master_variant_id"] for entry in
                   variant_authority["mapping"]]
    require(controller_ids == ["ABSTRACTION_VARIANT_1", "ABSTRACTION_VARIANT_2",
                               "ABSTRACTION_VARIANT_3"]
            and variant_ids == ["ABSTRACTION_V1_RELATION_SENTENCE",
                                "ABSTRACTION_V2_RELATION_FRAME",
                                "ABSTRACTION_V3_CONTEXT_FIRST"],
            "FROZEN_VARIANT_ID_MISMATCH")
    for index, row in enumerate(rows):
        request = row["request"]
        require(row["execution_ordinal"] == index + 1
                and row["source_ordinal"] == index // 3 + 1
                and row["variant_index"] == index % 3 + 1
                and row["variant_id_controller_only"] == variant_ids[index % 3]
                and row["request_sha256"] == sha(canonical(request))
                and request["model"] == "deepseek-flash"
                and request["thinking"] == {"type": "enabled"}
                and request["reasoning_effort"] == "high"
                and request["response_format"] == {"type": "json_object"}
                and len(request["messages"]) == 2
                and request["messages"][0]["role"] == "system"
                and request["messages"][1]["role"] == "user"
                and request["messages"][1]["content"].startswith(
                    "Source token: " + row["private_source_token"] + "\n")
                and not any(k in request for k in ("temperature", "top_p",
                                                    "max_tokens", "stream")),
                "FROZEN_REQUEST_PAYLOAD_MISMATCH:" + str(index + 1))
    return {"rows": rows, "schema": schema, "runtime": runtime,
            "budget": budget, "variant_ids": variant_ids}


def freeze_preflight(state: dict) -> None:
    OUT.mkdir()
    write_json(OUT / "alpha3_20b_root_verification.json", {
        "root_sha256": B_ROOT, "verified": True})
    write_json(OUT / "alpha3_20c_request_manifest_verification.json", {
        "combined_manifest": file_ref(B / "alpha3_20c_combined_request_manifest.jsonl"),
        "per_variant_manifests": [file_ref(
            B / f"alpha3_20c_variant_{index}_request_manifest.jsonl")
            for index in (1, 2, 3)], "verified": True,
        "request_regeneration_used": False})
    write_json(OUT / "alpha3_20c_pre_provider_integrity_barrier.json", {
        "status": "PASS", "source_count": 14, "variant_count": 3,
        "request_count": 42, "all_frozen_hashes_verified_before_provider_access": True,
        "builder_grounding_contract_v4_sha256": GROUNDING_SHA,
        "builder_output_schema_v4_sha256": SCHEMA_SHA,
        "prompt_variant_sha256": PROMPT_SHAS, "provider_calls_before_barrier": 0})
    write_json(OUT / "alpha3_20c_execution_order_verification.json", {
        "frozen_order": file_ref(B / "alpha3_20c_execution_order.json"),
        "order_verified": True, "execution_ordinals": list(range(1, 43))})
    write_json(OUT / "alpha3_20c_provider_binding_verification.json", {
        "provider": "DeepSeek", "model": "deepseek-flash",
        "thinking": {"type": "enabled"}, "reasoning_effort": "high",
        "response_format": {"type": "json_object"},
        "fallback_allowed": False})
    write_json(OUT / "alpha3_20c_runtime_policy_binding.json", {
        "runtime_policy": file_ref(B / "alpha3_20c_runtime_policy.json"),
        "call_budget": file_ref(B / "alpha3_20c_call_budget.json"),
        "technical_retries_allowed_by_frozen_policy": False,
        "ambiguous_execution_action": "STOP_NO_SECOND_SCIENTIFIC_INFERENCE"})


def provider_failure_state(status: int, raw: bytes) -> tuple[str, str]:
    # Only a deterministic pre-inference model/configuration rejection is known
    # not to have produced a scientific generation. Everything else is ambiguous.
    if status in (400, 404):
        try:
            error = json.loads(raw)["error"]
            message = " ".join(str(error.get(k, "")) for k in
                               ("message", "code", "type")).lower()
        except (ValueError, KeyError, TypeError, AttributeError):
            message = ""
        if "model" in message and any(word in message for word in
                ("not found", "does not exist", "invalid", "unsupported",
                 "unknown", "unavailable")):
            return "PROVIDER_NO_INFERENCE_TERMINAL_FAILURE", "PROVIDER_BINDING_FAILURE"
    return "PROVIDER_EXECUTION_AMBIGUOUS", "BUILDER_PROVIDER_EXECUTION_AMBIGUOUS"


def execute(state: dict, secret: str) -> tuple[list[dict], list[dict], list[dict],
                                                 list[dict], list[dict], list[dict],
                                                 list[dict], dict | None]:
    attempts: list[dict] = []
    raw_rows: list[dict] = []
    transport_rows: list[dict] = []
    terminal_rows: list[dict] = []
    validation_rows: list[dict] = []
    binding_rows: list[dict] = []
    candidate_rows: list[dict] = []
    failure = None
    for row in state["rows"]:
        ordinal = row["execution_ordinal"]
        token = row["private_source_token"]
        require(sha(canonical(row["request"])) == row["request_sha256"]
                and digest(B / "alpha3_20c_combined_request_manifest.jsonl")
                    == REQUEST_SHA, "REQUEST_MUTATED_BEFORE_PROVIDER_ACCESS")
        attempt = {
            "execution_ordinal": ordinal, "source_ordinal": row["source_ordinal"],
            "source_record_token": token,
            "variant_id_controller_only": row["variant_id_controller_only"],
            "request_sha256": row["request_sha256"], "provider": "DeepSeek",
            "model": "deepseek-flash", "attempt_number": 1,
            "started_unix_time": time.time(), "committed_before_network": True,
        }
        write_json(OUT / f"attempt_events/{ordinal:02d}.json", attempt)
        attempts.append(attempt)
        print(f"ALPHA320C_STARTED {ordinal}/42", flush=True)
        try:
            with httpx.Client(timeout=httpx.Timeout(connect=20.0, read=900.0,
                                                     write=120.0, pool=20.0)) as client:
                response = client.post(URL, headers={
                    "Authorization": f"Bearer {secret}",
                    "Content-Type": "application/json"},
                    content=canonical(row["request"]))
        except Exception as exc:
            terminal_rows.append({"execution_ordinal": ordinal,
                "source_record_token": token,
                "variant_id_controller_only": row["variant_id_controller_only"],
                "terminal_state": "PROVIDER_EXECUTION_AMBIGUOUS",
                "scientific_inference_occurrence": "UNKNOWN"})
            failure = {"code": "BUILDER_PROVIDER_EXECUTION_AMBIGUOUS",
                       "execution_ordinal": ordinal,
                       "error_type": type(exc).__name__, "error_message": str(exc)}
            write_json(OUT / f"terminal_events/{ordinal:02d}.json", terminal_rows[-1])
            break
        raw_path = OUT / f"raw_provider_response_bytes/{ordinal:02d}.bin"
        write_raw(raw_path, response.content)
        transport = {"execution_ordinal": ordinal,
            "source_record_token": token,
            "variant_id_controller_only": row["variant_id_controller_only"],
            "request_sha256": row["request_sha256"], "provider": "DeepSeek",
            "model": "deepseek-flash", "attempt_number": 1,
            "http_status": response.status_code,
            "raw_response_path": str(raw_path.relative_to(OUT)),
            "raw_response_sha256": digest(raw_path),
            "elapsed_seconds": response.elapsed.total_seconds(),
            "finished_unix_time": time.time(), "technical_retries": 0}
        write_json(OUT / f"transport_events/{ordinal:02d}.json", transport)
        transport_rows.append(transport)
        if response.status_code != 200:
            terminal_state, code = provider_failure_state(response.status_code,
                                                          response.content)
            terminal = {"execution_ordinal": ordinal,
                "source_record_token": token,
                "variant_id_controller_only": row["variant_id_controller_only"],
                "terminal_state": terminal_state,
                "scientific_inference_occurrence": "NO" if terminal_state ==
                    "PROVIDER_NO_INFERENCE_TERMINAL_FAILURE" else "UNKNOWN"}
            write_json(OUT / f"terminal_events/{ordinal:02d}.json", terminal)
            terminal_rows.append(terminal)
            failure = {"code": code, "execution_ordinal": ordinal,
                       "http_status": response.status_code,
                       "raw_response_sha256": digest(raw_path)}
            break
        try:
            envelope = response.json()
            choices = envelope["choices"]
            require(isinstance(choices, list) and len(choices) == 1,
                    "PROVIDER_CHOICES_INVALID")
            choice = choices[0]
            content = choice["message"]["content"]
            finish_reason = choice["finish_reason"]
            require((isinstance(content, str) or content is None)
                    and isinstance(finish_reason, str),
                    "PROVIDER_CONTENT_OR_FINISH_INVALID")
        except (ValueError, KeyError, TypeError, IndexError, RuntimeError) as exc:
            terminal = {"execution_ordinal": ordinal,
                "source_record_token": token,
                "variant_id_controller_only": row["variant_id_controller_only"],
                "terminal_state": "PROVIDER_EXECUTION_AMBIGUOUS",
                "scientific_inference_occurrence": "UNKNOWN"}
            write_json(OUT / f"terminal_events/{ordinal:02d}.json", terminal)
            terminal_rows.append(terminal)
            failure = {"code": "BUILDER_PROVIDER_EXECUTION_AMBIGUOUS",
                       "execution_ordinal": ordinal,
                       "error_type": type(exc).__name__, "error_message": str(exc)}
            break
        raw_event = {"execution_ordinal": ordinal,
            "source_record_token": token,
            "variant_id_controller_only": row["variant_id_controller_only"],
            "request_sha256": row["request_sha256"], "transport": transport,
            "model_content_raw": content,
            "finish_reason": finish_reason,
            "provider_response_id": envelope.get("id"),
            "usage": envelope.get("usage"),
            "scientific_inference_confirmed": True}
        write_json(OUT / f"raw_events/{ordinal:02d}.json", raw_event)
        raw_rows.append(raw_event)
        try:
            if not isinstance(content, str):
                raise ValueError("BUILDER_V4_RESPONSE_NO_TEXT_CONTENT")
            if finish_reason != "stop":
                raise ValueError("BUILDER_V4_RESPONSE_INCOMPLETE_FINISH:" + finish_reason)
            parsed = validate_builder_response(content.encode("utf-8"), token,
                                               state["schema"])
        except ValueError as exc:
            try:
                echo = json.loads(content).get("source_record_token") if content else None
                exact_binding = echo == token
            except (ValueError, AttributeError):
                exact_binding = None
            terminal_state = "COMPLETED_SCHEMA_INVALID"
            validation = {"execution_ordinal": ordinal,
                "status": "BUILDER_V4_RESPONSE_INVALID", "reason": str(exc),
                "candidate_count": None}
            binding = {"execution_ordinal": ordinal,
                "exact_token_echo_valid": exact_binding,
                "binding_state": "EXACT_MATCH" if exact_binding else
                    "INVALID_SCHEMA_OR_TOKEN"}
        else:
            count = len(parsed["candidates"])
            terminal_state = ("COMPLETED_SCHEMA_VALID_ZERO" if count == 0
                              else "COMPLETED_SCHEMA_VALID_NONZERO")
            validation = {"execution_ordinal": ordinal,
                "status": "BUILDER_V4_SCHEMA_VALID", "candidate_count": count}
            binding = {"execution_ordinal": ordinal,
                "exact_token_echo_valid": True, "binding_state": "EXACT_MATCH"}
            for position, candidate in enumerate(parsed["candidates"]):
                candidate_rows.append({"execution_ordinal": ordinal,
                    "source_record_token": token,
                    "variant_id_controller_only": row["variant_id_controller_only"],
                    "raw_array_position": position,
                    "candidate": candidate,
                    "state": "RAW_ALPHA3_20C_BUILDER_V4_DEVELOPMENT_CANDIDATE"})
        terminal = {"execution_ordinal": ordinal,
            "source_record_token": token,
            "variant_id_controller_only": row["variant_id_controller_only"],
            "terminal_state": terminal_state,
            "scientific_inference_occurrence": "YES"}
        write_json(OUT / f"validation_events/{ordinal:02d}.json", validation)
        write_json(OUT / f"binding_events/{ordinal:02d}.json", binding)
        write_json(OUT / f"terminal_events/{ordinal:02d}.json", terminal)
        validation_rows.append(validation)
        binding_rows.append(binding)
        terminal_rows.append(terminal)
        print(f"ALPHA320C_FROZEN {ordinal}/42 {terminal_state}", flush=True)
    for row in state["rows"][len(terminal_rows):]:
        terminal_rows.append({"execution_ordinal": row["execution_ordinal"],
            "source_record_token": row["private_source_token"],
            "variant_id_controller_only": row["variant_id_controller_only"],
            "terminal_state": "NOT_EXECUTED_AFTER_STAGE_STOP",
            "scientific_inference_occurrence": "NO"})
    return (attempts, raw_rows, transport_rows, terminal_rows,
            validation_rows, binding_rows, candidate_rows, failure)


def freeze_results(state: dict, execution: tuple) -> dict:
    (attempts, raw_rows, transport_rows, terminal_rows, validation_rows,
     binding_rows, candidate_rows, failure) = execution
    write_rows("alpha3_20c_request_attempt_log.jsonl", attempts)
    write_rows("alpha3_20c_raw_provider_responses.jsonl", raw_rows)
    raw_manifest_sha = digest(OUT / "alpha3_20c_raw_provider_responses.jsonl")
    write_raw(OUT / "alpha3_20c_raw_response_manifest_sha256",
              (raw_manifest_sha + "\n").encode("ascii"))
    write_rows("alpha3_20c_transport_provenance.jsonl", transport_rows)
    write_rows("alpha3_20c_cell_terminal_states.jsonl", terminal_rows)
    write_rows("alpha3_20c_response_schema_validation.jsonl", validation_rows)
    write_rows("alpha3_20c_source_token_binding_audit.jsonl", binding_rows)
    write_rows("alpha3_20c_raw_candidate_manifest.jsonl", candidate_rows)
    terminal_by_ordinal = {row["execution_ordinal"]: row for row in terminal_rows}
    complete, incomplete = [], []
    for source_ordinal in range(1, 15):
        cells = [terminal_by_ordinal[(source_ordinal - 1) * 3 + variant_index]
                 for variant_index in (1, 2, 3)]
        target = complete if all(cell["scientific_inference_occurrence"] == "YES"
                                 for cell in cells) else incomplete
        target.append({"source_ordinal": source_ordinal,
            "source_record_token": cells[0]["source_record_token"],
            "runtime_triplet_state": "COMPLETE_VARIANT_TRIPLET" if target is complete
                else "INCOMPLETE_VARIANT_TRIPLET",
            "cell_terminal_states": [cell["terminal_state"] for cell in cells]})
    write_rows("alpha3_20c_complete_triplet_manifest.jsonl", complete)
    write_rows("alpha3_20c_incomplete_triplet_manifest.jsonl", incomplete)
    terminal_counts = Counter(row["terminal_state"] for row in terminal_rows)
    events = sum(row["scientific_inference_occurrence"] == "YES"
                 for row in terminal_rows)
    per_variant = {}
    for variant_index, variant_id in enumerate(state["variant_ids"], 1):
        subset = [row for row in terminal_rows if row["variant_id_controller_only"]
                  == variant_id]
        counts = Counter(row["terminal_state"] for row in subset)
        per_variant[variant_id] = {"planned_calls": 14,
            "scientific_inference_events": sum(row["scientific_inference_occurrence"]
                                               == "YES" for row in subset),
            "schema_valid_zero": counts["COMPLETED_SCHEMA_VALID_ZERO"],
            "schema_valid_nonzero": counts["COMPLETED_SCHEMA_VALID_NONZERO"],
            "schema_invalid": counts["COMPLETED_SCHEMA_INVALID"],
            "raw_candidate_count": sum(row["variant_id_controller_only"] == variant_id
                                       for row in candidate_rows)}
    write_json(OUT / "alpha3_20c_per_variant_accounting.json", per_variant)
    binding_failures = sum(row["exact_token_echo_valid"] is False
                           for row in binding_rows)
    accounting = {"planned_sources": 14, "planned_variants": 3,
        "planned_builder_calls": 42, "builder_requests_attempted": len(attempts),
        "builder_scientific_inference_events": events,
        "technical_retries": 0,
        "completed_schema_valid": terminal_counts["COMPLETED_SCHEMA_VALID_ZERO"]
            + terminal_counts["COMPLETED_SCHEMA_VALID_NONZERO"],
        "completed_schema_invalid": terminal_counts["COMPLETED_SCHEMA_INVALID"],
        "valid_zero": terminal_counts["COMPLETED_SCHEMA_VALID_ZERO"],
        "valid_nonzero": terminal_counts["COMPLETED_SCHEMA_VALID_NONZERO"],
        "raw_candidate_count": len(candidate_rows),
        "complete_variant_triplet_count": len(complete),
        "incomplete_variant_triplet_count": len(incomplete),
        "source_token_binding_failure_count": binding_failures}
    write_json(OUT / "alpha3_20c_execution_accounting.json", accounting)
    write_json(OUT / "alpha3_20c_historical_inference_accounting.json", {
        "historical_alpha3_18_builder_inference_events": 56,
        "historical_alpha3_18_quality_inference_events": 1,
        "historical_alpha3_19_builder_inference_events": 14,
        "historical_alpha3_19_quality_inference_events": 0,
        "alpha3_20c_builder_scientific_inference_events": events,
        "historical_counts_mutated": False})
    write_json(OUT / "alpha3_20c_development_contamination_update.json", {
        "all_42_cell_outputs_role": "SEEN_DEVELOPMENT_HISTORY",
        "source_identities": [row["private_source_token"] for row in state["rows"][::3]],
        "raw_response_manifest_sha256": raw_manifest_sha,
        "raw_candidate_manifest_sha256": digest(OUT / "alpha3_20c_raw_candidate_manifest.jsonl"),
        "fresh_heldout_reuse_prohibited": True})
    manifest_unchanged = (digest(B / "alpha3_20c_combined_request_manifest.jsonl")
                          == REQUEST_SHA and root_hash(B,
                              "search_plan_v24_dev_alpha3_20b_sha256") == B_ROOT)
    write_json(OUT / "alpha3_20c_request_manifest_postexecution_verification.json", {
        "expected_sha256": REQUEST_SHA,
        "actual_sha256": digest(B / "alpha3_20c_combined_request_manifest.jsonl"),
        "request_manifest_unchanged_after_execution": manifest_unchanged})
    require(manifest_unchanged, "FROZEN_REQUEST_MANIFEST_CHANGED_DURING_EXECUTION")
    success = (failure is None and events == 42 and len(attempts) == 42
               and len(complete) == 14)
    classification = ("ALL_42_BUILDER_V4_DEVELOPMENT_CALLS_FROZEN" if success
                      else "BUILDER_V4_DEVELOPMENT_EXECUTION_INCOMPLETE")
    recommendation = NEXT_RECOMMENDATION if success else STOP_RECOMMENDATION
    write_json(OUT / "alpha3_20c_freeze_barrier.json", {
        "raw_responses_frozen_before_parsing": True,
        "terminal_states_frozen": True,
        "all_42_completed_inferences_frozen": success,
        "raw_response_manifest_sha256": raw_manifest_sha,
        "response_schema_validation_frozen": True,
        "alpha3_20d_evaluation_performed": False})
    write_json(OUT / "historical_preservation_audit.json", {
        "alpha3_20b_root_unchanged": True,
        "historical_assets_modified": False,
        "alpha3_18_and_alpha3_19_inference_counts_preserved": True})
    write_json(OUT / "scientific_state_safety_audit.json", {
        "provider": "DeepSeek", "model": "deepseek-flash",
        "deepseek_calls": len(attempts), "quality_calls": 0, "openai_calls": 0,
        "ncbi_calls": 0, "non_deepseek_network_calls": 0,
        "scientific_retry_used": False, "request_regeneration_used": False,
        "prompt_adaptation_used": False, "source_topup_used": False,
        "grounding_evaluation_performed": False,
        "leakage_evaluation_performed": False,
        "variant_comparison_performed": False,
        "historical_assets_modified": False})
    write_json(OUT / "protocol_compliance_audit.json", {
        "exact_frozen_request_universe": True,
        "source_major_v1_v2_v3_order": True,
        "independent_context_per_cell": True,
        "raw_response_preserved_before_schema_parsing": True,
        "one_inference_maximum_per_cell": True,
        "technical_retries": 0,
        "schema_invalid_and_zero_responses_not_retried": True,
        "no_grounding_leakage_structure_or_semantic_evaluation": True,
        "runtime_failure": failure})
    validation = {"status": "completed" if success else "failed",
        "alpha3_20c_classification": classification,
        "alpha3_20b_root_verified": True,
        "combined_request_manifest_verified": True,
        "request_manifest_unchanged_after_execution": manifest_unchanged,
        **accounting, "per_variant": per_variant,
        "provider": "DeepSeek", "model": "deepseek-flash",
        "scientific_retry_used": False,
        "request_regeneration_used": False,
        "prompt_adaptation_used": False, "source_topup_used": False,
        "grounding_evaluation_performed": False,
        "leakage_evaluation_performed": False,
        "variant_comparison_performed": False,
        "alpha3_20c_builder_scientific_inference_events": events,
        "historical_alpha3_18_builder_inference_events": 56,
        "historical_alpha3_18_quality_inference_events": 1,
        "historical_alpha3_19_builder_inference_events": 14,
        "historical_alpha3_19_quality_inference_events": 0,
        "deepseek_calls": len(attempts), "quality_calls": 0,
        "openai_calls": 0, "ncbi_calls": 0,
        "non_deepseek_network_calls": 0,
        "next_stage_recommendation": recommendation,
        "historical_assets_modified": False,
        "runtime_failure": failure}
    write_json(OUT / "validation.json", validation)
    write_json(OUT / "summary.json", {
        "status": validation["status"], "classification": classification,
        "requests_attempted": len(attempts), "scientific_inference_events": events,
        "completed_schema_valid": accounting["completed_schema_valid"],
        "completed_schema_invalid": accounting["completed_schema_invalid"],
        "raw_candidate_count": len(candidate_rows),
        "complete_variant_triplet_count": len(complete),
        "next_stage_recommendation": recommendation})
    write_raw(OUT / ROOT_MARKER, (root_hash(OUT, ROOT_MARKER) + "\n").encode("ascii"))
    return validation


def main() -> None:
    state = verify_preflight()
    secret = key()
    freeze_preflight(state)
    execution = execute(state, secret)
    validation = freeze_results(state, execution)
    print(json.dumps({"status": validation["status"],
        "classification": validation["alpha3_20c_classification"],
        "builder_requests_attempted": validation["builder_requests_attempted"],
        "builder_scientific_inference_events": validation[
            "builder_scientific_inference_events"],
        "root_sha256": (OUT / ROOT_MARKER).read_text().strip()},
        sort_keys=True), flush=True)


if __name__ == "__main__":
    main()
