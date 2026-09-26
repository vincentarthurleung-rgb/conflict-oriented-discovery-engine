#!/usr/bin/env python3
"""Freeze alpha3.14b blinded results, then unblind and apply frozen metrics."""

from __future__ import annotations

from collections import Counter
import hashlib
import json
from pathlib import Path
import shutil
import sys
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "runs/20260925_search_plan_v24_dev_alpha3_13_harmonized_neutral_review_preregistration_offline"
FAILED = ROOT / "runs/20260925_search_plan_v24_dev_alpha3_13_harmonized_deepseek_review"
AMENDMENT = ROOT / "runs/20260925_search_plan_v24_dev_alpha3_14a_review_identity_binding_amendment_offline"
RUN = ROOT / "runs/20260925_search_plan_v24_dev_alpha3_14b_harmonized_review_continuation"
CASE_FILE = ROOT / "runs/20260916_search_plan_v23_beta_2_primary_heldout_v2_case_freeze_offline/primary_heldout_v2_cases.json"


def require(ok: bool, why: str) -> None:
    if not ok:
        raise RuntimeError(why)


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
    return [json.loads(line) for line in path.read_bytes().splitlines() if line]


def write(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    require(not path.exists(), f"refusing overwrite: {path}")
    path.write_bytes(canonical(value) + b"\n")


def write_lines(path: Path, rows: list[Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    require(not path.exists(), f"refusing overwrite: {path}")
    path.write_bytes(b"".join(canonical(row) + b"\n" for row in rows))


def copy_once(source: Path, target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    require(not target.exists() and source.is_file() and not source.is_symlink(), f"unsafe physical copy: {source}")
    shutil.copyfile(source, target)
    require(sha(source) == sha(target), f"byte copy mismatch: {source}")


def check_schema(value: Any, schema: dict[str, Any], where: str = "$") -> None:
    if "type" in schema:
        types = schema["type"] if isinstance(schema["type"], list) else [schema["type"]]
        checks = {"object": lambda x: isinstance(x, dict), "array": lambda x: isinstance(x, list),
                  "string": lambda x: isinstance(x, str), "number": lambda x: isinstance(x, (int, float)) and not isinstance(x, bool),
                  "null": lambda x: x is None, "boolean": lambda x: isinstance(x, bool)}
        require(any(checks[t](value) for t in types), f"schema type: {where}")
    if "enum" in schema:
        require(value in schema["enum"], f"schema enum: {where}")
    if "const" in schema:
        require(value == schema["const"], f"schema const: {where}")
    if isinstance(value, dict):
        props = schema.get("properties", {})
        require(set(schema.get("required", [])) <= set(value), f"schema required: {where}")
        if schema.get("additionalProperties") is False:
            require(set(value) <= set(props), f"schema extra fields: {where}")
        for key, item in value.items():
            if key in props:
                check_schema(item, props[key], f"{where}.{key}")
    elif isinstance(value, list):
        require(schema.get("minItems", 0) <= len(value) <= schema.get("maxItems", float("inf")), f"schema array size: {where}")
        for index, item in enumerate(value):
            check_schema(item, schema.get("items", {}), f"{where}[{index}]")
    elif isinstance(value, str):
        require(len(value) >= schema.get("minLength", 0), f"schema minLength: {where}")
        if "pattern" in schema:
            import re
            require(re.search(schema["pattern"], value) is not None, f"schema pattern: {where}")
    elif isinstance(value, (int, float)) and not isinstance(value, bool):
        require(schema.get("minimum", float("-inf")) <= value <= schema.get("maximum", float("inf")), f"schema numeric bound: {where}")


def verify_alpha314a() -> None:
    root = (AMENDMENT / "search_plan_v24_dev_alpha3_14a_sha256").read_text().strip()
    pairs = [[path.name, sha(path)] for path in sorted(AMENDMENT.iterdir()) if path.is_file() and path.name != "search_plan_v24_dev_alpha3_14a_sha256"]
    require(digest(pairs) == root == "41d37150bd568ee7c4c17d49d3531a4e19bac91b9c954983162d5d959c5ddc70", "alpha3.14a root drift")


def freeze_blinded() -> None:
    verify_alpha314a()
    require(not (RUN / "harmonized_deepseek_blinded_adjudication_corpus_sha256").exists(), "blinded corpus already frozen")
    plan = load(SOURCE / "neutral_review_batching_plan.json")
    schemas = load(SOURCE / "neutral_review_output_schema.json")
    derived = load(RUN / "remaining_pass_b_derivation.json")
    require(derived["never_inferred_batch_indices"] == list(range(2, 9)), "continuation batch derivation drift")
    attempts = sorted((RUN / "attempts").glob("pass_b_batch_*.json"))
    require([int(path.stem.rsplit("_", 1)[1]) for path in attempts] == list(range(2, 9)), "new call count or order mismatch")
    require(not list((RUN / "failures").glob("*.json")), "failed continuation response exists")
    raw_rows, transport_rows, parsed_rows, identity_rows = [], [], [], []
    provenance = []
    a_records, b_records = [], []
    copy_once(AMENDMENT / "pass_a_v2_revalidation.json", RUN / "reused_validation/pass_a_v2_revalidation.json")
    copy_once(AMENDMENT / "pass_b_batch1_v2_revalidation.json", RUN / "reused_validation/pass_b_batch1_v2_revalidation.json")
    copy_once(AMENDMENT / "pass_b_batch1_id_set_audit.json", RUN / "reused_validation/pass_b_batch1_id_set_audit.json")
    for batch in plan["batch_plan"]:
        index, expected = batch["batch_index"], batch["unit_ids"]
        a_source = AMENDMENT / f"canonical_pass_a_batch_{index:02d}_blinded.jsonl"
        a = lines(a_source)
        check_schema({"records": a}, schemas["PASS_A"])
        require([row["review_unit_id"] for row in a] == expected, "reused PASS A IDs/order mismatch")
        a_records.extend(a)
        copy_once(FAILED / "raw_responses" / f"pass_a_batch_{index:02d}.json", RUN / "complete_raw_responses" / f"pass_a_batch_{index:02d}.json")
        copy_once(FAILED / "response_metadata" / f"pass_a_batch_{index:02d}.json", RUN / "reused_transport" / f"pass_a_batch_{index:02d}.json")
        copy_once(a_source, RUN / "complete_canonical_batches" / f"pass_a_batch_{index:02d}.jsonl")
        provenance.append({"pass": "PASS_A", "batch_index": index, "source": "HISTORICAL_REUSED", "provider": "deepseek", "model": "deepseek-v4-pro", "raw_response_sha256": sha(FAILED / "raw_responses" / f"pass_a_batch_{index:02d}.json"), "canonical_records_sha256": sha(a_source), "reinference_calls": 0})
        if index == 1:
            b_source = AMENDMENT / "canonical_pass_b_batch_01_blinded.jsonl"
            b = lines(b_source)
            b_identity = load(AMENDMENT / "pass_b_batch1_id_set_audit.json")
            require(b_identity["identity_binding"] == "VALID" and b_identity["expected_id_set_equals_returned_id_set"] is True, "reused B1 invalid")
            raw_source = FAILED / "raw_responses/pass_b_batch_01.json"
            copy_once(FAILED / "response_metadata/pass_b_batch_01.json", RUN / "reused_transport/pass_b_batch_01.json")
            copy_once(b_source, RUN / "complete_canonical_batches/pass_b_batch_01.jsonl")
            provenance.append({"pass": "PASS_B", "batch_index": 1, "source": "HISTORICAL_REUSED_WITH_V2_ID_CANONICALIZATION", "provider": "deepseek", "model": "deepseek-v4-pro", "raw_response_sha256": sha(raw_source), "canonical_records_sha256": sha(b_source), "reinference_calls": 0})
        else:
            parsed_source = RUN / "parsed" / f"pass_b_batch_{index:02d}.json"
            identity_source = RUN / "identity" / f"pass_b_batch_{index:02d}.json"
            raw_source = RUN / "raw_responses" / f"pass_b_batch_{index:02d}.json"
            transport_source = RUN / "transport" / f"pass_b_batch_{index:02d}.json"
            require(all(path.exists() for path in (parsed_source, identity_source, raw_source, transport_source)), "continuation batch not complete")
            b = load(parsed_source)["records"]
            identity = load(identity_source)
            require(identity["identity_binding"] == "VALID" and identity["scientific_field_mutation_count"] == 0, "new identity validation failure")
            raw_rows.append({"batch_index": index, "raw_response": load(raw_source), "raw_response_sha256": sha(raw_source)})
            transport_rows.append(load(transport_source))
            parsed_rows.append({"batch_index": index, "records": b, "parsed_file_sha256": sha(parsed_source)})
            identity_rows.append(identity)
            write_lines(RUN / "complete_canonical_batches" / f"pass_b_batch_{index:02d}.jsonl", b)
            provenance.append({"pass": "PASS_B", "batch_index": index, "source": "ALPHA314B_NEW_SINGLE_INFERENCE", "provider": "deepseek", "model": "deepseek-v4-pro", "raw_response_sha256": sha(raw_source), "canonical_records_sha256": sha(RUN / "complete_canonical_batches" / f"pass_b_batch_{index:02d}.jsonl"), "reinference_calls": 0})
        check_schema({"records": b}, schemas["PASS_B"])
        require([row["review_unit_id"] for row in b] == expected, "PASS B IDs/order mismatch")
        b_records.extend(b)
        copy_once(raw_source, RUN / "complete_raw_responses" / f"pass_b_batch_{index:02d}.json")
    require(len(a_records) == len(b_records) == 71, "incomplete review-unit count")
    require([row["review_unit_id"] for row in a_records] == [row["review_unit_id"] for row in b_records], "A/B review unit alignment mismatch")
    require(len(set(row["review_unit_id"] for row in a_records)) == 71, "duplicate review unit")
    write_lines(RUN / "pass_b_continuation_raw_responses.jsonl", raw_rows)
    write_lines(RUN / "pass_b_continuation_transport_provenance.jsonl", transport_rows)
    write_lines(RUN / "pass_b_continuation_parsed_outputs.jsonl", parsed_rows)
    write_lines(RUN / "pass_b_continuation_identity_binding_validation.jsonl", identity_rows)
    write(RUN / "pass_b_completion_summary.json", {"pass_b_total_batches": 8, "pass_b_completed_batches": 8, "pass_b_completed_review_units": 71, "historical_batch1_reused": True, "newly_completed_batches": 7, "duplicate_scientific_inference_pairs": 0})
    write(RUN / "model_call_accounting.json", {"historical_deepseek_calls_preserved": 9, "new_authorized_deepseek_calls": 7, "new_actual_deepseek_calls": 7, "total_unique_inferred_batches": 16, "pass_a_reinference_calls": 0, "pass_b_batch1_reinference_calls": 0, "ambiguous_provider_execution_count": 0, "unplanned_scientific_adjudication_calls": 0, "reviewer_type": "model_retrieval_adjudicator", "human_gold_labels_created": 0})
    complete = [{"review_unit_id": a["review_unit_id"], "pass_a": a, "pass_b": b} for a, b in zip(a_records, b_records)]
    write_lines(RUN / "complete_blinded_review_unit_results.jsonl", complete)
    write(RUN / "blinded_adjudication_freeze_audit.json", {"blinded_adjudication_freeze_complete": True, "pass_a_completed_batches": 8, "pass_b_completed_batches": 8, "pass_a_completed_units": 71, "pass_b_completed_units": 71, "arm_map_accessed_before_blinded_freeze": False, "identity_join_before_blinded_freeze": False, "raw_response_count": 16, "canonical_batch_count": 16, "validation_state_count": 16, "reviewer_provenance": provenance})
    names = ["remaining_pass_b_request_manifest.jsonl", "remaining_pass_b_request_manifest_sha256", "completed_pass_a_reuse_audit.json", "pass_b_batch1_reuse_audit.json", "pass_b_continuation_requests.jsonl", "pass_b_continuation_raw_responses.jsonl", "pass_b_continuation_transport_provenance.jsonl", "pass_b_continuation_parsed_outputs.jsonl", "pass_b_continuation_identity_binding_validation.jsonl", "pass_b_completion_summary.json", "model_call_accounting.json", "complete_blinded_review_unit_results.jsonl", "blinded_adjudication_freeze_audit.json"]
    artifacts = [RUN / name for name in names]
    artifacts += sorted((RUN / "complete_raw_responses").glob("*.json"))
    artifacts += sorted((RUN / "complete_canonical_batches").glob("*.jsonl"))
    artifacts += sorted((RUN / "identity").glob("*.json"))
    artifacts += sorted((RUN / "transport").glob("*.json"))
    artifacts += sorted((RUN / "parsed").glob("*.json"))
    artifacts += sorted((RUN / "attempts").glob("*.json"))
    artifacts += sorted((RUN / "reused_validation").glob("*.json"))
    artifacts += sorted((RUN / "reused_transport").glob("*.json"))
    pairs = [[str(path.relative_to(RUN)), sha(path)] for path in sorted(set(artifacts))]
    root = digest(pairs)
    write(RUN / "harmonized_deepseek_blinded_adjudication_corpus_manifest.json", {"aggregate_algorithm": "sha256(canonical JSON sorted [path,sha256] pairs)", "aggregate_components": pairs, "harmonized_deepseek_blinded_adjudication_corpus_sha256": root, "total_unique_inferred_batches": 16, "historical_provider_calls": 9, "new_provider_calls": 7, "arm_map_accessed_before_blinded_freeze": False, "complete_blinded_review_unit_count": 71})
    (RUN / "harmonized_deepseek_blinded_adjudication_corpus_sha256").write_text(root + "\n", encoding="utf-8")
    require(all(sha(RUN / name) == value for name, value in pairs), "blinded freeze component mismatch")
    require(digest(pairs) == (RUN / "harmonized_deepseek_blinded_adjudication_corpus_sha256").read_text().strip(), "blinded freeze root mismatch")
    print(f"BLINDED_FREEZE_COMPLETE {root}", flush=True)


if __name__ == "__main__":
    try:
        if len(sys.argv) != 2 or sys.argv[1] != "freeze-blinded":
            raise RuntimeError("usage: freeze-blinded")
        freeze_blinded()
    except Exception as error:
        print(f"FAIL_CLOSED {type(error).__name__}: {error}", file=sys.stderr, flush=True)
        raise SystemExit(1)
