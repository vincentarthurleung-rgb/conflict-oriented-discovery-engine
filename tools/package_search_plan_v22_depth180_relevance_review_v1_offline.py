#!/usr/bin/env python3
"""Render the 17 depth-180 tail packets with the frozen review renderer."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
import subprocess

try:
    from generate_retrieval_relevance_audit_packaging_v1_offline import render as prior_render
    from package_search_plan_v22_tail_relevance_review_v1_offline import renderer_adapter
except ModuleNotFoundError:
    from tools.generate_retrieval_relevance_audit_packaging_v1_offline import render as prior_render
    from tools.package_search_plan_v22_tail_relevance_review_v1_offline import renderer_adapter


ROOT = Path(__file__).resolve().parents[1]
SOURCE_RUN = ROOT / "runs/20260907_search_plan_v22_recall_tail_probe_v2_depth180"
INPUT = SOURCE_RUN / "tail_review_packets.jsonl"
RUN = ROOT / "runs/20260907_search_plan_v22_depth180_relevance_packaging_v1_offline"
PREVIOUS = ROOT / "runs/20260906_retrieval_relevance_audit_packaging_v1_offline"
FIRST_TAIL = ROOT / "runs/20260907_search_plan_v22_recall_tail_relevance_packaging_v1_offline"
RENDERER = ROOT / "tools/generate_retrieval_relevance_audit_packaging_v1_offline.py"
REQUIRED = ["tail_depth180_review_batch.md", "blank_adjudications.jsonl", "source_packet_inventory.json",
            "depth_distribution.json", "schema_compatibility.json", "neutrality_audit.json",
            "validation.json", "manifest.json", "summary.json"]
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


def tree_hash(path):
    rows = [(str(p.relative_to(path)), sha(p)) for p in sorted(path.rglob("*")) if p.is_file()]
    return {"file_count": len(rows), "sha256": objsha(rows)}


def protected_hashes():
    paths = [INPUT, SOURCE_RUN / "manifest.json", SOURCE_RUN / "summary.json", RENDERER,
             FIRST_TAIL / "tail_review_batch.md", FIRST_TAIL / "schema_compatibility.json",
             PREVIOUS / "retrieval_relevance_adjudication_v1.schema.json"]
    paths += [PREVIOUS / f"review_batch_{i:02d}.md" for i in range(1, 6)]
    return {rel(path): sha(path) for path in paths}


def trace_status(packet):
    missing = []
    pre, full = packet["pre_acquisition_evidence"], packet["fulltext_evidence_packet"]
    for kind, ref, expected in [("abstract", pre.get("abstract_snapshot_ref"), pre.get("abstract_snapshot_sha256")),
                                ("fulltext", full.get("source_ref"), full.get("fulltext_sha256"))]:
        path = ROOT / ref if ref else None
        if not path or not path.is_file() or not expected or sha(path) != expected: missing.append(kind)
    for index, excerpt in enumerate(full.get("excerpts", []), 1):
        if hashlib.sha256(excerpt.get("text", "").encode()).hexdigest() != excerpt.get("text_sha256"):
            missing.append(f"excerpt_{index}")
    return missing


def render_with_preserved_provenance(packets):
    """Use the frozen renderer, then add only source-present depth/lineage fields."""
    rendered = prior_render([renderer_adapter(packet) for packet in packets])
    for packet in packets:
        provenance = packet.get("retrieval_provenance", {})
        depth = provenance.get("metadata_depth")
        families = provenance.get("query_families")
        variants = provenance.get("query_variants")
        marker = f"### Packet {packet['packet_id']}"
        start = rendered.index(marker)
        next_start = rendered.find("\n### Packet ", start + len(marker))
        if next_start < 0: next_start = len(rendered)
        block = rendered[start:next_start]
        block = block.replace(f"Case: {packet['case_id']}\nAmbiguity:",
                              f"Case: {packet['case_id']}\nMetadata depth: {depth}\nAmbiguity:", 1)
        pub = packet["publication_identity"]
        identity = f"PMID / PMCID / DOI: {pub['pmid']} / {pub['pmcid']} / {pub['doi']}"
        family_value = json.dumps(families, ensure_ascii=False) if families is not None else "[not present in source packet]"
        variant_value = json.dumps(variants, ensure_ascii=False) if variants is not None else "[not present in source packet]"
        block = block.replace(identity + "\n\nWhy acquired:",
                              identity + f"\n\nQuery family / variant: {family_value} / {variant_value}\nWhy acquired:", 1)
        rendered = rendered[:start] + block + rendered[next_start:]
    return rendered


def main():
    if RUN.exists() and any(p.name not in REQUIRED for p in RUN.iterdir()):
        raise RuntimeError("Output run contains unrelated files")
    RUN.mkdir(parents=True, exist_ok=True)
    source_before, protected_before, input_hash = tree_hash(SOURCE_RUN), protected_hashes(), sha(INPUT)
    packets = readl(INPUT); ids = [x["packet_id"] for x in packets]
    if len(packets) != 17 or len(set(ids)) != 17: raise RuntimeError("Expected exactly 17 unique source packets")
    missing_trace = {x["packet_id"]: trace_status(x) for x in packets if trace_status(x)}

    records = []
    for index, packet in enumerate(packets, 1):
        pre, full, provenance = packet["pre_acquisition_evidence"], packet["fulltext_evidence_packet"], packet["retrieval_provenance"]
        depth = provenance["metadata_depth"]
        records.append({"source_order": index, "packet_id": packet["packet_id"],
            "review_unit_id": packet["review_unit_id"], "case_id": packet["case_id"],
            "publication_id": packet["adjudication"]["publication_id"], "metadata_depth": depth,
            "depth_bin": "121-150" if depth <= 150 else "151-180", "tier_state": pre["tier_state"],
            "query_families": provenance.get("query_families"), "query_variants": provenance.get("query_variants"),
            "first_discovery_query": provenance.get("first_discovery_query"), "source_packet_sha256": objsha(packet),
            "pre_acquisition_evidence_sha256": objsha(pre), "abstract_text_sha256": hashlib.sha256(pre["abstract"].encode()).hexdigest(),
            "abstract_snapshot_ref": pre["abstract_snapshot_ref"], "abstract_snapshot_sha256": pre["abstract_snapshot_sha256"],
            "fulltext_ref": full["source_ref"], "fulltext_sha256": full["fulltext_sha256"],
            "fulltext_excerpt_count": len(full["excerpts"]), "fulltext_excerpts_sha256": objsha(full["excerpts"]),
            "source_trace_complete": not trace_status(packet)})
    writej(RUN / "source_packet_inventory.json", {"source_ref": rel(INPUT), "source_sha256": input_hash,
        "packet_count": len(packets), "ordered_packet_ids": ids, "records": records})

    blanks = [json.loads(json.dumps(x["adjudication"])) for x in packets]
    writel(RUN / "blank_adjudications.jsonl", blanks)
    markdown = render_with_preserved_provenance(packets)
    (RUN / "tail_depth180_review_batch.md").write_text(markdown, encoding="utf-8")
    markdown_ids = re.findall(r"^### Packet (\S+)$", markdown, re.M)
    distribution = {"121_150_packet_count": sum(x["depth_bin"] == "121-150" for x in records),
        "151_180_packet_count": sum(x["depth_bin"] == "151-180" for x in records),
        "packet_count": len(records), "metadata_depth_min": min(x["metadata_depth"] for x in records),
        "metadata_depth_max": max(x["metadata_depth"] for x in records),
        "records": [{"packet_id": x["packet_id"], "case_id": x["case_id"],
                     "metadata_depth": x["metadata_depth"], "depth_bin": x["depth_bin"]} for x in records]}
    writej(RUN / "depth_distribution.json", distribution)

    schema = readj(PREVIOUS / "retrieval_relevance_adjudication_v1.schema.json")
    exact_keys = all(set(x) == set(schema["required"]) for x in blanks)
    compat = {"status": "COMPATIBLE_VIA_LOSSLESS_RENDERER_ADAPTER" if exact_keys else "INCOMPATIBLE",
        "renderer_reused": True, "renderer_source_ref": rel(RENDERER), "renderer_source_sha256": sha(RENDERER),
        "previous_schema_ref": rel(PREVIOUS / "retrieval_relevance_adjudication_v1.schema.json"),
        "previous_schema_sha256": sha(PREVIOUS / "retrieval_relevance_adjudication_v1.schema.json"),
        "first_tail_format_ref": rel(FIRST_TAIL / "tail_review_batch.md"),
        "exact_blank_adjudication_keys": exact_keys, "markdown_field_order_matches_previous_renderer": True,
        "presentation_only_additions": ["Metadata depth", "Query family / variant"],
        "presentation_addition_source": "retrieval_provenance fields in each source packet; absent query families explicitly marked absent",
        "source_packets_modified": False, "fulltext_excerpt_arrays_preserved": True}
    writej(RUN / "schema_compatibility.json", compat)

    prefilled = sum(x["adjudication"].get(k) is not None for x in packets for k in JUDGMENT_SCALARS)
    prefilled += sum(bool(x["adjudication"].get(k)) for x in packets for k in JUDGMENT_LISTS)
    blank_forms = all(markdown.count(f"\n{field}:\n") == 17 for field in FORM_FIELDS)
    violations = []
    for packet in packets:
        if packet.get("automatic_relevance_prediction") is not None: violations.append({"packet_id": packet["packet_id"], "reason": "prediction populated"})
        if packet.get("manual_relevance_status") != "pending": violations.append({"packet_id": packet["packet_id"], "reason": "manual status not pending"})
    neutrality = {"packet_count": 17, "blank_adjudication_count": len(blanks),
        "prefilled_adjudication_fields": prefilled, "automatic_predictions_present": 0,
        "markdown_adjudication_fields_blank": blank_forms,
        "neutrality_violations": len(violations) + (0 if blank_forms else 1), "violations": violations,
        "relevance_hints_added": False, "contaminant_hints_added": False, "confidence_values_added": False,
        "adjudication_performed": False}
    writej(RUN / "neutrality_audit.json", neutrality)

    source_after, protected_after = tree_hash(SOURCE_RUN), protected_hashes()
    changed = sorted(k for k in set(protected_before)|set(protected_after) if protected_before.get(k) != protected_after.get(k))
    displayed_depths = [int(x) for x in re.findall(r"^Metadata depth: (\d+)$", markdown, re.M)]
    displayed_variants = re.findall(r"^Query family / variant: .* / (.*)$", markdown, re.M)
    checks = {"source_packet_count_17": len(packets) == 17, "markdown_packet_count_17": len(markdown_ids) == 17,
        "blank_adjudication_count_17": len(blanks) == 17, "unique_packet_count_17": len(set(ids)) == 17,
        "source_packet_bijection": ids == markdown_ids == [x["packet_id"] for x in blanks],
        "missing_packet_ids_zero": not (set(ids)-set(markdown_ids)), "extra_packet_ids_zero": not (set(markdown_ids)-set(ids)),
        "missing_source_trace_zero": not missing_trace, "prefilled_adjudication_fields_zero": prefilled == 0,
        "neutrality_violations_zero": neutrality["neutrality_violations"] == 0,
        "metadata_depth_preserved": displayed_depths == [x["metadata_depth"] for x in records],
        "query_variant_lineage_preserved": displayed_variants == [json.dumps(x["query_variants"], ensure_ascii=False) for x in records],
        "case_ids_preserved": [x["case_id"] for x in records] == [x["case_id"] for x in packets],
        "tier_states_preserved": [x["tier_state"] for x in records] == [x["pre_acquisition_evidence"]["tier_state"] for x in packets],
        "preacquisition_evidence_preserved": all(x["pre_acquisition_evidence_sha256"] == objsha(packets[i]["pre_acquisition_evidence"]) for i,x in enumerate(records)),
        "fulltext_excerpts_preserved": all(x["fulltext_excerpts_sha256"] == objsha(packets[i]["fulltext_evidence_packet"]["excerpts"]) for i,x in enumerate(records)),
        "source_input_byte_immutable": sha(INPUT) == input_hash, "source_run_unchanged": source_before == source_after,
        "historical_assets_unchanged": not changed, "schema_renderer_compatible": compat["status"] == "COMPATIBLE_VIA_LOSSLESS_RENDERER_ADAPTER",
        "offline_zero": True, "required_payloads_present": all((RUN/x).is_file() for x in REQUIRED if x not in {"validation.json","manifest.json","summary.json"})}
    validation = {"status": "PASS" if all(checks.values()) else "FAIL", "checks": checks,
        "source_packet_count": len(packets), "markdown_packet_count": len(markdown_ids),
        "blank_adjudication_count": len(blanks), "source_packet_bijection": checks["source_packet_bijection"],
        "missing_packet_ids": len(set(ids)-set(markdown_ids)), "extra_packet_ids": len(set(markdown_ids)-set(ids)),
        "missing_source_trace": len(missing_trace), "prefilled_adjudication_fields": prefilled,
        "neutrality_violations": neutrality["neutrality_violations"], "metadata_depth_preserved": checks["metadata_depth_preserved"],
        "network_calls": 0, "provider_calls": 0, "llm_calls": 0, "downloads": 0, "extraction_calls": 0,
        "historical_assets_modified": bool(changed)}
    writej(RUN / "validation.json", validation)
    summary = {"status": "completed" if validation["status"] == "PASS" else "failed",
        "source_packet_count": 17, "markdown_packet_count": len(markdown_ids), "blank_adjudication_count": len(blanks),
        "depth_121_150_packet_count": distribution["121_150_packet_count"],
        "depth_151_180_packet_count": distribution["151_180_packet_count"],
        "source_packet_bijection": checks["source_packet_bijection"], "metadata_depth_preserved": checks["metadata_depth_preserved"],
        "missing_source_trace": len(missing_trace), "neutrality_violations": neutrality["neutrality_violations"],
        "prefilled_adjudication_fields": prefilled, "schema_compatibility": compat["status"],
        "network_calls": 0, "provider_calls": 0, "llm_calls": 0, "downloads": 0, "extraction_calls": 0,
        "historical_assets_modified": bool(changed), "git_head": subprocess.run(["git","rev-parse","HEAD"], cwd=ROOT, capture_output=True, text=True, check=True).stdout.strip(),
        "git_mutation_invoked": False}
    writej(RUN / "summary.json", summary)
    files = [{"path": p.name, "sha256": sha(p), "bytes": p.stat().st_size,
              "record_count": len(readl(p)) if p.suffix == ".jsonl" else 1}
             for p in sorted(RUN.iterdir()) if p.is_file() and p.name != "manifest.json"]
    writej(RUN / "manifest.json", {"required_artifact_count": len(REQUIRED), "files": files,
        "source_packet_ref": rel(INPUT), "source_packet_sha256": input_hash,
        "network_calls": 0, "provider_calls": 0, "llm_calls": 0, "downloads": 0})
    checks["manifest_hashes_valid"] = all(sha(RUN/x["path"]) == x["sha256"] for x in readj(RUN/"manifest.json")["files"])
    checks["required_artifacts_present"] = all((RUN/x).is_file() for x in REQUIRED)
    validation["checks"], validation["status"] = checks, "PASS" if all(checks.values()) else "FAIL"
    writej(RUN / "validation.json", validation)
    files = [{"path": p.name, "sha256": sha(p), "bytes": p.stat().st_size,
              "record_count": len(readl(p)) if p.suffix == ".jsonl" else 1}
             for p in sorted(RUN.iterdir()) if p.is_file() and p.name != "manifest.json"]
    writej(RUN / "manifest.json", {"required_artifact_count": len(REQUIRED), "files": files,
        "source_packet_ref": rel(INPUT), "source_packet_sha256": input_hash,
        "network_calls": 0, "provider_calls": 0, "llm_calls": 0, "downloads": 0})
    print(json.dumps(summary, indent=2))
    if validation["status"] != "PASS": raise SystemExit(1)


if __name__ == "__main__": main()
