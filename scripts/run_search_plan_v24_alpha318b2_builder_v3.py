#!/usr/bin/env python3
"""Execute the 28 frozen BODY-only V3 requests once, then freeze Quality inputs."""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

import httpx

try:
    from scripts import run_search_plan_v24_alpha318b_builder as base
    from scripts import search_plan_v24_alpha318b1_audit_grounding_contract_offline as b1
    from scripts import search_plan_v24_alpha318b_post_builder_prechecks as checks
except ModuleNotFoundError:
    import run_search_plan_v24_alpha318b_builder as base
    import search_plan_v24_alpha318b1_audit_grounding_contract_offline as b1
    import search_plan_v24_alpha318b_post_builder_prechecks as checks

ROOT = b1.ROOT
OUT = ROOT / "runs/20261001_search_plan_v24_dev_alpha3_18b2_builder_v3_execution"
ROOT_NAME = "search_plan_v24_dev_alpha3_18b2_sha256"
B1_SHA = "d8882e55a37d94f44ed94845dd24ccbd137591be4a60128ff1cc4e494fe0348a"
CONTRACT_SHA = "25d52f9ef10f3226e6003bcca46aa5d6a664b2b47bf7052db255a19da124e497"
SCHEMA_SHA = "092961a96fe2985633054b68760cd409780e7e44fbfb2c5cd14c12ed9a51e326"
REQUESTS_SHA = "065c709b8ca73bf214b68f2ee3e13693ff9a61f6b14ac5808c8326ebcad1c9dd"
MANIFEST_SHA = "8eadd79b0895a17e7d4162cf8e3dcee8f1f22b72fadc6a3764d2f3946df4a1e4"
URL = base.URL


