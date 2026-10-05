#!/usr/bin/env python3
"""Execute only the 28 root-bound E1R blinded replication requests."""

from __future__ import annotations

import json
import re
import time
from collections import Counter
from pathlib import Path

import httpx

from scripts import run_search_plan_v24_alpha320e1_semantic_adjudication_execution as e1
from scripts import run_search_plan_v24_alpha320e1r_full_blinded_semantic_replication_prereg_offline as r


ROOT = r.ROOT
R = r.OUT
OUT = ROOT / "runs/20261004_search_plan_v24_dev_alpha3_20e1r1_full_blinded_semantic_replication_execution"
ROOT_MARKER = "search_plan_v24_dev_alpha3_20e1r1_sha256"
R_ROOT = "a75663e6d3b03cd3456e8c9e82269aad496e53d00db1d09b127a3c7d92e37655"
ENVELOPE_SHA = "f44baaeb3a9b63dd7b570ef49478f6a6058cf71eedd1aca8849dd7cb5158a34a"
PROMPT_SHA = "b45bb14ba2ece19504d431ba7a344c8c835a0f47a53bba85f96353a193be0fc1"
MANIFEST_SHA = "dd7b66e16ee27a59f7663262f0cffa24f46d59ddc916c418bc5668e19bf6dd4e"
NEXT_SUCCESS = "PREREGISTER_ALPHA3_20E2_REPLICATION_UNBLIND_AGGREGATE_AND_SELECT_OFFLINE"
NEXT_INVALID = "INTERPRET_ALPHA3_20E1R1_INCOMPLETE_REPLICATION_OFFLINE"
NEXT_FAILURE = "AUDIT_ALPHA3_20E1R1_RUNTIME_FAILURE_OFFLINE"
PRIVATE_NAMES = ("replication_group_token_mapping_private.jsonl",
                 "replication_candidate_token_mapping_private.jsonl",
                 "replication_blinding_seed_private.json")


def require(condition: bool, reason: str) -> None:
    if not condition:
        raise RuntimeError(reason)


def put(name: str, value: object) -> None:
    e1.write_raw(OUT / name, r.canonical(value) + b"\n")


def put_rows(name: str, data: list[dict]) -> None:
    e1.write_raw(OUT / name, b"".join(r.canonical(row) + b"\n" for row in data))


def marker(name: str, value: str) -> None:
    e1.write_raw(OUT / name, (value + "\n").encode("ascii"))


