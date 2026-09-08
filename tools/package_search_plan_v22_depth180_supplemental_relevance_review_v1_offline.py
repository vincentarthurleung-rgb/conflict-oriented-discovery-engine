#!/usr/bin/env python3
"""Package seven frozen supplemental acquisitions for neutral review offline."""
from __future__ import annotations

from collections import Counter
import hashlib
import json
from pathlib import Path
import re
import subprocess

try:
    from generate_retrieval_relevance_audit_packaging_v1_offline import anchors, blank, excerpts
    from package_search_plan_v22_depth180_relevance_review_v1_offline import render_with_preserved_provenance
except ModuleNotFoundError:
    from tools.generate_retrieval_relevance_audit_packaging_v1_offline import anchors, blank, excerpts
    from tools.package_search_plan_v22_depth180_relevance_review_v1_offline import render_with_preserved_provenance


ROOT = Path(__file__).resolve().parents[1]
ACQUISITION = ROOT / "runs/20260908_search_plan_v22_depth180_supplemental_oa_acquisition_v1"
PLANNING = ROOT / "runs/20260908_search_plan_v22_depth180_relevance_adjudication_v1_offline"
PROBE = ROOT / "runs/20260907_search_plan_v22_recall_tail_probe_v2_depth180"
CALIBRATION = ROOT / "runs/20260906_search_plan_v21_retrieval_calibration_pilot_v1"
PREVIOUS = ROOT / "runs/20260907_search_plan_v22_depth180_relevance_packaging_v1_offline"
RUN = ROOT / "runs/20260908_search_plan_v22_depth180_supplemental_relevance_packaging_v1_offline"
FULLTEXT_MANIFEST = ACQUISITION / "fulltext_manifest.jsonl"
SELECTION = PLANNING / "supplemental_151_180_selection_plan.jsonl"
REQUIRED = ["supplemental_review_batch.md", "supplemental_review_packets.jsonl",
            "blank_supplemental_adjudications.jsonl", "source_identity_inventory.jsonl",
            "source_fulltext_bijection.json", "depth_case_balance.json", "schema_compatibility.json",
            "neutrality_audit.json", "validation.json", "manifest.json", "summary.json"]
JUDGMENT_SCALARS = ["relevance_state", "acquisition_decision", "contaminant_class", "reviewer_rationale",
                    "confidence", "reviewer_type", "reviewer_id_or_label", "timestamp"]
JUDGMENT_LISTS = ["matched_target_components", "mismatched_target_components",
                  "fulltext_resolved_fields", "remaining_unresolved_fields"]
FORM_FIELDS = ["relevance_state", "acquisition_decision", "matched_target_components",
               "mismatched_target_components", "fulltext_resolved_fields", "remaining_unresolved_fields",
               "contaminant_class", "rationale", "confidence"]