def preflight() -> dict[str, Any]:
    if OUT.exists():
        raise RuntimeError("ALPHA3_18B2_RUN_ALREADY_EXISTS_NO_REINFERENCE")
    upstream = base.frozen.preflight()
    if (b1.OUT / b1.ROOT_MARKER).read_text().strip() != B1_SHA or (
        b1.prior.a6.base.prior.all_file_root(b1.OUT, b1.ROOT_MARKER) != B1_SHA):
        raise RuntimeError("ALPHA3_18B1_ROOT_MISMATCH")
    if b1.prior.a6.base.prior.all_file_root(b1.HISTORY,
        "search_plan_v24_dev_alpha3_18b_sha256") != b1.HISTORY_SHA:
        raise RuntimeError("HISTORICAL_V2_ROOT_MISMATCH")
    files = (
        ("builder_grounding_contract_v3.json", "builder_grounding_contract_v3_sha256", CONTRACT_SHA),
        ("builder_output_schema_v3.json", "builder_output_schema_v3_sha256", SCHEMA_SHA),
        ("builder_v3_request_manifest.jsonl", "builder_v3_request_manifest_sha256", REQUESTS_SHA),
        ("alpha3_18b2_builder_v3_execution_manifest.json",
         "alpha3_18b2_builder_v3_execution_manifest_sha256", MANIFEST_SHA))
    for filename, marker_name, expected in files:
        if b1.digest(b1.OUT / filename) != expected or (
            (b1.OUT / marker_name).read_text().strip() != expected):
            raise RuntimeError("FROZEN_V3_ARTIFACT_MISMATCH:" + filename)
    manifest = b1.read(b1.OUT / "alpha3_18b2_builder_v3_execution_manifest.json")
    for reference in base.refs(manifest):
        path = ROOT / reference["path"]
        if not path.is_file() or path.is_symlink() or b1.digest(path) != reference["sha256"]:
            raise RuntimeError("V3_MANIFEST_BOUND_ARTIFACT_MISMATCH:" + reference["path"])
    requests = b1.rows(b1.OUT / "builder_v3_request_manifest.jsonl")
    sources = upstream["sources"]
    if not (len(requests) == len(sources) == 28):
        raise RuntimeError("V3_REQUEST_CARDINALITY_MISMATCH")
    if len(requests) != 28 or [row["source_token"] for row in requests] != [
        row["source_token"] for row in sources]:
        raise RuntimeError("V3_SOURCE_SET_OR_ORDER_MISMATCH")
    if [row["request_sha256"] for row in requests] != [
        row["request_sha256"] for row in manifest["builder_v3_request_order"]]:
        raise RuntimeError("V3_REQUEST_ORDER_MISMATCH")
    schema = b1.read(b1.OUT / "builder_output_schema_v3.json")["schema"]
    field = schema["properties"]["candidates"]["items"]["properties"][
        "construction_evidence_span"]["properties"]["source_field"]
    if field["enum"] != ["body"] or schema["properties"]["candidates"]["minItems"] != 0 or (
        schema["properties"]["candidates"]["maxItems"] != 3):
        raise RuntimeError("V3_BODY_ONLY_SCHEMA_MISMATCH")
    delta = b1.read(b1.OUT / "builder_prompt_v3_delta.json")
    old_system = upstream["protocol"]["system_prompt_utf8"]
    config = upstream["provider"]
    if config != manifest["provider_configuration"] or (
        manifest["quality_protocol_v2_root_sha256"] != b1.prior.QUALITY_SHA):
        raise RuntimeError("V3_PROVIDER_OR_QUALITY_CONFIG_MISMATCH")
    for original, row, source in zip(upstream["requests"], requests, sources):
        request = row["request"]
        if (row["document_sha256"] != source["document_sha256"] or
            base.sha(base.canonical(request)) != row["request_sha256"] or
            set(request) != set(original["request"]) or
            any(request[key] != original["request"][key] for key in request if key != "messages") or
            request["messages"][0]["content"] != old_system + delta["added_system_instruction_utf8"] or
            request["messages"][1]["content"].split("Output schema: ", 1)[0] !=
            original["request"]["messages"][1]["content"].split("Output schema: ", 1)[0]):
            raise RuntimeError("V3_REQUEST_HASH_OR_GROUNDING_DELTA_MISMATCH")
        if (b1.digest(b1.prior.a6.OUT / source["document_path"]) !=
            source["document_sha256"]):
            raise RuntimeError("V3_SOURCE_DOCUMENT_HASH_MISMATCH")
    quarantine = b1.read(b1.OUT / "v2_candidate_quarantine.json")
    if quarantine["candidate_count"] != 70 or len(quarantine["records"]) != 70:
        raise RuntimeError("V2_CANDIDATE_QUARANTINE_MISMATCH")
    v2_ids = {record["candidate_id"] for record in quarantine["records"]}
    if len(v2_ids) != 70:
        raise RuntimeError("V2_CANDIDATE_ID_SET_INVALID")
    return {"upstream": upstream, "requests": requests, "schema": schema,
        "manifest": manifest, "v2_ids": v2_ids}


def fail(code: str, ordinal: int | None, error: Exception | None = None) -> None:
    base.obj(OUT / "runtime_failure.json", {
        "status": "FAILED_CLOSED", "failure_code": code, "source_ordinal": ordinal,
        "error_type": type(error).__name__ if error else None,
        "error_message": str(error) if error else None,
        "scientific_retry_permitted": False, "quality_calls": 0,
        "next_stage_recommendation": "AUDIT_ALPHA3_18B2_RUNTIME_FAILURE_OFFLINE"})