def preflight() -> dict:
    require(not OUT.exists(), "E1R1_OUTPUT_ALREADY_EXISTS_NO_REINFERENCE")
    require((R / r.ROOT_MARKER).read_text().strip() == R_ROOT
            and r.e.d.c.root_hash(R, r.ROOT_MARKER) == R_ROOT,
            "E1R_ROOT_MISMATCH")
    values = {"manifest_bytes": r.digest(R /
                  "replication_semantic_adjudication_request_manifest.jsonl"),
              "dedicated_marker": (R /
                  "replication_semantic_adjudication_request_manifest_sha256").read_text().strip(),
              "validation": r.obj(R / "validation.json")[
                  "replication_semantic_adjudication_request_manifest_sha256"]}
    require(len(set(values.values())) == 1
            and all(re.fullmatch(r"[0-9a-f]{64}", value) for value in values.values())
            and values["manifest_bytes"] == MANIFEST_SHA,
            "REPLICATION_REQUEST_MANIFEST_AUTHORITY_UNRESOLVED")
    envelope_path = R / "development_semantic_adjudication_response_envelope_v2.json"
    prompt_path = R / "replication_semantic_adjudication_prompt_template.txt"
    require(r.digest(envelope_path) == ENVELOPE_SHA
            and (R / "development_semantic_adjudication_response_envelope_v2_sha256").read_text().strip() == ENVELOPE_SHA
            and r.digest(prompt_path) == PROMPT_SHA
            and (R / "replication_semantic_adjudication_prompt_template_sha256").read_text().strip() == PROMPT_SHA,
            "FROZEN_REPLICATION_INTERFACE_HASH_MISMATCH")
    policy = r.obj(R / "replication_runtime_policy.json")
    budget = r.obj(R / "replication_call_budget.json")
    order = r.obj(R / "replication_group_execution_order.json")
    parser = r.obj(R / "replication_parser_contract.json")
    schema = r.obj(envelope_path)
    strict = r.obj(R / "replication_strict_json_contract.json")
    blinding = r.obj(R / "replication_blinding_contract.json")
    independence = r.obj(R / "replication_dataset_independence_contract.json")
    require(policy["provider"] == "DeepSeek"
            and policy["model"] == "deepseek-flash"
            and policy["thinking"] == {"type": "enabled"}
            and policy["reasoning_effort"] == "high"
            and policy["response_format"] == {"type": "json_object"}
            and policy["automatic_retry"] is False
            and policy["known_no_inference_transport_retry_enabled"] is False
            and policy["fallback_model_or_provider"] is False
            and policy["one_fresh_independent_context_per_group"] is True
            and policy["scientific_inference_attempts_per_group_maximum"] == 1
            and policy["zero_result_dependent_prompt_adaptation"] is True
            and budget["planned_replication_semantic_groups"] == 28
            and budget["planned_replication_semantic_candidates"] == 84
            and budget["planned_replication_semantic_scientific_calls"] == 28
            and budget["calls_authorized_now"] == 0
            and order["group_count"] == 28
            and schema["schema_version"] ==
                "DevelopmentSemanticAdjudicationResponseEnvelopeV2"
            and schema["provider_native_json_schema_mode_activated"] is False
            and strict["strict_json"] is True
            and strict["trailing_commas_allowed"] is False
            and strict["response_repair_allowed"] is False
            and parser["underlying_validator_source_sha256"] == r.digest(
                ROOT / "scripts/run_search_plan_v24_alpha320e1_semantic_adjudication_execution.py")
            and parser["schema"]["sha256"] == ENVELOPE_SHA
            and parser["strict_json_parse"] is True
            and parser["whole_content_only"] is True
            and parser["trailing_comma_or_brace_repair"] is False
            and independence["replication_dataset_may_mix_with_e1"] is False,
            "FROZEN_REPLICATION_RUNTIME_OR_PARSER_POLICY_MISMATCH")
    for name, expected in (
        ("development_semantic_fidelity_rubric_v1_binding.json", r.e1.RUBRIC_SHA),
        ("semantic_dominance_rule_binding.json", None),
        ("semantic_variant_selection_rule_binding.json", None),
        ("semantic_candidate_overall_state_derivation_binding.json", None)):
        binding = r.obj(R / name)
        reference = binding.get("rubric") or binding.get("frozen_authority")
        path = ROOT / reference["path"]
        require(r.digest(path) == reference["sha256"]
                and (expected is None or reference["sha256"] == expected)
                and binding.get("rule_changed", False) is False,
                "SCIENTIFIC_POLICY_BINDING_CHANGED:" + name)
    private_refs = {}
    for name in PRIVATE_NAMES:
        path = R / name
        require(path.is_file() and not path.is_symlink()
                and path.stat().st_mode & 0o077 == 0,
                "REPLICATION_PRIVATE_MAPPING_PERMISSION_FAILURE")
        private_refs[name] = r.ref(path)
    require(private_refs[PRIVATE_NAMES[0]]["sha256"] == blinding[
                "private_group_mapping_sha256"]
            and private_refs[PRIVATE_NAMES[1]]["sha256"] == blinding[
                "private_candidate_mapping_sha256"]
            and private_refs[PRIVATE_NAMES[2]]["sha256"] == order[
                "seed_private_artifact_sha256"],
            "REPLICATION_PRIVATE_MAPPING_HASH_MISMATCH")
    template = prompt_path.read_text(encoding="utf-8")
    require(template.startswith("SYSTEM:\n") and "\nUSER:\n" in template
            and template.endswith("<BLINDED_PAYLOAD_JSON>\n"),
            "FROZEN_REPLICATION_PROMPT_TEMPLATE_INVALID")
    system, user = template.removeprefix("SYSTEM:\n").split("\nUSER:\n", 1)
    user_prefix = user.removesuffix("<BLINDED_PAYLOAD_JSON>\n")
    request_rows = r.rows(R / "replication_semantic_adjudication_request_manifest.jsonl")
    require(len(request_rows) == len(order["blinded_execution_ordinals"]) == 28,
            "REPLICATION_REQUEST_COUNT_MISMATCH")
    groups, candidates = set(), set()
    for ordinal, row in enumerate(request_rows, 1):
        request = row["request"]
        group = row["blinded_group_token"]
        tokens = row["blinded_candidate_tokens_in_display_order"]
        visible = request["messages"]
        payload = json.loads(visible[1]["content"].removeprefix(user_prefix))
        require(row["future_execution_ordinal"] == ordinal
                and order["blinded_execution_ordinals"][ordinal - 1] == {
                    "future_execution_ordinal": ordinal,
                    "blinded_group_token": group,
                    "request_sha256": row["request_sha256"]}
                and row["request_sha256"] == r.sha(r.canonical(request))
                and set(request) == {"model", "thinking", "reasoning_effort",
                                     "response_format", "messages"}
                and request["model"] == "deepseek-flash"
                and request["thinking"] == {"type": "enabled"}
                and request["reasoning_effort"] == "high"
                and request["response_format"] == {"type": "json_object"}
                and len(visible) == 2
                and visible[0] == {"role": "system", "content": system}
                and visible[1]["role"] == "user"
                and visible[1]["content"].startswith(user_prefix)
                and set(payload) == {"blinded_group_token", "source_context",
                                     "candidates"}
                and payload["blinded_group_token"] == group
                and len(payload["candidates"]) == len(tokens) == 3
                and [item["candidate_token"] for item in payload["candidates"]]
                    == tokens
                and all(set(item) == {"candidate_token", "neutral_proposition",
                                      "exact_body_evidence_quote"}
                        for item in payload["candidates"])
                and group not in groups and not candidates.intersection(tokens),
                "FROZEN_REPLICATION_REQUEST_ORDER_OR_PAYLOAD_MISMATCH:" +
                str(ordinal))
        groups.add(group)
        candidates.update(tokens)
    require(len(groups) == 28 and len(candidates) == 84,
            "REPLICATION_TOKEN_UNIVERSE_MISMATCH")
    # Inspect only protocol wrapper and field names; biological V1/V2 in a
    # paper's BODY is not experimental arm disclosure.
    wrapper = system + user_prefix
    require(all(marker.lower() not in wrapper.lower() for marker in
                r.EXPLICIT_EXPERIMENTAL_MARKERS),
            "MODEL_VISIBLE_REPLICATION_WRAPPER_LEAK")
    return {"requests": request_rows, "manifest_sha": MANIFEST_SHA,
            "manifest_hash_evidence": values, "policy": policy,
            "budget": budget, "order": order, "parser": parser,
            "envelope": schema, "private_refs": private_refs,
            "prompt_template": template}