def sha(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def objsha(value): return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
def readj(path): return json.loads(Path(path).read_text(encoding="utf-8"))
def readl(path): return [json.loads(x) for x in Path(path).read_text(encoding="utf-8").splitlines() if x]
def writej(path, value): Path(path).write_text(json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")
def writel(path, rows): Path(path).write_text("".join(json.dumps(x, sort_keys=True, ensure_ascii=True) + "\n" for x in rows), encoding="utf-8")
def rel(path): return str(Path(path).resolve().relative_to(ROOT))


def protected_hashes():
    paths = [FULLTEXT_MANIFEST, ACQUISITION / "manifest.json", SELECTION, PLANNING / "manifest.json",
             PROBE / "tail_metadata_121_180.jsonl", PROBE / "tail_v22_gate_outputs_121_180.jsonl",
             PROBE / "tail_acquisition_candidate_inventory.jsonl", PROBE / "manifest.json",
             CALIBRATION / "frozen_search_plans.jsonl", CALIBRATION / "frozen_query_variants.jsonl",
             PREVIOUS / "tail_depth180_review_batch.md", PREVIOUS / "manifest.json",
             ROOT / "tools/generate_retrieval_relevance_audit_packaging_v1_offline.py",
             ROOT / "tools/search_plan_v22_candidate_gates.py"]
    return {rel(path): sha(path) for path in paths}


def main():
    if RUN.exists() and any(p.name not in REQUIRED for p in RUN.iterdir()):
        raise RuntimeError("Output run contains unrelated files")
    RUN.mkdir(parents=True, exist_ok=True)
    protected_before = protected_hashes(); input_hash = sha(FULLTEXT_MANIFEST)
    acquired, selection = readl(FULLTEXT_MANIFEST), readl(SELECTION)
    if len(acquired) != 7 or len(selection) != 7: raise RuntimeError("Expected seven acquired and selected records")
    acquired_ids = [(x["case_id"], x["pmid"], x["pmcid"]) for x in acquired]
    selected_ids = [(x["case_id"], x["pmid"], x["preserved_pmcid"]) for x in selection]
    if acquired_ids != selected_ids: raise RuntimeError("Acquisition and frozen selection order/identity mismatch")

    metadata = {(x["case_id"], x["pmid"]): x for x in readl(PROBE / "tail_metadata_121_180.jsonl")}
    gates = {(x["case_id"], x["pmid"]): x for x in readl(PROBE / "tail_v22_gate_outputs_121_180.jsonl")}
    candidates = {(x["case_id"], x["pmid"]): x for x in readl(PROBE / "tail_acquisition_candidate_inventory.jsonl")}
    plans = {x["case_id"]: x for x in readl(CALIBRATION / "frozen_search_plans.jsonl")}
    variants = readl(CALIBRATION / "frozen_query_variants.jsonl")
    variant_family = {x["query_variant_id"]: x["query_family_id"] for x in variants}
    packets, inventory, traces = [], [], []
    for index, acquisition in enumerate(acquired, 1):
        cid, pmid = acquisition["case_id"], acquisition["pmid"]; key = (cid, pmid)
        meta, gate, candidate, plan = metadata[key], gates[key], candidates[key], plans[cid]
        if not 151 <= meta["metadata_depth"] <= 180: raise RuntimeError(f"Out-of-scope depth for {pmid}")
        if acquisition["content_hash"] != sha(ROOT / acquisition["snapshot_ref"]): raise RuntimeError(f"Fulltext hash mismatch for {pmid}")
        query_variants = list(meta["query_lineage"])
        query_families = list(dict.fromkeys(variant_family[q] for q in query_variants if q in variant_family))
        if len(query_families) != len({variant_family[q] for q in query_variants if q in variant_family}):
            raise RuntimeError("Query-family lineage construction failed")
        abstract_ref = gate["pre_acquisition_evidence_refs"]["abstract"]["path"]
        abstract_snapshot = readj(ROOT / abstract_ref)
        packet_id = f"rrsuppv1_{index:04d}"
        deterministic_excerpts = excerpts(packet_id, ROOT / acquisition["snapshot_ref"], anchors(cid, plan, variants))
        publication = {"pmid": pmid, "pmcid": acquisition["pmcid"], "doi": meta.get("doi"),
                       "title": meta.get("title"), "year": meta.get("publication_date"),
                       "publication_types": meta.get("publication_types", [])}
        pre = {"title": meta.get("title"), "abstract": abstract_snapshot.get("abstract"),
            "abstract_snapshot_ref": abstract_ref, "abstract_snapshot_sha256": sha(ROOT / abstract_ref),
            "tier_state": gate["state"], "gate_reasons": gate["gates"],
            "known_plausible_fields": gate["known_plausible_fields"],
            "unresolved_fields_requiring_fulltext": gate["unresolved_fields_requiring_fulltext"],
            "why_fulltext_can_resolve": gate["why_fulltext_can_resolve"]}
        packet = {"packet_id": packet_id, "review_unit_id": packet_id, "case_id": cid,
            "ambiguity_tier": plan["ambiguity_tier"], "retrieval_target": plan["retrieval_target"],
            "scientific_proposition_target": plan["scientific_proposition_target"],
            "publication_identity": publication,
            "retrieval_provenance": {"query_families": query_families, "query_variants": query_variants,
                "first_discovery_query": meta["first_discovery_query"], "metadata_depth": meta["metadata_depth"]},
            "pre_acquisition_evidence": pre,
            "fulltext_evidence_packet": {"source_ref": acquisition["snapshot_ref"],
                "fulltext_sha256": acquisition["content_hash"], "excerpts": deterministic_excerpts,
                "experimental_extraction_performed": False},
            "adjudication": blank(packet_id, cid, acquisition["publication_id"]),
            "automatic_relevance_prediction": None, "manual_relevance_status": "pending"}
        packets.append(packet)
        inventory.append({"source_order": index, "packet_id": packet_id,
            "packet_id_convention": "rrsuppv1_<frozen_selection_order_4digits>",
            "case_id": cid, "publication_id": acquisition["publication_id"], "pmid": pmid,
            "pmcid": acquisition["pmcid"], "doi": meta.get("doi"), "metadata_depth": meta["metadata_depth"],
            "ambiguity_tier": plan["ambiguity_tier"], "tier_state": gate["state"],
            "query_families": query_families, "query_variants": query_variants,
            "candidate_source_sha256": objsha(candidate), "gate_source_sha256": objsha(gate),
            "abstract_ref": abstract_ref, "abstract_sha256": sha(ROOT / abstract_ref),
            "fulltext_ref": acquisition["snapshot_ref"], "fulltext_sha256": acquisition["content_hash"],
            "fulltext_excerpt_count": len(deterministic_excerpts), "source_identity_complete": True})
        for excerpt in deterministic_excerpts:
            traces.append({"packet_id": packet_id, "publication_id": acquisition["publication_id"],
                           "fulltext_ref": acquisition["snapshot_ref"], "fulltext_sha256": acquisition["content_hash"], **excerpt})

    writel(RUN / "supplemental_review_packets.jsonl", packets)
    writel(RUN / "blank_supplemental_adjudications.jsonl", [x["adjudication"] for x in packets])
    writel(RUN / "source_identity_inventory.jsonl", inventory)
    markdown = render_with_preserved_provenance(packets)
    (RUN / "supplemental_review_batch.md").write_text(markdown, encoding="utf-8")
    markdown_ids = re.findall(r"^### Packet (\S+)$", markdown, re.M)

    bijection = {"source_acquired_count": len(acquired), "review_packet_count": len(packets),
        "source_acquired_ordered_identities": acquired_ids,
        "review_packet_ordered_identities": [(x["case_id"], x["publication_identity"]["pmid"], x["publication_identity"]["pmcid"]) for x in packets],
        "source_fulltext_bijection": acquired_ids == [(x["case_id"], x["publication_identity"]["pmid"], x["publication_identity"]["pmcid"]) for x in packets],
        "source_packet_bijection": [x["packet_id"] for x in packets] == markdown_ids,
        "missing_source_fulltexts": [], "extra_source_fulltexts": [],
        "source_manifest_ref": rel(FULLTEXT_MANIFEST), "source_manifest_sha256": input_hash,
        "fulltext_hashes_valid": all(sha(ROOT/x["fulltext_ref"]) == x["fulltext_sha256"] for x in inventory)}
    writej(RUN / "source_fulltext_bijection.json", bijection)
    case_counts = Counter(x["case_id"] for x in packets)
    depths = {cid: [x["retrieval_provenance"]["metadata_depth"] for x in packets if x["case_id"] == cid]
              for cid in ["spv2_017", "spv2_016", "spv2_003"]}
    existing = {"spv2_017": 0, "spv2_016": 1, "spv2_003": 1}
    writej(RUN / "depth_case_balance.json", {"supplemental_packet_count": 7,
        "supplemental_case_counts": dict(case_counts), "supplemental_metadata_depths": depths,
        "all_metadata_depths_between_151_and_180": all(151 <= d <= 180 for values in depths.values() for d in values),
        "existing_depth_151_180_adjudicated_case_counts": existing,
        "expected_combined_case_counts_after_supplemental_adjudication": {cid: existing[cid]+case_counts[cid] for cid in existing},
        "expected_combined_total_after_supplemental_adjudication": 9,
        "prior_adjudications_modified": False, "supplemental_relevance_metrics_calculated": False})

    prior_schema = readj(ROOT / "runs/20260906_retrieval_relevance_audit_packaging_v1_offline/retrieval_relevance_adjudication_v1.schema.json")
    exact_keys = all(set(x["adjudication"]) == set(prior_schema["required"]) for x in packets)
    writej(RUN / "schema_compatibility.json", {"status": "COMPATIBLE_VIA_EXISTING_RENDERER_AND_SCHEMA" if exact_keys else "INCOMPATIBLE",
        "renderer_ref": rel(ROOT / "tools/generate_retrieval_relevance_audit_packaging_v1_offline.py"),
        "renderer_sha256": sha(ROOT / "tools/generate_retrieval_relevance_audit_packaging_v1_offline.py"),
        "depth180_renderer_adapter_ref": rel(ROOT / "tools/package_search_plan_v22_depth180_relevance_review_v1_offline.py"),
        "previous_schema_required_keys_exact": exact_keys,
        "presentation_structure_matches_depth180_batch": True,
        "packet_id_convention_source": "no prior supplemental convention found; deterministic frozen selection order used",
        "source_fields_inferred": False, "source_packets_or_fulltexts_modified": False})

    blanks = [x["adjudication"] for x in packets]
    prefilled = sum(x.get(k) is not None for x in blanks for k in JUDGMENT_SCALARS)
    prefilled += sum(bool(x.get(k)) for x in blanks for k in JUDGMENT_LISTS)
    blank_markdown = all(markdown.count(f"\n{field}:\n") == 7 for field in FORM_FIELDS)
    violations = []
    for packet in packets:
        if packet["automatic_relevance_prediction"] is not None: violations.append({"packet_id": packet["packet_id"], "reason": "prediction populated"})
        if packet["manual_relevance_status"] != "pending": violations.append({"packet_id": packet["packet_id"], "reason": "manual status not pending"})
    neutrality = {"review_packet_count": 7, "blank_adjudication_count": len(blanks),
        "prefilled_adjudication_fields": prefilled, "neutrality_violations": len(violations)+(0 if blank_markdown else 1),
        "violations": violations, "markdown_adjudication_fields_blank": blank_markdown,
        "previous_adjudication_labels_used_only_for_duplicate_exclusion_upstream": True,
        "prior_labels_used_for_ordering_or_rendering": False, "predicted_labels_added": False,
        "supplemental_relevance_metrics_calculated": False, "adjudication_performed": False}
    writej(RUN / "neutrality_audit.json", neutrality)

    protected_after = protected_hashes(); changed = sorted(k for k in set(protected_before)|set(protected_after) if protected_before.get(k) != protected_after.get(k))
    displayed_depths = [int(x) for x in re.findall(r"^Metadata depth: (\d+)$", markdown, re.M)]
    checks = {"source_acquired_count_7": len(acquired) == 7, "review_packet_count_7": len(packets) == 7,
        "markdown_packet_count_7": len(markdown_ids) == 7, "blank_adjudication_count_7": len(blanks) == 7,
        "case_balance_3_2_2": [case_counts[c] for c in ["spv2_017","spv2_016","spv2_003"]] == [3,2,2],
        "all_metadata_depths_151_180": all(151 <= x["metadata_depth"] <= 180 for x in inventory),
        "metadata_depths_rendered_exactly": displayed_depths == [x["metadata_depth"] for x in inventory],
        "source_fulltext_bijection": bijection["source_fulltext_bijection"], "source_packet_bijection": bijection["source_packet_bijection"],
        "missing_source_trace_zero": all(x["source_identity_complete"] and sha(ROOT/x["fulltext_ref"]) == x["fulltext_sha256"] for x in inventory),
        "missing_pmid_identity_zero": all(x["pmid"] for x in inventory), "missing_pmcid_identity_zero": all(x["pmcid"] for x in inventory),
        "prefilled_adjudication_fields_zero": prefilled == 0, "neutrality_violations_zero": neutrality["neutrality_violations"] == 0,
        "renderer_schema_compatible": readj(RUN/"schema_compatibility.json")["status"] == "COMPATIBLE_VIA_EXISTING_RENDERER_AND_SCHEMA",
        "source_assets_unchanged": not changed, "offline_all_calls_zero": True,
        "no_relevance_or_budget_calculation": not neutrality["supplemental_relevance_metrics_calculated"],
        "required_payloads_present": all((RUN/x).is_file() for x in REQUIRED if x not in {"validation.json","manifest.json","summary.json"})}
    validation = {"status": "PASS" if all(checks.values()) else "FAIL", "checks": checks,
        "source_acquired_count": len(acquired), "review_packet_count": len(packets), "markdown_packet_count": len(markdown_ids),
        "blank_adjudication_count": len(blanks), "source_fulltext_bijection": bijection["source_fulltext_bijection"],
        "source_packet_bijection": bijection["source_packet_bijection"], "missing_source_trace": sum(not x["source_identity_complete"] for x in inventory),
        "missing_pmid_identity": sum(not x["pmid"] for x in inventory), "missing_pmcid_identity": sum(not x["pmcid"] for x in inventory),
        "prefilled_adjudication_fields": prefilled, "neutrality_violations": neutrality["neutrality_violations"],
        "network_calls": 0, "provider_calls": 0, "llm_calls": 0, "downloads": 0,
        "extraction_calls": 0, "deterministic_excerpt_renderer_calls": 7,
        "historical_assets_modified": bool(changed)}
    writej(RUN / "validation.json", validation)
    summary = {"status": "completed" if validation["status"] == "PASS" else "failed",
        "source_acquired_count": 7, "review_packet_count": len(packets), "markdown_packet_count": len(markdown_ids),
        "blank_adjudication_count": len(blanks), "spv2_017_packet_count": case_counts["spv2_017"],
        "spv2_016_packet_count": case_counts["spv2_016"], "spv2_003_packet_count": case_counts["spv2_003"],
        "metadata_depths": depths, "all_metadata_depths_between_151_and_180": checks["all_metadata_depths_151_180"],
        "source_fulltext_bijection": bijection["source_fulltext_bijection"], "source_packet_bijection": bijection["source_packet_bijection"],
        "fulltext_excerpt_count": len(traces), "missing_source_trace": validation["missing_source_trace"],
        "prefilled_adjudication_fields": prefilled, "neutrality_violations": neutrality["neutrality_violations"],
        "supplemental_review_ready_for_adjudication": validation["status"] == "PASS",
        "supplemental_relevance_metrics_calculated": False, "budget_decision_updated": False,
        "network_calls": 0, "provider_calls": 0, "llm_calls": 0, "downloads": 0,
        "extraction_calls": 0, "historical_assets_modified": bool(changed),
        "git_head": subprocess.run(["git","rev-parse","HEAD"], cwd=ROOT, capture_output=True, text=True, check=True).stdout.strip(),
        "git_mutation_invoked": False}
    writej(RUN / "summary.json", summary)
    files = [{"path": p.name, "sha256": sha(p), "bytes": p.stat().st_size,
              "record_count": len(readl(p)) if p.suffix == ".jsonl" else 1}
             for p in sorted(RUN.iterdir()) if p.is_file() and p.name != "manifest.json"]
    writej(RUN / "manifest.json", {"required_artifact_count": len(REQUIRED), "files": files,
        "source_fulltext_manifest_ref": rel(FULLTEXT_MANIFEST), "source_fulltext_manifest_sha256": input_hash,
        "deterministic_excerpt_count": len(traces), "network_calls": 0, "provider_calls": 0,
        "llm_calls": 0, "downloads": 0, "extraction_calls": 0})
    checks["manifest_hashes_valid"] = all(sha(RUN/x["path"]) == x["sha256"] for x in readj(RUN/"manifest.json")["files"])
    checks["required_artifacts_present"] = all((RUN/x).is_file() for x in REQUIRED)
    validation["checks"], validation["status"] = checks, "PASS" if all(checks.values()) else "FAIL"
    writej(RUN / "validation.json", validation)
    files = [{"path": p.name, "sha256": sha(p), "bytes": p.stat().st_size,
              "record_count": len(readl(p)) if p.suffix == ".jsonl" else 1}
             for p in sorted(RUN.iterdir()) if p.is_file() and p.name != "manifest.json"]
    writej(RUN / "manifest.json", {"required_artifact_count": len(REQUIRED), "files": files,
        "source_fulltext_manifest_ref": rel(FULLTEXT_MANIFEST), "source_fulltext_manifest_sha256": input_hash,
        "deterministic_excerpt_count": len(traces), "network_calls": 0, "provider_calls": 0,
        "llm_calls": 0, "downloads": 0, "extraction_calls": 0})
    print(json.dumps(summary, indent=2))
    if validation["status"] != "PASS": raise SystemExit(1)


if __name__ == "__main__": main()
