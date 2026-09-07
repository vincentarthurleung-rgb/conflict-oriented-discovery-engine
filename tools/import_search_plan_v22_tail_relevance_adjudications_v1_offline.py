#!/usr/bin/env python3
"""Import the submitted 15-packet tail relevance adjudication overlay offline."""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import re
import subprocess


ROOT = Path(__file__).resolve().parents[1]
SOURCE_RUN = ROOT / "runs/20260907_search_plan_v22_recall_tail_probe_v1"
PACKAGING_RUN = ROOT / "runs/20260907_search_plan_v22_recall_tail_relevance_packaging_v1_offline"
PREVIOUS_PACKAGING = ROOT / "runs/20260906_retrieval_relevance_audit_packaging_v1_offline"
SOURCE = SOURCE_RUN / "tail_review_packets.jsonl"
OUTPUT = ROOT / "runs/20260907_search_plan_v22_recall_tail_relevance_adjudication_v1_offline"
LIST_FIELDS = {"matched_target_components", "mismatched_target_components",
               "fulltext_resolved_fields", "remaining_unresolved_fields"}
RELEVANCE = {"DIRECTLY_RELEVANT", "PLAUSIBLY_RELEVANT_FULLTEXT_REQUIRED",
             "RELATED_BUT_WRONG_PROPOSITION", "WRONG_ENDPOINT", "WRONG_ENTITY",
             "WRONG_EVIDENCE_MODE", "WRONG_THERAPY", "TOPIC_ONLY",
             "INSUFFICIENT_SOURCE_EVIDENCE"}
ACQUISITION = {"JUSTIFIED", "BORDERLINE_BUT_JUSTIFIED", "NOT_JUSTIFIED",
               "UNDETERMINABLE_FROM_PRESERVED_PREACQUISITION_EVIDENCE"}
