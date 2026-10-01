#!/usr/bin/env python3
"""One-attempt-only runner for the 28 frozen alpha3.18B Builder requests."""
from __future__ import annotations

import hashlib
import json
import os
import time
from pathlib import Path
from typing import Any

import httpx

try:
    from scripts import search_plan_v24_alpha318b_preregister_builder_execution_offline as frozen
    from scripts import search_plan_v24_alpha318b_post_builder_prechecks as checks
except ModuleNotFoundError:
    import search_plan_v24_alpha318b_preregister_builder_execution_offline as frozen
    import search_plan_v24_alpha318b_post_builder_prechecks as checks

ROOT = frozen.ROOT
OUT = ROOT / "runs/20261001_search_plan_v24_dev_alpha3_18b_builder_execution"
ROOT_NAME = "search_plan_v24_dev_alpha3_18b_sha256"
PREREG_SHA = "01a0c81d80d9bffaf59411f45fe7b6880f63a9ed4e3b7c0e61c6e5709b9e3f4b"
MANIFEST_SHA = "58efb5ebc427d28e5677b892d6c395e3e0a52c33c85bc536f662e37ca0715fa6"
URL = "https://api.deepseek.com/v1/chat/completions"

def canonical(value: Any) -> bytes:
    return frozen.a6.base.canonical(value)

def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()

