#!/usr/bin/env python3
"""Import seven supplemental judgments and freeze the held-out budget offline."""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import re
import subprocess


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "runs/20260908_search_plan_v22_depth180_supplemental_relevance_packaging_v1_offline"
PRIOR = ROOT / "runs/20260908_search_plan_v22_depth180_relevance_adjudication_v1_offline"
FIRST_TAIL = ROOT / "runs/20260907_search_plan_v22_recall_tail_relevance_adjudication_v1_offline"
RUN = ROOT / "runs/20260909_search_plan_v22_depth180_supplemental_relevance_adjudication_v1_offline"
PACKETS = SOURCE / "supplemental_review_packets.jsonl"
LIST_FIELDS = {"matched_target_components", "mismatched_target_components",
               "fulltext_resolved_fields", "remaining_unresolved_fields"}
RELEVANCE = {"DIRECTLY_RELEVANT", "PLAUSIBLY_RELEVANT_FULLTEXT_REQUIRED",
             "RELATED_BUT_WRONG_PROPOSITION", "WRONG_ENDPOINT", "WRONG_ENTITY",
             "WRONG_EVIDENCE_MODE", "WRONG_THERAPY", "TOPIC_ONLY", "INSUFFICIENT_SOURCE_EVIDENCE"}
ACQUISITION = {"JUSTIFIED", "BORDERLINE_BUT_JUSTIFIED", "NOT_JUSTIFIED",
               "UNDETERMINABLE_FROM_PRESERVED_PREACQUISITION_EVIDENCE"}
ACCEPTABLE = {"JUSTIFIED", "BORDERLINE_BUT_JUSTIFIED"}
CALIBRATION_CASES = ["spv2_017", "spv2_026", "spv2_001", "spv2_016", "spv2_003", "spv2_004",
                     "spv2_006_REDESIGNED", "spv2_013_REDESIGNED"]
REQUIRED = ["supplemental_adjudications.jsonl", "supplemental_depth_joined_adjudications.jsonl",
            "balanced_depth_151_180_adjudications.jsonl", "source_packet_bijection.json", "schema_compatibility.json",
            "supplemental_metrics.json", "supplemental_case_metrics.jsonl", "depth_calibration_summary.json",
            "heldout_retrieval_budget_protocol_v1.json", "heldout_retrieval_budget_protocol_v1.md",
            "calibration_to_heldout_freeze_audit.json", "validation.json", "manifest.json", "summary.json",
            "scientific_state_safety_audit.json", "production_leakage_audit.json"]


