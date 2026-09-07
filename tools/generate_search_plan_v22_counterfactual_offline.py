#!/usr/bin/env python3
"""Freeze pre-acquisition gate outputs, then evaluate submitted review overlays."""
from __future__ import annotations

import argparse
import ast
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
PILOT = ROOT / "runs/20260906_search_plan_v21_retrieval_calibration_pilot_v1"
PACK = ROOT / "runs/20260906_retrieval_relevance_audit_packaging_v1_offline"
DEFAULT_OUT = ROOT / "runs/20260907_search_plan_v22_failure_decomposition_counterfactual_replay_offline"
OVERLAYS = [ROOT / f"runs/20260907_retrieval_relevance_adjudication_batch_{i:02d}_v1_offline" for i in range(1, 6)]
ENGINE = ROOT / "tools/search_plan_v22_candidate_gates.py"
ACCEPTABLE = {"JUSTIFIED", "BORDERLINE_BUT_JUSTIFIED"}
PROHIBITED = {"relevance_state", "acquisition_decision", "contaminant_class", "reviewer_rationale", "confidence", "packet_id", "pmid", "case_id"}
REQUIRED = [
    "baseline_metrics.json", "adjudication_overlay_integrity.json",
    "failure_inventory.jsonl", "failure_decomposition_summary.json",
    "evidence_mode_detectability_audit.jsonl", "evidence_mode_gate_candidate.json",
    "context_plausibility_gate_candidate.json", "endpoint_plausibility_gate_candidate.json",
    "relation_plausibility_gate_candidate.json", "tier_a_v22_candidate_contract.json",
    "tier_b_v22_candidate_contract.json", "reject_v22_candidate_contract.json",
    "counterfactual_gate_inputs.jsonl", "counterfactual_gate_outputs.jsonl",
    "label_leakage_audit.json", "counterfactual_evaluation.json",
    "counterfactual_case_metrics.jsonl", "incremental_gate_ablation.jsonl",
    "gate_overlap_audit.json", "query_family_failure_contribution.jsonl",
    "query_variant_failure_contribution.jsonl", "retrieval_depth_quality_curve.jsonl",
    "search_plan_v22_candidate_contract.json", "heldout_validation_requirements.json",
    "scientific_state_safety_audit.json", "production_leakage_audit.json",
    "final_validation.json", "manifest.json", "summary.json",
]


def readj(path): return json.loads(Path(path).read_text(encoding="utf-8"))
def readl(path): return [json.loads(x) for x in Path(path).read_text(encoding="utf-8").splitlines() if x]
def digest(path):
    checksum = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            checksum.update(block)
    return checksum.hexdigest()
