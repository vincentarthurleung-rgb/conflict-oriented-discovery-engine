#!/usr/bin/env python3
"""Sequential Pass B batch-3 replacement, then batches 4-8, under frozen V4."""

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
FAILED_313 = ROOT / "runs/20260925_search_plan_v24_dev_alpha3_13_harmonized_deepseek_review"
FAILED_314B = ROOT / "runs/20260925_search_plan_v24_dev_alpha3_14b_harmonized_review_continuation"
AMENDMENT = ROOT / "runs/20260925_search_plan_v24_dev_alpha3_14a_review_identity_binding_amendment_offline"
AUTOPSY = ROOT / "runs/20260925_search_plan_v24_dev_alpha3_14c_pass_b_batch3_schema_failure_autopsy_offline"
CONTRACT = ROOT / "runs/20260926_search_plan_v24_dev_alpha3_14d_pass_b_output_contract_hardening_offline"
RUN = ROOT / "runs/20260926_search_plan_v24_dev_alpha3_14e_harmonized_review_continuation"
ROOTS = {
    "alpha3_14d": "f9d78f0b430c4bd9bc143bc8b094125ad32d83bdfd0e58c51eb07d1f6c1bcb36",
    "pass_b_output_contract_v2": "15b3cea65d65793a060614705ebc3b0c2cf340fd888fda03cef0b1acf6fe8ea9",
    "protocol_v4": "778a07b4a8ee6f171ce7459156b844319867d9dc1c1843f6f7c92429facc6fa1",
    "source_alpha3_13": "5d893ae408fee8d30fefefa56a5b2db14d09a80d31260db44cb143c0057316a8",
    "failed_alpha3_14b": "0d9595e7d1b0a27b14133dc4c79ed9ea911c5564b25a9f716ef78acb3b8ba5e8",
    "autopsy_alpha3_14c": "78095a25aa4c60a0c2eb96ce888a1e7cb4b0132c40d0f7bf9eb0d33a676fc8b1",
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


def write_once(path: Path, body: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as stream:
        stream.write(body)
        stream.flush()
        os.fsync(stream.fileno())


def write_json(path: Path, value: Any) -> None:
    write_once(path, canonical(value) + b"\n")


def inventory(root: Path) -> list[list[Any]]:
    return [[str(path.relative_to(root)), sha(path), path.stat().st_size]
            for path in sorted(root.rglob("*")) if path.is_file()]


def verify_root(root: Path, root_file: str, expected: str) -> None:
    pairs = [[path.name, sha(path)] for path in sorted(root.iterdir()) if path.is_file() and path.name != root_file]
    require(digest(pairs) == expected == (root / root_file).read_text().strip(), f"root drift: {root.name}")


def verify_upstreams() -> dict[str, str]:
    verify_root(CONTRACT, "search_plan_v24_dev_alpha3_14d_sha256", ROOTS["alpha3_14d"])
    require(sha(CONTRACT / "pass_b_output_contract_v2.json") == ROOTS["pass_b_output_contract_v2"] == (CONTRACT / "pass_b_output_contract_v2_sha256").read_text().strip(), "output contract root drift")
    protocol = load(CONTRACT / "harmonized_review_protocol_v4_manifest.json")
    require(digest(protocol["aggregate_components"]) == ROOTS["protocol_v4"] == (CONTRACT / "harmonized_review_protocol_v4_sha256").read_text().strip(), "protocol V4 root drift")
    added = "pass_b_output_contract_v2.json"
    old_added = {"response_identity_binding_v2_contract.json", "canonicalization_by_id_contract.json"}
    require(all(sha((CONTRACT if name == added else AMENDMENT if name in old_added else SOURCE) / name) == checksum
                for name, checksum in protocol["aggregate_components"]), "protocol V4 component drift")
    source_manifest = load(SOURCE / "implementation_manifest.json")
    require(digest(source_manifest["aggregate_components"]) == ROOTS["source_alpha3_13"], "source alpha3.13 root drift")
    verify_root(FAILED_314B, "search_plan_v24_dev_alpha3_14b_sha256", ROOTS["failed_alpha3_14b"])
    verify_root(AUTOPSY, "search_plan_v24_dev_alpha3_14c_sha256", ROOTS["autopsy_alpha3_14c"])
    require(load(AUTOPSY / "batch3_reuse_eligibility.json")["PASS_B_BATCH3_REUSABLE_WITHOUT_REINFERENCE"] is False, "old invalid B3 incorrectly reusable")
    require(load(CONTRACT / "validation.json")["status"] == "PASS", "contract validation failed")
    return ROOTS


def schema_failures(value: Any, schema: dict[str, Any], where: str = "$") -> list[str]:
    errors: list[str] = []
    if "type" in schema:
        kinds = schema["type"] if isinstance(schema["type"], list) else [schema["type"]]
        checks = {"object": lambda x: isinstance(x, dict), "array": lambda x: isinstance(x, list),
                  "string": lambda x: isinstance(x, str), "number": lambda x: isinstance(x, (int, float)) and not isinstance(x, bool),
                  "null": lambda x: x is None, "boolean": lambda x: isinstance(x, bool)}
        if not any(checks[k](value) for k in kinds):
            return [f"{where}:TYPE"]
    if "enum" in schema and value not in schema["enum"]:
        errors.append(f"{where}:ENUM")
    if "const" in schema and value != schema["const"]:
        errors.append(f"{where}:CONST")
    if isinstance(value, dict):
        props = schema.get("properties", {})
        errors.extend(f"{where}.{key}:MISSING_REQUIRED" for key in schema.get("required", []) if key not in value)
        if schema.get("additionalProperties") is False:
            errors.extend(f"{where}.{key}:EXTRA_FIELD" for key in sorted(set(value) - set(props)))
        for key in sorted(set(value) & set(props)):
            errors.extend(schema_failures(value[key], props[key], f"{where}.{key}"))
    elif isinstance(value, list):
        if not schema.get("minItems", 0) <= len(value) <= schema.get("maxItems", float("inf")):
            errors.append(f"{where}:ARRAY_LENGTH")
        for index, item in enumerate(value):
            errors.extend(schema_failures(item, schema.get("items", {}), f"{where}[{index}]"))
    elif isinstance(value, str):
        if len(value) < schema.get("minLength", 0):
            errors.append(f"{where}:MIN_LENGTH")
        if "pattern" in schema and re.search(schema["pattern"], value) is None:
            errors.append(f"{where}:PATTERN")
    elif isinstance(value, (int, float)) and not isinstance(value, bool):
        if not schema.get("minimum", float("-inf")) <= value <= schema.get("maximum", float("inf")):
            errors.append(f"{where}:NUMBER_BOUNDS")
    return errors


def prepare() -> None:
    require(not RUN.exists(), "continuation run exists; never regenerate or replay")
    verify_upstreams()
    old_313 = inventory(FAILED_313)
    old_314b = inventory(FAILED_314B)
    old_autopsy = inventory(AUTOPSY)
    plan = load(SOURCE / "neutral_review_batching_plan.json")
    original_templates = load(SOURCE / "neutral_review_prompt_template.txt")
    schema = load(SOURCE / "neutral_review_output_schema.json")["PASS_B"]
    contract = load(CONTRACT / "pass_b_output_contract_v2.json")
    config = load(SOURCE / "neutral_review_provider_config.json")
    require(config["provider"] == "deepseek" and config["model"] == "deepseek-v4-pro" and config["thinking_mode"] == "enabled" and config["reasoning_effort"] == "high", "model configuration drift")
    require(config["automatic_retry"] is False and config["model_attempts_per_batch"] == 1, "frozen retry policy drift")
    require(plan["planned_model_calls"] == 16 and len(plan["batch_plan"]) == 8, "batch plan drift")
    require(contract["artifact_schema_version"] == "PassBOutputContractV2" and contract["frozen_scientific_output_schema_sha256"] == sha(SOURCE / "neutral_review_output_schema.json"), "output contract schema drift")
    require(contract["scientific_prompt_sha256"] == hashlib.sha256(original_templates["PASS_B"].split("\n\n--- RESPONSE SCHEMA ---\n", 1)[0].encode()).hexdigest(), "scientific prompt drift")
    require(contract["revised_pass_b_prompt_template"].split("\n\n--- RESPONSE SCHEMA ---\n", 1)[0] == original_templates["PASS_B"].split("\n\n--- RESPONSE SCHEMA ---\n", 1)[0], "scientific instruction changed")
    require(contract["revised_pass_b_prompt_template"].count("{batch_json}") == 1 and contract["revised_pass_b_prompt_template"].count("{output_schema_json}") == 1, "revised prompt placeholders drift")
    frozen_313 = load(FAILED_313 / "partial_failure_manifest.json")
    require(frozen_313["provider_calls_started"] == 9 and frozen_313["validated_pass_a_records"] == 71, "historical call accounting drift")
    frozen_314b = load(FAILED_314B / "continuation_partial_failure_manifest.json")
    require(frozen_314b["new_actual_deepseek_calls"] == 2 and frozen_314b["never_inferred_pass_b_batches_after_stop"] == [4, 5, 6, 7, 8], "continued call accounting drift")
    require(not (FAILED_314B / "parsed/pass_b_batch_03.json").exists(), "old invalid B3 unexpectedly validated")
    require([int(path.stem.rsplit("_", 1)[1]) for path in sorted((FAILED_314B / "attempts").glob("*.json"))] == [2, 3], "old B2/B3 attempt set drift")
    rows = [json.loads(line) for line in (SOURCE / "neutral_review_evidence_packets.jsonl").read_text().splitlines()]
    packets = {(row["review_unit_id"], row["pass"]): row["packet"] for row in rows}
    require(len(packets) == 142, "frozen evidence packet collision")
    manifest = []
    request_rows = []
    forbidden = ('"arm_membership"', '"case_id"', '"query_text"', '"query_family"', '"query_provenance"',
                 '"selection_rank"', '"frozen_preacquisition_tier"', '"historical_label"',
                 '"known_paper_status"', 'heldout_v2_', 'ARM_HISTORICAL', 'ARM_LEXICAL')
    for batch in plan["batch_plan"][2:]:
        index, ids = batch["batch_index"], batch["unit_ids"]
        require(index in (3, 4, 5, 6, 7, 8), "unexpected future batch identity")
        require(index == 3 or not (FAILED_314B / "attempts" / f"pass_b_batch_{index:02d}.json").exists(), "supposedly never-inferred batch already attempted")
        selected = [packets[(identifier, "PASS_B")] for identifier in ids]
        require(digest(selected) == batch["pass_b_packet_sha256"], f"evidence packet drift: batch {index}")
        schema_json, batch_json = canonical(schema).decode(), canonical(selected).decode()
        original_prompt = original_templates["PASS_B"].format(output_schema_json=schema_json, batch_json=batch_json)
        old_request = load(FAILED_313 / "requests" / f"pass_b_batch_{index:02d}.json")
        require(old_request["messages"] == [{"role": "user", "content": original_prompt}], f"original prompt/evidence drift: batch {index}")
        new_prompt = contract["revised_pass_b_prompt_template"].format(output_schema_json=schema_json, batch_json=batch_json)
        require(new_prompt != original_prompt, "output appendix missing")
        require(new_prompt.split("\n\n--- RESPONSE SCHEMA ---\n", 1)[0] == original_prompt.split("\n\n--- RESPONSE SCHEMA ---\n", 1)[0], "scientific prompt changed")
        require(new_prompt.split("--- PASS B PACKETS ---\n", 1)[1] == original_prompt.split("--- PASS B PACKETS ---\n", 1)[1], "evidence or batch payload changed")
        require(not [token for token in forbidden if token in new_prompt], f"outgoing blinding leak: batch {index}")
        new_request = {**old_request, "messages": [{"role": "user", "content": new_prompt}]}
        require(set(new_request) == {"model", "thinking", "reasoning_effort", "response_format", "messages"}, "request field drift")
        require(new_request["model"] == "deepseek-v4-pro" and new_request["thinking"] == {"type": "enabled"} and new_request["reasoning_effort"] == "high" and new_request["response_format"] == {"type": "json_object"}, "provider configuration drift")
        manifest.append({"batch_index": index, "batch_id": f"PASS_B_BATCH_{index:02d}", "kind": "REPLACEMENT_INVALID_SUPERSEDED_INFERENCE" if index == 3 else "NEVER_INFERRED", "ordered_review_unit_ids": ids, "evidence_packet_sha256": batch["pass_b_packet_sha256"], "original_request_sha256": digest(old_request), "new_request_sha256": digest(new_request), "scientific_prompt_sha256": contract["scientific_prompt_sha256"], "original_prompt_sha256": hashlib.sha256(original_prompt.encode()).hexdigest(), "revised_prompt_sha256": hashlib.sha256(new_prompt.encode()).hexdigest(), "output_contract_sha256": ROOTS["pass_b_output_contract_v2"], "protocol_v4_sha256": ROOTS["protocol_v4"]})
        request_rows.append({"batch_index": index, "request": new_request})
    require([item["batch_index"] for item in manifest] == [3, 4, 5, 6, 7, 8], "future execution set drift")
    RUN.mkdir(parents=True)
    write_json(RUN / "preflight_roots.json", {"status": "PASS", "roots": ROOTS, "verified_before_provider_access": True})
    write_json(RUN / "historical_preservation_snapshot.json", {"failed_alpha3_13_inventory_sha256": digest(old_313), "failed_alpha3_14b_inventory_sha256": digest(old_314b), "alpha3_14c_inventory_sha256": digest(old_autopsy), "historical_inference_events": 11, "old_invalid_batch3_preserved": True})
    manifest_bytes = b"".join(canonical(row) + b"\n" for row in manifest)
    write_once(RUN / "six_request_manifest.jsonl", manifest_bytes)
    write_once(RUN / "six_request_manifest_sha256", (hashlib.sha256(manifest_bytes).hexdigest() + "\n").encode())
    write_once(RUN / "frozen_requests.jsonl", b"".join(canonical(row) + b"\n" for row in request_rows))
    write_json(RUN / "preflight_freeze.json", {"status": "PASS", "planned_new_calls_maximum": 6, "first_required_batch": 3, "later_batches_blocked_until_replacement_valid": [4, 5, 6, 7, 8], "manifest_sha256": hashlib.sha256(manifest_bytes).hexdigest(), "original_failed_batch3_status": "INVALID_SUPERSEDED_INFERENCE", "reviewer_type": "model_retrieval_adjudicator", "arm_map_accessed": False, "metrics_computed": False})


def key() -> str:
    value = os.environ.get("DEEPSEEK_API_KEY")
    if value:
        return value
    for line in (ROOT / ".env").read_text(encoding="utf-8").splitlines():
        if line.startswith("DEEPSEEK_API_KEY="):
            return line.partition("=")[2].strip().strip('"\'')
    raise RuntimeError("DeepSeek credential unavailable")


def run() -> None:
    verify_upstreams()
    frozen = load(RUN / "preflight_freeze.json")
    manifest_bytes = (RUN / "six_request_manifest.jsonl").read_bytes()
    require(frozen["status"] == "PASS" and frozen["planned_new_calls_maximum"] == 6, "preflight invalid")
    require(hashlib.sha256(manifest_bytes).hexdigest() == frozen["manifest_sha256"] == (RUN / "six_request_manifest_sha256").read_text().strip(), "frozen request manifest drift")
    manifest = [json.loads(line) for line in manifest_bytes.splitlines()]
    requests = [json.loads(line) for line in (RUN / "frozen_requests.jsonl").read_bytes().splitlines()]
    require([row["batch_index"] for row in manifest] == [3, 4, 5, 6, 7, 8], "execution ordering drift")
    schema = load(SOURCE / "neutral_review_output_schema.json")["PASS_B"]
    secret = key()
    for item, request_row in zip(manifest, requests):
        index, body = item["batch_index"], request_row["request"]
        require(index == request_row["batch_index"] and digest(body) == item["new_request_sha256"], "request manifest/request mismatch")
        if index > 3:
            gate = load(RUN / "gate/replacement_batch3_validation.json")
            require(gate["status"] == "VALID" and gate["full_schema_valid"] is True and gate["identity_binding_valid"] is True, "replacement gate closed")
            for earlier in range(4, index):
                require((RUN / "validated" / f"pass_b_batch_{earlier:02d}.json").exists(), "prior never-inferred batch not valid")
        attempt = RUN / "attempts" / f"pass_b_batch_{index:02d}.json"
        require(not attempt.exists(), "batch already attempted; no retry")
        write_json(attempt, {"batch_index": index, "request_sha256": item["new_request_sha256"], "single_attempt_committed_before_network": True, "started_unix_time": time.time()})
        print(f"CALL_STARTED PASS_B batch {index}/8", flush=True)
        try:
            with httpx.Client(timeout=httpx.Timeout(connect=20.0, read=900.0, write=120.0, pool=20.0)) as client:
                response = client.post("https://api.deepseek.com/v1/chat/completions", headers={"Authorization": f"Bearer {secret}", "Content-Type": "application/json"}, json=body)
        except Exception as error:
            write_json(RUN / "failures" / f"pass_b_batch_{index:02d}.json", {"status": "AMBIGUOUS_PROVIDER_EXECUTION", "error_type": type(error).__name__, "message": str(error), "retry_permitted": False})
            raise RuntimeError(f"ambiguous provider execution for batch {index}; no replacement") from error
        raw_path = RUN / "raw_responses" / f"pass_b_batch_{index:02d}.json"
        write_once(raw_path, response.content)
        write_json(RUN / "transport" / f"pass_b_batch_{index:02d}.json", {"batch_index": index, "status_code": response.status_code, "raw_response_sha256": sha(raw_path), "elapsed_seconds": response.elapsed.total_seconds()})
        try:
            require(response.status_code == 200, f"provider HTTP status {response.status_code}")
            envelope = response.json()
            require(isinstance(envelope, dict) and len(envelope.get("choices", [])) == 1, "provider envelope invalid")
            choice = envelope["choices"][0]
            require(choice.get("finish_reason") == "stop", "provider completion unfinished")
            content = choice["message"]["content"]
            require(isinstance(content, str), "provider content not string")
            output = json.loads(content)
            errors = schema_failures(output, schema)
            require(not errors, f"frozen Pass B schema invalid: count={len(errors)} first={errors[0] if errors else None}")
            actual = [record["review_unit_id"] for record in output["records"]]
            expected = item["ordered_review_unit_ids"]
            require(len(actual) == len(expected) and len(set(actual)) == len(actual) and set(actual) == set(expected), "ReviewResponseIdentityBindingV2 invalid")
            by_id = {record["review_unit_id"]: record for record in output["records"]}
            canonical_records = [by_id[identifier] for identifier in expected]
            require(all(canonical(record) == canonical(by_id[identifier]) for identifier, record in zip(actual, output["records"])), "scientific field changed")
            positions = [{"review_unit_id": identifier, "provider_returned_position": actual.index(identifier) + 1, "canonical_request_position": i + 1} for i, identifier in enumerate(expected)]
            write_json(RUN / "validated" / f"pass_b_batch_{index:02d}.json", {"records": canonical_records})
            write_json(RUN / "identity" / f"pass_b_batch_{index:02d}.json", {"batch_index": index, "record_count": len(actual), "id_set_exact": True, "duplicate_id_count": 0, "missing_id_count": 0, "extra_id_count": 0, "provider_order_matches_request_order": actual == expected, "scientific_field_mutation_count": 0, "position_mapping": positions, "raw_response_sha256": sha(raw_path)})
            if index == 3:
                write_json(RUN / "gate/replacement_batch3_validation.json", {"status": "VALID", "full_schema_valid": True, "identity_binding_valid": True, "replacement_inference_event_count": 1, "old_invalid_inference_status": "INVALID_SUPERSEDED_INFERENCE", "old_invalid_inference_reused": False, "scientific_label_comparison_with_old": False, "next_batches_permitted": [4, 5, 6, 7, 8]})
        except Exception as error:
            write_json(RUN / "failures" / f"pass_b_batch_{index:02d}.json", {"status": "FAILED_CLOSED", "error_type": type(error).__name__, "message": str(error), "raw_response_sha256": sha(raw_path), "retry_permitted": False})
            raise
        print(f"CALL_VALIDATED PASS_B batch {index}/8 records={len(actual)} order_match={actual == expected}", flush=True)
    print("SIX_NEW_BATCHES_VALIDATED", flush=True)


if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) == 2 else ""
    try:
        if mode == "prepare":
            prepare()
        elif mode == "run":
            run()
        else:
            raise RuntimeError("usage: prepare|run")
    except Exception as error:
        print(f"FAIL_CLOSED {type(error).__name__}: {error}", file=sys.stderr, flush=True)
        raise SystemExit(1)