def freeze_preflight(state: dict) -> None:
    OUT.mkdir()
    put("alpha3_20e1r_root_verification.json", {"verified": True,
        "expected_sha256": R_ROOT})
    put("replication_request_manifest_authoritative_binding.json", {
        "authoritative_sha256": MANIFEST_SHA,
        "hash_sources": state["manifest_hash_evidence"],
        "valid_lowercase_64_hex": True,
        "conflicting_human_report_text_not_used": True,
        "root_verified_before_provider_access": True})
    put("replication_request_manifest_preexecution_verification.json", {
        "manifest": r.ref(R /
            "replication_semantic_adjudication_request_manifest.jsonl"),
        "verified": True, "request_count": 28,
        "request_regeneration_used": False})
    put("replication_response_envelope_v2_binding.json", {
        "envelope": r.ref(R /
            "development_semantic_adjudication_response_envelope_v2.json"),
        "schema_version": "DevelopmentSemanticAdjudicationResponseEnvelopeV2",
        "v1_fallback": False})
    put("replication_prompt_template_binding.json", {
        "template": r.ref(R /
            "replication_semantic_adjudication_prompt_template.txt"),
        "verified": True})
    put("replication_rubric_binding.json", {
        "rubric": r.obj(R /
            "development_semantic_fidelity_rubric_v1_binding.json")})
    put("replication_runtime_policy_binding.json", {
        "runtime_policy": r.ref(R / "replication_runtime_policy.json"),
        "call_budget": r.ref(R / "replication_call_budget.json"),
        "parser_contract": r.ref(R / "replication_parser_contract.json"),
        "automatic_retry": False,
        "ambiguous_execution_action": "STOP_NO_RETRY"})
    put("replication_execution_order_verification.json", {
        "order": r.ref(R / "replication_group_execution_order.json"),
        "order_verified": True,
        "blinded_group_tokens_in_order": [row["blinded_group_token"]
                                          for row in state["requests"]]})
    put("replication_provider_binding_verification.json", {
        "provider": "DeepSeek", "model": "deepseek-flash",
        "thinking": {"type": "enabled"}, "reasoning_effort": "high",
        "response_format": {"type": "json_object"},
        "fallback_allowed": False})
    put("replication_pre_provider_integrity_barrier.json", {
        "status": "PASS", "root_hash_verified": True,
        "authoritative_manifest_hash_resolved": True,
        "envelope_v2_verified": True,
        "prompt_verified": True,
        "rubric_dominance_selection_bindings_verified": True,
        "private_mapping_hashes_verified_without_parsing": True,
        "provider_calls_before_barrier": 0})