def sha(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def objsha(value): return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
def readj(path): return json.loads(Path(path).read_text(encoding="utf-8"))
def readl(path): return [json.loads(x) for x in Path(path).read_text(encoding="utf-8").splitlines() if x]
def writej(path, value): Path(path).write_text(json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")
def writel(path, rows): Path(path).write_text("".join(json.dumps(x, sort_keys=True, ensure_ascii=False) + "\n" for x in rows), encoding="utf-8")
def rel(path): return str(Path(path).resolve().relative_to(ROOT))


def tree_hash(path):
    rows = [(str(p.relative_to(path)), sha(p)) for p in sorted(Path(path).rglob("*")) if p.is_file()]
    return {"file_count": len(rows), "sha256": objsha(rows)}


def protected_hashes():
    paths = [PACKETS, SOURCE / "supplemental_review_batch.md", SOURCE / "manifest.json",
             PRIOR / "depth_joined_adjudications.jsonl", PRIOR / "manifest.json",
             FIRST_TAIL / "depth_bin_relevance_yield.jsonl", FIRST_TAIL / "adjudications.jsonl",
             ROOT / "tools/search_plan_v22_candidate_gates.py",
             ROOT / "runs/20260906_search_plan_v21_retrieval_calibration_pilot_v1/frozen_search_plans.jsonl",
             ROOT / "runs/20260906_search_plan_v21_retrieval_calibration_pilot_v1/frozen_query_variants.jsonl"]
    return {rel(path): sha(path) for path in paths}


def parse_submission(text):
    text = text.replace("\r\n", "\n")
    pattern = re.compile(r"^-{10,}\n(rrsuppv1_\d{4})\n-{10,}\n(.*?)(?=^-{10,}\nrrsuppv1_\d{4}\n|^={10,})", re.M | re.S)
    records = []
    for packet_id, block in pattern.findall(text):
        record = {field: [] for field in LIST_FIELDS}; record["packet_id"] = packet_id; current = None
        for line in block.strip().splitlines():
            if line.startswith("- ") and current:
                record[current].append(line[2:].strip()); continue
            match = re.match(r"^([a-z_]+):(?:\s*(.*))?$", line)
            if not match:
                if line.strip(): raise ValueError(f"Unparseable adjudication line: {line!r}")
                continue
            key, raw = match.groups(); current = key if key in LIST_FIELDS else None
            if current:
                if raw and raw.strip() != "[]": raise ValueError(f"List field {key} must use list items")
            else: record[key] = raw.strip() if raw else None
        records.append(record)
    return records


def fraction(n, d): return {"numerator": n, "denominator": d, "value": n/d if d else None}


def rate_metrics(rows):
    n = len(rows); direct = sum(x["relevance_state"] == "DIRECTLY_RELEVANT" for x in rows)
    justified = sum(x["acquisition_decision"] == "JUSTIFIED" for x in rows)
    acceptable = sum(x["acquisition_decision"] in ACCEPTABLE for x in rows)
    return {"count": n, "directly_relevant_count": direct,
        "related_wrong_proposition_count": sum(x["relevance_state"] == "RELATED_BUT_WRONG_PROPOSITION" for x in rows),
        "justified_count": justified, "not_justified_count": sum(x["acquisition_decision"] == "NOT_JUSTIFIED" for x in rows),
        "acquisition_acceptable_count": acceptable, "direct_relevance_rate": fraction(direct, n),
        "acquisition_justification_rate": fraction(justified, n),
        "acquisition_acceptability_rate": fraction(acceptable, n)}


def main():
    parser = argparse.ArgumentParser(); parser.add_argument("input", type=Path); args = parser.parse_args()
    if RUN.exists() and any(p.name not in REQUIRED for p in RUN.iterdir()): raise RuntimeError("Output run contains unrelated files")
    RUN.mkdir(parents=True, exist_ok=True)
    source_before, prior_before, protected_before = tree_hash(SOURCE), tree_hash(PRIOR), protected_hashes()
    packets = readl(PACKETS); source_ids = [x["packet_id"] for x in packets]
    raw = args.input.read_bytes(); submission_sha = hashlib.sha256(raw).hexdigest()
    submitted = parse_submission(raw.decode("utf-8")); submitted_ids = [x["packet_id"] for x in submitted]
    if submitted_ids != source_ids or len(set(submitted_ids)) != 7:
        raise ValueError("Submission must match all seven source packets in frozen order")
    taxonomy = set(readj(ROOT / "runs/20260906_retrieval_relevance_audit_packaging_v1_offline/contaminant_taxonomy.json")["labels"])

    adjudications, joined = [], []
    for supplied, packet in zip(submitted, packets):
        pid = supplied["packet_id"]; contaminant = supplied.get("contaminant_class") or None
        if supplied.get("relevance_state") not in RELEVANCE: raise ValueError(f"Invalid relevance state: {pid}")
        if supplied.get("acquisition_decision") not in ACQUISITION: raise ValueError(f"Invalid acquisition decision: {pid}")
        if contaminant is not None and contaminant not in taxonomy: raise ValueError(f"Invalid contaminant: {pid}")
        identity = packet["adjudication"]
        row = {"packet_id": pid, "case_id": identity["case_id"], "publication_id": identity["publication_id"],
            "relevance_state": supplied["relevance_state"], "acquisition_decision": supplied["acquisition_decision"],
            "matched_target_components": supplied["matched_target_components"],
            "mismatched_target_components": supplied["mismatched_target_components"],
            "fulltext_resolved_fields": supplied["fulltext_resolved_fields"],
            "remaining_unresolved_fields": supplied["remaining_unresolved_fields"],
            "contaminant_class": contaminant, "reviewer_rationale": supplied.get("rationale"),
            "confidence": supplied.get("confidence"), "reviewer_type": supplied.get("reviewer_type"),
            "reviewer_id_or_label": None, "timestamp": None}
        adjudications.append(row)
        joined.append({**row, "metadata_depth": packet["retrieval_provenance"]["metadata_depth"],
            "depth_bin": "151-180", "tier_state": packet["pre_acquisition_evidence"]["tier_state"],
            "source_packet_sha256": objsha(packet), "source_submission_sha256": submission_sha,
            "sample_component": "balanced_supplemental_pmca_available_label_blind_selection"})
    writel(RUN / "supplemental_adjudications.jsonl", adjudications)
    writel(RUN / "supplemental_depth_joined_adjudications.jsonl", joined)
    writej(RUN / "source_packet_bijection.json", {"source_packet_count": 7, "submitted_adjudication_count": 7,
        "source_ordered_packet_ids": source_ids, "submitted_ordered_packet_ids": submitted_ids,
        "exact_identity_order_bijection": source_ids == submitted_ids,
        "missing_packet_ids": [], "extra_packet_ids": [], "source_packet_ref": rel(PACKETS),
        "source_packet_sha256": sha(PACKETS), "submission_sha256": submission_sha})
    prior_schema = ROOT / "runs/20260906_retrieval_relevance_audit_packaging_v1_offline/retrieval_relevance_adjudication_v1.schema.json"
    writej(RUN / "schema_compatibility.json", {"status": "COMPATIBLE_WITH_DOCUMENTED_CATEGORICAL_CONFIDENCE_EXTENSION",
        "prior_schema_ref": rel(prior_schema), "prior_schema_sha256": sha(prior_schema),
        "categorical_confidence_preserved": True, "reviewer_type": "model_retrieval_adjudicator",
        "reviewer_identity_and_timestamp_policy": "preserved as null", "human_gold_claimed": False})

    supplemental_metrics = {**rate_metrics(joined), "tier_state": "TIER_B",
        "tier_b_count": len(joined), "tier_b_directly_relevant_count": sum(x["relevance_state"] == "DIRECTLY_RELEVANT" for x in joined),
        "selection_design": "deterministic PMCID-available label-blind depth/case-balance supplement",
        "true_tier_b_precision_claimed": False, "literature_recall_claimed": False}
    writej(RUN / "supplemental_metrics.json", supplemental_metrics)
    case_rows = []
    for cid in ["spv2_017", "spv2_016", "spv2_003"]:
        rows = [x for x in joined if x["case_id"] == cid]
        case_rows.append({"case_id": cid, **rate_metrics(rows),
            "metadata_depths": [x["metadata_depth"] for x in rows],
            "relevance_state_counts": dict(Counter(x["relevance_state"] for x in rows)),
            "contaminant_class_counts": dict(Counter(x["contaminant_class"] for x in rows if x["contaminant_class"]))})
    writel(RUN / "supplemental_case_metrics.jsonl", case_rows)

    prior_depth = [x for x in readl(PRIOR / "depth_joined_adjudications.jsonl") if x["depth_bin"] == "151-180"]
    balanced = [{**x, "sample_component": "existing_depth_151_180_acquired_sample"} for x in prior_depth] + joined
    writel(RUN / "balanced_depth_151_180_adjudications.jsonl", balanced)
    balanced_case = {}
    for cid in ["spv2_017", "spv2_016", "spv2_003"]:
        rows = [x for x in balanced if x["case_id"] == cid]
        balanced_case[cid] = {"count": len(rows),
            "directly_relevant_count": sum(x["relevance_state"] == "DIRECTLY_RELEVANT" for x in rows),
            "metadata_depths": [x["metadata_depth"] for x in rows]}
    balanced_direct = sum(x["relevance_state"] == "DIRECTLY_RELEVANT" for x in balanced)
    tier_composition = {tier: {"count": sum(x["tier_state"] == tier for x in balanced),
        "directly_relevant_count": sum(x["tier_state"] == tier and x["relevance_state"] == "DIRECTLY_RELEVANT" for x in balanced)}
        for tier in ["TIER_A", "TIER_B"]}

    first_tail = readj(FIRST_TAIL / "tail_relevance_metrics.json")
    depth_121_150 = [x for x in readl(PRIOR / "depth_joined_adjudications.jsonl") if x["depth_bin"] == "121-150"]
    depth_summary = {"observed_adjudicated_windows": [
        {"depth_window": "61-120", "count": first_tail["adjudicated_count"],
         "directly_relevant_count": first_tail["directly_relevant_count"], "sample_design": "first acquired tail sample",
         "source_ref": rel(FIRST_TAIL / "tail_relevance_metrics.json")},
        {"depth_window": "121-150", "count": len(depth_121_150),
         "directly_relevant_count": sum(x["relevance_state"] == "DIRECTLY_RELEVANT" for x in depth_121_150),
         "sample_design": "acquisition-selected depth-180 probe sample", "source_ref": rel(PRIOR / "depth_joined_adjudications.jsonl")},
        {"depth_window": "151-180", "count": len(balanced), "directly_relevant_count": balanced_direct,
         "sample_design": "case-balanced, PMCID-available supplemental sample joined to two existing acquisitions",
         "source_ref": rel(RUN / "balanced_depth_151_180_adjudications.jsonl")}],
        "historically_unadjudicated_depth_31_60": {"result": None, "fabricated": False},
        "balanced_depth_151_180_case_metrics": balanced_case, "balanced_depth_151_180_tier_composition": tier_composition,
        "deepest_adjudicated_direct_relevance_depth": max(x["metadata_depth"] for x in balanced if x["relevance_state"] == "DIRECTLY_RELEVANT"),
        "monotonicity_claimed": False, "true_precision_or_recall_claimed": False,
        "scientific_saturation_at_180_established": False,
        "allowed_interpretation": ["metadata ceiling 60 is too shallow for these calibration cases",
            "metadata ceiling 120 is too shallow as a hard coverage ceiling",
            "directly relevant literature remains observable beyond depth 150",
            "directly relevant literature is observed as deep as depth 171",
            "candidate yield remained active through depth 180"]}
    writej(RUN / "depth_calibration_summary.json", depth_summary)

    protocol = {"protocol_id": "heldout_retrieval_budget_protocol_v1", "heldout_budget_frozen": True,
        "scope": "next held-out validation only", "metadata_soft_checkpoint": 120,
        "metadata_hard_safety_ceiling": 180, "retrieval_beyond_180_allowed": False,
        "hard_ceiling_interpretation": "budget_and_safety_ceiling_not_scientific_completeness_or_saturation",
        "case_comparability_rule": "all held-out cases use the same frozen maximum metadata budget",
        "natural_query_family_exhaustion": "record exhaustion when it occurs before 180; otherwise continue to at most 180",
        "adaptive_early_stop_state": "deferred",
        "adaptive_early_stop_reason": "candidate yield remained active through depth 180 in all three calibration cases, and no clean label-independent saturation threshold can be frozen without more tuning",
        "new_adaptive_threshold_for_first_heldout": False,
        "ceiling_tuning_after_individual_heldout_labels": False,
        "search_plan_scientific_gate_state": "candidate_frozen_not_production_activated",
        "heldout_validation_started": False, "heldout_case_requirement": "entirely new unseen propositions",
        "excluded_calibration_case_ids": CALIBRATION_CASES, "deferred_not_heldout_case_ids": ["spv2_019"]}
    writej(RUN / "heldout_retrieval_budget_protocol_v1.json", protocol)
    md = """# Held-out Retrieval Budget Protocol v1

- Scope: next held-out validation only.
- Metadata soft checkpoint: 120.
- Metadata hard safety ceiling: 180.
- Retrieval beyond 180: prohibited.
- Adaptive early stopping: deferred.
- All held-out cases use the same frozen maximum budget for comparability.
- Natural query-family exhaustion before 180 is recorded; otherwise retrieval may continue to at most 180.
- The value 180 is a budget and safety ceiling. It is not a literature-completeness or scientific-saturation claim.
- Do not tune the ceiling after viewing individual held-out labels.
- Held-out cases must be entirely new, unseen propositions.
- Search Plan v2.2 scientific gates remain candidate/frozen and are not production activated.

Calibration-only propositions are excluded: spv2_017, spv2_026, spv2_001, spv2_016, spv2_003, spv2_004, spv2_006_REDESIGNED, spv2_013_REDESIGNED. spv2_019 remains deferred and is not held out.
"""
    (RUN / "heldout_retrieval_budget_protocol_v1.md").write_text(md, encoding="utf-8")
    freeze_audit = {"status": "PASS", "no_case_specific_gate_rules_added": True,
        "no_query_changes_based_on_current_labels": True, "no_spv2_016_specific_relation_gate_repair": True,
        "no_spv2_017_specific_context_gate_repair": True, "no_spv2_003_specific_emt_repair": True,
        "no_budget_extension_beyond_180": True, "no_adaptive_threshold_fitted_to_three_case_yields": True,
        "adaptive_early_stop_state": "deferred", "calibration_cases_closed_to_further_gate_or_budget_tuning": True,
        "future_heldout_cases_require_unseen_propositions": True, "excluded_calibration_case_ids": CALIBRATION_CASES,
        "spv2_019_remains_deferred": True, "heldout_validation_started": False}
    writej(RUN / "calibration_to_heldout_freeze_audit.json", freeze_audit)

    source_after, prior_after, protected_after = tree_hash(SOURCE), tree_hash(PRIOR), protected_hashes()
    safety = {"network_calls": 0, "provider_calls": 0, "llm_calls": 0, "downloads": 0, "extraction_calls": 0,
        "source_supplemental_packaging_modified": source_before != source_after,
        "historical_adjudications_modified": prior_before != prior_after,
        "historical_assets_modified": protected_before != protected_after,
        "search_plan_or_gate_modified": False, "adjudication_generated_by_importer": False,
        "external_model_adjudications_imported": 7, "human_gold_claimed": False,
        "git_mutation_invoked": False}
    writej(RUN / "scientific_state_safety_audit.json", safety)
    writej(RUN / "production_leakage_audit.json", {"search_plan_v22_activation_state": "candidate_not_activated",
        "search_plan_production_activation": False, "heldout_budget_protocol_frozen": True,
        "heldout_validation_started": False, "scientific_saturation_claimed": False,
        "literature_recall_complete_claimed": False, "calibration_labels_used_to_select_heldout_cases": False,
        "status": "NO_PRODUCTION_OR_HELDOUT_LEAKAGE"})

    summary = {"status": "completed", "supplemental_adjudication_count": len(joined),
        "supplemental_direct_relevant_count": supplemental_metrics["directly_relevant_count"],
        "supplemental_related_wrong_proposition_count": supplemental_metrics["related_wrong_proposition_count"],
        "supplemental_justified_count": supplemental_metrics["justified_count"],
        "supplemental_not_justified_count": supplemental_metrics["not_justified_count"],
        "balanced_depth_151_180_count": len(balanced), "balanced_depth_151_180_direct_relevant_count": balanced_direct,
        "balanced_depth_151_180_direct_relevance_rate": fraction(balanced_direct, len(balanced)),
        "balanced_case_metrics": balanced_case, "balanced_tier_composition": tier_composition,
        "deepest_adjudicated_direct_relevance_depth": depth_summary["deepest_adjudicated_direct_relevance_depth"],
        "metadata_soft_checkpoint": 120, "metadata_hard_safety_ceiling": 180,
        "adaptive_early_stop_state": "deferred", "heldout_budget_frozen": True,
        "heldout_validation_started": False, "search_plan_v22_activation_state": "candidate_not_activated",
        "scientific_saturation_at_180_established": False, "true_tail_precision_or_recall_claimed": False,
        "network_calls": 0, "provider_calls": 0, "llm_calls": 0, "downloads": 0, "extraction_calls": 0,
        "historical_assets_modified": safety["historical_assets_modified"],
        "git_head": subprocess.run(["git","rev-parse","HEAD"], cwd=ROOT, capture_output=True, text=True, check=True).stdout.strip(),
        "git_mutation_invoked": False}
    writej(RUN / "summary.json", summary)
    checks = {"supplemental_adjudications_7_exact_once": len(joined) == len(set(submitted_ids)) == 7,
        "source_order_preserved": submitted_ids == source_ids,
        "supplemental_expected_totals": supplemental_metrics["directly_relevant_count"] == 5 and supplemental_metrics["related_wrong_proposition_count"] == 2 and supplemental_metrics["justified_count"] == 5 and supplemental_metrics["not_justified_count"] == 2,
        "all_supplemental_tier_b": all(x["tier_state"] == "TIER_B" for x in joined),
        "balanced_expected_totals": len(balanced) == 9 and balanced_direct == 6,
        "balanced_case_counts_3_each": all(x["count"] == 3 for x in balanced_case.values()),
        "balanced_case_direct_counts_expected": [balanced_case[c]["directly_relevant_count"] for c in ["spv2_017","spv2_016","spv2_003"]] == [2,1,3],
        "balanced_tier_composition_expected": tier_composition == {"TIER_A":{"count":2,"directly_relevant_count":1},"TIER_B":{"count":7,"directly_relevant_count":5}},
        "deepest_direct_depth_171": summary["deepest_adjudicated_direct_relevance_depth"] == 171,
        "budget_protocol_120_180": protocol["metadata_soft_checkpoint"] == 120 and protocol["metadata_hard_safety_ceiling"] == 180,
        "adaptive_early_stop_deferred": protocol["adaptive_early_stop_state"] == "deferred",
        "heldout_budget_frozen": protocol["heldout_budget_frozen"],
        "search_plan_not_activated": not readj(RUN/"production_leakage_audit.json")["search_plan_production_activation"],
        "heldout_not_started": not protocol["heldout_validation_started"],
        "categorical_confidence_and_reviewer_preserved": all(x["confidence"] in {"high","moderate-high"} and x["reviewer_type"] == "model_retrieval_adjudicator" for x in adjudications),
        "no_human_gold_claim": not safety["human_gold_claimed"],
        "source_and_historical_assets_unchanged": not safety["source_supplemental_packaging_modified"] and not safety["historical_adjudications_modified"] and not safety["historical_assets_modified"],
        "offline_all_calls_zero": summary["network_calls"] == summary["provider_calls"] == summary["llm_calls"] == summary["downloads"] == summary["extraction_calls"] == 0,
        "required_payloads_present": all((RUN/x).is_file() for x in REQUIRED if x not in {"validation.json","manifest.json"})}
    writej(RUN / "validation.json", {"status": "PASS" if all(checks.values()) else "FAIL", "checks": checks})
    files = [{"path": p.name, "sha256": sha(p), "bytes": p.stat().st_size,
              "record_count": len(readl(p)) if p.suffix == ".jsonl" else 1}
             for p in sorted(RUN.iterdir()) if p.is_file() and p.name != "manifest.json"]
    writej(RUN / "manifest.json", {"required_artifact_count": len(REQUIRED), "files": files,
        "source_submission_sha256": submission_sha, "network_calls": 0, "provider_calls": 0,
        "llm_calls": 0, "downloads": 0, "extraction_calls": 0})
    checks["manifest_hashes_valid"] = all(sha(RUN/x["path"]) == x["sha256"] for x in readj(RUN/"manifest.json")["files"])
    checks["required_artifacts_present"] = all((RUN/x).is_file() for x in REQUIRED)
    writej(RUN / "validation.json", {"status": "PASS" if all(checks.values()) else "FAIL", "checks": checks})
    files = [{"path": p.name, "sha256": sha(p), "bytes": p.stat().st_size,
              "record_count": len(readl(p)) if p.suffix == ".jsonl" else 1}
             for p in sorted(RUN.iterdir()) if p.is_file() and p.name != "manifest.json"]
    writej(RUN / "manifest.json", {"required_artifact_count": len(REQUIRED), "files": files,
        "source_submission_sha256": submission_sha, "network_calls": 0, "provider_calls": 0,
        "llm_calls": 0, "downloads": 0, "extraction_calls": 0})
    print(json.dumps(summary, indent=2))
    if not all(checks.values()): raise SystemExit(1)


if __name__ == "__main__": main()
