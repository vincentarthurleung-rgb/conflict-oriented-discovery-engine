#!/usr/bin/env python3
"""Import, structurally validate, and freeze supplied PASS B adjudications offline."""
from __future__ import annotations

from collections import Counter
import hashlib
import json
from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[1]
PROTOCOL_RUN = ROOT / "runs/20260909_search_plan_v22_heldout_v1_case_freeze_offline"
CORPUS_RUN = ROOT / "runs/20260910_search_plan_v22_heldout_v1_neutral_review_freeze_offline"
BLINDED_RUN = ROOT / "runs/20260910_search_plan_v22_heldout_v1_blinded_adjudication_views_offline"
PASS_A_RUN = ROOT / "runs/20260910_search_plan_v22_heldout_v1_pass_a_acquisition_adjudication_freeze_offline"
WORKSPACE = ROOT / "pass_b_primary_evaluator_workspace"
WORKSPACE_AUDIT = ROOT / "runs/20260912_search_plan_v22_heldout_v1_pass_b_primary_evaluator_workspace_audit_offline/workspace_exposure_audit.json"
RUN = ROOT / "runs/20260912_search_plan_v22_heldout_v1_pass_b_relevance_adjudication_freeze_offline"

INPUTS = [
    Path("/home/vincent/.codex/attachments/fce5ec0c-6386-42e6-be7c-c7204f444ab2/pasted-text.txt"),
    Path("/home/vincent/.codex/attachments/65124df2-a013-4625-a658-cbb75f4df8fa/pasted-text.txt"),
    Path("/home/vincent/.codex/attachments/2bff884a-6106-48d8-bda3-00f1dc5ee591/pasted-text.txt"),
    Path("/home/vincent/.codex/attachments/d0f09e29-6ed0-407d-b87f-d007ce3948eb/pasted-text.txt"),
    Path("/home/vincent/.codex/attachments/4f563d89-3d0b-4a69-9582-3481b9b9f9d0/pasted-text.txt"),
]
HASHES = {
    "heldout_v1_protocol_sha256": "2aac90361272de64eb055099602ae68e696c760628fec3835c0f29eca63ca127",
    "heldout_v1_review_corpus_sha256": "f2cfe4f1657667a66b18d3123e82d76cc4bf1af9da2863ac6b10f9efc3d092fb",
    "heldout_v1_blinded_adjudication_views_sha256": "2940e058b63df5dc02fb6ed07d970f651a74f9a000c9b6784affe3e6fac1dc0e",
    "heldout_v1_pass_a_acquisition_adjudications_sha256": "333fc6f20bab33b21387f2453905c2c9c11d92797177688a9e75cc2bab2e52df",
}
FIELDS = [
    "packet_id",
    "relevance_state",
    "matched_target_components",
    "mismatched_target_components",
    "fulltext_resolved_fields",
    "remaining_unresolved_fields",
    "contaminant_class",
    "rationale",
    "confidence",
    "reviewer_type",
]
LIST_FIELDS = {
    "matched_target_components",
    "mismatched_target_components",
    "fulltext_resolved_fields",
    "remaining_unresolved_fields",
}
RELEVANCE_STATES = [
    "DIRECTLY_RELEVANT",
    "PLAUSIBLY_RELEVANT_FULLTEXT_REQUIRED",
    "RELATED_BUT_WRONG_PROPOSITION",
    "WRONG_ENDPOINT",
    "WRONG_ENTITY",
    "WRONG_EVIDENCE_MODE",
    "WRONG_THERAPY",
    "TOPIC_ONLY",
    "INSUFFICIENT_SOURCE_EVIDENCE",
]
CONTAMINANT_CLASSES = [
    "wrong_evidence_mode",
    "association_vs_functional_relation",
    "wrong_biological_unit",
    "wrong_endpoint",
    "wrong_entity",
    "baseline_viability_vs_adaptation",
]
CONFIDENCE_VALUES = ["high", "moderate-high", "moderate", "moderate-low", "low"]
REVIEWER_TYPE = "model_retrieval_adjudicator"
ZERO_CALLS = {
    "network_calls": 0,
    "provider_calls": 0,
    "llm_calls": 0,
    "downloads": 0,
    "scientific_extraction_calls": 0,
    "new_adjudication_calls": 0,
}
ZERO_MODIFICATIONS = {
    "case_modifications": 0,
    "target_modifications": 0,
    "query_modifications": 0,
    "gate_modifications": 0,
    "budget_modifications": 0,
    "sample_modifications": 0,
    "batch_assignment_modifications": 0,
    "pass_a_modifications": 0,
    "pass_b_label_modifications": 0,
}
REQUIRED = [
    "pass_b_relevance_adjudications.jsonl",
    "pass_b_packet_identity_validation.json",
    "pass_b_schema_validation.json",
    "pass_b_reviewer_validation.json",
    "root_hash_verification.json",
    "evaluator_workspace_verification.json",
    "adjudication_import_manifest.json",
    "scientific_state_safety_audit.json",
    "freeze_manifest.json",
    "validation.json",
    "manifest.json",
    "summary.json",
]


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha(path: Path) -> str:
    return digest(path.read_bytes())