def execute(state: dict, secret: str) -> dict:
    attempts, raw_rows, transport_rows, terminal_rows = [], [], [], []
    validity_rows, token_rows, judgment_rows = [], [], []
    failure = None
    schema = state["envelope"]["model_owned_payload_schema"]
    for row in state["requests"]:
        ordinal = row["future_execution_ordinal"]
        group = row["blinded_group_token"]
        tokens = row["blinded_candidate_tokens_in_display_order"]
        require(r.sha(r.canonical(row["request"])) == row["request_sha256"]
                and r.digest(R /
                    "replication_semantic_adjudication_request_manifest.jsonl")
                    == MANIFEST_SHA,
                "FROZEN_REPLICATION_REQUEST_CHANGED_BEFORE_NETWORK")
        attempt = {"execution_ordinal": ordinal, "blinded_group_token": group,
            "blinded_candidate_tokens": tokens,
            "request_sha256": row["request_sha256"],
            "provider": "DeepSeek", "model": "deepseek-flash",
            "attempt_number": 1, "started_unix_time": time.time(),
            "committed_before_network": True}
        e1.write_raw(OUT / f"attempt_events/{ordinal:02d}.json",
                     r.canonical(attempt) + b"\n")
        attempts.append(attempt)
        print(f"ALPHA320E1R1_STARTED {ordinal}/28", flush=True)
        try:
            with httpx.Client(timeout=httpx.Timeout(connect=20.0, read=900.0,
                                                     write=120.0, pool=20.0)) as client:
                response = client.post(e1.URL, headers={
                    "Authorization": f"Bearer {secret}",
                    "Content-Type": "application/json"},
                    content=r.canonical(row["request"]))
        except Exception as exc:
            terminal = {"execution_ordinal": ordinal,
                "blinded_group_token": group,
                "terminal_state": "PROVIDER_EXECUTION_AMBIGUOUS",
                "scientific_inference_occurrence": "UNKNOWN"}
            e1.write_raw(OUT / f"terminal_events/{ordinal:02d}.json",
                         r.canonical(terminal) + b"\n")
            terminal_rows.append(terminal)
            failure = {"code": "SEMANTIC_REPLICATION_PROVIDER_EXECUTION_AMBIGUOUS",
                       "execution_ordinal": ordinal,
                       "error_type": type(exc).__name__,
                       "error_message": str(exc)}
            break
        raw_path = OUT / f"raw_provider_response_bytes/{ordinal:02d}.bin"
        e1.write_raw(raw_path, response.content)
        transport = {"execution_ordinal": ordinal,
            "blinded_group_token": group,
            "request_sha256": row["request_sha256"],
            "provider": "DeepSeek", "model": "deepseek-flash",
            "attempt_number": 1, "http_status": response.status_code,
            "raw_response_path": str(raw_path.relative_to(OUT)),
            "raw_response_sha256": r.digest(raw_path),
            "elapsed_seconds": response.elapsed.total_seconds(),
            "finished_unix_time": time.time(), "technical_retries": 0}
        e1.write_raw(OUT / f"transport_events/{ordinal:02d}.json",
                     r.canonical(transport) + b"\n")
        transport_rows.append(transport)
        if response.status_code != 200:
            terminal_state, code = e1.provider_failure_state(response.status_code,
                                                              response.content)
            terminal = {"execution_ordinal": ordinal,
                "blinded_group_token": group,
                "terminal_state": terminal_state,
                "scientific_inference_occurrence": "NO" if terminal_state ==
                    "PROVIDER_NO_INFERENCE_TERMINAL_FAILURE" else "UNKNOWN"}
            e1.write_raw(OUT / f"terminal_events/{ordinal:02d}.json",
                         r.canonical(terminal) + b"\n")
            terminal_rows.append(terminal)
            failure = {"code": code, "execution_ordinal": ordinal,
                       "http_status": response.status_code,
                       "raw_response_sha256": r.digest(raw_path)}
            break
        try:
            provider_envelope = response.json()
            choices = provider_envelope["choices"]
            require(isinstance(choices, list) and len(choices) == 1,
                    "REPLICATION_PROVIDER_CHOICES_INVALID")
            choice = choices[0]
            content = choice["message"]["content"]
            finish_reason = choice["finish_reason"]
            require((isinstance(content, str) or content is None)
                    and isinstance(finish_reason, str),
                    "REPLICATION_PROVIDER_CONTENT_OR_FINISH_INVALID")
        except (ValueError, KeyError, TypeError, IndexError, RuntimeError) as exc:
            terminal = {"execution_ordinal": ordinal,
                "blinded_group_token": group,
                "terminal_state": "PROVIDER_EXECUTION_AMBIGUOUS",
                "scientific_inference_occurrence": "UNKNOWN"}
            e1.write_raw(OUT / f"terminal_events/{ordinal:02d}.json",
                         r.canonical(terminal) + b"\n")
            terminal_rows.append(terminal)
            failure = {"code": "SEMANTIC_REPLICATION_PROVIDER_EXECUTION_AMBIGUOUS",
                       "execution_ordinal": ordinal,
                       "error_type": type(exc).__name__,
                       "error_message": str(exc)}
            break
        raw_event = {"execution_ordinal": ordinal,
            "blinded_group_token": group,
            "request_sha256": row["request_sha256"],
            "transport": transport,
            "model_content_raw": content,
            "finish_reason": finish_reason,
            "provider_response_id": provider_envelope.get("id"),
            "usage": provider_envelope.get("usage"),
            "scientific_inference_confirmed": True}
        e1.write_raw(OUT / f"raw_events/{ordinal:02d}.json",
                     r.canonical(raw_event) + b"\n")
        raw_rows.append(raw_event)
        parsed, validity, diagnostics = r.validate_replication_response(
            content, finish_reason, tokens, schema)
        validity.update({"execution_ordinal": ordinal,
                         "blinded_group_token": group})
        token_record = {"execution_ordinal": ordinal,
            "blinded_group_token": group,
            "expected_candidate_tokens": tokens,
            "exact_token_set_valid": parsed is not None and not diagnostics[
                "candidate_token_set_failure"],
            "candidate_token_set_failure": diagnostics[
                "candidate_token_set_failure"],
            "criterion_enum_failure_count": diagnostics[
                "criterion_enum_failure_count"],
            "missing_required_judgment_count": diagnostics[
                "missing_required_judgment_count"]}
        if parsed is None:
            terminal_state = "COMPLETED_REPLICATION_SEMANTIC_RESPONSE_INVALID"
        else:
            terminal_state = "COMPLETED_REPLICATION_SEMANTIC_RESPONSE_VALID"
            for item in parsed["candidate_reviews"]:
                judgment_rows.append({"execution_ordinal": ordinal,
                    "blinded_group_token": group,
                    "blinded_candidate_token": item["candidate_token"],
                    "request_sha256": row["request_sha256"],
                    "raw_response_sha256": r.digest(raw_path),
                    "criteria": item["criteria"],
                    "state": "RAW_BLINDED_REPLICATION_SEMANTIC_CRITERION_JUDGMENTS"})
        terminal = {"execution_ordinal": ordinal,
            "blinded_group_token": group,
            "terminal_state": terminal_state,
            "scientific_inference_occurrence": "YES"}
        for folder, value in (("validation_events", validity),
                              ("token_set_events", token_record),
                              ("terminal_events", terminal)):
            e1.write_raw(OUT / f"{folder}/{ordinal:02d}.json",
                         r.canonical(value) + b"\n")
        validity_rows.append(validity)
        token_rows.append(token_record)
        terminal_rows.append(terminal)
        print(f"ALPHA320E1R1_FROZEN {ordinal}/28 {terminal_state}", flush=True)
    for row in state["requests"][len(terminal_rows):]:
        terminal_rows.append({"execution_ordinal": row["future_execution_ordinal"],
            "blinded_group_token": row["blinded_group_token"],
            "terminal_state": "NOT_EXECUTED_AFTER_STAGE_STOP",
            "scientific_inference_occurrence": "NO"})
    return {"attempts": attempts, "raw": raw_rows,
            "transport": transport_rows, "terminal": terminal_rows,
            "validity": validity_rows, "tokens": token_rows,
            "judgments": judgment_rows, "failure": failure}


