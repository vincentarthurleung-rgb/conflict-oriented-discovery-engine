#!/usr/bin/env python3
"""Execute only the frozen alpha3.13 arm-blinded DeepSeek review batches."""

from __future__ import annotations

import argparse
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
RUN = ROOT / "runs/20260925_search_plan_v24_dev_alpha3_13_harmonized_deepseek_review"
ROOTS = {
    "search_plan_v24_dev_alpha3_13": "5d893ae408fee8d30fefefa56a5b2db14d09a80d31260db44cb143c0057316a8",
    "harmonized_neutral_review_corpus": "afcdcd35690a0324426958504de09788ae78bee10a1836a2b526f0e7a82300c7",
    "harmonized_neutral_review_protocol": "5666288ab612a0f2ed3cd0deb00b7ed77dc6a4270e869e6b8a580605f9721481",
    "canonical_bounded_lexical_realization_v2_scientific_corpus": "53073bf83a402437c6428262d9e800c6556f7e8dbd1f9e4af017e3d564716eb7",
}


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


def digest(value: Any) -> str:
    return hashlib.sha256(canonical(value)).hexdigest()


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(name: str) -> Any:
    return json.loads((SOURCE / name).read_text(encoding="utf-8"))


def write_once(path: Path, body: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as stream:
        stream.write(body)
        stream.flush()
        os.fsync(stream.fileno())


def write_json_once(path: Path, value: Any) -> None:
    write_once(path, canonical(value) + b"\n")


def verify_aggregate(manifest_name: str, root_key: str) -> None:
    expected = ROOTS[root_key]
    manifest = read(manifest_name)
    pairs = manifest["aggregate_components"]
    require(all(sha(SOURCE / name) == checksum for name, checksum in pairs), f"component drift: {manifest_name}")
    require(digest(pairs) == expected, f"aggregate drift: {manifest_name}")
    require(manifest[root_key + "_sha256"] == expected, f"manifest root mismatch: {manifest_name}")
    require((SOURCE / (root_key + "_sha256")).read_text().strip() == expected, f"root file mismatch: {root_key}")


def verify_frozen_sources() -> None:
    verify_aggregate("harmonized_neutral_review_corpus_manifest.json", "harmonized_neutral_review_corpus")
    verify_aggregate("harmonized_neutral_review_protocol_manifest.json", "harmonized_neutral_review_protocol")
    verify_aggregate("implementation_manifest.json", "search_plan_v24_dev_alpha3_13")
    require((SOURCE / "canonical_bounded_lexical_realization_v2_scientific_corpus_sha256").read_text().strip() == ROOTS["canonical_bounded_lexical_realization_v2_scientific_corpus"], "canonical lexical corpus root drift")
    require(read("validation.json")["status"] == "PASS", "frozen preregistration invalid")


def check_schema(value: Any, schema: dict[str, Any], location: str = "$" ) -> None:
    if "type" in schema:
        kinds = schema["type"] if isinstance(schema["type"], list) else [schema["type"]]
        matches = {"object": lambda x: isinstance(x, dict), "array": lambda x: isinstance(x, list),
                   "string": lambda x: isinstance(x, str), "number": lambda x: isinstance(x, (int, float)) and not isinstance(x, bool),
                   "null": lambda x: x is None, "boolean": lambda x: isinstance(x, bool)}
        require(any(matches[kind](value) for kind in kinds), f"schema type at {location}")
    if "enum" in schema:
        require(value in schema["enum"], f"schema enum at {location}")
    if "const" in schema:
        require(value == schema["const"], f"schema const at {location}")
    if isinstance(value, dict):
        props = schema.get("properties", {})
        require(set(schema.get("required", [])) <= set(value), f"schema required at {location}")
        if schema.get("additionalProperties") is False:
            require(set(value) <= set(props), f"schema extra fields at {location}")
        for key, item in value.items():
            if key in props:
                check_schema(item, props[key], f"{location}.{key}")
    elif isinstance(value, list):
        require(len(value) >= schema.get("minItems", 0) and len(value) <= schema.get("maxItems", float("inf")), f"schema array size at {location}")
        for index, item in enumerate(value):
            check_schema(item, schema.get("items", {}), f"{location}[{index}]")
    elif isinstance(value, str):
        require(len(value) >= schema.get("minLength", 0), f"schema minLength at {location}")
        if "pattern" in schema:
            require(re.search(schema["pattern"], value) is not None, f"schema pattern at {location}")
    elif isinstance(value, (int, float)) and not isinstance(value, bool):
        require(value >= schema.get("minimum", float("-inf")) and value <= schema.get("maximum", float("inf")), f"schema number bounds at {location}")


def request_path(pass_name: str, index: int) -> Path:
    return RUN / "requests" / f"{pass_name.lower()}_batch_{index:02d}.json"


def response_path(pass_name: str, index: int) -> Path:
    return RUN / "raw_responses" / f"{pass_name.lower()}_batch_{index:02d}.json"


def validated_path(pass_name: str, index: int) -> Path:
    return RUN / "validated" / f"{pass_name.lower()}_batch_{index:02d}.json"


def prepare() -> None:
    verify_frozen_sources()
    require(not RUN.exists(), "execution directory already exists; never regenerate or rerun")
    config = read("neutral_review_provider_config.json")
    require(config["model"] == "deepseek-v4-pro" and config["thinking_mode"] == "enabled" and config["reasoning_effort"] == "high", "provider configuration drift")
    require(config["automatic_retry"] is False and config["model_attempts_per_batch"] == 1, "retry policy drift")
    request_schema = read("neutral_review_request_schema.json")
    require(request_schema["model"] == config["model"] and request_schema["thinking"] == {"type": "enabled"}, "request schema drift")
    plan = read("neutral_review_batching_plan.json")
    require(plan["planned_model_calls"] == 16 and plan["batches_per_pass"] == 8 and plan["unit_count"] == 71, "batch plan drift")
    require([b["unit_count"] for b in plan["batch_plan"]] == [10] * 7 + [1], "batch sizes drift")
    templates = read("neutral_review_prompt_template.txt")
    schemas = read("neutral_review_output_schema.json")
    rows = [json.loads(line) for line in (SOURCE / "neutral_review_evidence_packets.jsonl").read_text(encoding="utf-8").splitlines()]
    require(len(rows) == 142, "packet count drift")
    packets = {(row["review_unit_id"], row["pass"]): row["packet"] for row in rows}
    require(len(packets) == 142, "packet key collision")
    expected_ids = [identifier for batch in plan["batch_plan"] for identifier in batch["unit_ids"]]
    require(len(expected_ids) == len(set(expected_ids)) == 71, "review unit count drift")
    require(set(packets) == {(identifier, pass_name) for identifier in expected_ids for pass_name in ("PASS_A", "PASS_B")}, "packet membership drift")
    require(digest(expected_ids) == plan["mixed_order_sha256"], "mixed review order drift")
    require(read("neutral_review_order.json")["ordered_review_unit_ids"] == expected_ids, "order file drift")
    manifest = []
    for pass_name in ("PASS_A", "PASS_B"):
        for batch in plan["batch_plan"]:
            index, ids = batch["batch_index"], batch["unit_ids"]
            selected = [packets[(identifier, pass_name)] for identifier in ids]
            require(digest(selected) == batch[f"{pass_name.lower()}_packet_sha256"], f"frozen packet hash mismatch: {pass_name}/{index}")
            require(all(packet["review_unit_id"] == identifier for packet, identifier in zip(selected, ids)), "packet order mismatch")
            schema = schemas[pass_name]
            prompt = templates[pass_name].format(output_schema_json=canonical(schema).decode(), batch_json=canonical(selected).decode())
            body = {"model": "deepseek-v4-pro", "thinking": {"type": "enabled"}, "reasoning_effort": "high", "response_format": {"type": "json_object"}, "messages": [{"role": "user", "content": prompt}]}
            require(set(body) == {"model", "thinking", "reasoning_effort", "response_format", "messages"}, "request field mismatch")
            require(len(body["messages"]) == 1 and body["messages"][0]["role"] == "user", "session isolation mismatch")
            require(all(forbidden not in prompt for forbidden in ('"arm_membership"', '"case_id"', '"query_text"', '"selection_rank"', '"frozen_preacquisition_tier"', '"historical_label"')), "request blinding violation")
            manifest.append({"pass": pass_name, "batch_index": index, "unit_count": len(ids), "request_sha256": digest(body), "packet_sha256": digest(selected)})
            # Requests are fully rendered and frozen before any provider call.
            write_json_once(request_path(pass_name, index), body)
    write_json_once(RUN / "preflight_manifest.json", {"status": "PASS", "upstream_roots": ROOTS, "frozen_requests": manifest, "planned_provider_calls": 16, "authorization_scope": "one fresh DeepSeek call per frozen batch"})


def load_key() -> str:
    value = os.environ.get("DEEPSEEK_API_KEY")
    if value:
        return value
    env_path = ROOT / ".env"
    for line in env_path.read_text(encoding="utf-8").splitlines():
        if line.startswith("DEEPSEEK_API_KEY="):
            return line.partition("=")[2].strip().strip('"\'')
    raise RuntimeError("DeepSeek credential unavailable")


def run() -> None:
    verify_frozen_sources()
    preflight = json.loads((RUN / "preflight_manifest.json").read_text())
    require(preflight["status"] == "PASS" and len(preflight["frozen_requests"]) == 16, "missing frozen preflight")
    key = load_key()
    schemas = read("neutral_review_output_schema.json")
    plan = read("neutral_review_batching_plan.json")
    for item in preflight["frozen_requests"]:
        pass_name, index = item["pass"], item["batch_index"]
        request_file = request_path(pass_name, index)
        require(sha(request_file) == hashlib.sha256(canonical(json.loads(request_file.read_text())) + b"\n").hexdigest(), "request file malformed")
        body = json.loads(request_file.read_text())
        require(digest(body) == item["request_sha256"], "request drift")
        require(not (RUN / "attempts" / f"{pass_name.lower()}_batch_{index:02d}.json").exists(), "attempt already started; no retry")
        attempt = RUN / "attempts" / f"{pass_name.lower()}_batch_{index:02d}.json"
        write_json_once(attempt, {"pass": pass_name, "batch_index": index, "request_sha256": item["request_sha256"], "single_attempt_committed_before_network": True, "started_unix_time": time.time()})
        print(f"CALL_STARTED {pass_name} batch {index}/8", flush=True)
        try:
            with httpx.Client(timeout=httpx.Timeout(connect=20.0, read=900.0, write=120.0, pool=20.0)) as client:
                response = client.post("https://api.deepseek.com/v1/chat/completions", headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"}, json=body)
        except Exception as error:
            write_json_once(RUN / "failures" / f"{pass_name.lower()}_batch_{index:02d}.json", {"stage": "transport", "error_type": type(error).__name__, "message": str(error), "inference_occurred": "UNKNOWN", "retry_permitted": False})
            raise RuntimeError(f"transport failure, inference uncertain: {pass_name}/{index}") from error
        write_once(response_path(pass_name, index), response.content)
        write_json_once(RUN / "response_metadata" / f"{pass_name.lower()}_batch_{index:02d}.json", {"status_code": response.status_code, "raw_response_sha256": sha(response_path(pass_name, index)), "elapsed_seconds": response.elapsed.total_seconds()})
        try:
            require(response.status_code == 200, f"provider status {response.status_code}")
            envelope = response.json()
            require(isinstance(envelope, dict) and len(envelope.get("choices", [])) == 1, "invalid provider envelope")
            choice = envelope["choices"][0]
            require(choice.get("finish_reason") == "stop", f"incomplete finish: {choice.get('finish_reason')}")
            content = choice["message"]["content"]
            require(isinstance(content, str), "provider content is not a string")
            output = json.loads(content)
            check_schema(output, schemas[pass_name])
            actual = [record["review_unit_id"] for record in output["records"]]
            expected = plan["batch_plan"][index - 1]["unit_ids"]
            require(actual == expected, "exact batch order or identity mismatch")
            write_json_once(validated_path(pass_name, index), output)
        except Exception as error:
            write_json_once(RUN / "failures" / f"{pass_name.lower()}_batch_{index:02d}.json", {"stage": "provider_response_validation", "error_type": type(error).__name__, "message": str(error), "raw_response_sha256": sha(response_path(pass_name, index)), "retry_permitted": False})
            raise
        print(f"CALL_VALIDATED {pass_name} batch {index}/8 records={len(output['records'])}", flush=True)
    freeze_blinded(preflight)


def freeze_blinded(preflight: dict[str, Any]) -> None:
    pairs = []
    a_rows, b_rows = [], []
    for item in preflight["frozen_requests"]:
        pass_name, index = item["pass"], item["batch_index"]
        path = validated_path(pass_name, index)
        require(path.exists() and response_path(pass_name, index).exists(), "incomplete blinded output")
        rows = json.loads(path.read_text())["records"]
        (a_rows if pass_name == "PASS_A" else b_rows).extend(rows)
        for artifact in (request_path(pass_name, index), response_path(pass_name, index), path):
            pairs.append([str(artifact.relative_to(RUN)), sha(artifact)])
    require(len(a_rows) == len(b_rows) == 71, "blinded record count mismatch")
    require([row["review_unit_id"] for row in a_rows] == [row["review_unit_id"] for row in b_rows], "cross-pass identity mismatch")
    for pass_name, rows in (("PASS_A", a_rows), ("PASS_B", b_rows)):
        write_once(RUN / f"blinded_{pass_name.lower()}_adjudications.jsonl", b"".join(canonical(row) + b"\n" for row in rows))
        pairs.append([f"blinded_{pass_name.lower()}_adjudications.jsonl", sha(RUN / f"blinded_{pass_name.lower()}_adjudications.jsonl")])
    root = digest(pairs)
    write_json_once(RUN / "blinded_adjudication_freeze_manifest.json", {"aggregate_components": pairs, "blinded_adjudication_sha256": root, "pass_a_records": 71, "pass_b_records": 71, "provider_calls": 16, "hidden_arm_map_accessed_before_freeze": False})
    write_once(RUN / "blinded_adjudication_sha256", (root + "\n").encode())
    print(f"BLINDED_FREEZE_COMPLETE {root}", flush=True)


def seal_failure() -> None:
    """Seal a partial fail-closed run without repairing or unblinding it."""
    verify_frozen_sources()
    require(not (RUN / "blinded_adjudication_freeze_manifest.json").exists(), "a complete blinded freeze already exists")
    require(not (RUN / "partial_failure_manifest.json").exists(), "failure already sealed")
    attempts = sorted((RUN / "attempts").glob("*.json"))
    validated = sorted((RUN / "validated").glob("*.json"))
    failures = sorted((RUN / "failures").glob("*.json"))
    require(len(attempts) == 9 and len(validated) == 8 and len(failures) == 1, "unexpected partial-run counts")
    require(failures[0].name == "pass_b_batch_01.json", "unexpected failed batch")
    expected = read("neutral_review_batching_plan.json")["batch_plan"][0]["unit_ids"]
    raw_path = response_path("PASS_B", 1)
    raw = json.loads(raw_path.read_text(encoding="utf-8"))
    rows = json.loads(raw["choices"][0]["message"]["content"])["records"]
    actual = [row["review_unit_id"] for row in rows]
    require(len(actual) == 10 and set(actual) == set(expected) and actual != expected, "unexpected failure shape")
    artifacts = [path for folder in ("requests", "attempts", "raw_responses", "response_metadata", "validated", "failures")
                 for path in sorted((RUN / folder).glob("*.json"))]
    pairs = [[str(path.relative_to(RUN)), sha(path)] for path in artifacts]
    write_json_once(RUN / "partial_failure_manifest.json", {
        "status": "FAILED_CLOSED", "failure_reason": "PASS_B_BATCH_01_ID_ORDER_MISMATCH",
        "source_roots": ROOTS, "provider_calls_started": 9,
        "validated_pass_a_batches": 8, "validated_pass_a_records": 71,
        "validated_pass_b_batches": 0, "remaining_authorized_batches_not_called": 7,
        "failed_batch_response_record_count": 10, "failed_batch_id_set_matches": True,
        "failed_batch_id_order_matches": False,
        "failed_batch_mismatch_positions_one_based": [i for i, (seen, frozen) in enumerate(zip(actual, expected), 1) if seen != frozen],
        "blinded_adjudication_freeze_completed": False,
        "hidden_arm_map_opened": False, "identity_join_performed": False,
        "metrics_computed": False, "retry_or_repair_calls": 0,
        "aggregate_components": pairs, "partial_failure_sha256": digest(pairs),
    })
    print(f"FAILURE_SEALED {digest(pairs)}", flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("prepare", "run", "seal-failure"))
    args = parser.parse_args()
    try:
        {"prepare": prepare, "run": run, "seal-failure": seal_failure}[args.mode]()
    except Exception as error:
        print(f"FAIL_CLOSED {type(error).__name__}: {error}", file=sys.stderr, flush=True)
        sys.exit(1)