def canonical(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


def pretty(value: object) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n").encode("utf-8")


def read_json(path: Path) -> dict:
    return json.loads(path.read_bytes())


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_bytes().splitlines() if line.strip()]


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def verify_aggregate_root(base: Path, field: str, expected: str) -> dict:
    manifest = read_json(base / "freeze_manifest.json")
    components = []
    for row in manifest["components"]:
        actual = sha(base / row["path"])
        require(actual == row["sha256"], f"Frozen component hash mismatch: {base / row['path']}")
        components.append((row["path"], actual))
    actual = digest(canonical(components))
    require(actual == manifest[field] == expected, f"Frozen root mismatch: {field}")
    return {"field": field, "expected": expected, "actual": actual, "match": True}


def verify_pass_a_root() -> dict:
    manifest = read_json(PASS_A_RUN / "freeze_manifest.json")
    actual = sha(PASS_A_RUN / manifest["corpus"])
    expected = HASHES["heldout_v1_pass_a_acquisition_adjudications_sha256"]
    require(actual == manifest["heldout_v1_pass_a_acquisition_adjudications_sha256"] == expected,
            "Frozen PASS A root mismatch")
    return {"field": "heldout_v1_pass_a_acquisition_adjudications_sha256",
            "expected": expected, "actual": actual, "match": True}


def parse_list(field: str, text: str) -> list[str]:
    require(text.startswith("[") and text.endswith("]"), f"{field} is not bracketed")
    body = text[1:-1]
    if body == "":
        return []
    values = body.split(", ")
    require(all(value and value == value.strip() for value in values), f"Malformed {field}; no repair")
    require(", ".join(values) == body, f"Non-canonical delimiter in {field}; no repair")
    return values


def parse_submission(raw: bytes) -> tuple[list[dict], list[dict]]:
    lines = raw.decode("utf-8").splitlines()
    blocks: list[list[str]] = []
    current: list[str] = []
    for line in lines:
        if line == "":
            if current:
                blocks.append(current)
                current = []
        else:
            current.append(line)
    if current:
        blocks.append(current)
    records, trace = [], []
    for block_number, block in enumerate(blocks, 1):
        require(len(block) == len(FIELDS), f"Record {block_number} has the wrong field count")
        record = {}
        raw_values = {}
        for field, line in zip(FIELDS, block):
            prefix = field + ":"
            require(line == prefix or line.startswith(prefix + " "),
                    f"Unexpected field/order in record {block_number}; no repair")
            value = "" if line == prefix else line[len(prefix) + 1:]
            raw_values[field] = value
            record[field] = parse_list(field, value) if field in LIST_FIELDS else value
        records.append(record)
        trace.append({"input_record_order": block_number,
                      "input_record_text_sha256": digest("\n".join(block).encode("utf-8")),
                      "submitted_field_value_sha256": {field: digest(value.encode("utf-8"))
                                                       for field, value in raw_values.items()}})
    return records, trace


def validate_records(records: list[dict], expected_ids: list[str]) -> list[dict]:
    observed = [row["packet_id"] for row in records]
    require(len(expected_ids) == len(set(expected_ids)) == 70, "Frozen PASS B packet identity is invalid")
    require(len(records) == 70, "Expected exactly 70 PASS B records")
    require(Counter(observed) == Counter(expected_ids), "Missing, extra, or duplicate PASS B packet IDs")
    for row in records:
        require(list(row) == FIELDS, "PASS B record fields/order are not exact")
        require(row["relevance_state"] in RELEVANCE_STATES, "Invalid relevance_state")
        require(row["contaminant_class"] in ["", *CONTAMINANT_CLASSES], "Invalid contaminant_class")
        require(row["confidence"] in CONFIDENCE_VALUES, "Invalid confidence")
        require(row["reviewer_type"] == REVIEWER_TYPE, "Invalid reviewer_type")
        require(bool(row["rationale"].strip()), "Missing rationale; no inference or repair")
        require(all(isinstance(row[field], list) for field in LIST_FIELDS), "Component fields must be lists")
    by_id = {row["packet_id"]: row for row in records}
    return [by_id[packet_id] for packet_id in expected_ids]


