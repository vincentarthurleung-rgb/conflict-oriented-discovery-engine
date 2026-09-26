#!/usr/bin/env python3
"""Seven never-inferred PASS B DeepSeek batches under frozen identity binding V2."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import sys
import time
from typing import Any

import httpx

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "runs/20260925_search_plan_v24_dev_alpha3_13_harmonized_neutral_review_preregistration_offline"
FAILED = ROOT / "runs/20260925_search_plan_v24_dev_alpha3_13_harmonized_deepseek_review"
AMENDMENT = ROOT / "runs/20260925_search_plan_v24_dev_alpha3_14a_review_identity_binding_amendment_offline"
RUN = ROOT / "runs/20260925_search_plan_v24_dev_alpha3_14b_harmonized_review_continuation"
ROOTS = {
    "alpha3_13": "5d893ae408fee8d30fefefa56a5b2db14d09a80d31260db44cb143c0057316a8",
    "corpus": "afcdcd35690a0324426958504de09788ae78bee10a1836a2b526f0e7a82300c7",
    "protocol": "5666288ab612a0f2ed3cd0deb00b7ed77dc6a4270e869e6b8a580605f9721481",
    "alpha3_14a": "41d37150bd568ee7c4c17d49d3531a4e19bac91b9c954983162d5d959c5ddc70",
    "protocol_v2": "a1d975f2e2915e286abdb7202e9741921e65f6055791207d4282aff4c9217727",
    "canonical_lexical": "53073bf83a402437c6428262d9e800c6556f7e8dbd1f9e4af017e3d564716eb7",
}


def require(ok: bool, reason: str) -> None:
    if not ok:
        raise RuntimeError(reason)


def canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


def digest(value: Any) -> str:
    return hashlib.sha256(canonical(value)).hexdigest()


def sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_once(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as stream:
        stream.write(data)
        stream.flush()
        os.fsync(stream.fileno())


def write_json_once(path: Path, value: Any) -> None:
    write_once(path, canonical(value) + b"\n")


def inventory(root: Path) -> list[list[Any]]:
    return [[str(path.relative_to(root)), sha(path), path.stat().st_size]
            for path in sorted(root.rglob("*")) if path.is_file()]


def verify_source() -> None:
    for manifest_name, root_field, expected in (
        ("implementation_manifest.json", "search_plan_v24_dev_alpha3_13_sha256", ROOTS["alpha3_13"]),
        ("harmonized_neutral_review_corpus_manifest.json", "harmonized_neutral_review_corpus_sha256", ROOTS["corpus"]),
        ("harmonized_neutral_review_protocol_manifest.json", "harmonized_neutral_review_protocol_sha256", ROOTS["protocol"]),
    ):
        manifest = load(SOURCE / manifest_name)
        pairs = manifest["aggregate_components"]
        require(all(sha(SOURCE / name) == checksum for name, checksum in pairs), f"frozen source component drift: {manifest_name}")
        require(digest(pairs) == manifest[root_field] == expected, f"frozen source root drift: {manifest_name}")
    require((SOURCE / "canonical_bounded_lexical_realization_v2_scientific_corpus_sha256").read_text().strip() == ROOTS["canonical_lexical"], "lexical scientific corpus root drift")


def verify_amendment() -> None:
    files = sorted(path for path in AMENDMENT.iterdir() if path.is_file() and path.name != "search_plan_v24_dev_alpha3_14a_sha256")
    pairs = [[path.name, sha(path)] for path in files]
    require(digest(pairs) == ROOTS["alpha3_14a"] == (AMENDMENT / "search_plan_v24_dev_alpha3_14a_sha256").read_text().strip(), "alpha3.14a root drift")
    protocol = load(AMENDMENT / "revised_harmonized_review_protocol.json")
    require(protocol["base_protocol_sha256"] == ROOTS["protocol"], "revised protocol base mismatch")
    require(protocol["harmonized_neutral_review_protocol_v2_sha256"] == ROOTS["protocol_v2"], "revised protocol root field drift")
    require(digest(protocol["aggregate_components"]) == ROOTS["protocol_v2"], "revised protocol aggregate drift")
    require((AMENDMENT / "revised_harmonized_review_protocol_sha256").read_text().strip() == ROOTS["protocol_v2"], "revised protocol sidecar drift")
    replacements = set(protocol["replacement_components"])
    require(replacements == {"response_identity_binding_v2_contract.json", "canonicalization_by_id_contract.json"}, "revised protocol replacement mismatch")
    require(all(sha((AMENDMENT if name in replacements else SOURCE) / name) == checksum
                for name, checksum in protocol["aggregate_components"]), "revised protocol component drift")
    require(load(AMENDMENT / "validation.json")["status"] == "PASS", "amendment invalid")


def verify_failed_run() -> list[list[Any]]:
    frozen = load(FAILED / "partial_failure_manifest.json")
    require(frozen["status"] == "FAILED_CLOSED" and frozen["provider_calls_started"] == 9, "historical failed run state mismatch")
    require(frozen["validated_pass_a_records"] == 71 and frozen["validated_pass_b_batches"] == 0, "historical validation count mismatch")
    require(all(sha(FAILED / name) == checksum for name, checksum in frozen["aggregate_components"]), "historical failed run component drift")
    require(digest(frozen["aggregate_components"]) == frozen["partial_failure_sha256"], "historical failure root drift")
    require(load(AMENDMENT / "partial_failure_manifest_verification.json")["historical_partial_failure_sha256"] == frozen["partial_failure_sha256"], "amendment failed-run binding mismatch")
    require(load(AMENDMENT / "pass_a_v2_revalidation.json")["batches_revalidated"] == 8, "PASS A V2 revalidation missing")
    require(load(AMENDMENT / "pass_b_batch1_v2_revalidation.json")["reusable_without_reinference"] is True, "PASS B1 not reusable")
    require(not (FAILED / "blinded_adjudication_freeze_manifest.json").exists(), "historical failed run was modified")
    return inventory(FAILED)


def check_schema(value: Any, schema: dict[str, Any], where: str = "$") -> None:
    if "type" in schema:
        kinds = schema["type"] if isinstance(schema["type"], list) else [schema["type"]]
        checks = {"object": lambda x: isinstance(x, dict), "array": lambda x: isinstance(x, list),
                  "string": lambda x: isinstance(x, str), "number": lambda x: isinstance(x, (int, float)) and not isinstance(x, bool),
                  "null": lambda x: x is None, "boolean": lambda x: isinstance(x, bool)}
        require(any(checks[k](value) for k in kinds), f"schema type at {where}")
    if "enum" in schema:
        require(value in schema["enum"], f"schema enum at {where}")
    if "const" in schema:
        require(value == schema["const"], f"schema const at {where}")
    if isinstance(value, dict):
        props = schema.get("properties", {})
        require(set(schema.get("required", [])) <= set(value), f"schema required at {where}")
        if schema.get("additionalProperties") is False:
            require(set(value) <= set(props), f"schema extra fields at {where}")
        for key, item in value.items():
            if key in props:
                check_schema(item, props[key], f"{where}.{key}")
    elif isinstance(value, list):
        require(schema.get("minItems", 0) <= len(value) <= schema.get("maxItems", float("inf")), f"schema array size at {where}")
        for index, item in enumerate(value):
            check_schema(item, schema.get("items", {}), f"{where}[{index}]")
    elif isinstance(value, str):
        require(len(value) >= schema.get("minLength", 0), f"schema minLength at {where}")
        if "pattern" in schema:
            require(re.search(schema["pattern"], value) is not None, f"schema pattern at {where}")
    elif isinstance(value, (int, float)) and not isinstance(value, bool):
        require(schema.get("minimum", float("-inf")) <= value <= schema.get("maximum", float("inf")), f"schema bounds at {where}")


def request_path(index: int) -> Path:
    return FAILED / "requests" / f"pass_b_batch_{index:02d}.json"


def prepare() -> None:
    require(not RUN.exists(), "continuation run already exists; never regenerate or replay")
    verify_source()
    verify_amendment()
    before = verify_failed_run()
    plan = load(SOURCE / "neutral_review_batching_plan.json")
    config = load(SOURCE / "neutral_review_provider_config.json")
    schema = load(SOURCE / "neutral_review_output_schema.json")["PASS_B"]
    request_schema = load(SOURCE / "neutral_review_request_schema.json")
    require(plan["planned_model_calls"] == 16 and plan["batches_per_pass"] == 8, "original plan drift")
    require(config["provider"] == "deepseek" and config["model"] == "deepseek-v4-pro" and config["thinking_mode"] == "enabled" and config["reasoning_effort"] == "high", "provider configuration drift")
    require(config["automatic_retry"] is False and config["model_attempts_per_batch"] == 1, "retry policy drift")
    require(request_schema["model"] == config["model"] and request_schema["thinking"] == {"type": "enabled"}, "request schema drift")
    inferred = {int(path.stem.rsplit("_", 1)[1]) for path in (FAILED / "attempts").glob("pass_b_batch_*.json")}
    require(inferred == {1}, "historical PASS B attempt set drift")
    remaining = [batch for batch in plan["batch_plan"] if batch["batch_index"] not in inferred]
    require(len(remaining) == 7 and [b["batch_index"] for b in remaining] == list(range(2, 9)), "remaining set not exactly seven")
    for batch in remaining:
        index = batch["batch_index"]
        require(not (FAILED / "raw_responses" / f"pass_b_batch_{index:02d}.json").exists(), "supposedly never-inferred response exists")
    RUN.mkdir(parents=True)
    write_json_once(RUN / "upstream_root_verification.json", {"status": "PASS", "roots": ROOTS, "verified_before_provider_access": True})
    write_json_once(RUN / "revised_protocol_verification.json", {"status": "PASS", "alpha3_14a_sha256": ROOTS["alpha3_14a"], "revised_protocol_v2_sha256": ROOTS["protocol_v2"], "component_hashes_verified": True})
    write_json_once(RUN / "historical_9_call_preservation_audit.json", {"historical_failed_run_inventory_sha256": digest(before), "historical_file_count": len(before), "historical_deepseek_calls_preserved": 9, "historical_failure_preserved": True, "original_run_modified": False})
    write_json_once(RUN / "completed_pass_a_reuse_audit.json", {"completed_batches": 8, "completed_units": 71, "reinference_calls": 0, "scientific_output_modifications": 0, "canonical_source": str(AMENDMENT.relative_to(ROOT)), "validated_by_alpha3_14a": True})
    write_json_once(RUN / "pass_b_batch1_reuse_audit.json", {"completed_batches": 1, "completed_units": 10, "reinference_calls": 0, "identity_set_exact": True, "missing_ids": 0, "extra_ids": 0, "duplicate_ids": 0, "scientific_field_mutation_count": 0, "canonical_source": "canonical_pass_b_batch_01_blinded.jsonl", "raw_response_sha256": sha(FAILED / "raw_responses/pass_b_batch_01.json")})
    write_json_once(RUN / "remaining_pass_b_derivation.json", {"derivation": "frozen original batch plan minus frozen original PASS B attempt records", "historically_inferred_batch_indices": sorted(inferred), "never_inferred_batch_indices": [b["batch_index"] for b in remaining], "remaining_pass_b_batch_count": 7, "manual_selection": False})
    blocked = ('"arm_membership"', '"case_id"', '"query_text"', '"query_family"', '"query_provenance"',
               '"selection_rank"', '"frozen_preacquisition_tier"', '"historical_label"', '"known_paper_status"',
               'heldout_v2_', 'ARM_HISTORICAL', 'ARM_LEXICAL', 'alpha3.')
    manifest_rows = []
    requests = []
    blinding = []
    for batch in remaining:
        index = batch["batch_index"]
        original = request_path(index)
        body = load(original)
        require(set(body) == {"model", "thinking", "reasoning_effort", "response_format", "messages"}, "outbound request field drift")
        require(body["model"] == "deepseek-v4-pro" and body["thinking"] == {"type": "enabled"} and body["reasoning_effort"] == "high" and body["response_format"] == {"type": "json_object"}, "outbound provider settings drift")
        require(len(body["messages"]) == 1 and body["messages"][0]["role"] == "user", "outbound session not isolated")
        prompt = body["messages"][0]["content"]
        found = [marker for marker in blocked if marker in prompt]
        require(not found, f"blinding leak in batch {index}: {found}")
        # The frozen original request is reused byte-for-byte as provider payload.
        require(sha(original) == hashlib.sha256(canonical(body) + b"\n").hexdigest(), "original request bytes not canonical")
        batch_row = {"batch_id": f"PASS_B_BATCH_{index:02d}", "batch_index": index,
                     "ordered_review_unit_ids": batch["unit_ids"],
                     "evidence_packet_sha256": batch["pass_b_packet_sha256"],
                     "prompt_sha256": hashlib.sha256(prompt.encode("utf-8")).hexdigest(),
                     "request_sha256": digest(body), "original_request_file_sha256": sha(original),
                     "request_schema_sha256": sha(SOURCE / "neutral_review_request_schema.json"),
                     "output_schema_sha256": sha(SOURCE / "neutral_review_output_schema.json"),
                     "pass_b_output_schema_sha256": digest(schema),
                     "provider_configuration_sha256": sha(SOURCE / "neutral_review_provider_config.json"),
                     "revised_identity_binding_protocol_sha256": ROOTS["protocol_v2"]}
        manifest_rows.append(batch_row)
        requests.append({"batch_id": batch_row["batch_id"], "request": body, "request_sha256": digest(body)})
        blinding.append({"batch_id": batch_row["batch_id"], "forbidden_markers_present": [], "single_batch_only": True, "pass_a_output_present": False, "provider_payload_sha256": digest(body)})
    manifest_body = b"".join(canonical(row) + b"\n" for row in manifest_rows)
    write_once(RUN / "remaining_pass_b_request_manifest.jsonl", manifest_body)
    manifest_hash = hashlib.sha256(manifest_body).hexdigest()
    write_once(RUN / "remaining_pass_b_request_manifest_sha256", (manifest_hash + "\n").encode())
    write_once(RUN / "pass_b_continuation_requests.jsonl", b"".join(canonical(row) + b"\n" for row in requests))
    write_json_once(RUN / "reviewer_blinding_preflight_audit.json", {"status": "PASS", "outgoing_payloads_checked": 7, "checks": blinding, "model_blind_to_arm_architecture_case_query_tier_rank_history_known_paper": True})
    write_json_once(RUN / "arm_firewall_preflight_audit.json", {"arm_map_accessed_before_blinded_freeze": False, "hidden_arm_map_semantically_loaded": False, "hash_only_source_integrity_verification_allowed": True, "identity_join_before_blinded_freeze": False})
    write_json_once(RUN / "preflight_freeze.json", {"status": "PASS", "manifest_sha256": manifest_hash, "request_count": 7, "historical_inventory_sha256": digest(before), "upstream_roots": ROOTS, "frozen_before_provider_access": True})


def key() -> str:
    value = os.environ.get("DEEPSEEK_API_KEY")
    if value:
        return value
    for line in (ROOT / ".env").read_text(encoding="utf-8").splitlines():
        if line.startswith("DEEPSEEK_API_KEY="):
            return line.partition("=")[2].strip().strip('"\'')
    raise RuntimeError("DeepSeek credential unavailable")


def run() -> None:
    verify_source()
    verify_amendment()
    before = verify_failed_run()
    preflight = load(RUN / "preflight_freeze.json")
    manifest_body = (RUN / "remaining_pass_b_request_manifest.jsonl").read_bytes()
    require(preflight["status"] == "PASS" and preflight["request_count"] == 7, "preflight incomplete")
    require(hashlib.sha256(manifest_body).hexdigest() == preflight["manifest_sha256"] == (RUN / "remaining_pass_b_request_manifest_sha256").read_text().strip(), "request manifest drift")
    require(digest(before) == preflight["historical_inventory_sha256"], "historical failed run changed")
    rows = [json.loads(line) for line in manifest_body.splitlines()]
    require([row["batch_index"] for row in rows] == list(range(2, 9)), "call list not frozen seven")
    request_rows = [json.loads(line) for line in (RUN / "pass_b_continuation_requests.jsonl").read_bytes().splitlines()]
    schema = load(SOURCE / "neutral_review_output_schema.json")["PASS_B"]
    secret = key()
    for item, request_row in zip(rows, request_rows):
        index = item["batch_index"]
        body = request_row["request"]
        require(request_row["batch_id"] == item["batch_id"] and digest(body) == item["request_sha256"], "frozen request drift")
        require(sha(request_path(index)) == item["original_request_file_sha256"], "original request file drift")
        attempt_path = RUN / "attempts" / f"pass_b_batch_{index:02d}.json"
        require(not attempt_path.exists(), "attempt already started; no replay")
        write_json_once(attempt_path, {"batch_id": item["batch_id"], "request_sha256": item["request_sha256"], "single_attempt_committed_before_network": True, "started_unix_time": time.time()})
        print(f"CALL_STARTED PASS_B batch {index}/8", flush=True)
        try:
            with httpx.Client(timeout=httpx.Timeout(connect=20.0, read=900.0, write=120.0, pool=20.0)) as client:
                response = client.post("https://api.deepseek.com/v1/chat/completions", headers={"Authorization": f"Bearer {secret}", "Content-Type": "application/json"}, json=body)
        except Exception as error:
            write_json_once(RUN / "failures" / f"pass_b_batch_{index:02d}.json", {"status": "AMBIGUOUS_PROVIDER_EXECUTION", "error_type": type(error).__name__, "message": str(error), "retry_permitted": False})
            raise RuntimeError(f"ambiguous provider execution for PASS B batch {index}; no replacement request") from error
        raw_path = RUN / "raw_responses" / f"pass_b_batch_{index:02d}.json"
        write_once(raw_path, response.content)
        write_json_once(RUN / "transport" / f"pass_b_batch_{index:02d}.json", {"batch_id": item["batch_id"], "status_code": response.status_code, "raw_response_sha256": sha(raw_path), "elapsed_seconds": response.elapsed.total_seconds()})
        try:
            require(response.status_code == 200, f"provider HTTP status {response.status_code}")
            envelope = response.json()
            require(isinstance(envelope, dict) and len(envelope.get("choices", [])) == 1, "provider envelope invalid")
            choice = envelope["choices"][0]
            require(choice.get("finish_reason") == "stop", "provider completion not finished")
            content = choice["message"]["content"]
            require(isinstance(content, str), "provider content not a string")
            output = json.loads(content)
            check_schema(output, schema)
            returned = [record["review_unit_id"] for record in output["records"]]
            expected = item["ordered_review_unit_ids"]
            require(len(returned) == len(expected) and len(set(returned)) == len(returned)
                    and set(returned) == set(expected), "ReviewResponseIdentityBindingV2 invalid")
            by_id = {record["review_unit_id"]: record for record in output["records"]}
            canonical_records = [by_id[identifier] for identifier in expected]
            require(all(canonical(before_record) == canonical(by_id[identifier]) for before_record, identifier in zip(output["records"], returned)), "scientific field mutation")
            positions = [{"review_unit_id": identifier, "provider_returned_position": returned.index(identifier) + 1, "canonical_request_position": i + 1} for i, identifier in enumerate(expected)]
            write_json_once(RUN / "parsed" / f"pass_b_batch_{index:02d}.json", {"records": canonical_records})
            write_json_once(RUN / "identity" / f"pass_b_batch_{index:02d}.json", {"batch_id": item["batch_id"], "returned_record_count": len(returned), "expected_id_count": len(expected), "unique_returned_id_count": len(set(returned)), "missing_id_count": 0, "extra_id_count": 0, "duplicate_id_count": 0, "id_set_equality": True, "provider_returned_order_matches_request_order": returned == expected, "identity_binding": "VALID", "scientific_field_mutation_count": 0, "position_mapping": positions, "raw_response_sha256": sha(raw_path)})
        except Exception as error:
            write_json_once(RUN / "failures" / f"pass_b_batch_{index:02d}.json", {"status": "FAILED_CLOSED", "error_type": type(error).__name__, "message": str(error), "raw_response_sha256": sha(raw_path), "retry_permitted": False})
            raise
        print(f"CALL_VALIDATED PASS_B batch {index}/8 records={len(returned)} order_match={returned == expected}", flush=True)
    require(inventory(FAILED) == before, "historical failed run changed during continuation")
    print("SEVEN_NEW_BATCHES_VALIDATED", flush=True)


def seal_failure() -> None:
    """Freeze this partial continuation; do not retry or inspect label values."""
    verify_source()
    verify_amendment()
    before = verify_failed_run()
    require(not (RUN / "continuation_partial_failure_manifest.json").exists(), "partial failure already sealed")
    require(not (RUN / "harmonized_deepseek_blinded_adjudication_corpus_sha256").exists(), "complete blinded freeze unexpectedly exists")
    attempts = sorted((RUN / "attempts").glob("pass_b_batch_*.json"))
    require([path.name for path in attempts] == ["pass_b_batch_02.json", "pass_b_batch_03.json"], "unexpected provider attempt set")
    parsed = sorted((RUN / "parsed").glob("pass_b_batch_*.json"))
    require([path.name for path in parsed] == ["pass_b_batch_02.json"], "unexpected validated response set")
    failures = sorted((RUN / "failures").glob("*.json"))
    require([path.name for path in failures] == ["pass_b_batch_03.json"], "unexpected failure set")
    failure = load(failures[0])
    require(failure["status"] == "FAILED_CLOSED" and failure["message"] == "schema enum at $.records[1].relevance_state", "unexpected failure classification")
    require(failure["raw_response_sha256"] == sha(RUN / "raw_responses/pass_b_batch_03.json"), "failed raw response drift")
    require(all(not (RUN / "attempts" / f"pass_b_batch_{index:02d}.json").exists() for index in range(4, 9)), "subsequent call occurred")
    require(inventory(FAILED) == before, "historical failed run changed")
    paths = [path for path in sorted(RUN.rglob("*")) if path.is_file()]
    pairs = [[str(path.relative_to(RUN)), sha(path)] for path in paths]
    root = digest(pairs)
    write_json_once(RUN / "continuation_partial_failure_manifest.json", {
        "status": "FAILED_CLOSED", "failure_reason": "PASS_B_BATCH_03_SCIENTIFIC_OUTPUT_SCHEMA_ENUM_INVALID",
        "failure_field_path": "$.records[1].relevance_state", "invalid_scientific_value_not_inspected_or_repaired": True,
        "historical_deepseek_calls_preserved": 9, "new_authorized_deepseek_calls": 7,
        "new_actual_deepseek_calls": 2, "total_unique_inferred_batches": 11,
        "pass_a_completed_batches": 8, "pass_a_completed_units": 71,
        "pass_b_completed_batches": 2, "pass_b_completed_units": 20,
        "new_validated_pass_b_batches": [2], "new_failed_pass_b_batch": 3,
        "never_inferred_pass_b_batches_after_stop": [4, 5, 6, 7, 8],
        "pass_a_reinference_calls": 0, "pass_b_batch1_reinference_calls": 0,
        "ambiguous_provider_execution_count": 0,
        "unplanned_scientific_adjudication_calls": 0,
        "blinded_adjudication_freeze_complete": False,
        "arm_map_accessed_before_blinded_freeze": False,
        "metrics_computed": False, "retry_or_repair_calls": 0,
        "historical_assets_modified": False,
        "aggregate_components": pairs, "partial_continuation_sha256": root})
    write_json_once(RUN / "validation.json", {"status": "FAILED_CLOSED", "failure": "PASS_B_BATCH_03_SCIENTIFIC_OUTPUT_SCHEMA_ENUM_INVALID", "new_actual_deepseek_calls": 2, "blinded_adjudication_freeze_complete": False, "arm_map_accessed_before_blinded_freeze": False, "metrics_computed": False})
    write_json_once(RUN / "summary.json", {"status": "failed", "reason": "PASS_B_BATCH_03_SCIENTIFIC_OUTPUT_SCHEMA_ENUM_INVALID", "historical_deepseek_calls_preserved": 9, "new_actual_deepseek_calls": 2, "total_unique_inferred_batches": 11, "pass_a_completed_batches": 8, "pass_b_completed_batches": 2, "pass_a_completed_units": 71, "pass_b_completed_units": 20, "remaining_never_inferred_pass_b_batches": 5, "blinded_adjudication_freeze_complete": False, "arm_map_accessed_before_blinded_freeze": False, "metrics_computed": False, "next_stage_recommendation": "AWAIT_USER_DIRECTION_AFTER_FAIL_CLOSED_SCHEMA_FAILURE"})
    final_names = sorted(path for path in RUN.iterdir() if path.is_file() and path.name != "search_plan_v24_dev_alpha3_14b_sha256")
    final_pairs = [[path.name, sha(path)] for path in final_names]
    write_once(RUN / "search_plan_v24_dev_alpha3_14b_sha256", (digest(final_pairs) + "\n").encode())
    print(f"PARTIAL_FAILURE_SEALED {digest(final_pairs)}", flush=True)


if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) == 2 else ""
    try:
        if mode == "prepare":
            prepare()
        elif mode == "run":
            run()
        elif mode == "seal-failure":
            seal_failure()
        else:
            raise RuntimeError("usage: prepare|run|seal-failure")
    except Exception as error:
        print(f"FAIL_CLOSED {type(error).__name__}: {error}", file=sys.stderr, flush=True)
        raise SystemExit(1)
