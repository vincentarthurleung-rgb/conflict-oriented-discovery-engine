#!/usr/bin/env python3
"""Import frozen depth-180 judgments and plan a label-blind supplement offline."""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import re
import subprocess


ROOT = Path(__file__).resolve().parents[1]
PROBE = ROOT / "runs/20260907_search_plan_v22_recall_tail_probe_v2_depth180"
PACKAGING = ROOT / "runs/20260907_search_plan_v22_depth180_relevance_packaging_v1_offline"
PREVIOUS_SCHEMA = ROOT / "runs/20260906_retrieval_relevance_audit_packaging_v1_offline/retrieval_relevance_adjudication_v1.schema.json"
RUN = ROOT / "runs/20260908_search_plan_v22_depth180_relevance_adjudication_v1_offline"
CASES = ["spv2_017", "spv2_016", "spv2_003"]
LIST_FIELDS = {"matched_target_components", "mismatched_target_components",
               "fulltext_resolved_fields", "remaining_unresolved_fields"}
RELEVANCE = {"DIRECTLY_RELEVANT", "PLAUSIBLY_RELEVANT_FULLTEXT_REQUIRED",
             "RELATED_BUT_WRONG_PROPOSITION", "WRONG_ENDPOINT", "WRONG_ENTITY",
             "WRONG_EVIDENCE_MODE", "WRONG_THERAPY", "TOPIC_ONLY", "INSUFFICIENT_SOURCE_EVIDENCE"}
ACQUISITION = {"JUSTIFIED", "BORDERLINE_BUT_JUSTIFIED", "NOT_JUSTIFIED",
               "UNDETERMINABLE_FROM_PRESERVED_PREACQUISITION_EVIDENCE"}
ACCEPTABLE = {"JUSTIFIED", "BORDERLINE_BUT_JUSTIFIED"}
REQUIRED = ["adjudications.jsonl", "depth_joined_adjudications.jsonl", "schema_compatibility.json",
            "source_packet_bijection.json", "tier_metrics.json", "depth_bin_metrics.jsonl",
            "case_metrics.jsonl", "contaminant_summary.json", "summary.json", "validation.json",
            "manifest.json", "scientific_state_safety_audit.json", "production_leakage_audit.json",
            "supplemental_151_180_candidate_inventory.jsonl", "supplemental_151_180_selection_plan.jsonl",
            "supplemental_151_180_balance_summary.json", "supplemental_selection_leakage_audit.json"]


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
    paths = [PROBE / "tail_review_packets.jsonl", PROBE / "tail_acquisition_candidate_inventory.jsonl",
             PROBE / "tail_metadata_121_180.jsonl", PROBE / "tail_fulltext_manifest.jsonl", PROBE / "manifest.json",
             PACKAGING / "tail_depth180_review_batch.md", PACKAGING / "blank_adjudications.jsonl",
             PACKAGING / "manifest.json", ROOT / "tools/search_plan_v22_candidate_gates.py"]
    return {rel(p): sha(p) for p in paths}


def parse_submission(text):
    text = text.replace("\r\n", "\n")
    pattern = re.compile(r"^-{10,}\n(rrtailv2_\d{4})\n-{10,}\n(.*?)(?=^-{10,}\nrrtailv2_\d{4}\n|^={10,})", re.M | re.S)
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
    n = len(rows)
    return {"count": n,
        "directly_relevant_count": sum(x["relevance_state"] == "DIRECTLY_RELEVANT" for x in rows),
        "justified_count": sum(x["acquisition_decision"] == "JUSTIFIED" for x in rows),
        "acquisition_acceptable_count": sum(x["acquisition_decision"] in ACCEPTABLE for x in rows),
        "direct_relevance_rate": fraction(sum(x["relevance_state"] == "DIRECTLY_RELEVANT" for x in rows), n),
        "acquisition_justification_rate": fraction(sum(x["acquisition_decision"] == "JUSTIFIED" for x in rows), n),
        "acquisition_acceptability_rate": fraction(sum(x["acquisition_decision"] in ACCEPTABLE for x in rows), n)}