REQUIRED = ["submitted_adjudications.txt", "adjudications.jsonl", "tail_relevance_metrics.json",
            "per_case_metrics.jsonl", "depth_bin_relevance_yield.jsonl", "schema_compatibility.json",
            "baseline.json", "safety_audit.json", "validation.json", "summary.json", "manifest.json"]


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def objsha(value: object) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def readl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def writej(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")


def writel(path: Path, rows: list[dict]) -> None:
    path.write_text("".join(json.dumps(row, sort_keys=True, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")


def tree_hash(path: Path) -> dict:
    rows = [(str(item.relative_to(path)), sha(item)) for item in sorted(path.rglob("*")) if item.is_file()]
    return {"file_count": len(rows), "sha256": objsha(rows)}


def parse_submission(text: str) -> list[dict]:
    records = []
    for block in re.split(r"\n(?=packet_id:\s*)", text.replace("\r\n", "\n").strip()):
        record: dict[str, object] = {field: [] for field in LIST_FIELDS}
        current_list = None
        for line in block.splitlines():
            if line.startswith("- ") and current_list:
                record[current_list].append(line[2:].strip())
                continue
            match = re.match(r"^([a-z_]+):(?:\s*(.*))?$", line)
            if not match:
                if line.strip():
                    raise ValueError(f"Unparseable submission line: {line!r}")
                continue
            key, raw = match.groups()
            current_list = key if key in LIST_FIELDS else None
            if current_list:
                if raw and raw.strip() != "[]":
                    raise ValueError(f"List field {key} must be [] or use list items")
            else:
                record[key] = raw.strip() if raw else None
        records.append(record)
    return records


def fraction(n: int, d: int) -> dict:
    return {"numerator": n, "denominator": d, "value": n / d if d else None}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("input", type=Path)
    args = parser.parse_args()
    OUTPUT.mkdir(parents=True, exist_ok=True)
    unexpected = [p.name for p in OUTPUT.iterdir() if p.name not in REQUIRED]
    if unexpected:
        raise RuntimeError(f"Output run contains unrelated files: {unexpected}")

    source_before = tree_hash(SOURCE_RUN)
    packaging_before = tree_hash(PACKAGING_RUN)
    protected = [ROOT / "tools/search_plan_v22_candidate_gates.py",
                 ROOT / "runs/20260906_search_plan_v21_retrieval_calibration_pilot_v1/frozen_search_plans.jsonl",
                 ROOT / "runs/20260906_search_plan_v21_retrieval_calibration_pilot_v1/frozen_query_variants.jsonl"]
    protected_before = {str(p.relative_to(ROOT)): sha(p) for p in protected}
    packets = readl(SOURCE)
    expected_ids = [row["packet_id"] for row in packets]
    raw_bytes = args.input.read_bytes()
    raw_digest = hashlib.sha256(raw_bytes).hexdigest()
    submitted = parse_submission(raw_bytes.decode("utf-8"))
    submitted_ids = [row.get("packet_id") for row in submitted]
    if submitted_ids != expected_ids:
        raise ValueError("Submission packet identity/order does not exactly match the 15 frozen tail packets")
    if len(set(submitted_ids)) != 15:
        raise ValueError("Expected exactly 15 unique submitted packet IDs")

    taxonomy = set(json.loads((PREVIOUS_PACKAGING / "contaminant_taxonomy.json").read_text())["labels"])
    normalized = []
    for supplied, packet in zip(submitted, packets):
        packet_id = supplied["packet_id"]
        if supplied.get("relevance_state") not in RELEVANCE:
            raise ValueError(f"Invalid relevance state for {packet_id}")
        if supplied.get("acquisition_decision") not in ACQUISITION:
            raise ValueError(f"Invalid acquisition decision for {packet_id}")
        contaminant = supplied.get("contaminant_class") or None
        if contaminant is not None and contaminant not in taxonomy:
            raise ValueError(f"Invalid contaminant class for {packet_id}")
        expected_identity = packet["adjudication"]
        normalized.append({
            "packet_id": packet_id, "case_id": expected_identity["case_id"],
            "publication_id": expected_identity["publication_id"],
            "relevance_state": supplied["relevance_state"],
            "acquisition_decision": supplied["acquisition_decision"],
            "matched_target_components": supplied["matched_target_components"],
            "mismatched_target_components": supplied["mismatched_target_components"],
            "fulltext_resolved_fields": supplied["fulltext_resolved_fields"],
            "remaining_unresolved_fields": supplied["remaining_unresolved_fields"],
            "contaminant_class": contaminant, "reviewer_rationale": supplied.get("rationale"),
            "confidence": supplied.get("confidence"), "reviewer_type": supplied.get("reviewer_type"),
            "reviewer_id_or_label": None, "timestamp": None,
            "confidence_representation": "categorical_as_submitted",
            "source_submission_sha256": raw_digest, "source_packet_sha256": objsha(packet),
            "audit_scope": "recall_tail_relevance_and_acquisition_decision_only",
        })

    (OUTPUT / "submitted_adjudications.txt").write_bytes(raw_bytes)
    writel(OUTPUT / "adjudications.jsonl", normalized)
    by_id = {row["packet_id"]: packet for row, packet in zip(normalized, packets)}
    relevant_states = {"DIRECTLY_RELEVANT", "PLAUSIBLY_RELEVANT_FULLTEXT_REQUIRED"}
    acceptable = {"JUSTIFIED", "BORDERLINE_BUT_JUSTIFIED"}

    per_case = []
    for case_id in sorted({row["case_id"] for row in normalized}):
        rows = [row for row in normalized if row["case_id"] == case_id]
        direct = sum(row["relevance_state"] == "DIRECTLY_RELEVANT" for row in rows)
        per_case.append({"case_id": case_id, "adjudicated_tail_acquisitions": len(rows),
                         "directly_relevant": direct,
                         "retrieval_relevant": sum(row["relevance_state"] in relevant_states for row in rows),
                         "acquisition_acceptable": sum(row["acquisition_decision"] in acceptable for row in rows),
                         "direct_relevance_rate": fraction(direct, len(rows)),
                         "relevance_state_counts": dict(Counter(row["relevance_state"] for row in rows)),
                         "acquisition_decision_counts": dict(Counter(row["acquisition_decision"] for row in rows)),
                         "max_depth_with_direct_relevance": max((by_id[row["packet_id"]]["retrieval_provenance"]["metadata_depth"]
                                                                 for row in rows if row["relevance_state"] == "DIRECTLY_RELEVANT"), default=None)})
    writel(OUTPUT / "per_case_metrics.jsonl", per_case)

    depth_rows = []
    for case_id in sorted({row["case_id"] for row in normalized}):
        for label, low, high in [("61-90", 61, 90), ("91-120", 91, 120)]:
            rows = [row for row in normalized if row["case_id"] == case_id and
                    low <= by_id[row["packet_id"]]["retrieval_provenance"]["metadata_depth"] <= high]
            depth_rows.append({"case_id": case_id, "depth_bin": label, "adjudicated_tail_acquisitions": len(rows),
                               "directly_relevant": sum(row["relevance_state"] == "DIRECTLY_RELEVANT" for row in rows),
                               "retrieval_relevant": sum(row["relevance_state"] in relevant_states for row in rows),
                               "packet_ids": [row["packet_id"] for row in rows],
                               "scientific_recall_or_saturation_inferred": False})
    writel(OUTPUT / "depth_bin_relevance_yield.jsonl", depth_rows)

    tiers = Counter(by_id[row["packet_id"]]["pre_acquisition_evidence"]["tier_state"] for row in normalized)
    tier_direct = Counter(by_id[row["packet_id"]]["pre_acquisition_evidence"]["tier_state"]
                          for row in normalized if row["relevance_state"] == "DIRECTLY_RELEVANT")
    metrics = {"adjudicated_count": len(normalized),
               "directly_relevant_count": sum(row["relevance_state"] == "DIRECTLY_RELEVANT" for row in normalized),
               "retrieval_relevant_count": sum(row["relevance_state"] in relevant_states for row in normalized),
               "acquisition_acceptable_count": sum(row["acquisition_decision"] in acceptable for row in normalized),
               "direct_relevance_rate": fraction(sum(row["relevance_state"] == "DIRECTLY_RELEVANT" for row in normalized), len(normalized)),
               "relevance_state_counts": dict(Counter(row["relevance_state"] for row in normalized)),
               "acquisition_decision_counts": dict(Counter(row["acquisition_decision"] for row in normalized)),
               "tier_direct_relevance": {tier: fraction(tier_direct[tier], count) for tier, count in sorted(tiers.items())},
               "max_depth_with_direct_relevance": max(by_id[row["packet_id"]]["retrieval_provenance"]["metadata_depth"]
                                                       for row in normalized if row["relevance_state"] == "DIRECTLY_RELEVANT"),
               "scientific_recall_completeness_claimed": False,
               "search_plan_or_budget_changed": False,
               "interpretation": "Submitted adjudications confirm relevant yield in the 61-120 tail; this overlay does not tune the frozen plan or budget."}
    writej(OUTPUT / "tail_relevance_metrics.json", metrics)
    writej(OUTPUT / "schema_compatibility.json", {
        "status": "COMPATIBLE_WITH_DOCUMENTED_CONFIDENCE_EXTENSION",
        "previous_schema_ref": str((PREVIOUS_PACKAGING / "retrieval_relevance_adjudication_v1.schema.json").relative_to(ROOT)),
        "previous_schema_sha256": sha(PREVIOUS_PACKAGING / "retrieval_relevance_adjudication_v1.schema.json"),
        "identity_and_decision_enums_valid": True,
        "extension_reason": "Submitted confidence is categorical; the previous schema permits numeric confidence only.",
        "normalization_policy": "Preserve categorical confidence verbatim without inventing a numeric conversion.",
        "reviewer_id_and_timestamp_policy": "Preserve unavailable fields as null.",
    })

    source_after = tree_hash(SOURCE_RUN)
    packaging_after = tree_hash(PACKAGING_RUN)
    protected_after = {str(p.relative_to(ROOT)): sha(p) for p in protected}
    checks = {"exact_packet_set_and_order": submitted_ids == expected_ids,
              "unique_packet_ids_15": len(set(submitted_ids)) == 15,
              "packet_identity_join_complete": all(row["case_id"] and row["publication_id"] for row in normalized),
              "valid_relevance_states": all(row["relevance_state"] in RELEVANCE for row in normalized),
              "valid_acquisition_decisions": all(row["acquisition_decision"] in ACQUISITION for row in normalized),
              "valid_contaminant_classes": all(row["contaminant_class"] is None or row["contaminant_class"] in taxonomy for row in normalized),
              "rationales_present": all(row["reviewer_rationale"] for row in normalized),
              "reviewer_types_preserved": all(row["reviewer_type"] == "model_retrieval_adjudicator" for row in normalized),
              "categorical_confidence_preserved": all(row["confidence"] in {"high", "moderate-high"} for row in normalized),
              "missing_identity_and_timestamp_not_invented": all(row["reviewer_id_or_label"] is None and row["timestamp"] is None for row in normalized),
              "source_tail_run_unchanged": source_before == source_after,
              "neutral_packaging_unchanged": packaging_before == packaging_after,
              "frozen_search_assets_unchanged": protected_before == protected_after,
              "search_plan_or_budget_unchanged": not metrics["search_plan_or_budget_changed"],
              "no_recall_completeness_claim": not metrics["scientific_recall_completeness_claimed"],
              "offline_only": True}
    writej(OUTPUT / "validation.json", {"status": "PASS" if all(checks.values()) else "FAIL", "checks": checks})
    writej(OUTPUT / "safety_audit.json", {"network_calls": 0, "provider_calls": 0, "llm_calls": 0,
           "downloads": 0, "experimental_extraction_calls": 0, "search_plan_tuning_performed": False,
           "case_specific_fix_performed": False, "adjudication_generated_by_importer": False,
           "user_supplied_model_adjudications_imported": len(normalized), "historical_assets_modified": False})
    writej(OUTPUT / "baseline.json", {"source_tail_packets_ref": str(SOURCE.relative_to(ROOT)),
           "source_tail_packets_sha256": sha(SOURCE), "source_tail_run_tree": source_before,
           "source_packaging_run_ref": str(PACKAGING_RUN.relative_to(ROOT)), "source_packaging_tree": packaging_before,
           "submission_sha256": raw_digest, "git_head": subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT,
           capture_output=True, text=True, check=True).stdout.strip()})
    summary = {"status": "completed" if all(checks.values()) else "failed",
               "completion_state": "TAIL_RELEVANCE_ADJUDICATIONS_INGESTED", **metrics,
               "network_calls": 0, "provider_calls": 0, "llm_calls": 0,
               "experimental_extraction_calls": 0, "historical_assets_modified": False}
    writej(OUTPUT / "summary.json", summary)
    files = [{"path": p.name, "sha256": sha(p), "bytes": p.stat().st_size,
              "record_count": len(readl(p)) if p.suffix == ".jsonl" else 1}
             for p in sorted(OUTPUT.iterdir()) if p.is_file() and p.name != "manifest.json"]
    writej(OUTPUT / "manifest.json", {"required_artifact_count": len(REQUIRED), "files": files,
           "source_submission_sha256": raw_digest, "network_calls": 0, "provider_calls": 0, "llm_calls": 0})
    print(json.dumps(summary, indent=2))
    if not all(checks.values()):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