def verify_workspace() -> dict:
    expected_names = {
        "pass_b_evaluator_instruction.md",
        "evaluator_workspace_manifest.json",
        *[f"heldout_relevance_blind_batch_{index:02d}.md" for index in range(1, 6)],
    }
    require(WORKSPACE.is_dir() and not WORKSPACE.is_symlink(), "PASS B workspace is not a physical directory")
    actual_names = {path.name for path in WORKSPACE.iterdir()}
    require(actual_names == expected_names, "PASS B workspace membership changed")
    require(all(not path.is_symlink() for path in WORKSPACE.iterdir()), "PASS B workspace contains a symlink")
    manifest = read_json(WORKSPACE / "evaluator_workspace_manifest.json")
    manifest_rows = {row["path"]: row for row in manifest["files"]}
    source_matches = {}
    for index in range(1, 6):
        name = f"heldout_relevance_blind_batch_{index:02d}.md"
        workspace_hash = sha(WORKSPACE / name)
        source_hash = sha(BLINDED_RUN / name)
        require(workspace_hash == source_hash == manifest_rows[name]["sha256"],
                f"PASS B workspace batch mismatch: {name}")
        source_matches[name] = True
    for name in ["pass_b_evaluator_instruction.md", *source_matches]:
        require(sha(WORKSPACE / name) == manifest_rows[name]["sha256"],
                f"Workspace manifest hash mismatch: {name}")
    audit = read_json(WORKSPACE_AUDIT)
    require(audit["status"] == "PASS" and audit["workspace_contains_only_required_files"],
            "PASS B workspace exposure audit failed")
    require(audit["manifest_actual_file_sha256"] == sha(WORKSPACE / "evaluator_workspace_manifest.json"),
            "PASS B workspace manifest file hash mismatch")
    require(audit["source_blind_batches_byte_identical"] and audit["packet_count"] == 70,
            "PASS B workspace packet or byte-identity mismatch")
    return {
        "status": "PASS",
        "workspace_path": str(WORKSPACE),
        "workspace_manifest_sha256": sha(WORKSPACE / "evaluator_workspace_manifest.json"),
        "workspace_file_count": len(actual_names),
        "physical_files_only": True,
        "symlinks_present": False,
        "packet_count": 70,
        "batch_count": 5,
        "batch_size": 14,
        "source_blind_batches_byte_identical": all(source_matches.values()),
        "batch_hash_matches": source_matches,
        "exposure_audit_ref": str(WORKSPACE_AUDIT),
        "exposure_audit_sha256": sha(WORKSPACE_AUDIT),
        "unblinded_or_pass_a_material_present": False,
        "prefilled_workspace_labels": 0,
    }


def protected_state() -> dict[str, str]:
    paths = [path for base in (PROTOCOL_RUN, CORPUS_RUN, BLINDED_RUN, PASS_A_RUN, WORKSPACE)
             for path in sorted(base.rglob("*")) if path.is_file()]
    paths.append(WORKSPACE_AUDIT)
    paths.extend(INPUTS)
    return {str(path): sha(path) for path in paths}