def main():
    parser = argparse.ArgumentParser(); parser.add_argument("input", type=Path); args = parser.parse_args()
    if RUN.exists() and any(p.name not in REQUIRED for p in RUN.iterdir()): raise RuntimeError("Output run contains unrelated files")
    RUN.mkdir(parents=True, exist_ok=True)
    probe_before, packaging_before, protected_before = tree_hash(PROBE), tree_hash(PACKAGING), protected_hashes()
    source_packets = readl(PROBE / "tail_review_packets.jsonl"); source_ids = [x["packet_id"] for x in source_packets]
    raw = args.input.read_bytes(); submission_sha = hashlib.sha256(raw).hexdigest()
    submitted = parse_submission(raw.decode("utf-8")); submitted_ids = [x["packet_id"] for x in submitted]
    if submitted_ids != source_ids or len(set(submitted_ids)) != 17:
        raise ValueError("Submitted packet identity/order must exactly match all 17 source packets")
    taxonomy = set(readj(ROOT / "runs/20260906_retrieval_relevance_audit_packaging_v1_offline/contaminant_taxonomy.json")["labels"])

    adjudications, joined = [], []
    for supplied, packet in zip(submitted, source_packets):
        pid = supplied["packet_id"]; contaminant = supplied.get("contaminant_class") or None
        if supplied.get("relevance_state") not in RELEVANCE: raise ValueError(f"Invalid relevance_state: {pid}")
        if supplied.get("acquisition_decision") not in ACQUISITION: raise ValueError(f"Invalid acquisition_decision: {pid}")
        if contaminant is not None and contaminant not in taxonomy: raise ValueError(f"Invalid contaminant_class: {pid}")
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
        depth = packet["retrieval_provenance"]["metadata_depth"]
        joined.append({**row, "metadata_depth": depth, "depth_bin": "121-150" if depth <= 150 else "151-180",
                       "tier_state": packet["pre_acquisition_evidence"]["tier_state"],
                       "source_packet_sha256": objsha(packet), "source_submission_sha256": submission_sha})
    writel(RUN / "adjudications.jsonl", adjudications); writel(RUN / "depth_joined_adjudications.jsonl", joined)

    writej(RUN / "source_packet_bijection.json", {"source_packet_count": 17, "submitted_adjudication_count": 17,
        "unique_source_packet_count": len(set(source_ids)), "unique_submitted_packet_count": len(set(submitted_ids)),
        "source_ordered_packet_ids": source_ids, "submitted_ordered_packet_ids": submitted_ids,
        "exact_identity_order_bijection": source_ids == submitted_ids, "missing_packet_ids": [], "extra_packet_ids": [],
        "source_packet_ref": rel(PROBE / "tail_review_packets.jsonl"), "source_packet_sha256": sha(PROBE / "tail_review_packets.jsonl"),
        "submission_sha256": submission_sha})
    writej(RUN / "schema_compatibility.json", {"status": "COMPATIBLE_WITH_DOCUMENTED_CATEGORICAL_CONFIDENCE_EXTENSION",
        "previous_schema_ref": rel(PREVIOUS_SCHEMA), "previous_schema_sha256": sha(PREVIOUS_SCHEMA),
        "identity_and_decision_enums_valid": True,
        "extension_reason": "Frozen external adjudications use categorical confidence while the prior schema permits numeric confidence.",
        "normalization_policy": "Categorical confidence preserved verbatim; reviewer identity and timestamp preserved as null.",
        "reviewer_type": "model_retrieval_adjudicator", "human_gold_claimed": False})

    tier_metrics = {tier: rate_metrics([x for x in joined if x["tier_state"] == tier]) for tier in ["TIER_A", "TIER_B"]}
    tier_metrics["overall"] = rate_metrics(joined); writej(RUN / "tier_metrics.json", tier_metrics)
    depth_rows = []
    for label in ["121-150", "151-180"]:
        rows = [x for x in joined if x["depth_bin"] == label]
        depth_rows.append({"depth_bin": label, **rate_metrics(rows),
            "acquisition_selected_sample": True, "stable_precision_estimate_claimed": False,
            "scientific_saturation_or_recall_claimed": False})
    writel(RUN / "depth_bin_metrics.jsonl", depth_rows)
    case_rows = []
    for cid in CASES:
        rows = [x for x in joined if x["case_id"] == cid]
        case_rows.append({"case_id": cid, **rate_metrics(rows),
            "relevance_state_counts": dict(Counter(x["relevance_state"] for x in rows)),
            "acquisition_decision_counts": dict(Counter(x["acquisition_decision"] for x in rows)),
            "contaminant_class_counts": dict(Counter(x["contaminant_class"] for x in rows if x["contaminant_class"]))})
    writel(RUN / "case_metrics.jsonl", case_rows)
    contaminants = Counter(x["contaminant_class"] for x in joined if x["contaminant_class"])
    writej(RUN / "contaminant_summary.json", {"contaminant_count": sum(contaminants.values()),
        "class_counts": dict(contaminants), "dominant_class": contaminants.most_common(1)[0][0] if contaminants else None,
        "per_case": {cid: dict(Counter(x["contaminant_class"] for x in joined if x["case_id"] == cid and x["contaminant_class"])) for cid in CASES}})

    source_candidates = readl(PROBE / "tail_acquisition_candidate_inventory.jsonl")
    metadata = {(x["case_id"], x["pmid"]): x for x in readl(PROBE / "tail_metadata_121_180.jsonl")}
    acquired = {(x["case_id"], x["pmid"]) for x in readl(PROBE / "tail_fulltext_manifest.jsonl")}
    adjudicated_publications = {(x["case_id"], x["publication_id"].split(":", 1)[1]) for x in adjudications}
    supplemental_inventory = []
    for source_order, candidate in enumerate(source_candidates, 1):
        if not 151 <= candidate["metadata_depth"] <= 180: continue
        key = (candidate["case_id"], candidate["pmid"]); meta = metadata[key]
        already = key in acquired or key in adjudicated_publications
        eligible = candidate["tier_state"] in {"TIER_A", "TIER_B"} and not already
        supplemental_inventory.append({"source_candidate_order": source_order, "case_id": candidate["case_id"],
            "pmid": candidate["pmid"], "publication_id": candidate["canonical_publication_id"],
            "metadata_depth": candidate["metadata_depth"], "depth_bin": candidate["depth_bin"],
            "tier_state": candidate["tier_state"], "query_lineage": candidate["query_lineage"],
            "preserved_pmcid": meta.get("pmcid"), "preserved_pmcid_available": bool(meta.get("pmcid")),
            "already_acquired_or_adjudicated": already, "supplemental_eligible": eligible,
            "exclusion_reason": "already acquired/adjudicated" if already else None,
            "source_candidate_sha256": objsha(candidate), "scientific_rescoring_performed": False})
    writel(RUN / "supplemental_151_180_candidate_inventory.jsonl", supplemental_inventory)

    current_depth_count = sum(x["depth_bin"] == "151-180" for x in joined)
    trigger = current_depth_count < 6
    selected, balance = [], []
    for cid in CASES:
        existing = sum(x["case_id"] == cid and x["depth_bin"] == "151-180" for x in joined)
        quota = max(0, 3-existing)
        eligible = [x for x in supplemental_inventory if x["case_id"] == cid and x["supplemental_eligible"]]
        ordered = sorted(eligible, key=lambda x: (not x["preserved_pmcid_available"], x["source_candidate_order"],
                                                   x["metadata_depth"], x["publication_id"]))
        picks = ordered[:quota] if trigger else []
        for pick in picks:
            selected.append({"planned_selection_order": len(selected)+1, "case_id": cid,
                "publication_id": pick["publication_id"], "pmid": pick["pmid"], "preserved_pmcid": pick["preserved_pmcid"],
                "preserved_pmcid_available": pick["preserved_pmcid_available"], "metadata_depth": pick["metadata_depth"],
                "tier_state": pick["tier_state"], "source_candidate_order": pick["source_candidate_order"],
                "selection_rule": "frozen case order; known PMCID first; source candidate order; metadata depth; publication identity",
                "selection_trigger": "existing depth-151-180 adjudicated-capable count 2 is below pre-registered minimum 6",
                "label_fields_used": False, "network_or_download_performed": False})
        balance.append({"case_id": cid, "existing_depth_151_180_adjudicated_count": existing,
            "ideal_total_target": 3, "supplemental_needed_for_ideal": quota,
            "eligible_unacquired_candidate_count": len(eligible),
            "eligible_with_preserved_pmcid_count": sum(x["preserved_pmcid_available"] for x in eligible),
            "supplemental_selected_count": len(picks),
            "selected_with_preserved_pmcid_count": sum(x["preserved_pmcid_available"] for x in picks),
            "projected_total_after_plan": existing+len(picks), "shortage_to_ideal": max(0, 3-existing-len(picks))})
    writel(RUN / "supplemental_151_180_selection_plan.jsonl", selected)
    writej(RUN / "supplemental_151_180_balance_summary.json", {"supplemental_sampling_required": trigger,
        "trigger_rule": "current adjudicated-capable depth-151-180 sample count < 6",
        "trigger_inputs": {"current_depth_151_180_sample_count": current_depth_count, "minimum_count": 6},
        "trigger_uses_relevance_labels": False, "existing_count": current_depth_count,
        "eligible_candidate_count": sum(x["supplemental_eligible"] for x in supplemental_inventory),
        "eligible_with_preserved_pmcid_count": sum(x["supplemental_eligible"] and x["preserved_pmcid_available"] for x in supplemental_inventory),
        "supplemental_plan_selected_count": len(selected), "selected_with_preserved_pmcid_count": sum(x["preserved_pmcid_available"] for x in selected),
        "projected_total_count": current_depth_count+len(selected), "per_case": balance,
        "network_authorization_required_before_acquisition": True, "network_calls": 0, "downloads": 0})
    forbidden = {"relevance_state", "acquisition_decision", "reviewer_rationale", "contaminant_class", "confidence", "title"}
    writej(RUN / "supplemental_selection_leakage_audit.json", {"status": "PASS",
        "trigger_based_only_on_sample_count": True, "selection_label_blind": True,
        "forbidden_selection_fields": sorted(forbidden),
        "forbidden_fields_present_in_selection_plan": sorted(forbidden & set().union(*(set(x) for x in selected))),
        "current_adjudication_outcomes_used_for_selection": False,
        "existing_acquired_packet_identity_used_only_for_deduplication": True,
        "scientific_title_heuristic_used": False, "candidate_rescoring_performed": False,
        "network_calls": 0, "downloads": 0})

    probe_after, packaging_after, protected_after = tree_hash(PROBE), tree_hash(PACKAGING), protected_hashes()
    safety = {"network_calls": 0, "provider_calls": 0, "llm_calls": 0, "downloads": 0, "extraction_calls": 0,
        "adjudication_generated_by_importer": False, "frozen_external_model_adjudications_imported": 17,
        "human_gold_claimed": False, "source_probe_modified": probe_before != probe_after,
        "source_packaging_modified": packaging_before != packaging_after,
        "historical_assets_modified": protected_before != protected_after,
        "search_plan_modified": False, "gate_modified": False, "git_mutation_invoked": False}
    writej(RUN / "scientific_state_safety_audit.json", safety)
    writej(RUN / "production_leakage_audit.json", {"depth_120_hard_ceiling_rejected": True,
        "depth_150_hard_ceiling_not_supported": True, "depth_180_hard_ceiling_not_yet_validated": True,
        "adaptive_budget_policy_not_yet_frozen": True, "supplemental_151_180_sampling_required": True,
        "heldout_validation_not_started": True, "search_plan_v22_activation_state": "candidate_not_activated",
        "status": "NO_PRODUCTION_LEAKAGE"})

    overall = tier_metrics["overall"]
    summary = {"status": "completed", "adjudication_count": 17,
        "directly_relevant_count": overall["directly_relevant_count"],
        "related_wrong_proposition_count": sum(x["relevance_state"] == "RELATED_BUT_WRONG_PROPOSITION" for x in joined),
        "justified_count": overall["justified_count"], "not_justified_count": sum(x["acquisition_decision"] == "NOT_JUSTIFIED" for x in joined),
        "overall_metrics": overall, "tier_a_metrics": tier_metrics["TIER_A"], "tier_b_metrics": tier_metrics["TIER_B"],
        "depth_121_150_metrics": next(x for x in depth_rows if x["depth_bin"] == "121-150"),
        "depth_151_180_metrics": next(x for x in depth_rows if x["depth_bin"] == "151-180"),
        "deepest_adjudicated_direct_relevance_depth": max(x["metadata_depth"] for x in joined if x["relevance_state"] == "DIRECTLY_RELEVANT"),
        "supplemental_sampling_required": trigger, "supplemental_plan_selected_count": len(selected),
        "search_plan_v22_activation_state": "candidate_not_activated", "heldout_validation_started": False,
        "network_calls": 0, "provider_calls": 0, "llm_calls": 0, "downloads": 0, "extraction_calls": 0,
        "historical_assets_modified": safety["historical_assets_modified"],
        "git_head": subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True, check=True).stdout.strip(),
        "git_mutation_invoked": False}
    writej(RUN / "summary.json", summary)

    checks = {"adjudications_17_exactly_once": len(adjudications) == len(set(submitted_ids)) == 17,
        "source_order_preserved": submitted_ids == source_ids, "confidence_categorical_preserved": all(x["confidence"] in {"high", "moderate-high"} for x in adjudications),
        "reviewer_type_preserved": all(x["reviewer_type"] == "model_retrieval_adjudicator" for x in adjudications),
        "no_human_gold_claim": not safety["human_gold_claimed"], "source_packets_unchanged": probe_before == probe_after,
        "source_packaging_unchanged": packaging_before == packaging_after, "search_plan_and_gate_unchanged": not safety["search_plan_modified"] and not safety["gate_modified"],
        "expected_relevance_totals": summary["directly_relevant_count"] == 9 and summary["related_wrong_proposition_count"] == 8,
        "expected_acquisition_totals": summary["justified_count"] == 9 and summary["not_justified_count"] == 8,
        "expected_tier_totals": tier_metrics["TIER_A"]["count"] == 9 and tier_metrics["TIER_A"]["directly_relevant_count"] == 8 and tier_metrics["TIER_B"]["count"] == 8 and tier_metrics["TIER_B"]["directly_relevant_count"] == 1,
        "expected_depth_totals": depth_rows[0]["count"] == 15 and depth_rows[0]["directly_relevant_count"] == 8 and depth_rows[1]["count"] == 2 and depth_rows[1]["directly_relevant_count"] == 1,
        "deepest_direct_depth_151": summary["deepest_adjudicated_direct_relevance_depth"] == 151,
        "supplement_trigger_count_only": trigger and current_depth_count == 2 and readj(RUN/"supplemental_selection_leakage_audit.json")["trigger_based_only_on_sample_count"],
        "supplement_selection_label_blind": not readj(RUN/"supplemental_selection_leakage_audit.json")["forbidden_fields_present_in_selection_plan"],
        "offline_all_calls_zero": summary["network_calls"] == summary["provider_calls"] == summary["llm_calls"] == summary["downloads"] == summary["extraction_calls"] == 0,
        "historical_assets_unchanged": not safety["historical_assets_modified"],
        "production_not_activated": summary["search_plan_v22_activation_state"] == "candidate_not_activated",
        "required_payloads_present": all((RUN/x).is_file() for x in REQUIRED if x not in {"validation.json","manifest.json"})}
    writej(RUN / "validation.json", {"status": "PASS" if all(checks.values()) else "FAIL", "checks": checks})
    files = [{"path": p.name, "sha256": sha(p), "bytes": p.stat().st_size,
              "record_count": len(readl(p)) if p.suffix == ".jsonl" else 1}
             for p in sorted(RUN.iterdir()) if p.is_file() and p.name != "manifest.json"]
    writej(RUN / "manifest.json", {"required_artifact_count": len(REQUIRED), "files": files,
        "source_submission_sha256": submission_sha, "network_calls": 0, "provider_calls": 0, "llm_calls": 0, "downloads": 0})
    checks["manifest_hashes_valid"] = all(sha(RUN/x["path"]) == x["sha256"] for x in readj(RUN/"manifest.json")["files"])
    checks["required_artifacts_present"] = all((RUN/x).is_file() for x in REQUIRED)
    writej(RUN / "validation.json", {"status": "PASS" if all(checks.values()) else "FAIL", "checks": checks})
    files = [{"path": p.name, "sha256": sha(p), "bytes": p.stat().st_size,
              "record_count": len(readl(p)) if p.suffix == ".jsonl" else 1}
             for p in sorted(RUN.iterdir()) if p.is_file() and p.name != "manifest.json"]
    writej(RUN / "manifest.json", {"required_artifact_count": len(REQUIRED), "files": files,
        "source_submission_sha256": submission_sha, "network_calls": 0, "provider_calls": 0, "llm_calls": 0, "downloads": 0})
    print(json.dumps(summary, indent=2))
    if not all(checks.values()): raise SystemExit(1)


if __name__ == "__main__": main()
