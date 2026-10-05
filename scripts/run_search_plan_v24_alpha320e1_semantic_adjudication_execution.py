#!/usr/bin/env python3
"""Execute exactly 28 frozen blinded semantic-adjudication requests."""

from __future__ import annotations

import hashlib
import json
import os
import time
from collections import Counter
from pathlib import Path

import httpx

from scripts import run_search_plan_v24_alpha320e_semantic_adjudication_prereg_offline as e
from scripts.run_search_plan_v24_alpha318b_builder import key
from scripts.search_plan_v24_alpha318b_post_builder_prechecks import _validate_schema


ROOT = Path(__file__).resolve().parents[1]
E = e.OUT
OUT = ROOT / "runs/20261003_search_plan_v24_dev_alpha3_20e1_semantic_adjudication_execution"
ROOT_MARKER = "search_plan_v24_dev_alpha3_20e1_sha256"
E_ROOT = "adb49dbe995ca5f467c6af6c6a0b9477b7bf444de17ece185d879d89ddc15fdf"
REQUEST_SHA = "88b6eed3928d32bf89cb286e111c29879079b0cdb962382b7cc1188308f3d34b"
RUBRIC_SHA = "e43ce56389ebf6a9a1c9f751a7830ef71df5dc0d39f8ff1f8567f96a4573b88d"
ENVELOPE_SHA = "eef095c105f062b7894e90c6283ee961f06210999bb9a0235db1d88ec01279a2"
PROMPT_SHA = "16cea565b0cce1979f24ee370dbd644f6fd7cdb187cad93b021bbbd3fdfd397a"
URL = "https://api.deepseek.com/v1/chat/completions"
NEXT_SUCCESS = "PREREGISTER_ALPHA3_20E2_OFFLINE_UNBLIND_AGGREGATE_AND_SELECT"
NEXT_INVALID = "INTERPRET_ALPHA3_20E1_INCOMPLETE_SEMANTIC_RESPONSE_SET_OFFLINE"
NEXT_FAILURE = "AUDIT_ALPHA3_20E1_RUNTIME_FAILURE_OFFLINE"
EXPERIMENTAL_MARKERS = (
    "ABSTRACTION_V1_RELATION_SENTENCE", "ABSTRACTION_V2_RELATION_FRAME",
    "relation sentence", "relation frame", "reference variant",
    "39/42", "37/42", "leakage survivor", "eight-token", "jaccard",
)
PRIVATE_NAMES = (
    "semantic_group_token_mapping_private.jsonl",
    "semantic_candidate_token_mapping_private.jsonl",
    "semantic_blinding_seed_private.json",
)


def require(ok: bool, reason: str) -> None:
    if not ok:
        raise RuntimeError(reason)


def canonical(value: object) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":")).encode("utf-8")


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def digest(path: Path) -> str:
    return sha(path.read_bytes())


def obj(path: Path) -> dict:
    return json.loads(path.read_bytes())


def rows(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()
            if line]


def ref(path: Path) -> dict:
    return {"path": str(path.relative_to(ROOT)), "sha256": digest(path)}