def once(path: Path, raw: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as handle:
        handle.write(raw)

def obj(path: Path, value: Any) -> None:
    once(path, canonical(value) + b"\n")

def lines(path: Path, values: list[dict[str, Any]]) -> None:
    once(path, b"".join(canonical(value) + b"\n" for value in values))

def refs(value: Any) -> list[dict[str, str]]:
    if isinstance(value, list):
        return [ref for item in value for ref in refs(item)]
    if isinstance(value, dict):
        if set(value) == {"path", "sha256"}:
            return [value]
        return [ref for item in value.values() for ref in refs(item)]
    return []

def preflight() -> dict[str, Any]:
    if OUT.exists():
        raise RuntimeError("RUN_ALREADY_EXISTS_NO_REINFERENCE")
    source = frozen.preflight()
    if (frozen.OUT / frozen.ROOT_MARKER).read_text().strip() != PREREG_SHA or (
        frozen.a6.base.prior.all_file_root(frozen.OUT, frozen.ROOT_MARKER) != PREREG_SHA):
        raise RuntimeError("ALPHA3_18B_PREREG_ROOT_MISMATCH")
    path = frozen.OUT / "alpha3_18b_builder_execution_manifest.json"
    if sha(path.read_bytes()) != MANIFEST_SHA or (
        (frozen.OUT / "alpha3_18b_builder_execution_manifest_sha256").read_text().strip() != MANIFEST_SHA):
        raise RuntimeError("ALPHA3_18B_EXECUTION_MANIFEST_MISMATCH")
    manifest = json.loads(path.read_bytes())
    for reference in refs(manifest):
        artifact = ROOT / reference["path"]
        if not artifact.is_file() or artifact.is_symlink() or sha(artifact.read_bytes()) != reference["sha256"]:
            raise RuntimeError("MANIFEST_BOUND_ARTIFACT_MISMATCH:" + reference["path"])
    if manifest["quality_protocol_v2_root_sha256"] != frozen.QUALITY_SHA or (
        manifest["provider_configuration"] != source["provider"]):
        raise RuntimeError("PROVIDER_OR_QUALITY_FROZEN_STATE_MISMATCH")
    if [(row["source_token"], row["request_sha256"]) for row in manifest["execution_order"]] != [
        (row["source_token"], row["request_sha256"]) for row in source["requests"]]:
        raise RuntimeError("FROZEN_EXECUTION_ORDER_MISMATCH")
    return source

def key() -> str:
    value = os.environ.get("DEEPSEEK_API_KEY")
    if value:
        return value
    for line in (ROOT / ".env").read_text(encoding="utf-8").splitlines():
        if line.startswith("DEEPSEEK_API_KEY="):
            value = line.partition("=")[2].strip().strip('"\'')
            if value:
                return value
    raise RuntimeError("DEEPSEEK_CREDENTIAL_UNAVAILABLE")

def fail(code: str, ordinal: int | None, error: Exception | None = None) -> None:
    obj(OUT / "runtime_failure.json", {"status": "FAILED_CLOSED", "failure_code": code,
        "source_ordinal": ordinal, "error_type": type(error).__name__ if error else None,
        "error_message": str(error) if error else None, "retry_permitted": False,
        "quality_calls": 0,
        "next_stage_recommendation": "AUDIT_ALPHA3_18B_RUNTIME_FAILURE_OFFLINE"})

def private_identity(vault: dict[str, Any], jats: dict[str, Any]) -> dict[str, str]:
    path = frozen.a6.V3 / jats[vault["pmcid"]]["canonical_jats_path"]
    if frozen.digest(path) != vault["canonical_jats_sha256"]:
        raise RuntimeError("PRIVATE_JATS_HASH_CHANGED")
    return checks.private_identity_from_jats(path.read_bytes(), vault["pmid"],
                                             vault["pmcid"], vault["doi"])

def _execute() -> None:
    source = preflight()
    secret = key()
    requests, sources = source["requests"], source["sources"]
    vault = {row["source_token"]: row for row in source["vault"]}
    jats = {row["pmcid"]: row for row in frozen.a6.v3.replay.rows(
        frozen.a6.V3 / "pmc_jats_acquisition_results_v3.jsonl")}
    OUT.mkdir()
    obj(OUT / "builder_execution_preflight.json", {"status": "PASS",
        "prereg_sha256": PREREG_SHA, "execution_manifest_sha256": MANIFEST_SHA,
        "manifest_bound_local_artifacts_verified": True,
        "planned_builder_sources": 28, "planned_builder_requests": 28})
    obj(OUT / "builder_request_manifest_verification.json", {
        "source_manifest_sha256": frozen.SOURCE_SHA, "request_manifest_sha256": frozen.REQUEST_SHA,
        "verified_request_count": 28, "builder_request_hash_changes": 0})
    obj(OUT / "builder_call_order.json", {"calls": [
        {"ordinal": i, "source_token": row["source_token"], "request_sha256": row["request_sha256"]}
        for i, row in enumerate(requests, 1)]})
    logs: dict[str, list[dict[str, Any]]] = {name: [] for name in (
        "raw", "transport", "validation", "terminal", "candidate_raw", "identity",
        "grounding", "leakage", "prechecked")}
    groups: list[dict[str, Any]] = []
    for ordinal, (item, source_row) in enumerate(zip(requests, sources), 1):
        token, request = item["source_token"], item["request"]
        if sha(canonical(request)) != item["request_sha256"]:
            fail("BUILDER_REQUEST_FREEZE_MISMATCH", ordinal)
            raise RuntimeError("BUILDER_REQUEST_FREEZE_MISMATCH")
        obj(OUT / "attempts" / f"{ordinal:02d}.json", {
            "ordinal": ordinal, "source_token": token, "request_sha256": item["request_sha256"],
            "provider_configuration": source["provider"], "committed_before_network": True,
            "started_unix_time": time.time()})
        print(f"BUILDER_CALL_STARTED {ordinal}/28", flush=True)
        try:
            with httpx.Client(timeout=httpx.Timeout(connect=20.0, read=900.0,
                                                     write=120.0, pool=20.0)) as client:
                response = client.post(URL, headers={"Authorization": f"Bearer {secret}",
                    "Content-Type": "application/json"}, content=canonical(request))
        except Exception as exc:
            fail("BUILDER_PROVIDER_EXECUTION_AMBIGUOUS", ordinal, exc)
            raise RuntimeError("BUILDER_PROVIDER_EXECUTION_AMBIGUOUS") from exc
        raw_path = OUT / "raw_provider_responses" / f"{ordinal:02d}.json"
        once(raw_path, response.content)
        transport = {"ordinal": ordinal, "source_token": token,
            "request_sha256": item["request_sha256"], "http_status": response.status_code,
            "raw_response_sha256": sha(response.content),
            "raw_response_path": str(raw_path.relative_to(OUT)),
            "elapsed_seconds": response.elapsed.total_seconds(), "retry_count": 0}
        obj(OUT / "transport_events" / f"{ordinal:02d}.json", transport)
        logs["transport"].append(transport)
        if response.status_code != 200:
            fail("BUILDER_PROVIDER_EXECUTION_AMBIGUOUS", ordinal)
            raise RuntimeError("BUILDER_PROVIDER_EXECUTION_AMBIGUOUS:HTTP_" + str(response.status_code))
        try:
            envelope = response.json()
            choices = envelope["choices"]
            if not isinstance(choices, list) or len(choices) != 1:
                raise ValueError("PROVIDER_CHOICES_INVALID")
            content = choices[0]["message"]["content"]
            finish = choices[0]["finish_reason"]
            if not isinstance(content, str) or not isinstance(finish, str):
                raise ValueError("PROVIDER_CONTENT_OR_FINISH_INVALID")
        except Exception as exc:
            fail("BUILDER_PROVIDER_EXECUTION_AMBIGUOUS", ordinal, exc)
            raise RuntimeError("BUILDER_PROVIDER_EXECUTION_AMBIGUOUS:envelope") from exc
        raw = {"ordinal": ordinal, "source_token": token, "request_sha256": item["request_sha256"],
            "provider": source["provider"]["provider"], "model": source["provider"]["model"],
            "raw_response_path": str(raw_path.relative_to(OUT)),
            "raw_response_sha256": sha(response.content), "model_content_raw": content,
            "finish_reason": finish, "provider_response_id": envelope.get("id"),
            "usage": envelope.get("usage")}
        obj(OUT / "raw_events" / f"{ordinal:02d}.json", raw)
        logs["raw"].append(raw)
        try:
            if finish != "stop":
                raise ValueError("BUILDER_RESPONSE_INCOMPLETE_FINISH:" + finish)
            parsed = checks.validate_builder_response(content.encode("utf-8"), token, source["schema"])
        except ValueError as exc:
            validation = {"ordinal": ordinal, "source_token": token,
                "status": "BUILDER_RESPONSE_INVALID", "reason": str(exc)}
            terminal = {"ordinal": ordinal, "source_token": token,
                        "terminal_state": "BUILDER_RESPONSE_INVALID"}
            logs["validation"].append(validation)
            logs["terminal"].append(terminal)
            obj(OUT / "source_events" / f"{ordinal:02d}.json",
                {"raw": raw, "transport": transport, "validation": validation, "terminal": terminal})
            print(f"BUILDER_RESPONSE_INVALID {ordinal}/28", flush=True)
            continue
        validation = {"ordinal": ordinal, "source_token": token,
            "status": "BUILDER_SCHEMA_VALID", "candidate_count": len(parsed["candidates"])}
        terminal = {"ordinal": ordinal, "source_token": token,
            "terminal_state": "BUILDER_VALID_NONZERO" if parsed["candidates"] else "BUILDER_VALID_ZERO"}
        logs["validation"].append(validation)
        logs["terminal"].append(terminal)
        obj(OUT / "source_events" / f"{ordinal:02d}.json",
            {"raw": raw, "transport": transport, "validation": validation, "terminal": terminal})
        for position, candidate in enumerate(parsed["candidates"]):
            logs["candidate_raw"].append({"ordinal": ordinal, "source_token": token,
                "raw_array_position": position, "candidate": candidate})
        document_path = frozen.a6.OUT / source_row["document_path"]
        if frozen.digest(document_path) != source_row["document_sha256"]:
            fail("FROZEN_SOURCE_DOCUMENT_CHANGED", ordinal)
            raise RuntimeError("FROZEN_SOURCE_DOCUMENT_CHANGED")
        document = json.loads(document_path.read_bytes())
        identity = private_identity(vault[token], jats)
        checked = checks.precheck_candidates(parsed, document, identity["title_1"])
        for record in checked["candidate_records_private"]:
            logs["identity"].append({"ordinal": ordinal, "source_token": token, **record})
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
        print(f"BUILDER_CALL_FROZEN {ordinal}/28 state={terminal['terminal_state']} "
              f"raw_candidates={len(parsed['candidates'])}", flush=True)
    finalize(logs, groups)

def finalize(logs: dict[str, list[dict[str, Any]]], groups: list[dict[str, Any]]) -> None:
    if len(logs["terminal"]) != 28 or len(logs["raw"]) != 28 or (
        len(logs["transport"]) != 28):
        fail("ALPHA3_18B_EXECUTION_MANIFEST_INCOMPLETE", None)
        raise RuntimeError("ALPHA3_18B_EXECUTION_MANIFEST_INCOMPLETE")
    names = {
        "raw": "builder_raw_responses.jsonl",
        "transport": "builder_transport_provenance.jsonl",
        "validation": "builder_response_validation.jsonl",
        "terminal": "builder_source_terminal_states.jsonl",
        "candidate_raw": "builder_candidate_raw_manifest.jsonl",
        "identity": "builder_candidate_identity_manifest.jsonl",
        "grounding": "builder_grounding_reference_audit.jsonl",
        "leakage": "builder_leakage_audit.jsonl",
        "prechecked": "builder_prechecked_candidate_manifest.jsonl"}
    for name, filename in names.items():
        lines(OUT / filename, logs[name])
    raw_count = len(logs["candidate_raw"])
    duplicate_count = raw_count - len(logs["identity"])
    grounding_count = sum(row["state"] == "GROUNDING_REFERENCE_FAILED" for row in logs["grounding"])
    leakage_count = sum(row["state"] == "LEXICAL_LEAKAGE_FAILED" for row in logs["leakage"])
    states = [row["terminal_state"] for row in logs["terminal"]]
    zero, nonzero, invalid = (states.count(label) for label in (
        "BUILDER_VALID_ZERO", "BUILDER_VALID_NONZERO", "BUILDER_RESPONSE_INVALID"))
    obj(OUT / "builder_exact_duplicate_audit.json", {
        "raw_candidate_count": raw_count, "unique_candidate_count": len(logs["identity"]),
        "exact_duplicates_removed": duplicate_count, "semantic_near_dedup_used": False})
    obj(OUT / "builder_candidate_summary.json", {
        "raw_candidate_count": raw_count, "schema_valid_candidate_count": raw_count,
        "exact_duplicates_removed": duplicate_count,
        "grounding_reference_failures": grounding_count,
        "lexical_leakage_failures": leakage_count,
        "quality_adjudication_input_candidate_count": len(logs["prechecked"])})
    obj(OUT / "builder_execution_accounting.json", {
        "planned_sources": 28, "requests_attempted": len(logs["raw"]),
        "scientific_inference_events": len(logs["raw"]), "transport_only_retries": 0,
        "builder_valid_zero": zero, "builder_valid_nonzero": nonzero,
        "builder_response_invalid": invalid, "raw_candidate_count": raw_count})
    obj(OUT / "all_builder_outputs_freeze_barrier.json", {
        "crossed": True, "source_terminal_count": 28, "raw_outputs_frozen": True,
        "schema_validation_frozen": True, "candidate_ids_and_exact_dedup_frozen": True,
        "grounding_and_leakage_prechecks_frozen": True, "builder_calls_closed": True})
    print("ALL_BUILDER_OUTPUTS_FROZEN", flush=True)
    quality = frozen.QUALITY_DIR
    schema = json.loads((quality / "proposition_quality_adjudication_v2_schema.json").read_bytes())["schema"]
    appendix = json.loads((quality / "quality_machine_output_contract.json").read_bytes())["appendix_utf8"]
    system = (quality / "quality_adjudicator_system_prompt.txt").read_text()
    template = (quality / "quality_adjudicator_user_prompt_template.txt").read_text()
    quality_rows, group_rows = [], []
    for group in groups:
        payload = checks.build_quality_payload(group["source_token"], group["survivors"],
            group["document"], group["private_identity"])
        request = checks.build_quality_request(payload, schema, system, template, appendix)
        ids = [packet["candidate_id"] for packet in payload["candidate_packets"]]
        group_rows.append({"ordinal": group["ordinal"],
            "private_source_token": group["source_token"],
            "source_group_id": payload["source_group_id"], "candidate_ids": ids,
            "candidate_count": len(ids)})
        quality_rows.append({"ordinal": group["ordinal"], "source_group_id": payload["source_group_id"],
            "candidate_ids": ids, "request": request, "request_sha256": sha(canonical(request))})
    lines(OUT / "quality_source_group_manifest.jsonl", group_rows)
    obj(OUT / "actual_quality_call_budget.json", {
        "actual_quality_adjudication_call_count": len(group_rows),
        "maximum_future_quality_calls": 28, "derived_from_nonempty_source_groups": True})
    obj(OUT / "quality_visibility_preflight_audit.json", {
        "all_quality_payloads_checked_before_manifest_freeze": True,
        "group_count": len(group_rows), "private_identity_match_count": 0,
        "full_article_exposed": False})
    lines(OUT / "proposition_quality_v2_request_manifest.jsonl", quality_rows)
    quality_sha = sha((OUT / "proposition_quality_v2_request_manifest.jsonl").read_bytes())
    once(OUT / "proposition_quality_v2_request_manifest_sha256", (quality_sha + "\n").encode())
    obj(OUT / "quality_manifest_freeze_barrier.json", {
        "crossed": True, "builder_output_barrier_crossed_first": True,
        "quality_request_count": len(quality_rows), "request_manifest_sha256": quality_sha,
        "quality_calls": 0, "separate_authorization_required": True})
    obj(OUT / "anchor_firewall_audit.json", {
        "private_anchor_ids_in_quality_requests": False,
        "private_source_tokens_in_quality_requests": False,
        "private_identity_registry_used_controller_only": True})
    obj(OUT / "development_nonuse_audit.json", {
        "development_cases_or_labels_used": False, "known_pmid_recovery_checks": False,
        "heldout_selection": False})
    obj(OUT / "search_plan_firewall_audit.json", {
        "search_plan_queries_used": False, "search_plan_state_exposed": False, "ncbi_calls": 0})
    obj(OUT / "protocol_compliance_audit.json", {
        "alpha3_18b_execution_manifest_verified": True, "builder_request_hash_changes": 0,
        "source_topup_used": False, "scientific_builder_retry_used": False,
        "schema_invalid_response_reinferred": False, "candidate_cardinality_enforced": True,
        "candidate_identity_deterministic": True, "exact_within_source_dedup_used": True,
        "grounding_reference_precheck_used": True, "leakage_gate_used": True,
        "all_builder_outputs_frozen_before_quality_manifest": True,
        "quality_request_manifest_frozen": True})
    obj(OUT / "scientific_state_safety_audit.json", {
        "deepseek_calls": len(logs["raw"]), "openai_calls": 0, "quality_calls": 0,
        "ncbi_calls": 0, "non_deepseek_network_calls": 0, "source_topup_used": False,
        "historical_assets_modified": False})
    obj(OUT / "validation.json", {
        "status": "PASS", "planned_builder_sources": 28, "planned_builder_requests": 28,
        "builder_requests_attempted": len(logs["raw"]),
        "builder_scientific_inference_events": len(logs["raw"]),
        "builder_valid_zero": zero, "builder_valid_nonzero": nonzero,
        "builder_response_invalid": invalid,
        "actual_quality_adjudication_call_count": len(quality_rows),
        "quality_request_count": len(quality_rows), "quality_calls": 0})
    next_stage = ("INTERPRET_ZERO_QUALITY_INPUT_AFTER_ALPHA3_18B" if not quality_rows else
                  "PREREGISTER_ALPHA3_18C_QUALITY_EXECUTION_AUTHORIZATION")
    obj(OUT / "summary.json", {
        "status": "completed", "builder_requests_attempted": len(logs["raw"]),
        "builder_valid_zero": zero, "builder_valid_nonzero": nonzero,
        "builder_response_invalid": invalid, "builder_raw_candidate_count": raw_count,
        "exact_duplicates_removed": duplicate_count,
        "grounding_reference_failures": grounding_count,
        "lexical_leakage_failures": leakage_count,
        "quality_input_candidate_count": len(logs["prechecked"]),
        "quality_source_group_count": len(group_rows),
        "actual_quality_adjudication_call_count": len(group_rows),
        "proposition_quality_v2_request_manifest_sha256": quality_sha,
        "next_stage_recommendation": next_stage})
    root = frozen.a6.base.prior.all_file_root(OUT, ROOT_NAME)
    once(OUT / ROOT_NAME, (root + "\n").encode())
    print(json.dumps({"status": "completed", "root_sha256": root,
        "quality_request_count": len(quality_rows),
        "quality_request_manifest_sha256": quality_sha,
        "builder_inferences": len(logs["raw"])}, sort_keys=True), flush=True)

def execute() -> None:
    try:
        _execute()
    except Exception as exc:
        if OUT.is_dir():
            if not (OUT / "runtime_failure.json").exists():
                fail("ALPHA3_18B_RUNTIME_FAILURE", None, exc)
            if not (OUT / ROOT_NAME).exists():
                root = frozen.a6.base.prior.all_file_root(OUT, ROOT_NAME)
                once(OUT / ROOT_NAME, (root + "\n").encode())
        raise

if __name__ == "__main__":
    execute()