def _execute() -> None:
    state = preflight()
    secret = base.key()
    upstream, requests = state["upstream"], state["requests"]
    sources = upstream["sources"]
    vault = {row["source_token"]: row for row in upstream["vault"]}
    jats = {row["pmcid"]: row for row in b1.prior.a6.v3.replay.rows(
        b1.prior.a6.V3 / "pmc_jats_acquisition_results_v3.jsonl")}
    OUT.mkdir()
    base.obj(OUT / "builder_v3_execution_preflight.json", {
        "status": "PASS", "b1_root_sha256": B1_SHA,
        "v3_grounding_contract_sha256": CONTRACT_SHA, "v3_schema_sha256": SCHEMA_SHA,
        "v3_request_manifest_sha256": REQUESTS_SHA, "v3_execution_manifest_sha256": MANIFEST_SHA,
        "historical_v2_root_sha256": b1.HISTORY_SHA,
        "all_manifest_bound_artifacts_verified": True,
        "source_count": 28, "request_count": 28})
    base.obj(OUT / "builder_v3_request_manifest_verification.json", {
        "v3_request_manifest_sha256": REQUESTS_SHA,
        "v3_request_count": 28, "source_count": 28,
        "request_hash_changes": 0, "source_set_changed": False,
        "scientific_task_changed": False})
    base.obj(OUT / "builder_v3_call_order.json", {"calls": [
        {"ordinal": row["ordinal"], "source_token": row["source_token"],
         "request_sha256": row["request_sha256"]} for row in requests]})
    logs: dict[str, list[dict[str, Any]]] = {name: [] for name in (
        "raw", "transport", "validation", "terminal", "candidate_raw", "identity",
        "grounding", "leakage", "prechecked")}
    groups: list[dict[str, Any]] = []
    for ordinal, (item, source_row) in enumerate(zip(requests, sources), 1):
        token, request = item["source_token"], item["request"]
        if base.sha(base.canonical(request)) != item["request_sha256"]:
            fail("V3_REQUEST_HASH_CHANGED", ordinal)
            raise RuntimeError("V3_REQUEST_HASH_CHANGED")
        base.obj(OUT / "attempts" / f"{ordinal:02d}.json", {
            "ordinal": ordinal, "source_token": token,
            "request_sha256": item["request_sha256"],
            "provider_configuration": upstream["provider"],
            "single_v3_inference_attempt_committed_before_network": True,
            "started_unix_time": time.time()})
        print(f"BUILDER_V3_CALL_STARTED {ordinal}/28", flush=True)
        try:
            with httpx.Client(timeout=httpx.Timeout(connect=20.0, read=900.0,
                                                     write=120.0, pool=20.0)) as client:
                response = client.post(URL, headers={"Authorization": f"Bearer {secret}",
                    "Content-Type": "application/json"}, content=base.canonical(request))
        except Exception as exc:
            fail("BUILDER_PROVIDER_EXECUTION_AMBIGUOUS", ordinal, exc)
            raise RuntimeError("BUILDER_PROVIDER_EXECUTION_AMBIGUOUS") from exc
        raw_path = OUT / "raw_provider_responses" / f"{ordinal:02d}.json"
        base.once(raw_path, response.content)
        transport = {"ordinal": ordinal, "source_token": token,
            "request_sha256": item["request_sha256"], "http_status": response.status_code,
            "raw_response_sha256": base.sha(response.content),
            "raw_response_path": str(raw_path.relative_to(OUT)),
            "elapsed_seconds": response.elapsed.total_seconds(), "retry_count": 0}
        base.obj(OUT / "transport_events" / f"{ordinal:02d}.json", transport)
        logs["transport"].append(transport)
        if response.status_code != 200:
            fail("BUILDER_PROVIDER_EXECUTION_AMBIGUOUS", ordinal)
            raise RuntimeError("BUILDER_PROVIDER_EXECUTION_AMBIGUOUS:HTTP_" + str(response.status_code))
        try:
            envelope = response.json()
            choices = envelope["choices"]
            if not isinstance(choices, list) or len(choices) != 1:
                raise ValueError("V3_PROVIDER_CHOICES_INVALID")
            content = choices[0]["message"]["content"]
            finish = choices[0]["finish_reason"]
            if not isinstance(content, str) or not isinstance(finish, str):
                raise ValueError("V3_PROVIDER_CONTENT_OR_FINISH_INVALID")
        except Exception as exc:
            fail("BUILDER_PROVIDER_EXECUTION_AMBIGUOUS", ordinal, exc)
            raise RuntimeError("BUILDER_PROVIDER_EXECUTION_AMBIGUOUS:envelope") from exc
        raw = {"ordinal": ordinal, "source_token": token,
            "request_sha256": item["request_sha256"],
            "provider": upstream["provider"]["provider"],
            "model": upstream["provider"]["model"],
            "raw_response_path": str(raw_path.relative_to(OUT)),
            "raw_response_sha256": base.sha(response.content),
            "model_content_raw": content, "finish_reason": finish,
            "provider_response_id": envelope.get("id"), "usage": envelope.get("usage")}
        base.obj(OUT / "raw_events" / f"{ordinal:02d}.json", raw)
        logs["raw"].append(raw)
        try:
            if finish != "stop":
                raise ValueError("BUILDER_V3_RESPONSE_INCOMPLETE_FINISH:" + finish)
            parsed = checks.validate_builder_response(content.encode("utf-8"),
                token, state["schema"])
        except ValueError as exc:
            validation = {"ordinal": ordinal, "source_token": token,
                "status": "BUILDER_V3_RESPONSE_INVALID", "reason": str(exc)}
            terminal = {"ordinal": ordinal, "source_token": token,
                "terminal_state": "BUILDER_V3_RESPONSE_INVALID"}
            logs["validation"].append(validation)
            logs["terminal"].append(terminal)
            base.obj(OUT / "source_events" / f"{ordinal:02d}.json",
                {"raw": raw, "transport": transport,
                 "validation": validation, "terminal": terminal})
            print(f"BUILDER_V3_RESPONSE_INVALID {ordinal}/28", flush=True)
            continue
        validation = {"ordinal": ordinal, "source_token": token,
            "status": "V3_SCHEMA_VALID", "candidate_count": len(parsed["candidates"])}
        terminal = {"ordinal": ordinal, "source_token": token,
            "terminal_state": "BUILDER_VALID_NONZERO" if parsed["candidates"] else
                              "BUILDER_VALID_ZERO"}
        logs["validation"].append(validation)
        logs["terminal"].append(terminal)
        base.obj(OUT / "source_events" / f"{ordinal:02d}.json",
            {"raw": raw, "transport": transport,
             "validation": validation, "terminal": terminal})
        for position, candidate in enumerate(parsed["candidates"]):
            logs["candidate_raw"].append({"ordinal": ordinal, "source_token": token,
                "raw_array_position": position, "candidate": candidate})
        document_path = b1.prior.a6.OUT / source_row["document_path"]
        if b1.digest(document_path) != source_row["document_sha256"]:
            fail("V3_FROZEN_SOURCE_DOCUMENT_CHANGED", ordinal)
            raise RuntimeError("V3_FROZEN_SOURCE_DOCUMENT_CHANGED")
        document = json.loads(document_path.read_bytes())
        identity = base.private_identity(vault[token], jats)
        checked = checks.precheck_candidates(parsed, document, identity["title_1"])
        for record in checked["candidate_records_private"]:
            if record["candidate_id"] in state["v2_ids"]:
                fail("V3_CANDIDATE_ID_REUSES_V2_ID", ordinal)
                raise RuntimeError("V3_CANDIDATE_ID_REUSES_V2_ID")
            logs["identity"].append({"ordinal": ordinal, "source_token": token,
                "v3_schema_state": "V3_SCHEMA_VALID",
                "deterministic_id_state": record["deterministic_id_state"],
                "exact_duplicate_state": record["exact_dedup_state"],
                "body_grounding_state": record["grounding_reference_state"],
                "lexical_leakage_state": record["leakage_gate_state"],
                **record})
            logs["grounding"].append({"ordinal": ordinal, "source_token": token,
                "candidate_id": record["candidate_id"],
                "state": record["grounding_reference_state"],
                "reason": record.get("grounding_reason"),
                "private_anchor_id": record.get("private_anchor_id")})
            logs["leakage"].append({"ordinal": ordinal, "source_token": token,
                "candidate_id": record["candidate_id"], "state": record["leakage_gate_state"]})
        for survivor in checked["survivors_private"]:
            logs["prechecked"].append({"ordinal": ordinal, "source_token": token,
                "candidate_id": survivor["candidate_id"], "candidate": survivor["candidate"],
                "state": "QUALITY_ADJUDICATION_INPUT_CANDIDATE"})
        if checked["survivors_private"]:
            groups.append({"ordinal": ordinal, "source_token": token,
                "survivors": checked["survivors_private"],
                "document": document, "private_identity": identity})
        print(f"BUILDER_V3_CALL_FROZEN {ordinal}/28 state={terminal['terminal_state']} "
              f"raw_candidates={len(parsed['candidates'])}", flush=True)
    finalize(logs, groups)


