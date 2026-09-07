#!/usr/bin/env python3
"""Import user-supplied retrieval adjudications as a read-only packet overlay."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PACKAGING = ROOT / "runs/20260906_retrieval_relevance_audit_packaging_v1_offline"
PILOT = ROOT / "runs/20260906_search_plan_v21_retrieval_calibration_pilot_v1"
OUTPUT: Path
RELEVANCE = {
    "DIRECTLY_RELEVANT", "PLAUSIBLY_RELEVANT_FULLTEXT_REQUIRED",
    "RELATED_BUT_WRONG_PROPOSITION", "WRONG_ENDPOINT", "WRONG_ENTITY",
    "WRONG_EVIDENCE_MODE", "WRONG_THERAPY", "TOPIC_ONLY",
    "INSUFFICIENT_SOURCE_EVIDENCE",
}
ACQUISITION = {
    "JUSTIFIED", "BORDERLINE_BUT_JUSTIFIED", "NOT_JUSTIFIED",
    "UNDETERMINABLE_FROM_PRESERVED_PREACQUISITION_EVIDENCE",
}
LIST_FIELDS = {
    "matched_target_components", "mismatched_target_components",
    "fulltext_resolved_fields", "remaining_unresolved_fields",
}


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.write_text("".join(json.dumps(row, sort_keys=True, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")


def tree_hash(path: Path) -> dict:
    rows = [(str(item.relative_to(path)), sha(item)) for item in sorted(path.rglob("*")) if item.is_file()]
    digest = hashlib.sha256(json.dumps(rows, separators=(",", ":")).encode()).hexdigest()
    return {"file_count": len(rows), "sha256": digest}


def parse_submission(text: str) -> list[dict]:
    blocks = re.split(r"\n(?=packet_id:\s*)", text.strip())
    records = []
    for block in blocks:
        record: dict[str, object] = {field: [] for field in LIST_FIELDS}
        current_list = None
        for line in block.splitlines():
            if line.startswith("- ") and current_list:
                record[current_list].append(line[2:].strip())
                continue
            match = re.match(r"^([a-z_]+):(?:\s*(.*))?$", line)
            if not match:
                continue
            key, raw = match.groups()
            current_list = key if key in LIST_FIELDS else None
            if current_list:
                if raw and raw.strip() != "[]":
                    raise ValueError(f"List field {key} must use list items")
            else:
                record[key] = raw.strip() if raw else None
        records.append(record)
    return records


def fraction(numerator: int, denominator: int) -> dict:
    return {"numerator": numerator, "denominator": denominator, "value": numerator / denominator if denominator else None}


def write_completed_corpus_metrics(cumulative: list[dict], packets: list[dict]) -> None:
    by_packet = {row["packet_id"]: row for row in packets}
    relevant = {"DIRECTLY_RELEVANT", "PLAUSIBLY_RELEVANT_FULLTEXT_REQUIRED"}
    acceptable = {"JUSTIFIED", "BORDERLINE_BUT_JUSTIFIED"}
    tier_a = [row for row in cumulative if by_packet[row["packet_id"]]["pre_acquisition_evidence"]["tier_state"] == "TIER_A_HIGH_CONFIDENCE_ACQUIRE"]
    tier_b = [row for row in cumulative if by_packet[row["packet_id"]]["pre_acquisition_evidence"]["tier_state"] == "TIER_B_ACQUIRE_TO_RESOLVE"]
    tier_b_useful = [row for row in tier_b if row["acquisition_decision"] in acceptable and (row["fulltext_resolved_fields"] or by_packet[row["packet_id"]]["pre_acquisition_evidence"]["unresolved_fields_requiring_fulltext"])]
    metrics = {
        "status": "FINAL_ALL_79_ADJUDICATED",
        "adjudicated_count": len(cumulative),
        "tier_a_acquisition_precision": fraction(sum(row["acquisition_decision"] == "JUSTIFIED" for row in tier_a), len(tier_a)),
        "tier_a_acquisition_acceptability": fraction(sum(row["acquisition_decision"] in acceptable for row in tier_a), len(tier_a)),
        "tier_b_direct_relevance_rate": fraction(sum(row["relevance_state"] == "DIRECTLY_RELEVANT" for row in tier_b), len(tier_b)),
        "tier_b_utility_rate": fraction(len(tier_b_useful), len(tier_b)),
        "overall_acquisition_justification_rate": fraction(sum(row["acquisition_decision"] == "JUSTIFIED" for row in cumulative), len(cumulative)),
        "overall_acquisition_acceptability": fraction(sum(row["acquisition_decision"] in acceptable for row in cumulative), len(cumulative)),
        "overall_retrieval_relevance_rate": fraction(sum(row["relevance_state"] in relevant for row in cumulative), len(cumulative)),
        "retrieval_relevance_numerator_states": sorted(relevant),
        "tier_b_utility_rule": "JUSTIFIED or BORDERLINE_BUT_JUSTIFIED and fulltext resolved, or was needed to attempt resolution of, a preserved Tier B uncertainty",
    }
    write_json(OUTPUT / "final_corpus_quality_metrics.json", metrics)

    case_rows = []
    for case_id in sorted({row["case_id"] for row in cumulative}):
        rows = [row for row in cumulative if row["case_id"] == case_id]
        arows = [row for row in rows if by_packet[row["packet_id"]]["pre_acquisition_evidence"]["tier_state"] == "TIER_A_HIGH_CONFIDENCE_ACQUIRE"]
        brows = [row for row in rows if by_packet[row["packet_id"]]["pre_acquisition_evidence"]["tier_state"] == "TIER_B_ACQUIRE_TO_RESOLVE"]
        useful = [row for row in brows if row["acquisition_decision"] in acceptable and (row["fulltext_resolved_fields"] or by_packet[row["packet_id"]]["pre_acquisition_evidence"]["unresolved_fields_requiring_fulltext"])]
        rc = Counter(row["relevance_state"] for row in rows); ac = Counter(row["acquisition_decision"] for row in rows)
        case_rows.append({"case_id": case_id, "acquired_count": len(rows), "tier_a_acquired": len(arows), "tier_b_acquired": len(brows), "directly_relevant": rc["DIRECTLY_RELEVANT"], "plausibly_relevant": rc["PLAUSIBLY_RELEVANT_FULLTEXT_REQUIRED"], "related_wrong_proposition": rc["RELATED_BUT_WRONG_PROPOSITION"], "wrong_endpoint": rc["WRONG_ENDPOINT"], "wrong_entity": rc["WRONG_ENTITY"], "wrong_evidence_mode": rc["WRONG_EVIDENCE_MODE"], "wrong_therapy": rc["WRONG_THERAPY"], "topic_only": rc["TOPIC_ONLY"], "insufficient_source": rc["INSUFFICIENT_SOURCE_EVIDENCE"], "acquisition_justified": ac["JUSTIFIED"], "acquisition_borderline_justified": ac["BORDERLINE_BUT_JUSTIFIED"], "acquisition_not_justified": ac["NOT_JUSTIFIED"], "relevance_state_counts": dict(rc), "acquisition_decision_counts": dict(ac), "tier_a_precision": fraction(sum(row["acquisition_decision"] == "JUSTIFIED" for row in arows), len(arows)), "tier_b_utility": fraction(len(useful), len(brows)), "overall_acquisition_acceptability": fraction(sum(row["acquisition_decision"] in acceptable for row in rows), len(rows))})
    write_jsonl(OUTPUT / "final_case_quality_metrics.jsonl", case_rows)

    variant_rows: dict[tuple[str, str], list[dict]] = {(row["case_id"], row["query_variant_id"]): [] for row in read_jsonl(PILOT / "query_variant_contribution.jsonl")}
    family_rows: dict[tuple[str, str], list[dict]] = {(row["case_id"], row["query_family_id"]): [] for row in read_jsonl(PILOT / "query_family_contribution.jsonl")}
    for row in cumulative:
        packet = by_packet[row["packet_id"]]; provenance = packet["retrieval_provenance"]
        for variant_id in provenance["query_variants"]:
            variant_rows.setdefault((row["case_id"], variant_id), []).append({"decision": row, "packet": packet, "unique": provenance["unique_contribution_status"].get(variant_id, False)})
        for family_id in provenance["query_families"]:
            family_rows.setdefault((row["case_id"], family_id), []).append({"decision": row, "packet": packet, "unique": len(provenance["query_families"]) == 1})
    def contribution_rows(groups: dict, id_field: str) -> list[dict]:
        output = []
        for (case_id, identifier), rows in sorted(groups.items()):
            unique = [x for x in rows if x["unique"]]
            output.append({"case_id": case_id, id_field: identifier, "acquired_assignments": len(rows), "unique_acquired_additions": len(unique), "relevant_unique_additions": sum(x["decision"]["relevance_state"] in relevant for x in unique), "noise_unique_additions": sum(x["decision"]["relevance_state"] not in relevant for x in unique), "tier_a_justified_unique_additions": sum(x["packet"]["pre_acquisition_evidence"]["tier_state"] == "TIER_A_HIGH_CONFIDENCE_ACQUIRE" and x["decision"]["acquisition_decision"] == "JUSTIFIED" for x in unique), "tier_b_useful_unique_additions": sum(x["packet"]["pre_acquisition_evidence"]["tier_state"] == "TIER_B_ACQUIRE_TO_RESOLVE" and x["decision"]["acquisition_decision"] in acceptable for x in unique), "packet_ids": [x["decision"]["packet_id"] for x in rows]})
        return output
    write_jsonl(OUTPUT / "final_query_variant_contribution.jsonl", contribution_rows(variant_rows, "query_variant_id"))
    write_jsonl(OUTPUT / "final_query_family_contribution.jsonl", contribution_rows(family_rows, "query_family_id"))

    depth = {row["packet_id"]: row for row in read_jsonl(PACKAGING / "retrieval_depth_join_map.jsonl")}
    curves = []
    for case_id in sorted({row["case_id"] for row in cumulative}):
        rows = sorted((row for row in cumulative if row["case_id"] == case_id), key=lambda row: (depth[row["packet_id"]]["first_query_execution_order"], depth[row["packet_id"]]["retrieval_rank_in_first_query"] or 10**9, row["packet_id"]))
        for index, row in enumerate(rows, 1):
            prefix = rows[:index]
            curves.append({"case_id": case_id, "depth_index": index, "packet_id": row["packet_id"], "first_query_execution_order": depth[row["packet_id"]]["first_query_execution_order"], "retrieval_rank_in_first_query": depth[row["packet_id"]]["retrieval_rank_in_first_query"], "cumulative_retrieval_relevant": sum(x["relevance_state"] in relevant for x in prefix), "cumulative_acquisition_acceptable": sum(x["acquisition_decision"] in acceptable for x in prefix), "scientific_saturation_inferred": False})
    write_jsonl(OUTPUT / "final_retrieval_depth_yield_curves.jsonl", curves)


def main() -> None:
    global OUTPUT
    parser = argparse.ArgumentParser()
    parser.add_argument("input", type=Path)
    parser.add_argument("--batch", type=int, choices=range(1, 6), default=1)
    args = parser.parse_args()
    OUTPUT = ROOT / f"runs/20260907_retrieval_relevance_adjudication_batch_{args.batch:02d}_v1_offline"
    OUTPUT.mkdir(parents=True, exist_ok=True)
    packaging_before = tree_hash(PACKAGING)
    raw_bytes = args.input.read_bytes()
    raw = raw_bytes.decode("utf-8")
    raw_digest = hashlib.sha256(raw_bytes).hexdigest()
    submitted = parse_submission(raw)
    batch = read_jsonl(PACKAGING / f"review_batch_{args.batch:02d}.jsonl")
    packets = {row["packet_id"]: row for row in batch}
    expected_ids = [row["packet_id"] for row in batch]
    submitted_ids = [row.get("packet_id") for row in submitted]
    if submitted_ids != expected_ids:
        raise ValueError(f"Submission packet order/identity does not exactly match Batch {args.batch}")
    if len(set(submitted_ids)) != len(submitted_ids):
        raise ValueError("Duplicate packet_id in submission")

    normalized = []
    contaminant_labels = set(json.loads((PACKAGING / "contaminant_taxonomy.json").read_text())["labels"])
    for row in submitted:
        packet = packets[row["packet_id"]]
        if row.get("relevance_state") not in RELEVANCE:
            raise ValueError(f"Invalid relevance_state for {row['packet_id']}")
        if row.get("acquisition_decision") not in ACQUISITION:
            raise ValueError(f"Invalid acquisition_decision for {row['packet_id']}")
        contaminant = row.get("contaminant_class") or None
        if contaminant is not None and contaminant not in contaminant_labels:
            raise ValueError(f"Invalid contaminant_class for {row['packet_id']}")
        normalized.append({
            "packet_id": row["packet_id"],
            "case_id": packet["case_id"],
            "publication_id": f"pmid:{packet['publication_identity']['pmid']}",
            "relevance_state": row["relevance_state"],
            "acquisition_decision": row["acquisition_decision"],
            "matched_target_components": row["matched_target_components"],
            "mismatched_target_components": row["mismatched_target_components"],
            "fulltext_resolved_fields": row["fulltext_resolved_fields"],
            "remaining_unresolved_fields": row["remaining_unresolved_fields"],
            "contaminant_class": contaminant,
            "reviewer_rationale": row.get("rationale"),
            "confidence": row.get("confidence"),
            "confidence_representation": "categorical_as_submitted",
            "reviewer_type": row.get("reviewer_type"),
            "reviewer_id_or_label": None,
            "timestamp": None,
            "source_submission_sha256": raw_digest,
            "source_packet_sha256": hashlib.sha256(json.dumps(packet, sort_keys=True, ensure_ascii=False).encode()).hexdigest(),
            "audit_scope": "retrieval_relevance_and_acquisition_decision_only",
        })

    raw_path = OUTPUT / "submitted_adjudications.txt"
    raw_path.write_bytes(raw_bytes)
    write_jsonl(OUTPUT / "adjudications.jsonl", normalized)
    all_packets = read_jsonl(PACKAGING / "retrieval_relevance_review_packets.jsonl")
    tier = {row["packet_id"]: row["pre_acquisition_evidence"]["tier_state"] for row in all_packets}
    cumulative = []
    prior_batches_present = []
    prior_overlay_refs = []
    for batch_number in range(1, args.batch):
        prior_path = ROOT / f"runs/20260907_retrieval_relevance_adjudication_batch_{batch_number:02d}_v1_offline/adjudications.jsonl"
        if prior_path.is_file():
            cumulative.extend(read_jsonl(prior_path))
            prior_batches_present.append(batch_number)
            prior_overlay_refs.append({"batch": batch_number, "path": str(prior_path.relative_to(ROOT)), "sha256": sha(prior_path)})
    cumulative.extend(normalized)
    if len({row["packet_id"] for row in cumulative}) != len(cumulative):
        raise ValueError("Duplicate packet_id across cumulative batch overlays")
    write_jsonl(OUTPUT / "cumulative_adjudications.jsonl", cumulative)
    metrics = {
        "scope": f"batch_{args.batch:02d}_only_partial_79_packet_audit",
        "adjudicated_count": len(normalized),
        "relevance_state_counts": dict(Counter(row["relevance_state"] for row in normalized)),
        "acquisition_decision_counts": dict(Counter(row["acquisition_decision"] for row in normalized)),
        "tier_a_adjudicated": sum(tier[row["packet_id"]] == "TIER_A_HIGH_CONFIDENCE_ACQUIRE" for row in normalized),
        "tier_b_adjudicated": sum(tier[row["packet_id"]] == "TIER_B_ACQUIRE_TO_RESOLVE" for row in normalized),
        "corpus_total_packets": 79,
        "prior_batches_included_in_cumulative": prior_batches_present,
        "cumulative_adjudicated_count": len(cumulative),
        "cumulative_remaining_unadjudicated": 79 - len(cumulative),
        "cumulative_relevance_state_counts": dict(Counter(row["relevance_state"] for row in cumulative)),
        "cumulative_acquisition_decision_counts": dict(Counter(row["acquisition_decision"] for row in cumulative)),
        "corpus_level_metrics_final": len(cumulative) == 79,
    }
    write_json(OUTPUT / "batch_metrics.json", metrics)
    write_json(OUTPUT / "schema_compatibility.json", {
        "packaging_schema_ref": str((PACKAGING / "retrieval_relevance_adjudication_v1.schema.json").relative_to(ROOT)),
        "packaging_schema_sha256": sha(PACKAGING / "retrieval_relevance_adjudication_v1.schema.json"),
        "base_schema_validation": "EXTENSION_REQUIRED",
        "extension_reason": "submitted confidence uses categorical values while the packaging schema currently permits numeric confidence only",
        "normalization_policy": "preserve categorical confidence verbatim; do not invent a numeric conversion",
        "missing_reviewer_id_policy": "preserve as null",
        "missing_timestamp_policy": "preserve as null",
        "relevance_and_acquisition_enums_valid": True,
    })
    if len(cumulative) == 79:
        write_completed_corpus_metrics(cumulative, all_packets)
    packaging_after = tree_hash(PACKAGING)
    checks = {
        "exact_batch_packet_set_and_order": submitted_ids == expected_ids,
        "unique_packet_ids": len(set(submitted_ids)) == len(expected_ids),
        "valid_relevance_states": all(row["relevance_state"] in RELEVANCE for row in normalized),
        "valid_acquisition_decisions": all(row["acquisition_decision"] in ACQUISITION for row in normalized),
        "valid_contaminant_classes": all(row["contaminant_class"] is None or row["contaminant_class"] in contaminant_labels for row in normalized),
        "packet_identity_join_complete": all(row["case_id"] and row["publication_id"] for row in normalized),
        "rationales_present": all(row["reviewer_rationale"] for row in normalized),
        "reviewer_types_present": all(row["reviewer_type"] for row in normalized),
        "submitted_confidence_preserved_without_conversion": all(row["confidence"] in {"high", "moderate-high"} for row in normalized),
        "missing_reviewer_identity_not_invented": all(row["reviewer_id_or_label"] is None for row in normalized),
        "missing_timestamps_not_invented": all(row["timestamp"] is None for row in normalized),
        "neutral_packaging_unchanged": packaging_before == packaging_after,
        "offline_only": True,
        "complete_corpus_metric_artifacts_present": len(cumulative) < 79 or all((OUTPUT / name).is_file() for name in ["final_corpus_quality_metrics.json", "final_case_quality_metrics.jsonl", "final_query_variant_contribution.jsonl", "final_query_family_contribution.jsonl", "final_retrieval_depth_yield_curves.jsonl"]),
    }
    write_json(OUTPUT / "validation.json", {"status": "PASS" if all(checks.values()) else "FAIL", "checks": checks})
    write_json(OUTPUT / "safety_audit.json", {
        "network_calls": 0, "provider_calls": 0, "llm_calls": 0, "downloads": 0,
        "adjudication_generated_by_this_importer": False,
        "user_supplied_model_adjudications_imported": len(normalized),
        "neutral_packaging_modified": packaging_before != packaging_after,
        "historical_assets_modified": False,
    })
    write_json(OUTPUT / "baseline.json", {
        "source_packaging_run": str(PACKAGING.relative_to(ROOT)),
        "source_packaging_tree": packaging_before,
        "source_batch_sha256": sha(PACKAGING / f"review_batch_{args.batch:02d}.jsonl"),
        "submission_sha256": sha(raw_path),
        "prior_adjudication_overlays": prior_overlay_refs,
        "git_head": subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True, check=True).stdout.strip(),
    })
    write_json(OUTPUT / "summary.json", {
        "completion_state": "RETRIEVAL_RELEVANCE_CORPUS_ADJUDICATION_COMPLETE" if len(cumulative) == 79 else f"RETRIEVAL_RELEVANCE_BATCH_{args.batch:02d}_ADJUDICATIONS_INGESTED",
        **metrics,
        "network_calls": 0, "provider_calls": 0, "llm_calls": 0,
        "neutral_packaging_modified": False,
    })
    files = []
    for path in sorted(OUTPUT.iterdir()):
        if path.name == "manifest.json" or not path.is_file():
            continue
        files.append({"path": path.name, "sha256": sha(path), "bytes": path.stat().st_size})
    write_json(OUTPUT / "manifest.json", {"files": files, "file_count_excluding_manifest": len(files)})
    print(json.dumps(json.loads((OUTPUT / "summary.json").read_text()), indent=2))


if __name__ == "__main__":
    main()