def write_raw(path: Path, raw: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as handle:
        handle.write(raw)
        handle.flush()
        os.fsync(handle.fileno())


def put(name: str, value: object) -> None:
    write_raw(OUT / name, canonical(value) + b"\n")


def put_rows(name: str, records: list[dict]) -> None:
    write_raw(OUT / name, b"".join(canonical(record) + b"\n"
                                     for record in records))


def preflight() -> dict:
    require(not OUT.exists(), "ALPHA320E1_OUTPUT_ALREADY_EXISTS_NO_REINFERENCE")
    require((E / "search_plan_v24_dev_alpha3_20e_sha256").read_text().strip()
            == E_ROOT and e.d.c.root_hash(E,
                "search_plan_v24_dev_alpha3_20e_sha256") == E_ROOT,
            "ALPHA320E_ROOT_MISMATCH")
    for name, expected, marker in (
        ("semantic_adjudication_request_manifest.jsonl", REQUEST_SHA,
         "semantic_adjudication_request_manifest_sha256"),
        ("development_semantic_fidelity_rubric_v1.json", RUBRIC_SHA,
         "development_semantic_fidelity_rubric_v1_sha256"),
        ("development_semantic_adjudication_response_envelope_v1.json", ENVELOPE_SHA,
         "development_semantic_adjudication_response_envelope_v1_sha256"),
        ("semantic_adjudication_prompt_template.txt", PROMPT_SHA,
         "semantic_adjudication_prompt_template_sha256")):
        require(digest(E / name) == expected
                and (E / marker).read_text().strip() == expected,
                "FROZEN_SEMANTIC_AUTHORITY_MISMATCH:" + name)
    policy = obj(E / "semantic_adjudication_runtime_policy.json")
    budget = obj(E / "semantic_adjudication_call_budget.json")
    order = obj(E / "semantic_group_execution_order.json")
    envelope = obj(E / "development_semantic_adjudication_response_envelope_v1.json")
    validation = obj(E / "validation.json")
    require(policy["provider"] == "DeepSeek"
            and policy["model"] == "deepseek-flash"
            and policy["thinking"] == {"type": "enabled"}
            and policy["reasoning_effort"] == "high"
            and policy["response_format"] == {"type": "json_object"}
            and policy["automatic_retry"] is False
            and policy["known_no_inference_transport_retry_enabled"] is False
            and policy["fallback_model_or_provider"] is False
            and budget["planned_semantic_adjudication_groups"] == 28
            and budget["planned_semantic_adjudication_scientific_calls"] == 28
            and budget["calls_authorized_now"] == 0
            and order["group_count"] == 28
            and envelope["model_required_to_emit_schema_version"] is False
            and envelope["candidate_overall_state_controller_derived"] is True
            and validation["semantic_candidate_count"] == 84,
            "FROZEN_SEMANTIC_RUNTIME_OR_SCHEMA_MISMATCH")
    frozen_requests = rows(E / "semantic_adjudication_request_manifest.jsonl")
    order_rows = order["blinded_execution_ordinals"]
    template = (E / "semantic_adjudication_prompt_template.txt").read_text(
        encoding="utf-8")
    require(template.startswith("SYSTEM:\n") and "\nUSER:\n" in template
            and template.endswith("<BLINDED_PAYLOAD_JSON>\n"),
            "FROZEN_SEMANTIC_PROMPT_TEMPLATE_INVALID")
    frozen_system, frozen_user = template.removeprefix("SYSTEM:\n").split(
        "\nUSER:\n", 1)
    frozen_user_prefix = frozen_user.removesuffix("<BLINDED_PAYLOAD_JSON>\n")
    require(len(frozen_requests) == len(order_rows) == 28
            and [r["future_execution_ordinal"] for r in frozen_requests]
                == list(range(1, 29)),
            "FROZEN_SEMANTIC_REQUEST_COUNT_OR_ORDER_MISMATCH")
    group_tokens = set()
    candidate_tokens = set()
    for index, row in enumerate(frozen_requests):
        request = row["request"]
        visible = request["messages"]
        payload = json.loads(visible[1]["content"].split("\n", 1)[1])
        group = row["blinded_group_token"]
        tokens = row["blinded_candidate_tokens_in_display_order"]
        require(row["future_execution_ordinal"] == index + 1
                and order_rows[index] == {
                    "execution_ordinal": index + 1,
                    "blinded_group_token": group,
                    "request_sha256": row["request_sha256"]}
                and row["request_sha256"] == sha(canonical(request))
                and request["model"] == "deepseek-flash"
                and request["thinking"] == {"type": "enabled"}
                and request["reasoning_effort"] == "high"
                and request["response_format"] == {"type": "json_object"}
                and len(visible) == 2
                and visible[0]["role"] == "system"
                and visible[1]["role"] == "user"
                and visible[0]["content"] == frozen_system
                and visible[1]["content"].startswith(frozen_user_prefix)
                and set(payload) == {"blinded_group_token", "source_context", "candidates"}
                and payload["blinded_group_token"] == group
                and len(payload["candidates"]) == len(tokens) == 3
                and [x["candidate_token"] for x in payload["candidates"]] == tokens
                and len(set(tokens)) == 3
                and all(set(x) == {"candidate_token", "neutral_proposition",
                                      "exact_body_evidence_quote"}
                        for x in payload["candidates"])
                and set(request) == {"model", "thinking", "reasoning_effort",
                                     "response_format", "messages"},
                "FROZEN_SEMANTIC_REQUEST_PAYLOAD_MISMATCH:" + str(index + 1))
        require(group not in group_tokens and not candidate_tokens.intersection(tokens),
                "FROZEN_SEMANTIC_TOKEN_DUPLICATE")
        group_tokens.add(group)
        candidate_tokens.update(tokens)
    require(len(group_tokens) == 28 and len(candidate_tokens) == 84,
            "FROZEN_SEMANTIC_TOKEN_UNIVERSE_MISMATCH")
    private_refs = {}
    for name in PRIVATE_NAMES:
        path = E / name
        require(path.is_file() and not path.is_symlink()
                and path.stat().st_mode & 0o077 == 0,
                "FROZEN_PRIVATE_MAPPING_NOT_CONTROLLER_ONLY:" + name)
        private_refs[name] = ref(path)
    # Audit only explicit experimental labels, never ordinary scientific BODY
    # words such as V1 that could legitimately occur in a paper.
    wrapper = frozen_system + frozen_user_prefix
    require(all(marker.lower() not in wrapper.lower()
                for marker in EXPERIMENTAL_MARKERS),
            "MODEL_VISIBLE_EXPERIMENTAL_WRAPPER_LEAK")
    return {"requests": frozen_requests, "policy": policy, "budget": budget,
            "order": order, "envelope": envelope,
            "private_refs": private_refs}


def freeze_preflight(state: dict) -> None:
    OUT.mkdir()
    put("alpha3_20e_root_verification.json", {
        "expected_sha256": E_ROOT, "verified": True})
    put("semantic_request_manifest_preexecution_verification.json", {
        "manifest": ref(E / "semantic_adjudication_request_manifest.jsonl"),
        "verified": True, "request_count": 28,
        "request_regeneration_used": False})
    put("semantic_rubric_binding_verification.json", {
        "rubric": ref(E / "development_semantic_fidelity_rubric_v1.json"),
        "verified": True})
    put("semantic_response_envelope_binding_verification.json", {
        "envelope": ref(E /
            "development_semantic_adjudication_response_envelope_v1.json"),
        "verified": True, "model_required_to_emit_schema_version": False})
    put("semantic_prompt_template_binding_verification.json", {
        "prompt_template": ref(E / "semantic_adjudication_prompt_template.txt"),
        "verified": True})
    put("semantic_execution_preflight.json", {
        "status": "PASS", "planned_groups": 28, "planned_candidates": 84,
        "all_authorities_verified_before_provider_access": True,
        "provider_calls_before_barrier": 0,
        "private_mapping_contents_not_unblinded": True})
    put("semantic_execution_order_verification.json", {
        "frozen_order": ref(E / "semantic_group_execution_order.json"),
        "order_verified": True,
        "blinded_group_tokens_in_order": [r["blinded_group_token"]
                                          for r in state["requests"]]})
    put("semantic_provider_binding_verification.json", {
        "provider": "DeepSeek", "model": "deepseek-flash",
        "thinking": {"type": "enabled"}, "reasoning_effort": "high",
        "response_format": {"type": "json_object"},
        "fallback_allowed": False})
    put("semantic_runtime_policy_binding.json", {
        "runtime_policy": ref(E / "semantic_adjudication_runtime_policy.json"),
        "call_budget": ref(E / "semantic_adjudication_call_budget.json"),
        "automatic_retry": False,
        "ambiguous_execution_action": "STOP_NO_RETRY"})


def provider_failure_state(status: int, raw: bytes) -> tuple[str, str]:
    if status in (400, 404):
        try:
            error = json.loads(raw)["error"]
            message = " ".join(str(error.get(key, "")) for key in
                               ("message", "code", "type")).lower()
        except (ValueError, KeyError, TypeError, AttributeError):
            message = ""
        if "model" in message and any(term in message for term in
                ("not found", "does not exist", "invalid", "unsupported",
                 "unknown", "unavailable")):
            return "PROVIDER_NO_INFERENCE_TERMINAL_FAILURE", "PROVIDER_BINDING_FAILURE"
    return "PROVIDER_EXECUTION_AMBIGUOUS", (
        "SEMANTIC_ADJUDICATION_PROVIDER_EXECUTION_AMBIGUOUS")


def validate_response(content: str | None, finish_reason: str,
                      expected_tokens: list[str], schema: dict) -> tuple[dict | None,
                                                                          dict, dict]:
    diagnostics = {"candidate_token_set_failure": False,
                   "criterion_enum_failure_count": 0,
                   "missing_required_judgment_count": 0}
    try:
        if not isinstance(content, str):
            raise ValueError("SEMANTIC_RESPONSE_NO_TEXT_CONTENT")
        if finish_reason != "stop":
            raise ValueError("SEMANTIC_RESPONSE_INCOMPLETE_FINISH:" + finish_reason)
        def no_duplicate_keys(pairs: list[tuple[str, object]]) -> dict:
            result = {}
            for key, value in pairs:
                if key in result:
                    raise ValueError("SEMANTIC_RESPONSE_DUPLICATE_JSON_KEY:" + key)
                result[key] = value
            return result

        try:
            parsed = json.loads(content, object_pairs_hook=no_duplicate_keys)
        except json.JSONDecodeError as exc:
            raise ValueError("SEMANTIC_RESPONSE_MALFORMED_JSON") from exc
        if isinstance(parsed, dict) and isinstance(parsed.get("candidate_reviews"), list):
            returned = [entry.get("candidate_token") for entry in
                        parsed["candidate_reviews"] if isinstance(entry, dict)]
            diagnostics["candidate_token_set_failure"] = (
                len(returned) != 3 or
                not all(isinstance(token, str) for token in returned) or
                len(set(returned)) != 3 or
                set(returned) != set(expected_tokens))
            for entry in parsed["candidate_reviews"]:
                if not isinstance(entry, dict):
                    continue
                criteria = entry.get("criteria")
                if not isinstance(criteria, dict):
                    diagnostics["missing_required_judgment_count"] += len(e.CRITERIA)
                    continue
                for key in e.CRITERIA:
                    if key not in criteria or not isinstance(criteria[key], dict):
                        diagnostics["missing_required_judgment_count"] += 1
                    elif "state" not in criteria[key]:
                        diagnostics["missing_required_judgment_count"] += 1
                    elif criteria[key]["state"] not in e.STATES:
                        diagnostics["criterion_enum_failure_count"] += 1
        else:
            diagnostics["candidate_token_set_failure"] = True
        _validate_schema(parsed, schema)
        if diagnostics["candidate_token_set_failure"]:
            raise ValueError("SEMANTIC_CANDIDATE_TOKEN_SET_MISMATCH")
        return parsed, {"status": "SEMANTIC_RESPONSE_VALID",
                        "candidate_count": 3}, diagnostics
    except ValueError as exc:
        return None, {"status": "SEMANTIC_RESPONSE_INVALID",
                      "reason": str(exc)}, diagnostics


def execute(state: dict, secret: str) -> tuple:
    attempts, raw_rows, transport_rows, terminal_rows = [], [], [], []
    validity_rows, token_rows, judgment_rows = [], [], []
    failure = None
    schema = state["envelope"]["model_owned_payload_schema"]
    for row in state["requests"]:
        ordinal = row["future_execution_ordinal"]
        group = row["blinded_group_token"]
        expected_tokens = row["blinded_candidate_tokens_in_display_order"]
        require(sha(canonical(row["request"])) == row["request_sha256"]
                and digest(E / "semantic_adjudication_request_manifest.jsonl")
                    == REQUEST_SHA, "FROZEN_SEMANTIC_REQUEST_CHANGED_BEFORE_NETWORK")
        attempt = {"execution_ordinal": ordinal,
            "blinded_group_token": group,
            "blinded_candidate_tokens": expected_tokens,
            "request_sha256": row["request_sha256"],
            "provider": "DeepSeek", "model": "deepseek-flash",
            "attempt_number": 1, "started_unix_time": time.time(),
            "committed_before_network": True}
        write_raw(OUT / f"attempt_events/{ordinal:02d}.json",
                  canonical(attempt) + b"\n")
        attempts.append(attempt)
        print(f"ALPHA320E1_STARTED {ordinal}/28", flush=True)
        try:
            with httpx.Client(timeout=httpx.Timeout(connect=20.0, read=900.0,
                                                     write=120.0, pool=20.0)) as client:
                response = client.post(URL, headers={
                    "Authorization": f"Bearer {secret}",
                    "Content-Type": "application/json"},
                    content=canonical(row["request"]))
        except Exception as exc:
            terminal = {"execution_ordinal": ordinal,
                "blinded_group_token": group,
                "terminal_state": "PROVIDER_EXECUTION_AMBIGUOUS",
                "scientific_inference_occurrence": "UNKNOWN"}
            write_raw(OUT / f"terminal_events/{ordinal:02d}.json",
                      canonical(terminal) + b"\n")
            terminal_rows.append(terminal)
            failure = {"code": "SEMANTIC_ADJUDICATION_PROVIDER_EXECUTION_AMBIGUOUS",
                       "execution_ordinal": ordinal,
                       "error_type": type(exc).__name__, "error_message": str(exc)}
            break
        raw_path = OUT / f"raw_provider_response_bytes/{ordinal:02d}.bin"
        write_raw(raw_path, response.content)
        transport = {"execution_ordinal": ordinal,
            "blinded_group_token": group,
            "request_sha256": row["request_sha256"],
            "provider": "DeepSeek", "model": "deepseek-flash",
            "attempt_number": 1, "http_status": response.status_code,
            "raw_response_path": str(raw_path.relative_to(OUT)),
            "raw_response_sha256": digest(raw_path),
            "elapsed_seconds": response.elapsed.total_seconds(),
            "finished_unix_time": time.time(), "technical_retries": 0}
        write_raw(OUT / f"transport_events/{ordinal:02d}.json",
                  canonical(transport) + b"\n")
        transport_rows.append(transport)
        if response.status_code != 200:
            terminal_state, code = provider_failure_state(response.status_code,
                                                          response.content)
            terminal = {"execution_ordinal": ordinal,
                "blinded_group_token": group, "terminal_state": terminal_state,
                "scientific_inference_occurrence": "NO" if terminal_state ==
                    "PROVIDER_NO_INFERENCE_TERMINAL_FAILURE" else "UNKNOWN"}
            write_raw(OUT / f"terminal_events/{ordinal:02d}.json",
                      canonical(terminal) + b"\n")
            terminal_rows.append(terminal)
            failure = {"code": code, "execution_ordinal": ordinal,
                       "http_status": response.status_code,
                       "raw_response_sha256": digest(raw_path)}
            break
        try:
            envelope = response.json()
            choices = envelope["choices"]
            require(isinstance(choices, list) and len(choices) == 1,
                    "SEMANTIC_PROVIDER_CHOICES_INVALID")
            choice = choices[0]
            content = choice["message"]["content"]
            finish_reason = choice["finish_reason"]
            require((isinstance(content, str) or content is None)
                    and isinstance(finish_reason, str),
                    "SEMANTIC_PROVIDER_CONTENT_OR_FINISH_INVALID")
        except (ValueError, KeyError, TypeError, IndexError, RuntimeError) as exc:
            terminal = {"execution_ordinal": ordinal,
                "blinded_group_token": group,
                "terminal_state": "PROVIDER_EXECUTION_AMBIGUOUS",
                "scientific_inference_occurrence": "UNKNOWN"}
            write_raw(OUT / f"terminal_events/{ordinal:02d}.json",
                      canonical(terminal) + b"\n")
            terminal_rows.append(terminal)
            failure = {"code": "SEMANTIC_ADJUDICATION_PROVIDER_EXECUTION_AMBIGUOUS",
                       "execution_ordinal": ordinal,
                       "error_type": type(exc).__name__, "error_message": str(exc)}
            break
        raw_event = {"execution_ordinal": ordinal,
            "blinded_group_token": group,
            "request_sha256": row["request_sha256"],
            "transport": transport,
            "model_content_raw": content,
            "finish_reason": finish_reason,
            "provider_response_id": envelope.get("id"),
            "usage": envelope.get("usage"),
            "scientific_inference_confirmed": True}
        write_raw(OUT / f"raw_events/{ordinal:02d}.json",
                  canonical(raw_event) + b"\n")
        raw_rows.append(raw_event)
        parsed, validity, diagnostics = validate_response(
            content, finish_reason, expected_tokens, schema)
        validity.update({"execution_ordinal": ordinal,
                         "blinded_group_token": group})
        token_record = {"execution_ordinal": ordinal,
            "blinded_group_token": group,
            "expected_candidate_tokens": expected_tokens,
            "exact_token_set_valid": not diagnostics["candidate_token_set_failure"]
                if parsed is not None else False,
            "candidate_token_set_failure": diagnostics["candidate_token_set_failure"],
            "criterion_enum_failure_count": diagnostics[
                "criterion_enum_failure_count"],
            "missing_required_judgment_count": diagnostics[
                "missing_required_judgment_count"]}
        if parsed is None:
            terminal_state = "COMPLETED_SEMANTIC_RESPONSE_INVALID"
        else:
            terminal_state = "COMPLETED_SEMANTIC_RESPONSE_VALID"
            for item in parsed["candidate_reviews"]:
                judgment_rows.append({"execution_ordinal": ordinal,
                    "blinded_group_token": group,
                    "blinded_candidate_token": item["candidate_token"],
                    "request_sha256": row["request_sha256"],
                    "raw_response_sha256": digest(raw_path),
                    "criteria": item["criteria"],
                    "state": "RAW_BLINDED_SEMANTIC_CRITERION_JUDGMENTS"})
        terminal = {"execution_ordinal": ordinal,
            "blinded_group_token": group,
            "terminal_state": terminal_state,
            "scientific_inference_occurrence": "YES"}
        for folder, value in (("validation_events", validity),
                              ("token_set_events", token_record),
                              ("terminal_events", terminal)):
            write_raw(OUT / f"{folder}/{ordinal:02d}.json",
                      canonical(value) + b"\n")
        validity_rows.append(validity)
        token_rows.append(token_record)
        terminal_rows.append(terminal)
        print(f"ALPHA320E1_FROZEN {ordinal}/28 {terminal_state}", flush=True)
    for row in state["requests"][len(terminal_rows):]:
        terminal_rows.append({"execution_ordinal": row["future_execution_ordinal"],
            "blinded_group_token": row["blinded_group_token"],
            "terminal_state": "NOT_EXECUTED_AFTER_STAGE_STOP",
            "scientific_inference_occurrence": "NO"})
    return {"attempts": attempts, "raw": raw_rows, "transport": transport_rows,
            "terminal": terminal_rows, "validity": validity_rows,
            "tokens": token_rows, "judgments": judgment_rows, "failure": failure}


def freeze_results(state: dict, execution: dict) -> dict:
    attempts = execution["attempts"]
    raw_rows = execution["raw"]
    terminal_rows = execution["terminal"]
    validity_rows = execution["validity"]
    token_rows = execution["tokens"]
    judgment_rows = execution["judgments"]
    failure = execution["failure"]
    put_rows("semantic_request_attempt_log.jsonl", attempts)
    put_rows("semantic_raw_provider_responses.jsonl", raw_rows)
    raw_manifest_sha = digest(OUT / "semantic_raw_provider_responses.jsonl")
    write_raw(OUT / "semantic_raw_response_manifest_sha256",
              (raw_manifest_sha + "\n").encode("ascii"))
    put_rows("semantic_transport_provenance.jsonl", execution["transport"])
    put_rows("semantic_group_terminal_states.jsonl", terminal_rows)
    put_rows("semantic_response_envelope_validation.jsonl", validity_rows)
    put_rows("semantic_candidate_token_set_validation.jsonl", token_rows)
    put_rows("semantic_raw_judgment_manifest_blinded.jsonl", judgment_rows)
    judgment_sha = digest(OUT / "semantic_raw_judgment_manifest_blinded.jsonl")
    write_raw(OUT / "semantic_raw_judgment_manifest_blinded_sha256",
              (judgment_sha + "\n").encode("ascii"))
    states = Counter(row["terminal_state"] for row in terminal_rows)
    inference_events = sum(row["scientific_inference_occurrence"] == "YES"
                           for row in terminal_rows)
    valid_groups = states["COMPLETED_SEMANTIC_RESPONSE_VALID"]
    invalid_groups = states["COMPLETED_SEMANTIC_RESPONSE_INVALID"]
    ambiguous = states["PROVIDER_EXECUTION_AMBIGUOUS"]
    require(len(judgment_rows) == valid_groups * 3,
            "VALID_SEMANTIC_JUDGMENT_COVERAGE_MISMATCH")
    put("semantic_group_validity_summary.json", {
        "planned_groups": 28, "valid_group_count": valid_groups,
        "invalid_group_count": invalid_groups,
        "provider_execution_ambiguous_count": ambiguous,
        "not_executed_count": states["NOT_EXECUTED_AFTER_STAGE_STOP"],
        "semantic_selection_complete": valid_groups == 28 and failure is None})
    put("semantic_candidate_coverage_summary.json", {
        "planned_candidate_judgment_sets": 84,
        "valid_candidate_judgment_set_count": len(judgment_rows),
        "three_per_valid_group": True,
        "missing_groups_not_imputed": True})
    request_unchanged = (digest(E / "semantic_adjudication_request_manifest.jsonl")
                         == REQUEST_SHA)
    private_unchanged = all(digest(E / name) == state["private_refs"][name]["sha256"]
                            for name in PRIVATE_NAMES)
    upstream_root_unchanged = e.d.c.root_hash(E,
        "search_plan_v24_dev_alpha3_20e_sha256") == E_ROOT
    require(request_unchanged and private_unchanged and upstream_root_unchanged,
            "FROZEN_SEMANTIC_REQUEST_OR_MAPPING_CHANGED_DURING_EXECUTION")
    put("semantic_private_mapping_preservation_audit.json", {
        "private_mapping_unchanged": private_unchanged,
        "private_mapping_refs": state["private_refs"],
        "mapping_contents_not_used_for_arm_aggregation": True,
        "unblinding_performed": False})
    put("semantic_request_manifest_postexecution_verification.json", {
        "expected_sha256": REQUEST_SHA,
        "actual_sha256": digest(E / "semantic_adjudication_request_manifest.jsonl"),
        "semantic_request_manifest_unchanged": request_unchanged})
    template = (E / "semantic_adjudication_prompt_template.txt").read_text(
        encoding="utf-8")
    request_wrapper = template.replace("<BLINDED_PAYLOAD_JSON>", "")
    request_keys = []
    for request_row in state["requests"]:
        payload = json.loads(request_row["request"]["messages"][1]["content"].split(
            "\n", 1)[1])
        request_keys.extend(payload.keys())
    request_key_text = " ".join(request_keys)
    response_texts = [r["model_content_raw"] or "" for r in raw_rows]
    # Exact experimental labels only; isolated biological V1/V2 terms in a
    # scientific BODY or rationale are not treated as protocol disclosure.
    request_leaks = sum(text.lower().count(marker.lower())
                        for text in (request_wrapper, request_key_text)
                        for marker in EXPERIMENTAL_MARKERS)
    response_leaks = sum(text.lower().count(marker.lower())
                         for text in response_texts for marker in EXPERIMENTAL_MARKERS)
    put("semantic_blinding_postexecution_audit.json", {
        "experimental_marker_request_occurrences": request_leaks,
        "experimental_marker_response_occurrences": response_leaks,
        "total_explicit_experimental_marker_leak_count": request_leaks + response_leaks,
        "variant_identity_exposed_to_model": request_leaks > 0,
        "leakage_result_exposed_to_model": False,
        "selection_objective_exposed_to_model": False,
        "ordinary_scientific_body_or_rationale_v1_v2_terms_not_treated_as_arm_identity": True,
        "private_mapping_never_sent": True})
    put("semantic_response_freeze_before_unblinding.json", {
        "raw_response_manifest_sha256": raw_manifest_sha,
        "raw_judgment_manifest_sha256": judgment_sha,
        "all_attempted_raw_http_responses_saved_before_parsing": True,
        "terminal_states_frozen": True,
        "response_validation_frozen": True,
        "inference_accounting_frozen": True,
        "unblinding_performed": False,
        "candidate_overall_state_derived": False,
        "arm_aggregation_performed": False,
        "semantic_dominance_evaluated": False,
        "variant_selection_performed": False})
    if failure is not None:
        classification = "SEMANTIC_ADJUDICATION_EXECUTION_INCOMPLETE"
        next_stage = NEXT_FAILURE
        status = "failed"
    elif valid_groups == 28 and inference_events == 28 and len(attempts) == 28:
        classification = "ALL_28_BLINDED_SEMANTIC_ADJUDICATION_RESPONSES_FROZEN"
        next_stage = NEXT_SUCCESS
        status = "completed"
    else:
        classification = "SEMANTIC_ADJUDICATION_EXECUTED_WITH_INCOMPLETE_VALID_RESPONSE_SET"
        next_stage = NEXT_INVALID
        status = "failed"
    accounting = {"planned_semantic_groups": 28,
        "planned_semantic_candidates": 84,
        "semantic_groups_attempted": len(attempts),
        "semantic_scientific_inference_events": inference_events,
        "technical_retries": 0,
        "valid_semantic_group_count": valid_groups,
        "invalid_semantic_group_count": invalid_groups,
        "valid_candidate_judgment_set_count": len(judgment_rows),
        "candidate_token_set_failure_count": sum(row[
            "candidate_token_set_failure"] for row in token_rows),
        "criterion_enum_failure_count": sum(row[
            "criterion_enum_failure_count"] for row in token_rows),
        "missing_required_judgment_count": sum(row[
            "missing_required_judgment_count"] for row in token_rows),
        "provider_execution_ambiguous_count": ambiguous,
        "semantic_selection_complete": classification ==
            "ALL_28_BLINDED_SEMANTIC_ADJUDICATION_RESPONSES_FROZEN"}
    put("semantic_execution_accounting.json", accounting)
    put("historical_inference_accounting.json", {
        "historical_alpha3_18_builder_inference_events": 56,
        "historical_alpha3_18_quality_inference_events": 1,
        "historical_alpha3_19_builder_inference_events": 14,
        "historical_alpha3_19_quality_inference_events": 0,
        "historical_alpha3_20c_builder_inference_events": 42,
        "alpha3_20e1_semantic_adjudication_inference_events": inference_events,
        "historical_counts_mutated": False})
    put("development_contamination_update.json", {
        "historical_role": "SEEN_DEVELOPMENT_HISTORY",
        "blinded_request_manifest_sha256": REQUEST_SHA,
        "raw_response_manifest_sha256": raw_manifest_sha,
        "raw_judgment_manifest_sha256": judgment_sha,
        "fresh_heldout_reuse_prohibited": True})
    put("historical_preservation_audit.json", {
        "alpha3_20e_root_unchanged": upstream_root_unchanged,
        "semantic_request_manifest_unchanged": request_unchanged,
        "private_mapping_unchanged": private_unchanged,
        "historical_assets_modified": False})
    put("scientific_state_safety_audit.json", {
        "deepseek_calls": len(attempts),
        "builder_calls": 0, "quality_calls": 0,
        "openai_calls": 0, "ncbi_calls": 0,
        "non_deepseek_network_calls": 0,
        "semantic_scientific_retry_used": False,
        "request_regeneration_used": False,
        "unblinding_performed": False,
        "candidate_overall_state_derived": False,
        "arm_aggregation_performed": False,
        "semantic_dominance_evaluated": False,
        "variant_selection_performed": False})
    put("protocol_compliance_audit.json", {
        "exact_frozen_28_request_universe": True,
        "frozen_execution_order": True,
        "one_fresh_independent_context_per_group": True,
        "raw_response_before_parse": True,
        "scientific_retry_used": False,
        "no_semantic_overall_state_or_arm_aggregation": True,
        "no_leakage_merge_or_variant_selection": True,
        "runtime_failure": failure})
    validation = {"status": status,
        "alpha3_20e1_classification": classification,
        "alpha3_20e_root_verified": True,
        "semantic_request_manifest_verified": True,
        "semantic_request_manifest_unchanged": request_unchanged,
        "private_mapping_unchanged": private_unchanged,
        **accounting,
        "variant_identity_exposed_to_model": request_leaks > 0,
        "leakage_result_exposed_to_model": False,
        "selection_objective_exposed_to_model": False,
        "unblinding_performed": False,
        "candidate_overall_state_derived": False,
        "arm_aggregation_performed": False,
        "semantic_dominance_evaluated": False,
        "variant_selection_performed": False,
        "semantic_raw_judgment_manifest_blinded_sha256": judgment_sha,
        "provider": "DeepSeek", "model": "deepseek-flash",
        "semantic_scientific_retry_used": False,
        "request_regeneration_used": False,
        "alpha3_20e1_semantic_adjudication_inference_events": inference_events,
        "historical_alpha3_18_builder_inference_events": 56,
        "historical_alpha3_18_quality_inference_events": 1,
        "historical_alpha3_19_builder_inference_events": 14,
        "historical_alpha3_19_quality_inference_events": 0,
        "historical_alpha3_20c_builder_inference_events": 42,
        "deepseek_calls": len(attempts),
        "builder_calls": 0, "quality_calls": 0,
        "openai_calls": 0, "ncbi_calls": 0,
        "non_deepseek_network_calls": 0,
        "next_stage_recommendation": next_stage,
        "historical_assets_modified": False,
        "runtime_failure": failure}
    put("validation.json", validation)
    put("summary.json", {"status": status,
        "classification": classification,
        "semantic_groups_attempted": len(attempts),
        "semantic_scientific_inference_events": inference_events,
        "valid_semantic_group_count": valid_groups,
        "invalid_semantic_group_count": invalid_groups,
        "valid_candidate_judgment_set_count": len(judgment_rows),
        "next_stage_recommendation": next_stage})
    root = e.d.c.root_hash(OUT, ROOT_MARKER)
    write_raw(OUT / ROOT_MARKER, (root + "\n").encode("ascii"))
    return validation


def main() -> None:
    state = preflight()
    secret = key()
    freeze_preflight(state)
    execution = execute(state, secret)
    validation = freeze_results(state, execution)
    print(json.dumps({"status": validation["status"],
        "classification": validation["alpha3_20e1_classification"],
        "semantic_groups_attempted": validation["semantic_groups_attempted"],
        "semantic_scientific_inference_events": validation[
            "semantic_scientific_inference_events"],
        "root_sha256": (OUT / ROOT_MARKER).read_text().strip()},
        sort_keys=True), flush=True)


if __name__ == "__main__":
    main()
