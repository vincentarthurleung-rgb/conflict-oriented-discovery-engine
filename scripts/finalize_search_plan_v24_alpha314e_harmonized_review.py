#!/usr/bin/env python3
"""Freeze all blinded review outputs before any arm map or metric access."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import shutil
import sys
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "runs/20260925_search_plan_v24_dev_alpha3_13_harmonized_neutral_review_preregistration_offline"
FAILED_313 = ROOT / "runs/20260925_search_plan_v24_dev_alpha3_13_harmonized_deepseek_review"
FAILED_314B = ROOT / "runs/20260925_search_plan_v24_dev_alpha3_14b_harmonized_review_continuation"
AMENDMENT = ROOT / "runs/20260925_search_plan_v24_dev_alpha3_14a_review_identity_binding_amendment_offline"
RUN = ROOT / "runs/20260926_search_plan_v24_dev_alpha3_14e_harmonized_review_continuation"


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


def lines(path: Path) -> list[Any]:
    body = path.read_text(encoding="utf-8")
    decoder = json.JSONDecoder()
    pos = 0
    values = []
    while pos < len(body):
        while pos < len(body) and body[pos].isspace():
            pos += 1
        if pos < len(body):
            value, pos = decoder.raw_decode(body, pos)
            values.append(value)
    return values


def write(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    body = canonical(value) + b"\n"
    if path.exists():
        require(path.read_bytes() == body, f"refusing different existing artifact: {path}")
        return
    path.write_bytes(body)


def write_lines(path: Path, rows: list[Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    body = b"".join(canonical(row) + b"\n" for row in rows)
    if path.exists():
        require(path.read_bytes() == body, f"refusing different existing artifact: {path}")
        return
    path.write_bytes(body)


def copy_once(source: Path, target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    require(source.is_file() and not source.is_symlink(), f"unsafe source: {source}")
    if target.exists():
        require(target.is_file() and not target.is_symlink() and sha(source) == sha(target), f"existing copy differs: {target}")
        return
    shutil.copyfile(source, target)
    require(sha(source) == sha(target), f"copy hash mismatch: {source}")


def schema_failures(value: Any, schema: dict[str, Any], path: str = "$") -> list[str]:
    failures: list[str] = []
    if "type" in schema:
        kinds = schema["type"] if isinstance(schema["type"], list) else [schema["type"]]
        checks = {"object": lambda x: isinstance(x, dict), "array": lambda x: isinstance(x, list),
                  "string": lambda x: isinstance(x, str), "number": lambda x: isinstance(x, (int, float)) and not isinstance(x, bool),
                  "null": lambda x: x is None, "boolean": lambda x: isinstance(x, bool)}
        if not any(checks[k](value) for k in kinds):
            return [f"{path}:TYPE"]
    if "enum" in schema and value not in schema["enum"]:
        failures.append(f"{path}:ENUM")
    if "const" in schema and value != schema["const"]:
        failures.append(f"{path}:CONST")
    if isinstance(value, dict):
        props = schema.get("properties", {})
        failures.extend(f"{path}.{key}:MISSING" for key in schema.get("required", []) if key not in value)
        if schema.get("additionalProperties") is False:
            failures.extend(f"{path}.{key}:EXTRA" for key in sorted(set(value) - set(props)))
        for key in sorted(set(value) & set(props)):
            failures.extend(schema_failures(value[key], props[key], f"{path}.{key}"))
    elif isinstance(value, list):
        if not schema.get("minItems", 0) <= len(value) <= schema.get("maxItems", float("inf")):
            failures.append(f"{path}:LENGTH")
        for index, item in enumerate(value):
            failures.extend(schema_failures(item, schema.get("items", {}), f"{path}[{index}]"))
    elif isinstance(value, str):
        import re
        if len(value) < schema.get("minLength", 0):
            failures.append(f"{path}:MIN_LENGTH")
        if "pattern" in schema and re.search(schema["pattern"], value) is None:
            failures.append(f"{path}:PATTERN")
    elif isinstance(value, (int, float)) and not isinstance(value, bool):
        if not schema.get("minimum", float("-inf")) <= value <= schema.get("maximum", float("inf")):
            failures.append(f"{path}:NUMBER_BOUNDS")
    return failures


def freeze_blinded() -> None:
    root_path = RUN / "harmonized_deepseek_blinded_adjudication_corpus_sha256"
    require(not root_path.exists(), "blinded corpus already frozen")
    require(not list((RUN / "failures").glob("*.json")), "continuation contains a failed response")
    attempts = sorted((RUN / "attempts").glob("pass_b_batch_*.json"))
    require([int(path.stem.rsplit("_", 1)[1]) for path in attempts] == [3, 4, 5, 6, 7, 8], "six authorized attempts not complete")
    gate = load(RUN / "gate/replacement_batch3_validation.json")
    require(gate["status"] == "VALID" and gate["old_invalid_inference_reused"] is False, "replacement gate invalid")
    plan = load(SOURCE / "neutral_review_batching_plan.json")
    schema = load(SOURCE / "neutral_review_output_schema.json")
    a_records, b_records, provenance = [], [], []
    copy_once(AMENDMENT / "pass_a_v2_revalidation.json", RUN / "reused_validation/pass_a_v2_revalidation.json")
    copy_once(AMENDMENT / "pass_b_batch1_v2_revalidation.json", RUN / "reused_validation/pass_b_batch1_v2_revalidation.json")
    copy_once(AMENDMENT / "pass_b_batch1_id_set_audit.json", RUN / "reused_validation/pass_b_batch1_id_set_audit.json")
    copy_once(FAILED_314B / "identity/pass_b_batch_02.json", RUN / "reused_validation/pass_b_batch_02_identity.json")
    copy_once(FAILED_314B / "transport/pass_b_batch_02.json", RUN / "reused_transport/pass_b_batch_02.json")
    for batch in plan["batch_plan"]:
        index, expected = batch["batch_index"], batch["unit_ids"]
        a_source = AMENDMENT / f"canonical_pass_a_batch_{index:02d}_blinded.jsonl"
        a = lines(a_source)
        require(not schema_failures({"records": a}, schema["PASS_A"]), f"PASS A batch {index} schema failure")
        require([record["review_unit_id"] for record in a] == expected, f"PASS A batch {index} ID order failure")
        a_records.extend(a)
        copy_once(a_source, RUN / "complete_canonical_batches" / f"pass_a_batch_{index:02d}.jsonl")
        a_raw_source = FAILED_313 / "raw_responses" / f"pass_a_batch_{index:02d}.json"
        copy_once(a_raw_source, RUN / "complete_raw_responses" / f"pass_a_batch_{index:02d}.json")
        copy_once(FAILED_313 / "response_metadata" / f"pass_a_batch_{index:02d}.json", RUN / "reused_transport" / f"pass_a_batch_{index:02d}.json")
        provenance.append({"pass": "PASS_A", "batch_index": index, "source": "ORIGINAL_VALID_REUSED", "model": "deepseek-v4-pro", "raw_response_sha256": sha(a_raw_source), "canonical_records_sha256": sha(a_source), "new_inference_calls": 0})
        if index == 1:
            b_source = AMENDMENT / "canonical_pass_b_batch_01_blinded.jsonl"
            b = lines(b_source)
            b_raw_source = FAILED_313 / "raw_responses/pass_b_batch_01.json"
            copy_once(FAILED_313 / "response_metadata/pass_b_batch_01.json", RUN / "reused_transport/pass_b_batch_01.json")
            kind = "ORIGINAL_VALID_V2_CANONICALIZED_REUSED"
        elif index == 2:
            b_source = FAILED_314B / "parsed/pass_b_batch_02.json"
            b = load(b_source)["records"]
            b_raw_source = FAILED_314B / "raw_responses/pass_b_batch_02.json"
            kind = "ALPHA314B_VALID_REUSED"
        else:
            b_source = RUN / "validated" / f"pass_b_batch_{index:02d}.json"
            b = load(b_source)["records"]
            b_raw_source = RUN / "raw_responses" / f"pass_b_batch_{index:02d}.json"
            identity = load(RUN / "identity" / f"pass_b_batch_{index:02d}.json")
            require(identity["id_set_exact"] is True and identity["scientific_field_mutation_count"] == 0, "new identity validation drift")
            kind = "ALPHA314E_VALID_NEW_REPLACEMENT" if index == 3 else "ALPHA314E_VALID_NEVER_INFERRED"
        require(not schema_failures({"records": b}, schema["PASS_B"]), f"PASS B batch {index} schema failure")
        require([record["review_unit_id"] for record in b] == expected, f"PASS B batch {index} ID order failure")
        b_records.extend(b)
        target = RUN / "complete_canonical_batches" / f"pass_b_batch_{index:02d}.jsonl"
        if index == 1:
            copy_once(b_source, target)
        else:
            write_lines(target, b)
        copy_once(b_raw_source, RUN / "complete_raw_responses" / f"pass_b_batch_{index:02d}.json")
        provenance.append({"pass": "PASS_B", "batch_index": index, "source": kind, "model": "deepseek-v4-pro", "raw_response_sha256": sha(b_raw_source), "canonical_records_sha256": sha(target), "new_inference_calls": 1 if index >= 3 else 0})
    ids_a = [record["review_unit_id"] for record in a_records]
    ids_b = [record["review_unit_id"] for record in b_records]
    require(len(a_records) == len(b_records) == len(set(ids_a)) == 71 and ids_a == ids_b, "complete blinded unit alignment failure")
    complete = [{"review_unit_id": a["review_unit_id"], "pass_a": a, "pass_b": b} for a, b in zip(a_records, b_records)]
    write_lines(RUN / "complete_blinded_review_unit_results.jsonl", complete)
    write(RUN / "reviewer_provenance.json", {"reviewer_type": "model_retrieval_adjudicator", "provider": "deepseek", "model": "deepseek-v4-pro", "thinking": "enabled", "reasoning_effort": "high", "batches": provenance})
    write(RUN / "model_call_accounting.json", {"planned_batch_identities": 16, "valid_final_batch_adjudications": 16, "cumulative_provider_inference_events": 17, "historical_inference_events": 11, "new_inference_events": 6, "invalid_superseded_inference_events": 1, "reinferred_batch_identities": 1, "never_reinferred_valid_batch_identities": 15, "pass_a_reinference_calls": 0, "pass_b_batch1_reinference_calls": 0, "pass_b_batch2_reinference_calls": 0, "unplanned_scientific_adjudication_calls": 0})
    old_invalid = FAILED_314B / "raw_responses/pass_b_batch_03.json"
    write(RUN / "invalid_superseded_inference_preservation_audit.json", {"old_batch3_raw_sha256": sha(old_invalid), "old_inference_status": "INVALID_SUPERSEDED_INFERENCE", "old_scientific_labels_not_compared_to_replacement": True, "old_raw_preserved_at": str(old_invalid.relative_to(ROOT)), "old_inference_event_count": 1, "new_batch3_raw_sha256": sha(RUN / "raw_responses/pass_b_batch_03.json"), "new_batch3_complete_schema_and_identity_valid": True})
    write(RUN / "blinded_adjudication_freeze_audit.json", {"blinded_adjudication_freeze_complete": True, "pass_a_batches": 8, "pass_b_batches": 8, "pass_a_units": 71, "pass_b_units": 71, "raw_valid_response_count": 16, "canonical_valid_batch_count": 16, "old_invalid_response_excluded_from_valid_corpus": True, "old_invalid_response_preserved_as_inference_event": True, "arm_map_accessed_before_blinded_freeze": False, "metrics_computed_before_blinded_freeze": False})
    artifact_dirs = ("complete_raw_responses", "complete_canonical_batches", "reused_validation", "reused_transport", "attempts", "raw_responses", "transport", "validated", "identity", "gate")
    artifacts = [path for folder in artifact_dirs for path in sorted((RUN / folder).glob("*")) if path.is_file()]
    artifacts += [RUN / name for name in ("six_request_manifest.jsonl", "six_request_manifest_sha256", "frozen_requests.jsonl", "preflight_freeze.json", "complete_blinded_review_unit_results.jsonl", "reviewer_provenance.json", "model_call_accounting.json", "invalid_superseded_inference_preservation_audit.json", "blinded_adjudication_freeze_audit.json")]
    pairs = [[str(path.relative_to(RUN)), sha(path)] for path in sorted(set(artifacts))]
    root = digest(pairs)
    write(RUN / "harmonized_deepseek_blinded_adjudication_corpus_manifest.json", {"aggregate_algorithm": "sha256(canonical JSON sorted [path,sha256] pairs)", "aggregate_components": pairs, "harmonized_deepseek_blinded_adjudication_corpus_sha256": root, "valid_batch_identities": 16, "valid_review_units_per_pass": 71, "cumulative_inference_events": 17, "invalid_superseded_inference_events": 1, "arm_map_accessed_before_blinded_freeze": False})
    root_path.write_text(root + "\n", encoding="utf-8")
    require(all(sha(RUN / name) == checksum for name, checksum in pairs), "blinded freeze component drift")
    require(digest(pairs) == root_path.read_text().strip(), "blinded freeze root drift")
    print(f"BLINDED_FREEZE_COMPLETE {root}", flush=True)


if __name__ == "__main__":
    try:
        if len(sys.argv) != 2 or sys.argv[1] != "freeze-blinded":
            raise RuntimeError("usage: freeze-blinded")
        freeze_blinded()
    except Exception as error:
        print(f"FAIL_CLOSED {type(error).__name__}: {error}", file=sys.stderr, flush=True)
        raise SystemExit(1)