def generate() -> dict[str, bytes]:
    roots = [
        verify_aggregate_root(PROTOCOL_RUN, "heldout_v1_protocol_sha256",
                              HASHES["heldout_v1_protocol_sha256"]),
        verify_aggregate_root(CORPUS_RUN, "heldout_v1_review_corpus_sha256",
                              HASHES["heldout_v1_review_corpus_sha256"]),
        verify_aggregate_root(BLINDED_RUN, "heldout_v1_blinded_adjudication_views_sha256",
                              HASHES["heldout_v1_blinded_adjudication_views_sha256"]),
        verify_pass_a_root(),
    ]
    workspace = verify_workspace()
    before = protected_state()
    canonical_packets = read_jsonl(CORPUS_RUN / "frozen_neutral_review_packets.jsonl")
    expected_ids = [row["packet_id"] for row in canonical_packets]
    pass_b_manifest_ids = [row["packet_id"] for row in read_jsonl(BLINDED_RUN / "pass_b_packet_manifest.jsonl")]
    require(expected_ids == pass_b_manifest_ids, "PASS B manifest order differs from frozen review corpus")

    submitted, traces, batch_ids = [], [], []
    input_inventory = []
    for batch_number, path in enumerate(INPUTS, 1):
        raw = path.read_bytes()
        records, record_traces = parse_submission(raw)
        require(len(records) == 14, f"PASS B batch {batch_number:02d} does not contain 14 records")
        frozen_batch_text = (WORKSPACE / f"heldout_relevance_blind_batch_{batch_number:02d}.md").read_text(encoding="utf-8")
        frozen_ids = re.findall(r"^### Packet (\S+)$", frozen_batch_text, flags=re.MULTILINE)
        observed_ids = [row["packet_id"] for row in records]
        require(observed_ids == frozen_ids, f"PASS B batch {batch_number:02d} order/identity mismatch")
        offset = len(submitted)
        for record_trace in record_traces:
            record_trace["batch_id"] = f"batch_{batch_number:02d}"
            record_trace["batch_record_order"] = record_trace["input_record_order"]
            record_trace["input_record_order"] += offset
        submitted.extend(records)
        traces.extend(record_traces)
        batch_ids.extend(observed_ids)
        input_inventory.append({
            "batch_id": f"batch_{batch_number:02d}",
            "source_path": str(path),
            "source_sha256": digest(raw),
            "record_count": len(records),
            "packet_ids_match_frozen_batch_in_order": True,
        })
    ordered = validate_records(submitted, expected_ids)
    require(batch_ids == [packet_id for index in range(1, 6) for packet_id in
                           re.findall(r"^### Packet (\S+)$",
                                      (WORKSPACE / f"heldout_relevance_blind_batch_{index:02d}.md").read_text(),
                                      flags=re.MULTILINE)],
            "Submitted batch sequence mismatch")
    corpus = b"".join(canonical(row) + b"\n" for row in ordered)
    roundtrip = [json.loads(line) for line in corpus.splitlines()]
    require(roundtrip == ordered, "Canonical serialization changed PASS B values")
    pass_b_hash = digest(corpus)
    hashes = {**HASHES, "heldout_v1_pass_b_relevance_adjudications_sha256": pass_b_hash}
    outputs: dict[str, bytes] = {"pass_b_relevance_adjudications.jsonl": corpus}

    def put(name: str, value: object) -> None:
        outputs[name] = pretty(value)

    identity = {
        "expected_packet_count": 70,
        "observed_adjudication_count": len(ordered),
        "unique_packet_ids": len({row["packet_id"] for row in ordered}),
        "missing_packet_ids": 0,
        "extra_packet_ids": 0,
        "duplicate_packet_ids": 0,
        "packet_identity_bijection": True,
        "merge_identity_key": "packet_id",
        "canonical_order_preserved": [row["packet_id"] for row in ordered] == expected_ids,
    }
    put("pass_b_packet_identity_validation.json", identity)
    put("pass_b_schema_validation.json", {
        "schema_valid": True,
        "structural_validation_only": True,
        "record_count": 70,
        "required_fields": FIELDS,
        "relevance_taxonomy_valid": True,
        "allowed_relevance_states": RELEVANCE_STATES,
        "contaminant_taxonomy_valid": True,
        "allowed_nonempty_contaminant_classes": CONTAMINANT_CLASSES,
        "empty_contaminant_class_allowed": True,
        "confidence_taxonomy_valid": True,
        "allowed_confidence_values": CONFIDENCE_VALUES,
        "component_lists_valid": True,
        "label_combinations_reinterpreted": False,
        "scientific_relabeling_performed": False,
    })
    put("pass_b_reviewer_validation.json", {
        "reviewer_type_valid": True,
        "record_count": 70,
        "required_reviewer_type": REVIEWER_TYPE,
        "reviewer_type_modified": False,
        "fresh_evaluator_completion_authority": "user-supplied five completed isolated PASS B outputs",
        "new_adjudication_calls": 0,
    })
    put("root_hash_verification.json", {
        "status": "PASS",
        "roots": roots,
        "all_four_upstream_hashes_verified": True,
        **HASHES,
    })
    put("evaluator_workspace_verification.json", workspace)
    trace_by_id = {record["packet_id"]: trace for record, trace in zip(submitted, traces)}
    source_order_by_id = {record["packet_id"]: index for index, record in enumerate(submitted, 1)}
    put("adjudication_import_manifest.json", {
        "input_inventory": input_inventory,
        "input_record_count": 70,
        "canonical_record_count": 70,
        "canonical_order_authority": str(CORPUS_RUN / "frozen_neutral_review_packets.jsonl"),
        "identity_key": "packet_id",
        "verbatim_fields": FIELDS,
        "field_values_normalized": False,
        "labels_reinterpreted": False,
        "labels_repaired": False,
        "pass_a_accessed_for_label_repair": False,
        "tier_or_gate_accessed_for_label_repair": False,
        "records": [
            {
                "packet_id": row["packet_id"],
                "canonical_record_order": index,
                "submitted_record_order": source_order_by_id[row["packet_id"]],
                "source_batch_id": trace_by_id[row["packet_id"]]["batch_id"],
                "source_batch_record_order": trace_by_id[row["packet_id"]]["batch_record_order"],
                "input_record_text_sha256": trace_by_id[row["packet_id"]]["input_record_text_sha256"],
                "submitted_field_value_sha256": trace_by_id[row["packet_id"]]["submitted_field_value_sha256"],
                "canonical_record_sha256": digest(canonical(row)),
            }
            for index, row in enumerate(ordered, 1)
        ],
    })
    after = protected_state()
    require(before == after, "Historical or evaluator workspace artifact changed")
    safety = {
        **ZERO_CALLS,
        **ZERO_MODIFICATIONS,
        "offline_only": True,
        "canonical_source_modified": False,
        "existing_review_batches_modified": False,
        "blinded_views_modified": False,
        "isolated_evaluator_workspace_modified": False,
        "historical_assets_modified": False,
        "git_mutation_invoked": False,
        "protected_hashes_before": before,
        "protected_hashes_after": after,
    }
    put("scientific_state_safety_audit.json", safety)
    put("freeze_manifest.json", {
        **hashes,
        "hash_algorithm": "sha256(exact canonical ordered UTF-8 JSONL bytes)",
        "canonical_serialization": "sort_keys=true; ensure_ascii=false; compact separators; LF after each record",
        "corpus": "pass_b_relevance_adjudications.jsonl",
        "record_count": 70,
        "ordering": "frozen review-corpus packet order",
        "append_only": True,
        "pass_b_corpus_frozen": True,
        "pass_a_pass_b_merged": False,
        "metrics_embargo_active": True,
        "next_stage": "deterministic packet_id merge and primary-results corpus freeze before metrics",
    })
    summary = {
        "status": "completed",
        **hashes,
        **identity,
        **ZERO_CALLS,
        **ZERO_MODIFICATIONS,
        "schema_valid": True,
        "reviewer_type_valid": True,
        "heldout_metrics_calculated": False,
        "relevance_distribution_reported": False,
        "pass_a_pass_b_merged": False,
        "canonical_source_modified": False,
        "existing_review_batches_modified": False,
        "blinded_views_modified": False,
        "isolated_evaluator_workspace_modified": False,
        "historical_assets_modified": False,
        "pass_b_corpus_frozen": True,
    }
    put("summary.json", summary)
    checks = {
        "four_upstream_roots_verified": True,
        "workspace_manifest_and_batches_verified": True,
        "packet_identity_bijection": True,
        "canonical_order_preserved": True,
        "batch_order_and_identity_preserved": True,
        "schema_valid": True,
        "reviewer_type_valid": True,
        "all_submitted_field_values_preserved": roundtrip == ordered,
        "pass_b_hash_valid": digest(corpus) == pass_b_hash,
        "historical_and_workspace_assets_unchanged": before == after,
        "offline_no_new_adjudication": True,
        "metrics_embargo_preserved": True,
        "pass_a_pass_b_not_merged": True,
    }
    put("validation.json", {"status": "PASS", "checks": checks})
    files = [
        {"path": name, "sha256": digest(data), "bytes": len(data),
         "record_count": len(data.splitlines()) if name.endswith(".jsonl") else 1}
        for name, data in sorted(outputs.items())
    ]
    put("manifest.json", {
        "required_artifact_count": len(REQUIRED),
        "required_artifacts": REQUIRED,
        "all_required_present": True,
        "files": files,
        **hashes,
        **ZERO_CALLS,
    })
    return outputs


def main() -> None:
    outputs = generate()
    if RUN.exists():
        require(RUN.is_dir() and not RUN.is_symlink(), "Existing PASS B freeze path is invalid")
        require({path.name for path in RUN.iterdir()} == set(outputs),
                "Existing PASS B freeze membership differs; refusing to modify")
        require(all((RUN / name).read_bytes() == data for name, data in outputs.items()),
                "Existing PASS B freeze differs; refusing to overwrite")
    else:
        RUN.mkdir()
        for name, data in outputs.items():
            with (RUN / name).open("xb") as handle:
                handle.write(data)
    print(outputs["summary.json"].decode("utf-8"))


if __name__ == "__main__":
    main()