def freeze_results(state: dict, execution: dict) -> dict:
    attempts = execution["attempts"]
    raw_rows = execution["raw"]
    terminal_rows = execution["terminal"]
    validity_rows = execution["validity"]
    token_rows = execution["tokens"]
    judgment_rows = execution["judgments"]
    failure = execution["failure"]
    for name, data in (
        ("replication_request_attempt_log.jsonl", attempts),
        ("replication_raw_provider_responses.jsonl", raw_rows),
        ("replication_transport_provenance.jsonl", execution["transport"]),
        ("replication_group_terminal_states.jsonl", terminal_rows),
        ("replication_response_envelope_validation.jsonl", validity_rows),
        ("replication_candidate_token_set_validation.jsonl", token_rows),
        ("replication_raw_judgment_manifest_blinded.jsonl", judgment_rows)):
        put_rows(name, data)
    raw_manifest_sha = r.digest(OUT / "replication_raw_provider_responses.jsonl")
    judgment_sha = r.digest(OUT /
        "replication_raw_judgment_manifest_blinded.jsonl")
    marker("replication_raw_response_manifest_sha256", raw_manifest_sha)
    marker("replication_raw_judgment_manifest_blinded_sha256", judgment_sha)
    states = Counter(row["terminal_state"] for row in terminal_rows)
    inference_events = sum(row["scientific_inference_occurrence"] == "YES"
                           for row in terminal_rows)
    valid_groups = states["COMPLETED_REPLICATION_SEMANTIC_RESPONSE_VALID"]
    invalid_groups = states["COMPLETED_REPLICATION_SEMANTIC_RESPONSE_INVALID"]
    ambiguous = states["PROVIDER_EXECUTION_AMBIGUOUS"]
    require(len(judgment_rows) == valid_groups * 3,
            "VALID_REPLICATION_JUDGMENT_COVERAGE_MISMATCH")
    full = (len(attempts) == inference_events == valid_groups == 28
            and invalid_groups == ambiguous == 0 and len(judgment_rows) == 84
            and failure is None)
    put("replication_group_validity_summary.json", {
        "planned_groups": 28, "valid_group_count": valid_groups,
        "invalid_group_count": invalid_groups,
        "provider_execution_ambiguous_count": ambiguous,
        "not_executed_count": states["NOT_EXECUTED_AFTER_STAGE_STOP"],
        "replication_selection_eligible": full})
    put("replication_candidate_coverage_summary.json", {
        "planned_candidate_judgment_sets": 84,
        "valid_candidate_judgment_set_count": len(judgment_rows),
        "three_per_valid_group": True,
        "missing_groups_not_imputed_from_e1": True})
    request_unchanged = r.digest(R /
        "replication_semantic_adjudication_request_manifest.jsonl") == MANIFEST_SHA
    private_unchanged = all(r.digest(R / name) == state["private_refs"][name][
        "sha256"] for name in PRIVATE_NAMES)
    upstream_unchanged = r.e.d.c.root_hash(R, r.ROOT_MARKER) == R_ROOT
    require(request_unchanged and private_unchanged and upstream_unchanged,
            "FROZEN_REPLICATION_REQUEST_OR_MAPPING_CHANGED_DURING_EXECUTION")
    put("replication_private_mapping_preservation_audit.json", {
        "replication_private_mapping_unchanged": True,
        "private_mapping_refs": state["private_refs"],
        "mapping_contents_not_used_for_arm_aggregation": True,
        "unblinding_performed": False})
    put("replication_request_manifest_postexecution_verification.json", {
        "authoritative_sha256": MANIFEST_SHA,
        "actual_sha256": r.digest(R /
            "replication_semantic_adjudication_request_manifest.jsonl"),
        "replication_request_manifest_unchanged": True})
    template = state["prompt_template"]
    wrapper = template.replace("<BLINDED_PAYLOAD_JSON>", "")
    request_keys = []
    for row in state["requests"]:
        payload = json.loads(row["request"]["messages"][1]["content"].split(
            "\n", 1)[1])
        request_keys.extend(payload.keys())
    marker_texts = (wrapper, " ".join(request_keys))
    request_leaks = sum(text.lower().count(marker.lower())
                        for text in marker_texts
                        for marker in r.EXPLICIT_EXPERIMENTAL_MARKERS)
    model_content_texts = [row["model_content_raw"] or "" for row in raw_rows]
    response_leaks = sum(text.lower().count(marker.lower())
                         for text in model_content_texts
                         for marker in r.EXPLICIT_EXPERIMENTAL_MARKERS)
    require(request_leaks == 0, "MODEL_VISIBLE_REPLICATION_REQUEST_BLINDING_LEAK")
    put("replication_blinding_postexecution_audit.json", {
        "explicit_experimental_marker_request_occurrences": request_leaks,
        "explicit_experimental_marker_response_occurrences": response_leaks,
        "variant_identity_exposed_to_model": False,
        "leakage_result_exposed_to_model": False,
        "e1_judgment_exposed_to_model": False,
        "selection_objective_exposed_to_model": False,
        "private_mapping_never_sent": True,
        "scientific_body_v1_v2_terms_not_treated_as_experimental_arm_labels": True})
    put("replication_e1_nonuse_audit.json", {
        "e1_scientific_judgment_content_read_for_execution_or_selection": False,
        "e1_judgments_merged_into_replication": False,
        "e1_response_substituted_for_replication_response": False,
        "e1_root_or_accounting_metadata_only": True,
        "replication_dataset_may_mix_with_e1": False})
    put("replication_response_freeze_before_unblinding.json", {
        "raw_response_manifest_sha256": raw_manifest_sha,
        "raw_judgment_manifest_sha256": judgment_sha,
        "all_attempted_http_response_bytes_saved_before_parsing": True,
        "terminal_states_frozen": True,
        "response_validation_frozen": True,
        "inference_accounting_frozen": True,
        "unblinding_performed": False,
        "candidate_overall_state_derived": False,
        "arm_aggregation_performed": False,
        "semantic_dominance_evaluated": False,
        "variant_selection_performed": False})
    if failure is not None:
        classification = "FULL_REPLICATION_EXECUTION_INCOMPLETE"
        next_stage = NEXT_FAILURE
        status = "failed"
    elif full:
        classification = "ALL_28_REPLICATION_SEMANTIC_RESPONSES_VALID_AND_FROZEN"
        next_stage = NEXT_SUCCESS
        status = "completed"
    else:
        classification = "FULL_REPLICATION_EXECUTED_WITH_INCOMPLETE_VALID_RESPONSE_SET"
        next_stage = NEXT_INVALID
        status = "failed"
    accounting = {"planned_replication_groups": 28,
        "planned_replication_candidates": 84,
        "replication_groups_attempted": len(attempts),
        "replication_semantic_scientific_inference_events": inference_events,
        "technical_retries": 0,
        "valid_replication_group_count": valid_groups,
        "invalid_replication_group_count": invalid_groups,
        "valid_replication_candidate_judgment_set_count": len(judgment_rows),
        "candidate_token_set_failure_count": sum(row[
            "candidate_token_set_failure"] for row in token_rows),
        "criterion_enum_failure_count": sum(row[
            "criterion_enum_failure_count"] for row in token_rows),
        "missing_required_judgment_count": sum(row[
            "missing_required_judgment_count"] for row in token_rows),
        "malformed_json_response_count": sum(row.get("reason") ==
            "SEMANTIC_RESPONSE_MALFORMED_JSON" for row in validity_rows),
        "provider_execution_ambiguous_count": ambiguous,
        "replication_selection_eligible": full}
    put("replication_execution_accounting.json", accounting)
    put("historical_inference_accounting.json", {
        "historical_alpha3_18_builder_inference_events": 56,
        "historical_alpha3_18_quality_inference_events": 1,
        "historical_alpha3_19_builder_inference_events": 14,
        "historical_alpha3_19_quality_inference_events": 0,
        "historical_alpha3_20c_builder_inference_events": 42,
        "historical_alpha3_20e1_semantic_adjudication_inference_events": 28,
        "alpha3_20e1r1_semantic_adjudication_inference_events": inference_events,
        "historical_counts_mutated": False})
    put("development_contamination_update.json", {
        "historical_role": "SEEN_DEVELOPMENT_HISTORY",
        "replication_request_manifest_sha256": MANIFEST_SHA,
        "raw_response_manifest_sha256": raw_manifest_sha,
        "raw_judgment_manifest_sha256": judgment_sha,
        "future_fresh_heldout_reuse_prohibited": True,
        "e1_judgments_quarantined": True})
    put("historical_preservation_audit.json", {
        "alpha3_20e1r_root_unchanged": upstream_unchanged,
        "replication_request_manifest_unchanged": request_unchanged,
        "replication_private_mapping_unchanged": private_unchanged,
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
        "strict_response_envelope_v2_only": True,
        "scientific_retry_used": False,
        "e1_judgments_not_used": True,
        "no_semantic_overall_state_or_arm_aggregation": True,
        "no_leakage_merge_or_variant_selection": True,
        "runtime_failure": failure})
    validation = {"status": status,
        "alpha3_20e1r1_classification": classification,
        "alpha3_20e1r_root_verified": True,
        "authoritative_replication_request_manifest_sha256": MANIFEST_SHA,
        **accounting,
        "variant_identity_exposed_to_model": False,
        "leakage_result_exposed_to_model": False,
        "e1_judgment_exposed_to_model": False,
        "selection_objective_exposed_to_model": False,
        "unblinding_performed": False,
        "candidate_overall_state_derived": False,
        "arm_aggregation_performed": False,
        "semantic_dominance_evaluated": False,
        "variant_selection_performed": False,
        "replication_raw_judgment_manifest_blinded_sha256": judgment_sha,
        "replication_request_manifest_unchanged": True,
        "replication_private_mapping_unchanged": True,
        "provider": "DeepSeek", "model": "deepseek-flash",
        "semantic_scientific_retry_used": False,
        "request_regeneration_used": False,
        "alpha3_20e1r1_semantic_adjudication_inference_events": inference_events,
        "historical_alpha3_18_builder_inference_events": 56,
        "historical_alpha3_18_quality_inference_events": 1,
        "historical_alpha3_19_builder_inference_events": 14,
        "historical_alpha3_19_quality_inference_events": 0,
        "historical_alpha3_20c_builder_inference_events": 42,
        "historical_alpha3_20e1_semantic_adjudication_inference_events": 28,
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
        "replication_groups_attempted": len(attempts),
        "replication_semantic_scientific_inference_events": inference_events,
        "valid_replication_group_count": valid_groups,
        "invalid_replication_group_count": invalid_groups,
        "valid_replication_candidate_judgment_set_count": len(judgment_rows),
        "next_stage_recommendation": next_stage})
    root = r.e.d.c.root_hash(OUT, ROOT_MARKER)
    marker(ROOT_MARKER, root)
    return validation


def main() -> None:
    state = preflight()
    secret = e1.key()
    freeze_preflight(state)
    execution = execute(state, secret)
    validation = freeze_results(state, execution)
    print(json.dumps({"status": validation["status"],
        "classification": validation["alpha3_20e1r1_classification"],
        "replication_groups_attempted": validation["replication_groups_attempted"],
        "replication_semantic_scientific_inference_events": validation[
            "replication_semantic_scientific_inference_events"],
        "root_sha256": (OUT / ROOT_MARKER).read_text().strip()},
        sort_keys=True), flush=True)


if __name__ == "__main__":
    main()