def finalize(logs: dict[str, list[dict[str, Any]]], groups: list[dict[str, Any]]) -> None:
    if len(logs["terminal"]) != 28 or len(logs["raw"]) != 28 or (
        len(logs["transport"]) != 28):
        fail("ALPHA3_18B2_EXECUTION_MANIFEST_INCOMPLETE", None)
        raise RuntimeError("ALPHA3_18B2_EXECUTION_MANIFEST_INCOMPLETE")
    names = {
        "raw": "builder_v3_raw_responses.jsonl",
        "transport": "builder_v3_transport_provenance.jsonl",
        "validation": "builder_v3_response_validation.jsonl",
        "terminal": "builder_v3_source_terminal_states.jsonl",
        "candidate_raw": "builder_v3_candidate_raw_manifest.jsonl",
        "identity": "builder_v3_candidate_identity_manifest.jsonl",
        "grounding": "builder_v3_grounding_reference_audit.jsonl",
        "leakage": "builder_v3_leakage_audit.jsonl",
        "prechecked": "builder_v3_prechecked_candidate_manifest.jsonl"}
    for category, filename in names.items():
        base.lines(OUT / filename, logs[category])
    raw_count = len(logs["candidate_raw"])
    duplicate_count = raw_count - len(logs["identity"])
    grounded = [row for row in logs["grounding"]
                if row["state"] == "GROUNDING_REFERENCE_VALID"]
    grounding_failures = len(logs["grounding"]) - len(grounded)
    leakage_evaluated = [row for row in logs["leakage"] if row["state"] in (
        "LEXICAL_LEAKAGE_FAILED", "LEXICAL_LEAKAGE_PASSED")]
    if len(leakage_evaluated) != len(grounded):
        fail("V3_LEAKAGE_DENOMINATOR_MISMATCH", None)
        raise RuntimeError("V3_LEAKAGE_DENOMINATOR_MISMATCH")
    leakage_failures = sum(row["state"] == "LEXICAL_LEAKAGE_FAILED"
                           for row in leakage_evaluated)
    states = [row["terminal_state"] for row in logs["terminal"]]
    zero = states.count("BUILDER_VALID_ZERO")
    nonzero = states.count("BUILDER_VALID_NONZERO")
    invalid = states.count("BUILDER_V3_RESPONSE_INVALID")
    if zero + nonzero + invalid != 28:
        fail("V3_SOURCE_TERMINAL_STATE_MISMATCH", None)
        raise RuntimeError("V3_SOURCE_TERMINAL_STATE_MISMATCH")
    base.obj(OUT / "builder_v3_exact_duplicate_audit.json", {
        "raw_candidate_count": raw_count, "unique_after_exact_dedup": len(logs["identity"]),
        "exact_duplicates_removed": duplicate_count,
        "semantic_near_duplicate_elimination": False})
    base.obj(OUT / "builder_v3_candidate_summary.json", {
        "raw_candidate_count": raw_count, "schema_valid_candidate_count": raw_count,
        "exact_duplicates_removed": duplicate_count,
        "body_grounding_reference_evaluated": len(logs["grounding"]),
        "grounding_reference_failures": grounding_failures,
        "leakage_evaluated_denominator": len(leakage_evaluated),
        "lexical_leakage_failures": leakage_failures,
        "quality_adjudication_input_candidate_count": len(logs["prechecked"])})
    base.obj(OUT / "builder_v3_execution_accounting.json", {
        "planned_sources": 28, "requests_attempted": len(logs["raw"]),
        "v3_scientific_inference_events": len(logs["raw"]),
        "transport_only_retries": 0, "valid_zero": zero,
        "valid_nonzero": nonzero, "response_invalid": invalid,
        "raw_candidate_count": raw_count})
    base.obj(OUT / "cumulative_builder_inference_accounting.json", {
        "historical_builder_v2_scientific_inference_events": 28,
        "builder_v3_scientific_inference_events": len(logs["raw"]),
        "cumulative_builder_scientific_inference_events": 28 + len(logs["raw"]),
        "historical_v2_events_erased_or_relabelled": False})
    base.obj(OUT / "v2_candidate_nonuse_audit.json", {
        "historical_v2_quarantine_source": b1.ref(b1.OUT / "v2_candidate_quarantine.json"),
        "historical_v2_candidate_count": 70,
        "v2_candidate_ids_used_only_for_collision_guard": True,
        "v2_candidate_scientific_content_read": False,
        "v2_candidates_entering_v3_or_quality": 0,
        "v2_v3_scientific_comparison": False,
        "best_of_two_selection": False})
    base.obj(OUT / "all_builder_v3_outputs_freeze_barrier.json", {
        "crossed": True, "source_terminal_count": 28, "raw_responses_frozen": True,
        "v3_schema_validation_frozen": True,
        "candidate_ids_and_exact_dedup_frozen": True,
        "body_grounding_and_leakage_prechecks_frozen": True,
        "builder_v3_calls_closed": True})
    print("ALL_BUILDER_V3_OUTPUTS_FROZEN", flush=True)

    quality = b1.prior.QUALITY_DIR
    schema = json.loads((quality / "proposition_quality_adjudication_v2_schema.json").read_bytes())["schema"]
    appendix = json.loads((quality / "quality_machine_output_contract.json").read_bytes())["appendix_utf8"]
    system = (quality / "quality_adjudicator_system_prompt.txt").read_text(encoding="utf-8")
    template = (quality / "quality_adjudicator_user_prompt_template.txt").read_text(encoding="utf-8")
    quality_rows: list[dict[str, Any]] = []
    group_rows: list[dict[str, Any]] = []
    for group in groups:
        payload = checks.build_quality_payload(group["source_token"], group["survivors"],
            group["document"], group["private_identity"])
        request = checks.build_quality_request(payload, schema, system, template, appendix)
        ids = [packet["candidate_id"] for packet in payload["candidate_packets"]]
        group_rows.append({"ordinal": group["ordinal"],
            "private_source_token": group["source_token"],
            "source_group_id": payload["source_group_id"],
            "candidate_ids": ids, "candidate_count": len(ids)})
        quality_rows.append({"ordinal": group["ordinal"],
            "source_group_id": payload["source_group_id"],
            "candidate_ids": ids, "request": request,
            "request_sha256": base.sha(base.canonical(request))})
    base.lines(OUT / "quality_v3_source_group_manifest.jsonl", group_rows)
    base.obj(OUT / "actual_quality_call_budget_v3.json", {
        "actual_quality_adjudication_call_count": len(group_rows),
        "maximum_future_quality_calls": 28,
        "derived_from_nonempty_v3_source_groups": True})
    base.obj(OUT / "quality_v3_visibility_preflight_audit.json", {
        "source_groups_audited": len(group_rows),
        "all_payloads_checked_before_manifest_freeze": True,
        "private_identity_match_count": 0,
        "v2_candidate_exposure_count": 0,
        "full_article_exposure_count": 0})
    base.lines(OUT / "proposition_quality_v2_request_manifest_v3.jsonl", quality_rows)
    quality_sha = base.sha((OUT / "proposition_quality_v2_request_manifest_v3.jsonl").read_bytes())
    base.once(OUT / "proposition_quality_v2_request_manifest_v3_sha256",
              (quality_sha + "\n").encode("ascii"))
    base.obj(OUT / "quality_v3_manifest_freeze_barrier.json", {
        "crossed": True, "builder_v3_output_barrier_crossed_first": True,
        "quality_request_count": len(quality_rows),
        "quality_request_manifest_sha256": quality_sha,
        "quality_calls": 0, "separate_quality_authorization_required": True})
    base.obj(OUT / "development_nonuse_audit.json", {
        "development_labels_or_retrieval_used": False,
        "known_pmid_recovery_checks": False, "heldout_selection": False})
    base.obj(OUT / "search_plan_firewall_audit.json", {
        "search_plan_state_exposed": False, "search_plan_queries_used": False,
        "ncbi_calls": 0})
    base.obj(OUT / "protocol_compliance_audit.json", {
        "alpha3_18b2_execution_manifest_verified": True,
        "builder_v3_request_manifest_verified": True,
        "builder_v3_source_count": 28, "builder_v3_request_count": 28,
        "source_set_changed": False, "scientific_task_changed": False,
        "body_only_grounding_enforced": True,
        "abstract_grounding_schema_valid": False,
        "v2_candidates_used": False, "source_topup_used": False,
        "scientific_builder_v3_retry_used": False,
        "exact_within_source_dedup_used": True,
        "body_grounding_precheck_used": True, "leakage_gate_used": True,
        "leakage_evaluated_denominator": len(leakage_evaluated),
        "all_builder_v3_outputs_frozen_before_quality_manifest": True,
        "actual_quality_call_count_derived": True,
        "quality_request_manifest_v3_frozen": True})
    base.obj(OUT / "scientific_state_safety_audit.json", {
        "provider": "DeepSeek", "model": "deepseek-v4-pro",
        "deepseek_calls": len(logs["raw"]), "openai_calls": 0,
        "quality_calls": 0, "ncbi_calls": 0,
        "non_deepseek_network_calls": 0, "source_topup_used": False,
        "historical_assets_modified": False})
    base.obj(OUT / "validation.json", {
        "status": "PASS", "planned_builder_v3_sources": 28,
        "planned_builder_v3_requests": 28,
        "builder_v3_requests_attempted": len(logs["raw"]),
        "builder_v3_scientific_inference_events": len(logs["raw"]),
        "builder_v3_valid_zero": zero, "builder_v3_valid_nonzero": nonzero,
        "builder_v3_response_invalid": invalid,
        "actual_quality_adjudication_call_count": len(group_rows),
        "quality_request_count_v3": len(quality_rows), "quality_calls": 0})
    next_stage = ("INTERPRET_ZERO_QUALITY_INPUT_AFTER_CORRECTED_BUILDER_V3"
                  if not quality_rows else
                  "PREREGISTER_ALPHA3_18C_QUALITY_EXECUTION_AUTHORIZATION")
    base.obj(OUT / "summary.json", {
        "status": "completed", "builder_v3_requests_attempted": len(logs["raw"]),
        "builder_v3_valid_zero": zero, "builder_v3_valid_nonzero": nonzero,
        "builder_v3_response_invalid": invalid,
        "builder_v3_raw_candidate_count": raw_count,
        "builder_v3_exact_duplicates_removed": duplicate_count,
        "builder_v3_grounding_reference_failures": grounding_failures,
        "builder_v3_leakage_evaluated_denominator": len(leakage_evaluated),
        "builder_v3_lexical_leakage_failures": leakage_failures,
        "quality_input_candidate_count_v3": len(logs["prechecked"]),
        "quality_source_group_count_v3": len(group_rows),
        "actual_quality_adjudication_call_count": len(group_rows),
        "proposition_quality_v2_request_manifest_v3_sha256": quality_sha,
        "historical_builder_v2_scientific_inference_events": 28,
        "builder_v3_scientific_inference_events": len(logs["raw"]),
        "cumulative_builder_scientific_inference_events": 28 + len(logs["raw"]),
        "next_stage_recommendation": next_stage})
    if b1.prior.a6.base.prior.all_file_root(b1.HISTORY,
        "search_plan_v24_dev_alpha3_18b_sha256") != b1.HISTORY_SHA:
        fail("HISTORICAL_V2_ASSET_MUTATED", None)
        raise RuntimeError("HISTORICAL_V2_ASSET_MUTATED")
    root = b1.prior.a6.base.prior.all_file_root(OUT, ROOT_NAME)
    base.once(OUT / ROOT_NAME, (root + "\n").encode("ascii"))
    print(json.dumps({"status": "completed", "root_sha256": root,
        "builder_v3_inferences": len(logs["raw"]),
        "quality_request_count": len(quality_rows),
        "quality_request_manifest_sha256": quality_sha}, sort_keys=True), flush=True)


def execute() -> None:
    try:
        _execute()
    except Exception as exc:
        if OUT.is_dir():
            if not (OUT / "runtime_failure.json").exists():
                fail("ALPHA3_18B2_RUNTIME_FAILURE", None, exc)
            if not (OUT / ROOT_NAME).exists():
                root = b1.prior.a6.base.prior.all_file_root(OUT, ROOT_NAME)
                base.once(OUT / ROOT_NAME, (root + "\n").encode("ascii"))
        raise


if __name__ == "__main__":
    execute()
