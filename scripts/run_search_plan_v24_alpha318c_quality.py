#!/usr/bin/env python3
"""Execute the three frozen Quality V2 groups once under the Flash binding."""
from __future__ import annotations

import copy
import json
import re
import time
from pathlib import Path
from typing import Any

import httpx

from scripts import search_plan_v24_alpha318c_preregister_quality_offline as frozen
from scripts import run_search_plan_v24_alpha318b_builder as historical_transport


ROOT = frozen.ROOT
PREREG = frozen.OUT
OUT = ROOT / "runs/20261001_search_plan_v24_dev_alpha3_18c_quality_execution"
ROOT_MARKER = "search_plan_v24_dev_alpha3_18c_sha256"
PREREG_SHA = "f8cab0d34ac2de3c376ec8a2176f624091fcad1aecff4617ed9a66400356f2e0"
MANIFEST_SHA = "5bb2a2dc5cc447a5df5e3c253ba381153e6a8a962f2ef04422a39dff1158925e"
BINDING_SHA = "bdf4d844f22466c5d748671b2d35c4b3db1ea4c1fd05d6e4baee33f194893db5"
URL = "https://api.deepseek.com/v1/chat/completions"


def write_raw(path: Path, raw: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as handle:
        handle.write(raw)


def obj(path: Path, value: Any) -> None:
    write_raw(path, frozen.canonical(value) + b"\n")


def jsonl(path: Path, values: list[dict[str, Any]]) -> None:
    write_raw(path, b"".join(frozen.canonical(item) + b"\n" for item in values))


def refs(value: Any) -> list[dict[str, str]]:
    if isinstance(value, list):
        return [ref for item in value for ref in refs(item)]
    if isinstance(value, dict):
        if set(value) == {"path", "sha256"}:
            return [value]
        return [ref for item in value.values() for ref in refs(item)]
    return []


def project_request(item: dict[str, Any]) -> dict[str, Any]:
    result = copy.deepcopy(item["request"])
    frozen.require(result["model"] == frozen.OLD_MODEL,
        "QUALITY_REQUEST_FREEZE_MISMATCH")
    result["model"] = frozen.MODEL
    frozen.require(set(result) == {"model", "thinking", "reasoning_effort",
        "response_format", "stream", "messages"} and
        result["thinking"] == {"type": "enabled"} and
        result["reasoning_effort"] == "high" and
        result["response_format"] == {"type": "json_object"} and
        result["stream"] is False,
        "QUALITY_PROVIDER_CONFIG_UNRESOLVED")
    return result


def preflight() -> dict[str, Any]:
    frozen.require(not OUT.exists(), "QUALITY_RUN_ALREADY_EXISTS_NO_REINFERENCE")
    frozen.require(frozen.root(PREREG, frozen.ROOT_MARKER) == PREREG_SHA and
        (PREREG / frozen.ROOT_MARKER).read_text().strip() == PREREG_SHA,
        "ALPHA3_18C_PREREG_ROOT_MISMATCH")
    manifest_path = PREREG / "alpha3_18c_quality_execution_manifest.json"
    binding_path = PREREG / "quality_execution_provider_binding_v2_1.json"
    frozen.require(frozen.digest(manifest_path) == MANIFEST_SHA and
        (PREREG / "alpha3_18c_quality_execution_manifest_sha256").read_text().strip() == MANIFEST_SHA,
        "ALPHA3_18C_EXECUTION_MANIFEST_MISMATCH")
    frozen.require(frozen.digest(binding_path) == BINDING_SHA and
        (PREREG / "quality_execution_provider_binding_v2_1_sha256").read_text().strip() == BINDING_SHA,
        "QUALITY_PROVIDER_BINDING_MISMATCH")
    manifest = frozen.load(manifest_path)
    binding = frozen.load(binding_path)
    for reference in refs(manifest):
        target = ROOT / reference["path"]
        frozen.require(target.is_file() and not target.is_symlink() and
            frozen.digest(target) == reference["sha256"],
            "QUALITY_MANIFEST_BOUND_ARTIFACT_MISMATCH:" + reference["path"])
    candidates, groups, requests = frozen.verify_upstream()
    frozen.require((len(requests), len(groups), len(candidates)) == (3, 3, 5) and
        manifest["B2_root_sha256"] == frozen.B2_SHA and
        manifest["frozen_quality_request_manifest_sha256"] == frozen.REQUEST_SHA and
        manifest["quality_v2_scientific_protocol_sha256"] == frozen.QUALITY_SHA and
        manifest["provider"] == "DeepSeek" and manifest["model"] == frozen.MODEL and
        manifest["reviewer_role"] == "proposition_quality_adjudicator" and
        manifest["maximum_scientific_inferences"] == 3 and
        manifest["planned_source_groups"] == 3,
        "QUALITY_EXECUTION_UNIVERSE_MISMATCH")
    provider = binding["provider_configuration"]
    frozen.require(provider["provider"] == "DeepSeek" and provider["model"] == frozen.MODEL and
        provider["thinking"] == {"type": "enabled"} and
        provider["reasoning_effort"] == "high" and
        provider["temperature"] == provider["top_p"] == "omitted" and
        provider["automatic_retry"] is False and
        provider["scientific_repair_calls"] is False and
        provider["openai_or_alternate_model_fallback"] is False,
        "QUALITY_PROVIDER_CONFIG_UNRESOLVED")
    membership = frozen.load(PREREG / "quality_candidate_membership_freeze.json")["source_groups"]
    evidence = frozen.load(PREREG / "quality_evidence_packet_verification.json")["records"]
    group_by_id = {group["source_group_id"]: group for group in groups}
    projections = binding["projected_requests"]
    frozen.require(len(membership) == len(evidence) == len(projections) == 3,
        "QUALITY_INPUT_MEMBERSHIP_MISMATCH")
    prepared = []
    for index, (item, order, member, ev, projection) in enumerate(zip(
        requests, manifest["execution_order"], membership, evidence, projections), 1):
        gid = item["source_group_id"]
        packets = frozen.packets_from_frozen_request(item["request"])
        ids = {packet["candidate_id"] for packet in packets}
        frozen.require(index == order["order_index"] == member["order_index"] == projection["order_index"] and
            gid == order["source_group_id"] == member["source_group_id"] ==
            ev["source_group_id"] == projection["source_group_id"] and
            item["ordinal"] == order["frozen_source_ordinal"] and
            frozen.sha(frozen.canonical(item["request"])) == item["request_sha256"] ==
            order["frozen_request_sha256"] == member["frozen_request_sha256"] ==
            projection["frozen_request_sha256"] and
            ids == set(item["candidate_ids"]) == set(member["candidate_ids_sorted"]) ==
            set(group_by_id[gid]["candidate_ids"]) and
            len(ids) == len(packets) == member["candidate_count"],
            "QUALITY_INPUT_MEMBERSHIP_MISMATCH")
        hashes = {row["candidate_id"]: row for row in member["evidence_packets"]}
        contexts = {row["candidate_id"]: row["bounded_context_sha256"]
            for row in member["bounded_contexts"]}
        frozen.require(member["evidence_packets"] == ev["evidence_packet_hashes"] and
            member["bounded_contexts"] == ev["bounded_context_hashes"],
            "QUALITY_EVIDENCE_PACKET_MISMATCH")
        for packet in packets:
            cid = packet["candidate_id"]
            frozen.require(frozen.sha(frozen.canonical(packet)) == hashes[cid]["packet_sha256"] and
                frozen.sha(frozen.canonical(packet["evidence"])) == hashes[cid]["evidence_sha256"] and
                frozen.sha(packet["evidence"]["bounded_local_context"].encode("utf-8")) == contexts[cid],
                "QUALITY_EVIDENCE_PACKET_MISMATCH")
        outbound = project_request(item)
        frozen.require(frozen.sha(frozen.canonical(outbound)) ==
            order["provider_serialized_request_sha256"] == projection["provider_serialized_request_sha256"] and
            frozen.sha(frozen.canonical(outbound["messages"])) == projection["messages_sha256"],
            "QUALITY_PROVIDER_SERIALIZATION_MISMATCH")
        prepared.append({"order_index": index, "source_group_id": gid,
            "candidate_ids": sorted(ids), "private_source_token": group_by_id[gid]["private_source_token"],
            "frozen_request_sha256": item["request_sha256"],
            "outbound_request_sha256": order["provider_serialized_request_sha256"],
            "outbound_request": outbound, "packets": packets})
    schema = frozen.load(frozen.Q2 / "proposition_quality_adjudication_v2_schema.json")["schema"]
    frozen.require(schema["properties"]["judgments"]["items"]["properties"]["criteria"]["required"] ==
        frozen.quality.CRITERIA and
        all(schema["properties"]["judgments"]["items"]["properties"]["criteria"]["properties"][name]["enum"] ==
            frozen.quality.STATES for name in frozen.quality.CRITERIA),
        "QUALITY_RESPONSE_SCHEMA_DRIFT")
    return {"manifest": manifest, "binding": binding, "requests": prepared,
        "schema": schema}


def model_rejection(response: httpx.Response) -> bool:
    """Only an explicit provider-side model-identifier rejection is pre-inference."""
    if response.status_code not in (400, 404, 422):
        return False
    try:
        error = response.json()["error"]
        if not isinstance(error, dict):
            return False
        value = " ".join(str(error.get(key, "")) for key in ("type", "code", "message"))
    except (ValueError, KeyError, TypeError):
        return False
    return bool(re.search(r"(?:unknown|invalid|unsupported|not found|not available|does not exist).{0,60}model|model.{0,60}(?:unknown|invalid|unsupported|not found|not available|does not exist)",
        value, re.IGNORECASE))


def parse_completed(response: httpx.Response) -> tuple[dict[str, Any], str, str]:
    envelope = response.json()
    choices = envelope["choices"]
    if not isinstance(choices, list) or len(choices) != 1:
        raise ValueError("PROVIDER_CHOICES_INVALID")
    message = choices[0]["message"]
    content = message["content"]
    finish = choices[0]["finish_reason"]
    if not isinstance(content, str) or not isinstance(finish, str):
        raise ValueError("PROVIDER_CONTENT_OR_FINISH_INVALID")
    return envelope, content, finish


def outcome(criteria: dict[str, str]) -> str:
    frozen.quality.quality_result(criteria)
    if any(value == "FAIL" for value in criteria.values()):
        return "QUALITY_FAIL"
    if any(value == "UNRESOLVED" for value in criteria.values()):
        return "QUALITY_UNRESOLVED"
    return "QUALITY_PASS"


def freeze_logs(logs: dict[str, list[dict[str, Any]]]) -> None:
    mapping = {
        "raw": "quality_raw_responses.jsonl",
        "transport": "quality_transport_provenance.jsonl",
        "identity": "quality_response_identity_validation.jsonl",
        "schema": "quality_response_schema_validation.jsonl",
        "criteria": "quality_candidate_criterion_results.jsonl",
        "final": "quality_candidate_final_states.jsonl",
        "terminal": "quality_source_terminal_states.jsonl",
    }
    for key, name in mapping.items():
        jsonl(OUT / name, logs[key])


def finalize_failure(logs: dict[str, list[dict[str, Any]]], reason: str,
                     next_stage: str) -> None:
    freeze_logs(logs)
    attempts = len(logs["transport"])
    known_inferences = sum(row["scientific_inference_event"] == 1 for row in logs["transport"])
    ambiguous = sum(row["scientific_inference_event"] is None for row in logs["transport"])
    inferences: int | None = None if ambiguous else known_inferences
    invalid = sum(row["status"] == "QUALITY_RESPONSE_INVALID" for row in logs["schema"])
    valid = sum(row["status"] == "VALID" for row in logs["schema"])
    obj(OUT / "quality_execution_accounting.json", {"planned_groups": 3,
        "requests_attempted": attempts, "scientific_inference_events": inferences,
        "known_scientific_inference_events": known_inferences,
        "ambiguous_execution_events": ambiguous,
        "transport_retries": 0, "valid_responses": valid, "invalid_responses": invalid,
        "builder_calls": 0, "source_topups": 0})
    obj(OUT / "all_quality_outputs_freeze_barrier.json", {"crossed": False,
        "reason": reason, "post_quality_manifests_derived": False})
    obj(OUT / "post_quality_pool_finalization_boundary.json", {
        "duplicate_finalization_executed": False, "final_pool_selected": False,
        "fresh_heldout_sampled": False})
    obj(OUT / "deepseek_flash_execution_audit.json", {"provider": "DeepSeek",
        "model": frozen.MODEL,
        "provider_accepted": True if any(row["http_status"] == 200 for row in logs["transport"])
            else None if ambiguous else False,
        "historical_model_fallback_used": False})
    obj(OUT / "historical_provider_nonmutation_audit.json", {"B2_root_sha256":
        frozen.root(frozen.B2, "search_plan_v24_dev_alpha3_18b2_sha256"),
        "prereg_root_sha256": frozen.root(PREREG, frozen.ROOT_MARKER),
        "historical_assets_modified": False})
    obj(OUT / "builder_nonuse_audit.json", {"builder_calls": 0,
        "historical_builder_v2_inferences": 28, "builder_v3_inferences": 28,
        "cumulative_builder_inferences": 56})
    obj(OUT / "development_nonuse_audit.json", {"development_labels_used": False,
        "known_pmid_checks": False})
    obj(OUT / "search_plan_firewall_audit.json", {"search_plan_state_exposed": False,
        "fresh_heldout_sampling": False, "ncbi_calls": 0})
    obj(OUT / "protocol_compliance_audit.json", {"quality_request_count": 3,
        "inference_limit_respected": known_inferences <= 3, "scientific_retry_used": False,
        "response_identity_exact_set_binding": True, "enum_domain_strict": True,
        "quality_all_pass_rule_used": True, "all_outputs_frozen": False})
    obj(OUT / "scientific_state_safety_audit.json", {"deepseek_calls": attempts,
        "openai_calls": 0, "ncbi_calls": 0, "non_deepseek_network_calls": 0,
        "builder_calls": 0, "source_topups": 0})
    obj(OUT / "validation.json", {"status": "FAIL_CLOSED", "failure_code": reason,
        "quality_requests_attempted": attempts, "quality_scientific_inference_events": inferences,
        "quality_valid_responses": valid, "quality_invalid_responses": invalid,
        "next_stage_recommendation": next_stage})
    obj(OUT / "summary.json", {"status": "failed", "failure_code": reason,
        "quality_requests_attempted": attempts, "quality_scientific_inference_events": inferences,
        "quality_valid_responses": valid, "quality_invalid_responses": invalid,
        "all_quality_outputs_frozen": False,
        "next_stage_recommendation": next_stage})
    marker = frozen.root(OUT, ROOT_MARKER)
    write_raw(OUT / ROOT_MARKER, (marker + "\n").encode("ascii"))
    print(json.dumps({"status": "failed", "failure_code": reason,
        "root_sha256": marker, "next_stage_recommendation": next_stage}, sort_keys=True), flush=True)


def finalize_success(logs: dict[str, list[dict[str, Any]]], requests: list[dict[str, Any]]) -> None:
    frozen.require(len(logs["raw"]) == len(logs["transport"]) == len(logs["identity"]) ==
        len(logs["schema"]) == len(logs["terminal"]) == 3 and
        len(logs["criteria"]) == len(logs["final"]) == 5,
        "QUALITY_OUTPUT_FREEZE_BARRIER_INCOMPLETE")
    freeze_logs(logs)
    obj(OUT / "quality_execution_accounting.json", {"planned_groups": 3,
        "requests_attempted": 3, "scientific_inference_events": 3,
        "transport_retries": 0, "valid_responses": 3, "invalid_responses": 0,
        "builder_calls": 0, "source_topups": 0})
    obj(OUT / "all_quality_outputs_freeze_barrier.json", {"crossed": True,
        "raw_responses_frozen": True, "schema_and_identity_validation_frozen": True,
        "candidate_criterion_states_frozen": True,
        "candidate_final_states_frozen": True,
        "post_quality_manifests_derived_after_barrier": True})
    for state, filename in (
        ("QUALITY_PASS", "quality_pass_candidate_manifest.jsonl"),
        ("QUALITY_FAIL", "quality_fail_candidate_manifest.jsonl"),
        ("QUALITY_UNRESOLVED", "quality_unresolved_candidate_manifest.jsonl")):
        jsonl(OUT / filename, [row for row in logs["final"] if row["quality_state"] == state])
    multiplicity = []
    for item in requests:
        gid = item["source_group_id"]
        count = sum(row["source_group_id"] == gid and row["quality_state"] == "QUALITY_PASS"
            for row in logs["final"])
        multiplicity.append({"order_index": item["order_index"], "source_group_id": gid,
            "private_source_token": item["private_source_token"],
            "quality_pass_candidate_count": count})
    jsonl(OUT / "quality_source_pass_multiplicity.jsonl", multiplicity)
    obj(OUT / "post_quality_pool_finalization_boundary.json", {
        "duplicate_finalization_executed": False, "one_per_source_selector_executed": False,
        "final_pool_selected": False, "fresh_heldout_sampled": False,
        "next_stage": "PREREGISTER_ALPHA3_18D_POOL_FINALIZATION"})
    obj(OUT / "deepseek_flash_execution_audit.json", {"provider": "DeepSeek",
        "model": frozen.MODEL, "provider_accepted": True,
        "historical_model_fallback_used": False,
        "historical_model_output_equivalence_claimed": False})
    obj(OUT / "historical_provider_nonmutation_audit.json", {"B2_root_sha256":
        frozen.root(frozen.B2, "search_plan_v24_dev_alpha3_18b2_sha256"),
        "prereg_root_sha256": frozen.root(PREREG, frozen.ROOT_MARKER),
        "historical_assets_modified": False})
    obj(OUT / "builder_nonuse_audit.json", {"builder_calls": 0,
        "historical_builder_v2_inferences": 28, "builder_v3_inferences": 28,
        "cumulative_builder_inferences": 56})
    obj(OUT / "development_nonuse_audit.json", {"development_labels_used": False,
        "known_pmid_checks": False})
    obj(OUT / "search_plan_firewall_audit.json", {"search_plan_state_exposed": False,
        "fresh_heldout_sampling": False, "ncbi_calls": 0})
    obj(OUT / "protocol_compliance_audit.json", {"alpha3_18c_execution_manifest_verified": True,
        "quality_request_count": 3, "quality_input_candidate_count": 5,
        "quality_execution_order_preserved": True, "scientific_retry_used": False,
        "response_identity_exact_set_binding": True,
        "response_order_semantically_irrelevant": True,
        "enum_domain_strict": True, "quality_all_pass_rule_used": True,
        "all_outputs_frozen": True, "source_topups": 0})
    obj(OUT / "scientific_state_safety_audit.json", {"deepseek_calls": 3,
        "openai_calls": 0, "ncbi_calls": 0, "non_deepseek_network_calls": 0,
        "builder_calls": 0, "source_topups": 0})
    counts = {state: sum(row["quality_state"] == state for row in logs["final"])
        for state in ("QUALITY_PASS", "QUALITY_FAIL", "QUALITY_UNRESOLVED")}
    source_counts = [row["quality_pass_candidate_count"] for row in multiplicity]
    obj(OUT / "validation.json", {"status": "PASS", "quality_requests_attempted": 3,
        "quality_scientific_inference_events": 3, "quality_valid_responses": 3,
        "quality_invalid_responses": 0, "quality_pass_candidate_count": counts["QUALITY_PASS"],
        "quality_fail_candidate_count": counts["QUALITY_FAIL"],
        "quality_unresolved_candidate_count": counts["QUALITY_UNRESOLVED"],
        "quality_sources_with_zero_pass": source_counts.count(0),
        "quality_sources_with_one_pass": source_counts.count(1),
        "quality_sources_with_multiple_pass": sum(count > 1 for count in source_counts)})
    obj(OUT / "summary.json", {"status": "completed", "quality_requests_attempted": 3,
        "quality_scientific_inference_events": 3, "quality_valid_responses": 3,
        "quality_invalid_responses": 0, "quality_pass_candidate_count": counts["QUALITY_PASS"],
        "quality_fail_candidate_count": counts["QUALITY_FAIL"],
        "quality_unresolved_candidate_count": counts["QUALITY_UNRESOLVED"],
        "quality_sources_with_zero_pass": source_counts.count(0),
        "quality_sources_with_one_pass": source_counts.count(1),
        "quality_sources_with_multiple_pass": sum(count > 1 for count in source_counts),
        "all_quality_outputs_frozen": True,
        "next_stage_recommendation": "PREREGISTER_ALPHA3_18D_POOL_FINALIZATION"})
    frozen.require(frozen.root(frozen.B2, "search_plan_v24_dev_alpha3_18b2_sha256") == frozen.B2_SHA and
        frozen.root(PREREG, frozen.ROOT_MARKER) == PREREG_SHA,
        "HISTORICAL_ASSET_MUTATION_DETECTED")
    root_sha = frozen.root(OUT, ROOT_MARKER)
    write_raw(OUT / ROOT_MARKER, (root_sha + "\n").encode("ascii"))
    print(json.dumps({"status": "completed", "root_sha256": root_sha,
        "quality_pass": counts["QUALITY_PASS"], "quality_fail": counts["QUALITY_FAIL"],
        "quality_unresolved": counts["QUALITY_UNRESOLVED"]}, sort_keys=True), flush=True)


def execute() -> None:
    state = preflight()
    secret = historical_transport.key()
    OUT.mkdir()
    obj(OUT / "quality_execution_preflight.json", {"status": "PASS",
        "alpha3_18c_prereg_sha256": PREREG_SHA, "execution_manifest_sha256": MANIFEST_SHA,
        "provider_binding_sha256": BINDING_SHA,
        "manifest_bound_local_artifacts_verified": True,
        "Quality_V2_scientific_protocol_sha256": frozen.QUALITY_SHA,
        "request_count": 3, "candidate_count": 5, "source_group_count": 3})
    obj(OUT / "quality_provider_binding_verification.json", {"provider": "DeepSeek",
        "model": frozen.MODEL, "thinking": {"type": "enabled"},
        "reasoning_effort": "high", "temperature_omitted": True,
        "top_p_omitted": True, "binding_sha256": BINDING_SHA,
        "historical_model_fallback_allowed": False})
    obj(OUT / "quality_request_manifest_verification.json", {"request_manifest_sha256":
        frozen.REQUEST_SHA, "verified_request_count": 3,
        "candidate_count": 5, "original_request_rewrites": 0,
        "projection_only_model_field": True})
    obj(OUT / "quality_execution_order.json", {"order": [
        {key: item[key] for key in ("order_index", "source_group_id", "candidate_ids",
            "frozen_request_sha256", "outbound_request_sha256")}
        for item in state["requests"]]})
    logs: dict[str, list[dict[str, Any]]] = {key: [] for key in
        ("raw", "transport", "identity", "schema", "criteria", "final", "terminal")}
    for item in state["requests"]:
        index, gid = item["order_index"], item["source_group_id"]
        write_raw(OUT / "attempts" / f"{index:02d}.json", frozen.canonical({
            "order_index": index, "source_group_id": gid,
            "candidate_ids": item["candidate_ids"],
            "frozen_request_sha256": item["frozen_request_sha256"],
            "outbound_request_sha256": item["outbound_request_sha256"],
            "provider": "DeepSeek", "model": frozen.MODEL,
            "single_inference_attempt_committed_before_network": True,
            "started_unix_time": time.time()}) + b"\n")
        print(f"QUALITY_CALL_STARTED {index}/3", flush=True)
        try:
            # A new client is constructed for each source-local request.
            with httpx.Client(timeout=httpx.Timeout(connect=20.0, read=900.0,
                write=120.0, pool=20.0)) as client:
                response = client.post(URL, headers={"Authorization": f"Bearer {secret}",
                    "Content-Type": "application/json"},
                    content=frozen.canonical(item["outbound_request"]))
        except Exception as exc:
            transport = {"order_index": index, "source_group_id": gid,
                "candidate_ids": item["candidate_ids"],
                "request_sha256": item["outbound_request_sha256"],
                "provider": "DeepSeek", "model": frozen.MODEL,
                "http_status": None, "transport_exception_type": type(exc).__name__,
                "scientific_inference_event": None, "execution_status": "AMBIGUOUS",
                "retry_count": 0}
            obj(OUT / "transport_events" / f"{index:02d}.json", transport)
            logs["transport"].append(transport)
            terminal = {"order_index": index, "source_group_id": gid,
                "terminal_state": "QUALITY_PROVIDER_EXECUTION_AMBIGUOUS"}
            logs["terminal"].append(terminal)
            obj(OUT / "source_events" / f"{index:02d}.json", {"transport": transport,
                "terminal": terminal})
            finalize_failure(logs, "QUALITY_PROVIDER_EXECUTION_AMBIGUOUS",
                "AUDIT_ALPHA3_18C_RUNTIME_FAILURE_OFFLINE")
            return
        raw_path = OUT / "raw_provider_responses" / f"{index:02d}.json"
        write_raw(raw_path, response.content)
        transport = {"order_index": index, "source_group_id": gid,
            "candidate_ids": item["candidate_ids"],
            "request_sha256": item["outbound_request_sha256"],
            "provider": "DeepSeek", "model": frozen.MODEL,
            "http_status": response.status_code,
            "raw_response_path": str(raw_path.relative_to(OUT)),
            "raw_response_sha256": frozen.sha(response.content),
            "elapsed_seconds": response.elapsed.total_seconds(),
            "scientific_inference_event": 0, "execution_status": "PENDING_CLASSIFICATION",
            "retry_count": 0}
        if model_rejection(response):
            transport.update({"execution_status": "PRE_INFERENCE_MODEL_BINDING_REJECTED"})
            obj(OUT / "transport_events" / f"{index:02d}.json", transport)
            logs["transport"].append(transport)
            logs["raw"].append({"order_index": index, "source_group_id": gid,
                "request_sha256": item["outbound_request_sha256"],
                "raw_response_path": str(raw_path.relative_to(OUT)),
                "raw_response_sha256": frozen.sha(response.content),
                "provider": "DeepSeek", "model": frozen.MODEL})
            terminal = {"order_index": index, "source_group_id": gid,
                "terminal_state": "QUALITY_PROVIDER_BINDING_REJECTED_PRE_INFERENCE"}
            logs["terminal"].append(terminal)
            obj(OUT / "source_events" / f"{index:02d}.json", {"transport": transport,
                "terminal": terminal})
            finalize_failure(logs, "QUALITY_PROVIDER_BINDING_REJECTED_PRE_INFERENCE",
                "AUDIT_ALPHA3_18C_PROVIDER_BINDING_FAILURE_OFFLINE")
            return
        if response.status_code != 200:
            transport.update({"execution_status": "AMBIGUOUS",
                "scientific_inference_event": None})
            obj(OUT / "transport_events" / f"{index:02d}.json", transport)
            logs["transport"].append(transport)
            logs["raw"].append({"order_index": index, "source_group_id": gid,
                "request_sha256": item["outbound_request_sha256"],
                "raw_response_path": str(raw_path.relative_to(OUT)),
                "raw_response_sha256": frozen.sha(response.content),
                "provider": "DeepSeek", "model": frozen.MODEL})
            terminal = {"order_index": index, "source_group_id": gid,
                "terminal_state": "QUALITY_PROVIDER_EXECUTION_AMBIGUOUS"}
            logs["terminal"].append(terminal)
            obj(OUT / "source_events" / f"{index:02d}.json", {"transport": transport,
                "terminal": terminal})
            finalize_failure(logs, "QUALITY_PROVIDER_EXECUTION_AMBIGUOUS",
                "AUDIT_ALPHA3_18C_RUNTIME_FAILURE_OFFLINE")
            return
        try:
            envelope, content, finish = parse_completed(response)
        except (ValueError, KeyError, TypeError, json.JSONDecodeError):
            transport.update({"execution_status": "AMBIGUOUS",
                "scientific_inference_event": None})
            obj(OUT / "transport_events" / f"{index:02d}.json", transport)
            logs["transport"].append(transport)
            logs["raw"].append({"order_index": index, "source_group_id": gid,
                "request_sha256": item["outbound_request_sha256"],
                "raw_response_path": str(raw_path.relative_to(OUT)),
                "raw_response_sha256": frozen.sha(response.content),
                "provider": "DeepSeek", "model": frozen.MODEL})
            terminal = {"order_index": index, "source_group_id": gid,
                "terminal_state": "QUALITY_PROVIDER_EXECUTION_AMBIGUOUS"}
            logs["terminal"].append(terminal)
            obj(OUT / "source_events" / f"{index:02d}.json", {"transport": transport,
                "terminal": terminal})
            finalize_failure(logs, "QUALITY_PROVIDER_EXECUTION_AMBIGUOUS",
                "AUDIT_ALPHA3_18C_RUNTIME_FAILURE_OFFLINE")
            return
        transport.update({"execution_status": "COMPLETED_INFERENCE",
            "scientific_inference_event": 1})
        obj(OUT / "transport_events" / f"{index:02d}.json", transport)
        logs["transport"].append(transport)
        raw_event = {"order_index": index, "source_group_id": gid,
            "candidate_ids": item["candidate_ids"],
            "request_sha256": item["outbound_request_sha256"],
            "provider": "DeepSeek", "model": frozen.MODEL,
            "raw_response_path": str(raw_path.relative_to(OUT)),
            "raw_response_sha256": frozen.sha(response.content),
            "model_content_raw": content, "finish_reason": finish,
            "provider_response_id": envelope.get("id"), "usage": envelope.get("usage")}
        obj(OUT / "raw_events" / f"{index:02d}.json", raw_event)
        logs["raw"].append(raw_event)
        try:
            if finish != "stop":
                raise ValueError("QUALITY_RESPONSE_INCOMPLETE_FINISH:" + finish)
            payload = json.loads(content)
            packets = {packet["candidate_id"]: packet for packet in item["packets"]}
            visible = {cid: packet["evidence"]["exact_evidence_span"] + "\n" +
                packet["evidence"]["bounded_local_context"] for cid, packet in packets.items()}
            records = frozen.quality.validate_response(payload, gid,
                set(item["candidate_ids"]), visible, state["schema"])
        except (ValueError, TypeError, KeyError) as exc:
            identity = {"order_index": index, "source_group_id": gid,
                "status": "INVALID_OR_NOT_REACHED", "expected_candidate_ids": item["candidate_ids"]}
            validation = {"order_index": index, "source_group_id": gid,
                "status": "QUALITY_RESPONSE_INVALID", "reason": str(exc)}
            terminal = {"order_index": index, "source_group_id": gid,
                "terminal_state": "QUALITY_RESPONSE_INVALID"}
            obj(OUT / "source_events" / f"{index:02d}.json", {"raw": raw_event,
                "transport": transport, "identity": identity,
                "validation": validation, "terminal": terminal})
            logs["identity"].append(identity)
            logs["schema"].append(validation)
            logs["terminal"].append(terminal)
            finalize_failure(logs, "QUALITY_RESPONSE_INVALID",
                "AUDIT_ALPHA3_18C_RUNTIME_FAILURE_OFFLINE")
            return
        identity = {"order_index": index, "source_group_id": gid,
            "status": "VALID", "expected_candidate_ids": item["candidate_ids"],
            "returned_candidate_ids": [record["candidate_id"] for record in records],
            "set_equal": True, "array_position_used_as_identity": False}
        validation = {"order_index": index, "source_group_id": gid,
            "status": "VALID", "schema_version": frozen.quality.QUALITY_VERSION,
            "candidate_count": len(records), "enum_domain_strict": True}
        terminal = {"order_index": index, "source_group_id": gid,
            "terminal_state": "QUALITY_RESPONSE_VALID"}
        obj(OUT / "source_events" / f"{index:02d}.json", {"raw": raw_event,
            "transport": transport, "identity": identity,
            "validation": validation, "terminal": terminal})
        logs["identity"].append(identity)
        logs["schema"].append(validation)
        logs["terminal"].append(terminal)
        for record in records:
            cid = record["candidate_id"]
            criteria = {key: record["criteria"][key] for key in frozen.quality.CRITERIA}
            logs["criteria"].append({"order_index": index, "source_group_id": gid,
                "private_source_token": item["private_source_token"],
                "candidate_id": cid, "criteria": criteria,
                "evidence_support_reference": record["evidence_support_reference"]})
            logs["final"].append({"order_index": index, "source_group_id": gid,
                "private_source_token": item["private_source_token"],
                "candidate_id": cid, "quality_state": outcome(criteria),
                "failed_criteria": sorted(k for k, v in criteria.items() if v == "FAIL"),
                "unresolved_criteria": sorted(k for k, v in criteria.items() if v == "UNRESOLVED")})
        print(f"QUALITY_CALL_FROZEN {index}/3 valid_candidates={len(records)}", flush=True)
    finalize_success(logs, state["requests"])


if __name__ == "__main__":
    execute()