def objhash(value): return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
def ref(path): return str(Path(path).relative_to(ROOT))
def writej(path, value): Path(path).write_text(json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")
def writel(path, rows): Path(path).write_text("".join(json.dumps(x, sort_keys=True, ensure_ascii=False) + "\n" for x in rows), encoding="utf-8")
def rate(n, d): return {"numerator": n, "denominator": d, "value": n / d if d else None}
def counts(values): return dict(sorted(Counter(values).items()))
def nested_keys(x):
    if isinstance(x, dict): return set(x) | {k for v in x.values() for k in nested_keys(v)}
    if isinstance(x, list): return {k for v in x for k in nested_keys(v)}
    return set()


PROTECTED_SCOPES = ["src", "configs", "runs", "runs_archive", "data", "system_b_inputs",
                    "system_b_outputs", "system_b_replays", "case_bundles", "case_bundles_preserved",
                    "preserved_case_bundles", "reference_inputs", "search_plan_reviews", "scripts",
                    "alembic", "docker", "batch_runs", "archived_experiments", "tools"]


def protected_hashes(output_path):
    """Opaque byte hashes only: scientific/fulltext contents are never parsed here."""
    protected = {ref(p): digest(p) for scope in PROTECTED_SCOPES for p in sorted((ROOT / scope).rglob("*"))
            if p.is_file() and "__pycache__" not in p.parts
            and not p.is_relative_to(output_path) and not p.is_relative_to(DEFAULT_OUT)
            and p not in {ENGINE, Path(__file__).resolve()}}
    protected.update({ref(p): digest(p) for p in sorted(ROOT.iterdir()) if p.is_file()})
    return protected


def strip_identifiers(obj):
    if isinstance(obj, dict):
        return {k: strip_identifiers(v) for k, v in obj.items()
                if k not in PROHIBITED and not k.endswith("_ref") and not k.endswith("_id")
                and k not in {"historical_target_ref", "supersedes_for_candidate_planning", "candidate_version"}}
    if isinstance(obj, list): return [strip_identifiers(x) for x in obj]
    return obj


def prepare_inputs():
    """No review label or fulltext file is opened in this phase."""
    from search_plan_v22_candidate_gates import build_target_contract
    units = readl(PACK / "review_unit_inventory.jsonl")
    plans = {x["case_id"]: x for x in readl(PILOT / "frozen_search_plans.jsonl")}
    gates = readl(PILOT / "frozen_gate_rules.jsonl")
    original_plans_path = ROOT / "runs/20260906_search_plan_v2_multicase_stress_test_offline/search_plan_v2_candidates.jsonl"
    original_plans = {x["case_id"]: x for x in readl(original_plans_path)}
    variants = readl(PILOT / "frozen_query_variants.jsonl")
    identities = {x["pmid"]: x for x in readl(PILOT / "publication_identity_inventory.jsonl")}
    screens = {(x["case_id"], x["pmid"]): x for x in readl(PILOT / "abstract_screening_results.jsonl")}
    metadata = readl(PILOT / "metadata_stage_results.jsonl")
    metadata_map = {(x["case_id"], x["canonical_publication_id"]): x for x in metadata}
    executed = readl(PILOT / "executed_queries.jsonl")
    queries = {x["query_variant_id"]: x for x in executed}
    ranks = {}
    reconstructed = defaultdict(list)
    seen = defaultdict(set)
    for q in sorted(executed, key=lambda x: x["execution_order"]):
        if q["execution_status"] != "executed": continue
        ids = readj(ROOT / q["raw_response_snapshot_ref"])["esearchresult"]["idlist"]
        for rank, pmid in enumerate(ids, 1):
            ranks[(q["query_variant_id"], pmid)] = rank
            if pmid not in seen[q["case_id"]] and len(seen[q["case_id"]]) < plans[q["case_id"]]["budget"]["metadata_unique"]["hard"]:
                reconstructed[q["case_id"]].append(pmid)
                seen[q["case_id"]].add(pmid)
    actual_order = defaultdict(list)
    for x in metadata: actual_order[x["case_id"]].append(x["canonical_publication_id"].split(":")[1])
    if dict(actual_order) != dict(reconstructed): raise ValueError("Preserved metadata order does not match esearch first-discovery order")
    depth = {(cid, pmid): i for cid, pmids in reconstructed.items() for i, pmid in enumerate(pmids, 1)}
    inputs = []
    for unit in units:
        cid = unit["case_id"]; pmid = unit["canonical_publication_id"].split(":")[1]
        identity = identities[pmid]; screen = screens[(cid, pmid)]
        snap = ROOT / screen["abstract_snapshot_ref"]; abstract = readj(snap)
        target = build_target_contract(plans[cid], [g for g in gates if g["case_id"] == cid], [v for v in variants if v["case_id"] == cid])
        target["primary_evidence_required"] = True
        target["primary_requirement_authority"] = {
            "policy": "Current task section 5 explicitly preserves primary evidence for current calibration targets",
            "frozen_reject_rule": "conditional review rejection when primary evidence is required",
            "authority_caveat": "Frozen plan lacks an explicit primary-evidence Boolean; this task resolves that policy parameter",
            "original_planning_rubric": original_plans[cid.removesuffix("_REDESIGNED")]["review_rubric"]["fulltext_download_precision"]["rationale"],
        }
        target = strip_identifiers(target)
        scientific = {"title": abstract["title"], "abstract": abstract["abstract"], "publication_types": identity["publication_types"], "target": target}
        if nested_keys(scientific) & PROHIBITED: raise ValueError("Identifier or label in gate scientific input")
        md = metadata_map[(cid, unit["canonical_publication_id"])]
        qids = md["query_lineage"]; first = md["first_seen_query_variant_id"]
        inputs.append({
            "packet_id": unit["packet_id"], "case_id": cid, "publication_id": unit["canonical_publication_id"],
            "ambiguity_tier": plans[cid]["ambiguity_tier"], "original_tier": "TIER_A" if "TIER_A" in unit["tier_state"] else "TIER_B",
            "scientific_input": scientific, "pre_acquisition_evidence_refs": {
                "abstract": {"path": ref(snap), "sha256": digest(snap)},
                "title": {"path": ref(snap), "sha256": digest(snap)},
                "publication_types": {"path": ref(PILOT / "publication_identity_inventory.jsonl"), "sha256": digest(PILOT / "publication_identity_inventory.jsonl"), "selector": f"pmid={pmid}"},
                "target": {"path": ref(PILOT / "frozen_search_plans.jsonl"), "sha256": digest(PILOT / "frozen_search_plans.jsonl"), "selector": f"case_id={cid}"},
                "primary_evidence_requirement": {"path": ref(original_plans_path), "sha256": digest(original_plans_path),
                                                 "selector": f"case_id={cid.removesuffix('_REDESIGNED')}/review_rubric/fulltext_download_precision/rationale"},
            },
            "query_variant_ids": qids, "query_family_ids": sorted({queries[q]["query_family_id"] for q in qids}),
            "first_discovery_query": first, "metadata_first_seen_depth": depth[(cid, pmid)],
            "first_query_execution_order": queries[first]["execution_order"], "rank_in_first_query": ranks[(first, pmid)],
            "ranks_by_query": {q: ranks[(q, pmid)] for q in qids},
        })
    return inputs, metadata, depth, queries


def gate_worker(input_path):
    """Process-level label isolation: the only readable data file is input_path."""
    from search_plan_v22_candidate_gates import evaluate
    allowed = str(Path(input_path).resolve())
    audit = {"file_reads": [], "network_events": 0, "forbidden_reads": [], "evaluate_calls": 0}
    def hook(event, args):
        if event == "open":
            file, mode, flags = args
            if not isinstance(file, (str, bytes)): raise PermissionError("File descriptor open forbidden")
            name = str(Path(file).resolve())
            if name != allowed or mode not in {"r", "rb"}:
                audit["forbidden_reads"].append(name); raise PermissionError("Gate worker data access denied")
            audit["file_reads"].append(Path(name).name)
        if event.startswith(("socket.", "subprocess.", "urllib.", "http.")):
            audit["network_events"] += 1; raise PermissionError("Gate worker external calls denied")
    sys.addaudithook(hook)
    inputs = readl(allowed)
    outputs = []
    for x in inputs:
        scientific = x["scientific_input"]
        assert not (nested_keys(scientific) & PROHIBITED)
        decision = evaluate(scientific)
        audit["evaluate_calls"] += 1
        outputs.append({"packet_id": x["packet_id"], "case_id": x["case_id"], "publication_id": x["publication_id"],
                        "original_tier": x["original_tier"], "pre_acquisition_evidence_refs": x["pre_acquisition_evidence_refs"],
                        "scientific_input_sha256": objhash(scientific), **decision})
    print(json.dumps({"outputs": outputs, "audit": audit}, sort_keys=True, ensure_ascii=False))


def check_manifest(base):
    manifest = readj(base / "manifest.json")
    invalid = [x["path"] for x in manifest["files"] if digest(base / x["path"]) != x["sha256"]]
    return {"path": ref(base / "manifest.json"), "sha256": digest(base / "manifest.json"), "invalid_hashes": invalid}


def load_overlays(inputs):
    """Called only after counterfactual outputs have been durably written."""
    labels = []; checks = []
    for i, base in enumerate(OVERLAYS, 1):
        rows = readl(base / "adjudications.jsonl")
        raw_sha = digest(base / "submitted_adjudications.txt")
        batch = readl(PACK / f"review_batch_{i:02d}.jsonl")
        packetmap = {p["packet_id"]: p for p in batch}
        raw_text = (base / "submitted_adjudications.txt").read_text()
        raw_ids = re.findall(r"^packet_id:[ \t]*(\S+)", raw_text, re.M)
        raw_confidence = re.findall(r"^confidence:[ \t]*(.*)$", raw_text, re.M)
        good = ([x["packet_id"] for x in rows] == raw_ids == [x["packet_id"] for x in batch]
                and [x["confidence"] for x in rows] == raw_confidence
                and all(x["source_submission_sha256"] == raw_sha for x in rows)
                and all(x["source_packet_sha256"] == objhash(packetmap[x["packet_id"]]) for x in rows)
                and all(x["case_id"] == packetmap[x["packet_id"]]["case_id"] and x["publication_id"] == "pmid:" + packetmap[x["packet_id"]]["publication_identity"]["pmid"] for x in rows))
        checks.append({"batch": i, "count": len(rows), "raw_input_sha256": raw_sha, "adjudications_sha256": digest(base / "adjudications.jsonl"), "identity_confidence_and_hashes_match": good, "manifest_check": check_manifest(base)})
        labels.extend(rows)
    integrity = {"overlay_checks": checks, "neutral_packet_manifest_check": check_manifest(PACK),
                 "pilot_manifest_check": check_manifest(PILOT),
                 "packet_bijection": len(labels) == len({x["packet_id"] for x in labels}) == len(inputs) == 79 and {x["packet_id"] for x in labels} == {x["packet_id"] for x in inputs},
                 "confidence_categorical_preserved": all(isinstance(x["confidence"], str) for x in labels),
                 "historical_adjudications_rewritten": False, "labels_loaded_after_gate_outputs_written": True}
    acquired = readl(PILOT / "fulltext_acquired_manifest.jsonl")
    integrity["original_acquisition_assignment_bijection"] = len(acquired) == len(inputs) and {
        (x["case_id"], x["canonical_publication_id"]) for x in acquired
    } == {(x["case_id"], x["publication_id"]) for x in inputs}
    integrity["status"] = "PASS" if integrity["packet_bijection"] and integrity["original_acquisition_assignment_bijection"] and all(x["identity_confidence_and_hashes_match"] and not x["manifest_check"]["invalid_hashes"] for x in checks) and not integrity["neutral_packet_manifest_check"]["invalid_hashes"] and not integrity["pilot_manifest_check"]["invalid_hashes"] else "FAIL"
    if integrity["status"] != "PASS": raise ValueError("Overlay integrity failure")
    return {x["packet_id"]: x for x in labels}, integrity


def utility(rows):
    """Conservative observable utility proxy; no inference from mere uncertainty."""
    eligible = [x for x in rows if x["label"]["acquisition_decision"] in ACCEPTABLE]
    reported = [x for x in eligible if x["label"]["fulltext_resolved_fields"]]
    unknown = [x["packet_id"] for x in eligible if not x["label"]["fulltext_resolved_fields"]]
    return {**rate(len(reported), len(rows)), "interpretation": "reviewer-reported-resolution utility proxy",
            "exact_candidate_field_linked_utility_rate": None,
            "exact_utility_estimation_state": "NOT_ESTIMABLE_WITHOUT_FIELD_LINKAGE_AND_NEEDED_TO_ATTEMPT_DECISION",
            "reported_resolution_packet_ids": [x["packet_id"] for x in reported],
            "unknown_attempt_necessity_packet_ids": unknown,
            "limitation": "Overlays lack an explicit fulltext-needed-to-attempt-resolution decision and field-level links; unresolved fields alone do not establish utility."}


def quality(rows, state_key):
    a = [x for x in rows if x[state_key] == "TIER_A"]; b = [x for x in rows if x[state_key] == "TIER_B"]
    direct = lambda rs: sum(x["label"]["relevance_state"] == "DIRECTLY_RELEVANT" for x in rs)
    justified = lambda rs: sum(x["label"]["acquisition_decision"] == "JUSTIFIED" for x in rs)
    acceptable = lambda rs: sum(x["label"]["acquisition_decision"] in ACCEPTABLE for x in rs)
    return {
        "paper_count": len(rows), "tier_a_count": len(a), "tier_b_count": len(b),
        "tier_a_direct_relevance_rate": rate(direct(a), len(a)),
        "tier_a_justification_rate": rate(justified(a), len(a)),
        "tier_a_acceptability_rate": rate(acceptable(a), len(a)),
        "tier_b_direct_relevance_rate": rate(direct(b), len(b)),
        "tier_b_justification_rate": rate(justified(b), len(b)),
        "tier_b_utility_rate": utility(b),
        "overall_direct_relevance_rate": rate(direct(rows), len(rows)),
        "overall_acquisition_justification_rate": rate(justified(rows), len(rows)),
        "overall_acquisition_acceptability_rate": rate(acceptable(rows), len(rows)),
        "relevance_state_counts": counts(x["label"]["relevance_state"] for x in rows),
        "acquisition_decision_counts": counts(x["label"]["acquisition_decision"] for x in rows),
    }


def evaluate_variant(rows, enabled=None, complete=False):
    output = []
    for x in rows:
        state = x["state"] if complete else ("REJECT" if set(x["reject_gate_names"]) & set(enabled or []) else x["original_tier"])
        output.append({**x, "evaluation_state": state})
    retained = [x for x in output if x["evaluation_state"] in {"TIER_A", "TIER_B"}]
    rejected = [x for x in output if x["evaluation_state"] == "REJECT"]
    direct_total = sum(x["label"]["relevance_state"] == "DIRECTLY_RELEVANT" for x in rows)
    dr = sum(x["label"]["relevance_state"] == "DIRECTLY_RELEVANT" for x in retained)
    return {
        "retained_count": len(retained), "rejected_count": len(rejected),
        "counterfactual_tier_a_count": sum(x["evaluation_state"] == "TIER_A" for x in output),
        "counterfactual_tier_b_count": sum(x["evaluation_state"] == "TIER_B" for x in output),
        "unresolved_contract_count": sum(x["evaluation_state"] is None for x in output),
        "directly_relevant_retained": dr, "directly_relevant_rejected": sum(x["label"]["relevance_state"] == "DIRECTLY_RELEVANT" for x in rejected),
        "acceptable_retained": sum(x["label"]["acquisition_decision"] in ACCEPTABLE for x in retained),
        "not_justified_retained": sum(x["label"]["acquisition_decision"] == "NOT_JUSTIFIED" for x in retained),
        "wrong_evidence_mode_rejected": sum(x["label"]["relevance_state"] == "WRONG_EVIDENCE_MODE" for x in rejected),
        "wrong_context_unit_rejected": sum(x["label"]["contaminant_class"] == "wrong_biological_unit" for x in rejected),
        "wrong_endpoint_rejected": sum(x["label"]["relevance_state"] == "WRONG_ENDPOINT" for x in rejected),
        "wrong_relation_rejected": sum(x["label"]["contaminant_class"] == "association_vs_functional_relation" for x in rejected),
        "gate_triggered_rejections": {g: sum(g in x["reject_gate_names"] for x in rejected)
                                      for g in ["evidence_mode", "context", "endpoint", "relation", "entity", "therapy"]},
        "rejected_packet_ids": [x["packet_id"] for x in rejected], "retained_packet_ids": [x["packet_id"] for x in retained],
        "calibration_set_direct_relevant_retention": rate(dr, direct_total),
        "retained_set_metrics": quality(retained, "evaluation_state"), "true_literature_recall": "not_estimable",
        "rejected_category_counts_basis": {
            "wrong_evidence_mode_rejected": "original relevance_state=WRONG_EVIDENCE_MODE",
            "wrong_endpoint_rejected": "original relevance_state=WRONG_ENDPOINT",
            "wrong_context_unit_rejected": "original contaminant_class=wrong_biological_unit",
            "wrong_relation_rejected": "original contaminant_class=association_vs_functional_relation",
            "gate_triggered_rejections": "separate positive gate-trigger counts; multiple gates may overlap",
        },
    }


def decompose(rows):
    failures = []
    patterns = {
        "biological_context_unit_mismatch": r"biological|cancer.cell|neutrophil|neuronal|immune tolerance|organism|non.cancer",
        "endpoint_mismatch": r"endpoint|outcome|viability|survival|tolerance|adaptation|prognos",
        "relation_mismatch": r"relation|functional|causal|mechanism|association|perturbation",
        "therapy_mismatch": r"therapy|treatment|drug|anticancer",
    }
    for x in rows:
        label = x["label"]
        if label["acquisition_decision"] != "NOT_JUSTIFIED": continue
        components = label["mismatched_target_components"]
        failures.append({
            "packet_id": x["packet_id"], "case_id": x["case_id"], "ambiguity_tier": x["ambiguity_tier"],
            "original_tier": x["original_tier"], "relevance_state": label["relevance_state"],
            "contaminant_class": label["contaminant_class"], "mismatched_target_components": components,
            "supported_mismatch_dimensions": {k: [c for c in components if re.search(p, c, re.I)] for k, p in patterns.items()},
            "dimension_policy": "nonexclusive lexical indexing of verbatim reviewer mismatch components; empty means unspecified",
            "query_family_ids": x["query_family_ids"], "query_variant_ids": x["query_variant_ids"],
            "metadata_first_seen_depth": x["metadata_first_seen_depth"], "rank_in_first_query": x["rank_in_first_query"],
            "publication_types": x["scientific_input"]["publication_types"],
            "reviewer_rationale": label["reviewer_rationale"], "evidence_mode_gate": x["gates"]["evidence_mode"],
        })
    summary = {"not_justified_count": len(failures),
               "by_relevance_state": counts(x["relevance_state"] for x in failures),
               "by_contaminant_class": counts(x["contaminant_class"] or "unassigned" for x in failures),
               "by_case": counts(x["case_id"] for x in failures), "by_ambiguity_tier": counts(x["ambiguity_tier"] for x in failures),
               "by_original_tier": counts(x["original_tier"] for x in failures),
               "by_query_family_multilabel": counts(q for x in failures for q in x["query_family_ids"]),
               "by_query_variant_multilabel": counts(q for x in failures for q in x["query_variant_ids"]),
               "by_publication_type_multilabel": counts(t for x in failures for t in x["publication_types"]),
               "by_exact_metadata_depth": counts(str(x["metadata_first_seen_depth"]) for x in failures),
               "by_mismatch_dimension_nonexclusive": {k: sum(bool(x["supported_mismatch_dimensions"][k]) for x in failures) for k in patterns}}
    return failures, summary


def query_diagnostics(rows, queries, group):
    id_field = f"query_{group}_id"; line_field = f"query_{group}_ids"
    ids = sorted({(q["case_id"], q[id_field]) for q in queries.values()})
    answer = []
    for cid, qid in ids:
        linked = [x for x in rows if x["case_id"] == cid and qid in x[line_field]]
        first = [x for x in linked if (x["first_discovery_query"] if group == "variant" else queries[x["first_discovery_query"]]["query_family_id"]) == qid]
        exclusive = [x for x in linked if len(x[line_field]) == 1]
        retained = [x for x in linked if x["state"] in {"TIER_A", "TIER_B"}]
        rejected_noise = [x for x in linked if x["state"] == "REJECT" and x["label"]["acquisition_decision"] == "NOT_JUSTIFIED"]
        answer.append({
            "case_id": cid, id_field: qid, "linked_adjudicated_acquisitions": len(linked),
            "linked_directly_relevant": sum(x["label"]["relevance_state"] == "DIRECTLY_RELEVANT" for x in linked),
            "counterfactual_retained": len(retained), "rejected_not_justified": len(rejected_noise),
            "counterfactual_retained_directly_relevant": sum(x["label"]["relevance_state"] == "DIRECTLY_RELEVANT" for x in retained),
            "counterfactual_rejected_directly_relevant": sum(x["state"] == "REJECT" and x["label"]["relevance_state"] == "DIRECTLY_RELEVANT" for x in linked),
            "counterfactual_retained_justified": sum(x["label"]["acquisition_decision"] == "JUSTIFIED" for x in retained),
            "counterfactual_retained_acceptable": sum(x["label"]["acquisition_decision"] in ACCEPTABLE for x in retained),
            "mostly_rejected_noise_in_audited_acquisitions": bool(linked) and len(rejected_noise) > len(linked)/2,
            "zero_observed_direct_value": bool(linked) and not any(x["label"]["relevance_state"] == "DIRECTLY_RELEVANT" for x in linked),
            "no_adjudicated_acquisition_not_zero_literature_value": not linked,
            "only_review_contamination": bool(linked) and all(x["label"]["contaminant_class"] == "review_only" for x in linked),
            "first_discovery_additions": len(first), "first_discovery_direct_additions": sum(x["label"]["relevance_state"] == "DIRECTLY_RELEVANT" for x in first),
            "exclusive_acquired_contributions": len(exclusive), "exclusive_direct_contributions": sum(x["label"]["relevance_state"] == "DIRECTLY_RELEVANT" for x in exclusive),
            "packet_ids": [x["packet_id"] for x in linked], "scope": "only acquired and reviewed subset; shared lineage counts overlap",
        })
    return answer


def depth_diagnostics(rows, metadata, depth, queries):
    by_identity = {(x["case_id"], x["publication_id"]): x for x in rows}
    trajectories = []; running = defaultdict(Counter)
    raw_ranks = {}
    for qid, q in queries.items():
        if q["execution_status"] == "executed":
            for rank, pmid in enumerate(readj(ROOT / q["raw_response_snapshot_ref"])["esearchresult"]["idlist"], 1):
                raw_ranks[(qid, str(pmid))] = rank
    for md in metadata:
        cid = md["case_id"]; pub = md["canonical_publication_id"]; d = depth[(cid, pub.split(":")[1])]
        row = by_identity.get((cid, pub)); label = row["label"] if row else None
        first = md.get("first_seen_query_variant_id") or md["query_lineage"][0]
        running[cid]["audited"] += bool(row)
        running[cid]["direct"] += bool(label and label["relevance_state"] == "DIRECTLY_RELEVANT")
        running[cid]["not_justified"] += bool(label and label["acquisition_decision"] == "NOT_JUSTIFIED")
        trajectories.append({
            "case_id": cid, "publication_id": pub, "metadata_first_seen_depth": d,
            "first_discovery_query": first, "query_execution_order": queries[first]["execution_order"] if first else None,
            "rank_in_first_query": raw_ranks[(first, pub.split(":")[1])],
            "adjudication_observed": bool(row), "relevance_state": label["relevance_state"] if label else None,
            "acquisition_decision": label["acquisition_decision"] if label else None,
            "cumulative_adjudicated": running[cid]["audited"], "cumulative_observed_direct": running[cid]["direct"],
            "cumulative_observed_not_justified": running[cid]["not_justified"],
            "missing_labels_are_not_irrelevant": True,
            "depth_31_to_60_direct_yield": "UNOBSERVED_ABSTRACT_SCREENING_CEILING_30" if d > 30 else "within_observed_prefix",
            "saturation_inferred": False,
        })
    return trajectories


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--output", type=Path, default=DEFAULT_OUT)
    ap.add_argument("--gate-worker", type=Path)
    args = ap.parse_args()
    if args.gate_worker:
        gate_worker(args.gate_worker); return
    out = args.output.resolve()
    if out.is_relative_to(ROOT) and out != DEFAULT_OUT:
        raise ValueError("In-repository output must be the designated new candidate run; historical outputs cannot be overwritten")
    if out.exists() and any(p.name not in REQUIRED for p in out.iterdir()):
        raise ValueError("Output contains unrelated files; choose a fresh external temporary directory")
    out.mkdir(parents=True, exist_ok=True)
    before = protected_hashes(out)
    inputs, metadata, depth, queries = prepare_inputs()
    from search_plan_v22_candidate_gates import contracts
    candidate_contracts = contracts()
    for name, contract in candidate_contracts.items(): writej(out / name, contract)
    writel(out / "counterfactual_gate_inputs.jsonl", inputs)
    engine_hash = digest(ENGINE)
    command = [sys.executable, str(Path(__file__).resolve()), "--gate-worker", str(out / "counterfactual_gate_inputs.jsonl")]
    completed = subprocess.run(command, cwd=ROOT, text=True, capture_output=True, check=True)
    worker = json.loads(completed.stdout)
    outputs = worker["outputs"]
    writel(out / "counterfactual_gate_outputs.jsonl", outputs)
    output_hash_before_labels = digest(out / "counterfactual_gate_outputs.jsonl")
    # Strict phase boundary: no overlay row or packet body has been read above.
    labels, integrity = load_overlays(inputs)
    writej(out / "adjudication_overlay_integrity.json", integrity)
    by_id = {x["packet_id"]: x for x in outputs}
    rows = [{**x, **by_id[x["packet_id"]], "label": labels[x["packet_id"]]} for x in inputs]
    baseline = quality(rows, "original_tier")
    baseline.update({"metrics_recalculated_from_five_original_overlays": True, "justification_is_not_scientific_precision": True,
                     "reviewer_type_counts": counts(x["label"]["reviewer_type"] for x in rows),
                     "metric_terminology_correction": "Historical Tier A acquisition precision is named tier_a_justification_rate; direct relevance is computed independently."})
    writej(out / "baseline_metrics.json", baseline)
    failures, failure_summary = decompose(rows)
    writel(out / "failure_inventory.jsonl", failures)
    mode_audit = []
    for x in rows:
        if x["label"]["relevance_state"] != "WRONG_EVIDENCE_MODE": continue
        g = x["gates"]["evidence_mode"]
        status = "DETECTABLE_PRE_ACQUISITION" if g["state"] == "NON_PRIMARY_EVIDENCE_DETECTED" else ("AMBIGUOUS_PRE_ACQUISITION" if g["state"] == "EVIDENCE_MODE_UNRESOLVED" else "NOT_DETECTABLE_PRE_ACQUISITION")
        mode_audit.append({"packet_id": x["packet_id"], "case_id": x["case_id"], "classification": status,
                           "evidence": g["evidence"], "gate_reasons": g["reasons"], "publication_types": x["scientific_input"]["publication_types"],
                           "pre_acquisition_evidence_refs": x["pre_acquisition_evidence_refs"], "acquisition_decision": x["label"]["acquisition_decision"]})
    writel(out / "evidence_mode_detectability_audit.jsonl", mode_audit)
    evaluation = evaluate_variant(rows, complete=True)
    evaluation.update({"calibration_only": True, "held_out_validated": False, "no_replacement_acquisitions_simulated": True,
                       "no_new_query_or_budget_changes": True, "gate_code_sha256_before_labels": engine_hash})
    writej(out / "counterfactual_evaluation.json", evaluation)
    stages = [("baseline_v21", []), ("plus_evidence_mode", ["evidence_mode"]), ("plus_context", ["evidence_mode", "context"]),
              ("plus_endpoint", ["evidence_mode", "context", "endpoint"]), ("plus_relation", ["evidence_mode", "context", "endpoint", "relation"])]
    ablations = []
    previous = set()
    for name, enabled in stages + [("complete_v22_candidate", None)]:
        e = evaluate_variant(rows, enabled, complete=enabled is None)
        rejected = set(e["rejected_packet_ids"])
        ablations.append({"stage": name, "enabled_gates": enabled or ([] if name == "baseline_v21" else "all"),
                          "incrementally_removed_count": len(rejected - previous), "incrementally_removed_packet_ids": sorted(rejected - previous), **e})
        previous = rejected
    writel(out / "incremental_gate_ablation.jsonl", ablations)
    evidence_failures = [x for x in failures if x["relevance_state"] == "WRONG_EVIDENCE_MODE"]
    detectable_ids = {x["packet_id"] for x in mode_audit if x["classification"] == "DETECTABLE_PRE_ACQUISITION"}
    failure_summary["review_only_sensitivity"] = {
        "wrong_evidence_mode_among_not_justified": rate(len(evidence_failures), len(failures)),
        "preacquisition_detectable_wrong_evidence_mode_total": len(detectable_ids),
        "preacquisition_detectable_wrong_evidence_mode_not_justified": sum(x["packet_id"] in detectable_ids for x in evidence_failures),
        "evidence_mode_only_counterfactual": ablations[1],
        "attribution": "label association and replay detection; not a causal fraction",
    }
    writej(out / "failure_decomposition_summary.json", failure_summary)
    gates = sorted({g for x in rows for g in x["reject_gate_names"]})
    overlap = {
        "individual_gate_rejections": {g: [x["packet_id"] for x in rows if g in x["reject_gate_names"]] for g in gates},
        "pairwise_overlap": [{"gates": [a, b], "count": sum(a in x["reject_gate_names"] and b in x["reject_gate_names"] for x in rows)} for i, a in enumerate(gates) for b in gates[i+1:]],
        "multiply_flagged_packet_ids": [x["packet_id"] for x in rows if len(x["reject_gate_names"]) > 1],
        "overlap_patterns": counts("+".join(sorted(x["reject_gate_names"])) for x in rows if x["reject_gate_names"]),
        "causal_independence_claimed": False, "ablation_order_dependent": True,
    }
    writej(out / "gate_overlap_audit.json", overlap)
    case_metrics = []
    for cid in sorted({x["case_id"] for x in rows}):
        subset = [x for x in rows if x["case_id"] == cid]; cf = evaluate_variant(subset, complete=True)
        removed = [x for x in subset if x["state"] == "REJECT"]
        case_metrics.append({"case_id": cid, "original_acquired": len(subset),
                             "original_direct_relevance": sum(x["label"]["relevance_state"] == "DIRECTLY_RELEVANT" for x in subset),
                             "original_acceptable_acquisition": sum(x["label"]["acquisition_decision"] in ACCEPTABLE for x in subset),
                             "counterfactual_retained": cf["retained_count"], "counterfactual_direct_relevance": cf["directly_relevant_retained"],
                             "counterfactual_acceptable": cf["acceptable_retained"], "directly_relevant_lost": cf["directly_relevant_rejected"],
                             "removed_contaminants": counts(x["label"]["contaminant_class"] or "unassigned" for x in removed),
                             "dominant_removed_contaminant": Counter(x["label"]["contaminant_class"] or "unassigned" for x in removed).most_common(1),
                             "retained_set_metrics": cf["retained_set_metrics"]})
    writel(out / "counterfactual_case_metrics.jsonl", case_metrics)
    for group in ["family", "variant"]:
        writel(out / f"query_{group}_failure_contribution.jsonl", query_diagnostics(rows, queries, group))
    writel(out / "retrieval_depth_quality_curve.jsonl", depth_diagnostics(rows, metadata, depth, queries))
    heldout = {
        "activation_state": "CANDIDATE_NOT_PRODUCTION_ACTIVATED_NOT_HELD_OUT_VALIDATED",
        "requirements": ["Freeze gate code/lexical match policy before a new held-out cohort", "Separate reviewers and adjudicate both axes independently",
                         "Include primary studies, reviews, mixed evidence, non-cancer contexts, and multiple endpoints", "Audit rejected candidates to measure false rejection",
                         "Prespecify relevant-retention and acceptability thresholds", "Record explicit fulltext-needed and uncertainty-resolution links for Tier B utility",
                         "Run a separately authorized Recall Tail Probe beyond the abstract-screened prefix", "Keep retrieval query/budget effects distinguishable from gate effects"],
        "calibration_retention_is_not_literature_recall": True,
        "current_corpus_selection_limit": "Only original 79 acquired assignments evaluated; no judgments for the metadata tail or unacquired candidates",
    }
    writej(out / "heldout_validation_requirements.json", heldout)
    replay = json.loads(subprocess.run(command, cwd=ROOT, text=True, capture_output=True, check=True).stdout)
    code = ENGINE.read_text()
    tree = ast.parse(code)
    imports = [node.module or "" for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)] + [a.name for node in ast.walk(tree) if isinstance(node, ast.Import) for a in node.names]
    leak = {
        "gate_code_sha256_before_label_read": engine_hash, "gate_code_sha256_after_evaluation": digest(ENGINE),
        "gate_outputs_sha256_before_label_read": output_hash_before_labels,
        "gate_outputs_sha256_after_evaluation": digest(out / "counterfactual_gate_outputs.jsonl"),
        "execution_order": ["prepare_label_free_inputs", "restricted_worker_generates_outputs", "persist_outputs_and_hash", "read_overlays", "evaluate"],
        "worker_io_audit": worker["audit"], "gate_module_imports": imports,
        "scientific_input_prohibited_keys_absent": all(not (nested_keys(x["scientific_input"]) & PROHIBITED) for x in inputs),
        "gate_source_label_field_mentions": sorted(k for k in {"relevance_state", "acquisition_decision", "contaminant_class", "reviewer_rationale", "confidence", "packet_id", "pmid", "case_id"} if re.search(rf'["\x27]{k}["\x27]', code)),
        "replayed_after_label_read_identical": replay["outputs"] == outputs,
        "calibration_design_aware_of_failure_classes": True,
        "runtime_label_access": False, "fulltext_read_during_gate_execution": False,
    }
    writej(out / "label_leakage_audit.json", leak)
    after = protected_hashes(out)
    changed = sorted(p for p in set(before) | set(after) if before.get(p) != after.get(p))
    safety = {
        "network_calls": 0, "provider_calls": 0, "llm_calls": 0, "downloads": 0, "extraction_invoked": False,
        "historical_assets_modified": bool(changed), "changed_protected_paths": changed,
        "protected_file_count": len(before), "protected_hashes_before_sha256": objhash(before), "protected_hashes_after_sha256": objhash(after),
        "protected_scopes": PROTECTED_SCOPES, "byte_hashing_does_not_parse_fulltext": True,
        "protected_root_files_included": True,
        "protected_scope_exclusions": [ref(DEFAULT_OUT), "requested output directory", "__pycache__", ref(ENGINE), ref(Path(__file__))],
        "query_family_variants_budgets_order_unchanged": not changed, "production_behavior_modified": False,
        "search_plan_v22_activation_state": "candidate_not_activated", "formal_v3_modified": False, "atlas_activated": False,
        "active_pointer_changed": False, "variational_em_called": False, "git_commit_created": False,
    }
    writej(out / "scientific_state_safety_audit.json", safety)
    writej(out / "production_leakage_audit.json", safety)
    checks = {
        "exact_79_overlay_bijection": integrity["packet_bijection"], "source_overlay_integrity": integrity["status"] == "PASS",
        "preacquisition_only_inputs": leak["scientific_input_prohibited_keys_absent"],
        "gate_outputs_frozen_before_label_join": output_hash_before_labels == digest(out / "counterfactual_gate_outputs.jsonl"),
        "gate_code_unchanged_after_label_join": engine_hash == digest(ENGINE),
        "restricted_worker_no_forbidden_access": not worker["audit"]["forbidden_reads"] and worker["audit"]["network_events"] == 0,
        "no_label_or_identifier_branch_fields_in_gate_source": not leak["gate_source_label_field_mentions"],
        "all_79_outputs_in_requested_three_states": len(outputs) == 79 and all(x["state"] in {"TIER_A", "TIER_B", "REJECT"} for x in outputs),
        "tier_b_resolution_ledgers": all(x["known_plausible_fields"] and x["unresolved_fields_requiring_fulltext"] and x["why_fulltext_can_resolve"] and not x["reject_gate_names"] for x in outputs if x["state"] == "TIER_B"),
        "reject_requires_positive_mismatch": all(x["reject_gate_names"] for x in outputs if x["state"] == "REJECT"),
        "historical_queries_budgets_state_unchanged": before == after,
        "deterministic_replay": replay["outputs"] == outputs,
        "counterfactual_partition": evaluation["retained_count"] + evaluation["rejected_count"] == 79,
        "candidate_not_activated": safety["search_plan_v22_activation_state"] == "candidate_not_activated",
        "required_payload_artifacts_present": all((out / x).exists() for x in REQUIRED if x not in {"final_validation.json", "manifest.json", "summary.json"}),
    }
    kept = evaluation["retained_set_metrics"]
    valid = all(checks.values())
    promising = (valid and kept["overall_direct_relevance_rate"]["value"] is not None
                 and kept["overall_direct_relevance_rate"]["value"] > baseline["overall_direct_relevance_rate"]["value"]
                 and kept["overall_acquisition_acceptability_rate"]["value"] > baseline["overall_acquisition_acceptability_rate"]["value"]
                 and evaluation["calibration_set_direct_relevant_retention"]["value"] >= .9)
    decision = "CALIBRATION_REPLAY_INVALID" if not valid else ("V22_GATE_REPAIR_PROMISING_HELDOUT_VALIDATION_REQUIRED" if promising else "V22_GATE_REPAIR_INSUFFICIENT")
    summary = {
        "completion_state": decision, "status": "completed" if valid else "failed", "calibration_paper_count": 79,
        "baseline_direct_relevance_rate": baseline["overall_direct_relevance_rate"]["value"],
        "baseline_acquisition_justification_rate": baseline["overall_acquisition_justification_rate"]["value"],
        "baseline_acquisition_acceptability_rate": baseline["overall_acquisition_acceptability_rate"]["value"],
        "wrong_evidence_mode_count": len(mode_audit), "evidence_mode_preacquisition_detectable_count": len(detectable_ids),
        "counterfactual_retained_count": evaluation["retained_count"], "counterfactual_rejected_count": evaluation["rejected_count"],
        "counterfactual_direct_relevance_rate": kept["overall_direct_relevance_rate"]["value"],
        "counterfactual_acquisition_justification_rate": kept["overall_acquisition_justification_rate"]["value"],
        "counterfactual_acquisition_acceptability_rate": kept["overall_acquisition_acceptability_rate"]["value"],
        "calibration_set_direct_relevant_retention": evaluation["calibration_set_direct_relevant_retention"]["value"],
        "counterfactual_tier_a_count": evaluation["counterfactual_tier_a_count"], "counterfactual_tier_b_count": evaluation["counterfactual_tier_b_count"],
        "counterfactual_tier_b_utility_rate": kept["tier_b_utility_rate"]["value"], "tier_b_utility_is_reported_resolution_proxy": True,
        "decision_rule": "Both retained-set rates improve and calibration direct retention >=0.9; diagnostic candidate selection, not held-out proof",
        **{k: safety[k] for k in ["network_calls", "provider_calls", "llm_calls", "downloads", "historical_assets_modified", "search_plan_v22_activation_state"]},
    }
    writej(out / "summary.json", summary)
    checks["required_artifacts_present"] = all((out / x).exists() for x in REQUIRED if x not in {"final_validation.json", "manifest.json"})
    writej(out / "final_validation.json", {"status": "PASS" if all(checks.values()) else "FAIL", "checks": checks})
    manifest = {"required_artifact_count": len(REQUIRED), "gate_engine_source_sha256": engine_hash,
                "generator_sha256": digest(Path(__file__)), "files": [{"path": p.name, "sha256": digest(p), "bytes": p.stat().st_size} for p in sorted(out.iterdir()) if p.is_file() and p.name != "manifest.json"]}
    writej(out / "manifest.json", manifest)
    print(json.dumps(summary, indent=2))
    if not all(checks.values()): raise SystemExit(1)


if __name__ == "__main__":
    main()
