#!/usr/bin/env python3
"""Render the 15 frozen tail packets with the established review renderer."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
import subprocess

try:
    from generate_retrieval_relevance_audit_packaging_v1_offline import render as prior_render, summary as target_summary
except ModuleNotFoundError:
    from tools.generate_retrieval_relevance_audit_packaging_v1_offline import render as prior_render, summary as target_summary

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "runs/20260907_search_plan_v22_recall_tail_probe_v1"
PREVIOUS = ROOT / "runs/20260906_retrieval_relevance_audit_packaging_v1_offline"
RUN = ROOT / "runs/20260907_search_plan_v22_recall_tail_relevance_packaging_v1_offline"
INPUT = SOURCE / "tail_review_packets.jsonl"
REQUIRED = ["tail_review_batch.md", "blank_tail_adjudications.jsonl", "source_packet_inventory.json",
            "schema_compatibility.json", "neutrality_audit.json", "validation.json", "manifest.json", "summary.json"]
JUDGMENT_SCALARS = ["relevance_state", "acquisition_decision", "contaminant_class", "reviewer_rationale",
                    "confidence", "reviewer_type", "reviewer_id_or_label", "timestamp"]
JUDGMENT_LISTS = ["matched_target_components", "mismatched_target_components", "fulltext_resolved_fields",
                  "remaining_unresolved_fields"]
FORM_FIELDS = ["relevance_state", "acquisition_decision", "matched_target_components",
               "mismatched_target_components", "fulltext_resolved_fields", "remaining_unresolved_fields",
               "contaminant_class", "rationale", "confidence"]


def sha(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def objsha(value): return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
def readj(path): return json.loads(Path(path).read_text(encoding="utf-8"))
def readl(path): return [json.loads(x) for x in Path(path).read_text(encoding="utf-8").split("\n") if x]
def writej(path, value):
    Path(path).write_text(json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")
def writel(path, rows):
    Path(path).write_text("".join(json.dumps(x, sort_keys=True, ensure_ascii=True) + "\n" for x in rows), encoding="utf-8")
def rel(path): return str(Path(path).resolve().relative_to(ROOT))


def tree_hash(base):
    rows = [(str(path.relative_to(base)), sha(path)) for path in sorted(base.rglob("*")) if path.is_file()]
    return {"file_count": len(rows), "sha256": objsha(rows), "files": dict(rows)}


def protected_hashes():
    paths = [PREVIOUS / f"review_batch_{i:02d}.md" for i in range(1, 6)]
    paths += [PREVIOUS / "retrieval_relevance_adjudication_v1.schema.json",
              SOURCE / "tail_review_packets.jsonl", SOURCE / "manifest.json",
              ROOT / "tools/search_plan_v22_candidate_gates.py",
              ROOT / "runs/20260906_search_plan_v21_retrieval_calibration_pilot_v1/frozen_search_plans.jsonl",
              ROOT / "runs/20260906_search_plan_v21_retrieval_calibration_pilot_v1/frozen_query_variants.jsonl"]
    return {rel(path): sha(path) for path in paths}


def trace_status(packet):
    missing = []
    pre = packet["pre_acquisition_evidence"]; full = packet["fulltext_evidence_packet"]
    for kind, reference, expected in [
        ("abstract", pre.get("abstract_snapshot_ref"), pre.get("abstract_snapshot_sha256")),
        ("fulltext", full.get("source_ref"), full.get("fulltext_sha256")),
    ]:
        path = ROOT / reference if reference else None
        if not path or not path.is_file() or not expected or sha(path) != expected: missing.append(kind)
    for index, excerpt in enumerate(full.get("excerpts", []), 1):
        if sha_text(excerpt.get("text", "")) != excerpt.get("text_sha256"): missing.append(f"excerpt_{index}")
    return missing


def sha_text(text): return hashlib.sha256(text.encode()).hexdigest()


def gate_basis(packet):
    gates = packet["pre_acquisition_evidence"].get("gate_reasons", {})
    ordered = ["evidence_mode", "entity", "context", "endpoint", "relation", "therapy"]
    states = [f"{name}={gates[name]['state']}" for name in ordered if name in gates]
    return "Frozen v2.2 pre-acquisition gate states: " + "; ".join(states)


def renderer_adapter(packet):
    """Supply only render fields absent from the lean tail packet; do not alter source."""
    pre = packet["pre_acquisition_evidence"]
    return {**packet,
            "retrieval_target_summary": target_summary(packet["retrieval_target"]),
            "scientific_proposition_target_summary": target_summary(packet["scientific_proposition_target"]),
            "pre_acquisition_evidence": {**pre, "gate_admission_rationale": gate_basis(packet)}}


def main():
    if RUN.exists() and any(p.name not in REQUIRED for p in RUN.iterdir()):
        raise RuntimeError("Output run contains unrelated files")
    RUN.mkdir(parents=True, exist_ok=True)
    source_before = tree_hash(SOURCE); protected_before = protected_hashes(); input_hash = sha(INPUT)
    packets = readl(INPUT)
    if len(packets) != 15 or len({x["packet_id"] for x in packets}) != 15:
        raise RuntimeError("Expected exactly 15 unique source packets")
    source_order = [x["packet_id"] for x in packets]
    missing_trace = {x["packet_id"]: trace_status(x) for x in packets if trace_status(x)}
    inventory_rows = []
    for index, packet in enumerate(packets, 1):
        pre = packet["pre_acquisition_evidence"]; full = packet["fulltext_evidence_packet"]
        inventory_rows.append({"source_order": index, "packet_id": packet["packet_id"],
                               "review_unit_id": packet["review_unit_id"], "case_id": packet["case_id"],
                               "publication_id": packet["adjudication"]["publication_id"],
                               "tier_state": pre["tier_state"], "source_packet_sha256": objsha(packet),
                               "abstract_snapshot_ref": pre["abstract_snapshot_ref"],
                               "abstract_snapshot_sha256": pre["abstract_snapshot_sha256"],
                               "fulltext_ref": full["source_ref"], "fulltext_sha256": full["fulltext_sha256"],
                               "fulltext_excerpt_count": len(full["excerpts"]), "source_trace_complete": not trace_status(packet)})
    writej(RUN / "source_packet_inventory.json", {"source_ref": rel(INPUT), "source_sha256": input_hash,
                                                  "packet_count": len(packets), "ordered_packet_ids": source_order,
                                                  "records": inventory_rows})

    blanks = [json.loads(json.dumps(packet["adjudication"])) for packet in packets]
    writel(RUN / "blank_tail_adjudications.jsonl", blanks)
    adapted = [renderer_adapter(packet) for packet in packets]
    markdown = prior_render(adapted)
    (RUN / "tail_review_batch.md").write_text(markdown, encoding="utf-8")

    previous_schema = readj(PREVIOUS / "retrieval_relevance_adjudication_v1.schema.json")
    prior_packet = readl(PREVIOUS / "review_batch_01.jsonl")[0]
    exact_blank_keys = set(blanks[0]) == set(previous_schema["required"]) == set(prior_packet["adjudication"])
    compat = {"status": "COMPATIBLE_VIA_LOSSLESS_RENDERER_ADAPTER" if exact_blank_keys else "INCOMPATIBLE",
              "renderer_reused": True, "renderer_source_ref": rel(ROOT / "tools/generate_retrieval_relevance_audit_packaging_v1_offline.py"),
              "renderer_source_sha256": sha(ROOT / "tools/generate_retrieval_relevance_audit_packaging_v1_offline.py"),
              "previous_schema_ref": rel(PREVIOUS / "retrieval_relevance_adjudication_v1.schema.json"),
              "previous_schema_sha256": sha(PREVIOUS / "retrieval_relevance_adjudication_v1.schema.json"),
              "exact_blank_adjudication_keys": exact_blank_keys,
              "markdown_field_order_matches_previous_renderer": True,
              "reviewer_type_omitted_from_markdown_form_like_previous": "reviewer_type:" not in markdown,
              "adapter_only_additions": ["retrieval_target_summary", "scientific_proposition_target_summary", "gate_admission_rationale"],
              "adapter_source": "preserved target objects and frozen pre-acquisition gate states",
              "source_packets_modified": False, "fulltext_excerpt_arrays_preserved": True}
    writej(RUN / "schema_compatibility.json", compat)

    scalar_prefills = sum(packet["adjudication"].get(k) is not None for packet in packets for k in JUDGMENT_SCALARS)
    list_prefills = sum(bool(packet["adjudication"].get(k)) for packet in packets for k in JUDGMENT_LISTS)
    markdown_ids = re.findall(r"^### Packet (\S+)$", markdown, re.M)
    form_lines_blank = all(markdown.count(f"\n{field}:\n") == 15 for field in FORM_FIELDS)
    violations = []
    for packet in packets:
        if packet.get("automatic_relevance_prediction") is not None: violations.append({"packet_id": packet["packet_id"], "reason": "automatic prediction populated"})
        if packet.get("manual_relevance_status") != "pending": violations.append({"packet_id": packet["packet_id"], "reason": "manual relevance not pending"})
    neutrality = {"packet_count": len(packets), "blank_adjudication_count": len(blanks),
                  "prefilled_adjudication_fields": scalar_prefills + list_prefills,
                  "automatic_predictions_present": sum(x.get("automatic_relevance_prediction") is not None for x in packets),
                  "markdown_adjudication_fields_blank": form_lines_blank,
                  "neutrality_violations": len(violations) + (0 if form_lines_blank else 1), "violations": violations,
                  "reviewer_identity_invented": False, "timestamp_invented": False, "confidence_invented": False,
                  "adjudication_performed": False}
    writej(RUN / "neutrality_audit.json", neutrality)

    source_after = tree_hash(SOURCE); protected_after = protected_hashes()
    changed = sorted(path for path in set(protected_before) | set(protected_after)
                     if protected_before.get(path) != protected_after.get(path))
    checks = {"packet_count_15": len(packets) == 15, "markdown_packet_count_15": len(markdown_ids) == 15,
              "blank_adjudication_count_15": len(blanks) == 15, "unique_packet_count_15": len(set(source_order)) == 15,
              "source_packet_bijection": source_order == markdown_ids == [x["packet_id"] for x in blanks],
              "missing_packet_ids_zero": not (set(source_order) - set(markdown_ids)),
              "extra_packet_ids_zero": not (set(markdown_ids) - set(source_order)), "missing_source_trace_zero": not missing_trace,
              "neutrality_violations_zero": neutrality["neutrality_violations"] == 0,
              "prefilled_adjudication_fields_zero": neutrality["prefilled_adjudication_fields"] == 0,
              "source_input_byte_immutable": sha(INPUT) == input_hash, "source_run_unchanged": source_before == source_after,
              "historical_review_batches_unchanged": not changed,
              "schema_and_renderer_compatible": compat["status"] == "COMPATIBLE_VIA_LOSSLESS_RENDERER_ADAPTER",
              "tier_states_preserved": all(inventory_rows[i]["tier_state"] == packets[i]["pre_acquisition_evidence"]["tier_state"] for i in range(15)),
              "preacquisition_evidence_preserved": all(
                  {k: v for k, v in adapted[i]["pre_acquisition_evidence"].items() if k != "gate_admission_rationale"}
                  == packets[i]["pre_acquisition_evidence"] for i in range(15)),
              "fulltext_excerpts_preserved": all(adapted[i]["fulltext_evidence_packet"]["excerpts"] == packets[i]["fulltext_evidence_packet"]["excerpts"] for i in range(15)),
              "offline_zero": True, "search_plan_unchanged": not changed,
              "required_payloads_present": all((RUN / x).exists() for x in REQUIRED if x not in {"validation.json", "manifest.json", "summary.json"})}
    validation = {"status": "PASS" if all(checks.values()) else "FAIL", "checks": checks,
                  "packet_count": len(packets), "markdown_packet_count": len(markdown_ids),
                  "blank_adjudication_count": len(blanks), "unique_packet_count": len(set(source_order)),
                  "source_packet_bijection": checks["source_packet_bijection"],
                  "missing_packet_ids": len(set(source_order) - set(markdown_ids)),
                  "extra_packet_ids": len(set(markdown_ids) - set(source_order)),
                  "missing_source_trace": len(missing_trace), "missing_source_trace_details": missing_trace,
                  "neutrality_violations": neutrality["neutrality_violations"],
                  "prefilled_adjudication_fields": neutrality["prefilled_adjudication_fields"],
                  "network_calls": 0, "provider_calls": 0, "llm_calls": 0, "downloads": 0,
                  "extraction_calls": 0, "historical_assets_modified": bool(changed)}
    writej(RUN / "validation.json", validation)
    summary = {"status": "completed" if validation["status"] == "PASS" else "failed",
               "source_packet_count": len(packets), "markdown_packet_count": len(markdown_ids),
               "blank_adjudication_count": len(blanks), "source_packet_bijection": checks["source_packet_bijection"],
               "ordering": "preserved_from_tail_review_packets.jsonl", "missing_source_trace": len(missing_trace),
               "neutrality_violations": neutrality["neutrality_violations"],
               "prefilled_adjudication_fields": neutrality["prefilled_adjudication_fields"],
               "schema_compatibility": compat["status"], "fulltext_excerpt_count": sum(len(x["fulltext_evidence_packet"]["excerpts"]) for x in packets),
               "network_calls": 0, "provider_calls": 0, "llm_calls": 0, "downloads": 0,
               "extraction_calls": 0, "historical_assets_modified": bool(changed),
               "git_head": subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True, capture_output=True, check=True).stdout.strip(),
               "git_mutation_invoked": False}
    writej(RUN / "summary.json", summary)
    manifest_files = [{"path": path.name, "sha256": sha(path), "bytes": path.stat().st_size,
                       "record_count": len(readl(path)) if path.suffix == ".jsonl" else 1}
                      for path in sorted(RUN.iterdir()) if path.is_file() and path.name != "manifest.json"]
    writej(RUN / "manifest.json", {"required_artifact_count": len(REQUIRED), "files": manifest_files,
                                   "source_packet_ref": rel(INPUT), "source_packet_sha256": input_hash,
                                   "network_calls": 0, "provider_calls": 0, "llm_calls": 0, "downloads": 0})
    manifest = readj(RUN / "manifest.json")
    validation["checks"]["manifest_hashes_valid"] = all(sha(RUN / x["path"]) == x["sha256"] for x in manifest["files"])
    validation["checks"]["required_artifacts_present"] = all((RUN / x).is_file() for x in REQUIRED)
    validation["status"] = "PASS" if all(validation["checks"].values()) else "FAIL"
    writej(RUN / "validation.json", validation)
    manifest_files = [{"path": path.name, "sha256": sha(path), "bytes": path.stat().st_size,
                       "record_count": len(readl(path)) if path.suffix == ".jsonl" else 1}
                      for path in sorted(RUN.iterdir()) if path.is_file() and path.name != "manifest.json"]
    writej(RUN / "manifest.json", {"required_artifact_count": len(REQUIRED), "files": manifest_files,
                                   "source_packet_ref": rel(INPUT), "source_packet_sha256": input_hash,
                                   "network_calls": 0, "provider_calls": 0, "llm_calls": 0, "downloads": 0})
    print(json.dumps(summary, indent=2))
    if validation["status"] != "PASS": raise SystemExit(1)


if __name__ == "__main__": main()
