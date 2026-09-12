#!/usr/bin/env python3
"""Fail-closed offline preflight for held-out v1 network retrieval."""
from __future__ import annotations

from collections import Counter
import hashlib
import json
from pathlib import Path
import subprocess


ROOT = Path(__file__).resolve().parents[1]
FREEZE = ROOT / "runs/20260909_search_plan_v22_heldout_v1_case_freeze_offline"
OUT = ROOT / "runs/20260909_search_plan_v22_heldout_v1_network_preflight_offline"
NETWORK_RUN = ROOT / "runs/20260909_search_plan_v22_heldout_v1_network_retrieval"
GATE = ROOT / "tools/search_plan_v22_candidate_gates.py"
GATE_BASELINE = ROOT / "runs/20260908_search_plan_v22_depth180_supplemental_oa_acquisition_v1/baseline.json"
EXPECTED_PROTOCOL_HASH = "2aac90361272de64eb055099602ae68e696c760628fec3835c0f29eca63ca127"
CASE_IDS = [f"heldout_v1_{index:03d}" for index in range(1, 9)]
OUTPUTS = [
    "protocol_verification.json",
    "freeze_hash_verification.json",
    "heldout_boundary_verification.json",
    "heldout_case_execution_inventory.jsonl",
    "frozen_network_execution_plan.jsonl",
    "scientific_state_safety_audit.json",
    "validation.json",
    "manifest.json",
    "summary.json",
]


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def object_sha(value: object) -> str:
    payload = json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(payload.encode()).hexdigest()


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.write_text(
        "".join(json.dumps(row, sort_keys=True, ensure_ascii=True) + "\n" for row in rows),
        encoding="utf-8",
    )


def relative(path: Path) -> str:
    return str(path.resolve().relative_to(ROOT))


def prior_heldout_hits() -> tuple[list[str], list[str]]:
    references: list[str] = []
    adjudications: list[str] = []
    label_markers = (
        '"relevance_state"',
        '"acquisition_decision"',
        '"automatic_relevance_prediction"',
        '"manual_relevance_status"',
    )
    result = subprocess.run(
        ["rg", "-l", "heldout_v1_00[1-8]", str(ROOT / "runs"),
         "--glob", "*.json", "--glob", "*.jsonl", "--glob", "*.txt", "--glob", "*.md"],
        cwd=ROOT, capture_output=True, text=True, check=False,
    )
    fail_if(result.returncode not in {0, 1}, f"Local held-out boundary scan failed: {result.stderr.strip()}")
    for raw_path in sorted(line for line in result.stdout.splitlines() if line):
        path = Path(raw_path).resolve()
        if FREEZE in path.resolve().parents or OUT in path.resolve().parents:
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        references.append(relative(path))
        if any(marker in text for marker in label_markers):
            adjudications.append(relative(path))
    return references, adjudications


def fail_if(condition: bool, message: str) -> None:
    if condition:
        raise RuntimeError(message)


def main() -> None:
    fail_if(not FREEZE.is_dir(), "Frozen held-out protocol run is missing")
    fail_if(NETWORK_RUN.exists(), "Formal held-out network retrieval run already exists")

    freeze_manifest = read_json(FREEZE / "freeze_manifest.json")
    component_checks = []
    for component in freeze_manifest["components"]:
        path = FREEZE / component["path"]
        actual = sha(path) if path.is_file() else None
        component_checks.append({
            "path": component["path"],
            "expected_sha256": component["sha256"],
            "actual_sha256": actual,
            "match": actual == component["sha256"],
        })
    recomputed_protocol_hash = object_sha(
        [(row["path"], row["actual_sha256"]) for row in component_checks]
    )
    freeze_hash_match = all(row["match"] for row in component_checks)
    protocol_hash_match = (
        freeze_hash_match
        and freeze_manifest["heldout_v1_protocol_sha256"] == EXPECTED_PROTOCOL_HASH
        and recomputed_protocol_hash == EXPECTED_PROTOCOL_HASH
    )
    fail_if(not protocol_hash_match, "Frozen protocol hash mismatch; preflight stopped")

    registry = read_jsonl(FREEZE / "heldout_case_registry.jsonl")
    scientific_targets = read_jsonl(FREEZE / "heldout_scientific_targets.jsonl")
    retrieval_targets = read_jsonl(FREEZE / "heldout_retrieval_targets.jsonl")
    families = read_jsonl(FREEZE / "heldout_query_families.jsonl")
    variants = read_jsonl(FREEZE / "heldout_query_variants.jsonl")
    queries = read_jsonl(FREEZE / "heldout_frozen_queries.jsonl")
    budget = read_json(FREEZE / "heldout_budget_binding.json")
    acquisition = read_json(FREEZE / "heldout_fulltext_acquisition_protocol.json")
    metrics = read_json(FREEZE / "heldout_evaluation_metrics_preregistration.json")
    heuristics = read_json(FREEZE / "heldout_evaluation_heuristics_preregistration.json")
    leakage = read_json(FREEZE / "production_leakage_audit.json")

    ambiguity = Counter(row["ambiguity_tier"] for row in registry)
    case_ids_exact = [row["case_id"] for row in registry] == CASE_IDS
    replacement_count = sum(bool(row["replacement_allowed"]) for row in registry)
    variant_by_id = {row["query_variant_id"]: row for row in variants}
    query_alignment = all(
        query["query_variant_id"] in variant_by_id
        and query["query_text"] == variant_by_id[query["query_variant_id"]]["query_text"]
        and query["query_order"] == variant_by_id[query["query_variant_id"]]["query_order"]
        and query["query_family_id"] == variant_by_id[query["query_variant_id"]]["query_family_id"]
        for query in queries
    )

    gate_baseline = read_json(GATE_BASELINE)["protected_hashes_before"][relative(GATE)]
    gate_actual = sha(GATE)
    gate_hash_match = gate_actual == gate_baseline
    prior_refs, prior_adjudications = prior_heldout_hits()

    invariants = {
        "protocol_hash_match": protocol_hash_match,
        "heldout_case_count_8": len(registry) == 8,
        "case_ids_and_order_exact": case_ids_exact,
        "low_count_2": ambiguity["LOW"] == 2,
        "medium_count_2": ambiguity["MEDIUM"] == 2,
        "high_count_4": ambiguity["HIGH"] == 4,
        "oncology_count_2": sum(row["oncology_case"] for row in registry) == 2,
        "non_oncology_count_6": sum(not row["oncology_case"] for row in registry) == 6,
        "query_family_count_48": len(families) == 48,
        "query_variant_count_48": len(variants) == 48,
        "frozen_query_count_48": len(queries) == 48,
        "query_order_exact": [row["query_order"] for row in queries] == list(range(1, 49)),
        "query_variant_alignment": query_alignment,
        "queries_frozen": all(row["frozen"] for row in queries),
        "targets_frozen": all(row["frozen"] for row in scientific_targets + retrieval_targets),
        "metrics_frozen": metrics["frozen_before_retrieval"],
        "evaluation_heuristics_frozen": heuristics["frozen_before_retrieval"],
        "budget_120_180_deferred": (
            budget["metadata_soft_checkpoint"] == 120
            and budget["metadata_hard_safety_ceiling"] == 180
            and budget["adaptive_early_stop_state"] == "deferred"
        ),
        "fulltext_max_10": acquisition["max_fulltext_selection_per_case"] == 10,
        "no_case_replacement": replacement_count == 0,
        "no_prior_heldout_results": not prior_refs,
        "no_prior_heldout_adjudications": not prior_adjudications,
        "gate_hash_match": gate_hash_match,
        "calibration_tuning_not_reopened": not leakage["calibration_tuning_reopened"],
        "formal_network_run_absent": not NETWORK_RUN.exists(),
    }
    fail_if(not all(invariants.values()), "Held-out boundary or frozen invariant mismatch; preflight stopped")

    protected_paths = [FREEZE / row["path"] for row in freeze_manifest["components"]] + [
        FREEZE / "freeze_manifest.json",
        GATE,
        GATE_BASELINE,
    ]
    protected_before = {relative(path): sha(path) for path in protected_paths}

    OUT.mkdir(parents=True, exist_ok=True)
    write_json(OUT / "protocol_verification.json", {
        "status": "PASS",
        "frozen_protocol_ref": relative(FREEZE),
        "expected_protocol_sha256": EXPECTED_PROTOCOL_HASH,
        "recomputed_protocol_sha256": recomputed_protocol_hash,
        "protocol_hash_match": protocol_hash_match,
        "heldout_case_count": len(registry),
        "low_count": ambiguity["LOW"],
        "medium_count": ambiguity["MEDIUM"],
        "high_count": ambiguity["HIGH"],
        "oncology_case_count": sum(row["oncology_case"] for row in registry),
        "non_oncology_case_count": sum(not row["oncology_case"] for row in registry),
        "query_family_count": len(families),
        "query_variant_count": len(variants),
        "frozen_query_count": len(queries),
        "metadata_soft_checkpoint": budget["metadata_soft_checkpoint"],
        "metadata_hard_safety_ceiling": budget["metadata_hard_safety_ceiling"],
        "adaptive_early_stop_state": budget["adaptive_early_stop_state"],
        "max_fulltext_selection_per_case": acquisition["max_fulltext_selection_per_case"],
        "network_authorized": False,
    })
    write_json(OUT / "freeze_hash_verification.json", {
        "status": "PASS",
        "component_count": len(component_checks),
        "components": component_checks,
        "all_component_hashes_match": freeze_hash_match,
        "expected_protocol_sha256": EXPECTED_PROTOCOL_HASH,
        "manifest_protocol_sha256": freeze_manifest["heldout_v1_protocol_sha256"],
        "recomputed_protocol_sha256": recomputed_protocol_hash,
        "protocol_hash_match": protocol_hash_match,
    })
    write_json(OUT / "heldout_boundary_verification.json", {
        "status": "PASS",
        "case_ids": CASE_IDS,
        "prior_heldout_result_refs": prior_refs,
        "prior_heldout_result_artifact_count": len(prior_refs),
        "prior_heldout_adjudication_refs": prior_adjudications,
        "prior_heldout_adjudication_count": len(prior_adjudications),
        "case_replacement_count": replacement_count,
        "query_modifications": 0,
        "target_modifications": 0,
        "gate_modifications": 0,
        "budget_modifications": 0,
        "gate_baseline_ref": relative(GATE_BASELINE),
        "gate_baseline_sha256": gate_baseline,
        "gate_actual_sha256": gate_actual,
        "gate_hash_match": gate_hash_match,
        "calibration_tuning_reopened": leakage["calibration_tuning_reopened"],
        "formal_network_run_exists": NETWORK_RUN.exists(),
        "external_literature_inspected": False,
    })

    case_inventory = []
    for registry_row in registry:
        case_id = registry_row["case_id"]
        case_queries = [row for row in queries if row["case_id"] == case_id]
        case_inventory.append({
            "case_id": case_id,
            "case_order": registry_row["case_order"],
            "ambiguity_tier": registry_row["ambiguity_tier"],
            "execution_state": "AWAITING_EXPLICIT_NETWORK_AUTHORIZATION",
            "network_authorized": False,
            "frozen_query_count": len(case_queries),
            "first_query_order": min(row["query_order"] for row in case_queries),
            "last_query_order": max(row["query_order"] for row in case_queries),
            "metadata_soft_checkpoint": 120,
            "maximum_unique_metadata_records": 180,
            "adaptive_early_stop_state": "deferred",
            "natural_exhaustion_must_be_recorded": True,
            "max_fulltext_selection": 10,
            "fulltext_eligibility": ["frozen Tier A or Tier B", "legal NCBI/PMC OA"],
            "provider_allowed": False,
            "llm_allowed": False,
            "scientific_extraction_allowed": False,
        })
    write_jsonl(OUT / "heldout_case_execution_inventory.jsonl", case_inventory)

    plan = []
    for query in queries:
        plan.append({
            "execution_order": query["query_order"],
            "case_id": query["case_id"],
            "case_order": query["case_order"],
            "query_family": query["query_family"],
            "query_family_id": query["query_family_id"],
            "query_variant": query["query_variant"],
            "query_variant_id": query["query_variant_id"],
            "query_text": query["query_text"],
            "sort": query["sort"],
            "source_query_sha256": object_sha({
                "query_order": query["query_order"],
                "query_family_id": query["query_family_id"],
                "query_variant_id": query["query_variant_id"],
                "query_text": query["query_text"],
                "sort": query["sort"],
            }),
            "deduplication_identity": "PMID within case; preserve all query provenance",
            "maximum_unique_metadata_records_for_case": 180,
            "metadata_soft_checkpoint": 120,
            "stop_at_soft_checkpoint": False,
            "permitted_early_completion_reasons": [
                "all frozen query families naturally exhausted",
                "fewer than 180 unique publications exist under frozen execution",
            ],
            "execution_state": "NOT_EXECUTED_AWAITING_EXPLICIT_AUTHORIZATION",
            "network_authorized": False,
        })
    write_jsonl(OUT / "frozen_network_execution_plan.jsonl", plan)

    protected_after = {relative(path): sha(path) for path in protected_paths}
    changed = sorted(path for path in protected_before if protected_before[path] != protected_after[path])
    safety = {
        "offline_preflight_only": True,
        "sections_completed": [1, 2, 3, 4],
        "network_authorized": False,
        "network_calls": 0,
        "provider_calls": 0,
        "llm_calls": 0,
        "downloads": 0,
        "extraction_calls": 0,
        "retrieval_performed": False,
        "external_literature_inspected": False,
        "relevance_labels_created": False,
        "historical_assets_modified": bool(changed),
        "changed_protected_paths": changed,
        "formal_network_run_created": NETWORK_RUN.exists(),
        "git_mutation_invoked": False,
    }
    write_json(OUT / "scientific_state_safety_audit.json", safety)

    validation = dict(invariants)
    validation.update({
        "query_modifications_zero": True,
        "target_modifications_zero": True,
        "gate_modifications_zero": True,
        "budget_modifications_zero": True,
        "network_calls_zero": safety["network_calls"] == 0,
        "provider_calls_zero": safety["provider_calls"] == 0,
        "llm_calls_zero": safety["llm_calls"] == 0,
        "extraction_calls_zero": safety["extraction_calls"] == 0,
        "historical_assets_unchanged": not safety["historical_assets_modified"],
        "execution_plan_has_48_queries": len(plan) == 48,
        "all_execution_rows_unauthorized": all(not row["network_authorized"] for row in plan),
    })
    write_json(OUT / "validation.json", {"status": "PASS" if all(validation.values()) else "FAIL", "checks": validation})
    write_json(OUT / "summary.json", {
        "status": "completed" if all(validation.values()) else "failed",
        "protocol_hash_match": protocol_hash_match,
        "heldout_case_count": len(registry),
        "frozen_query_count": len(queries),
        "query_modifications": 0,
        "target_modifications": 0,
        "gate_modifications": 0,
        "budget_modifications": 0,
        "network_authorized": False,
        "network_calls": 0,
        "provider_calls": 0,
        "llm_calls": 0,
        "downloads": 0,
        "extraction_calls": 0,
        "historical_assets_modified": bool(changed),
        "formal_network_run_created": NETWORK_RUN.exists(),
        "git_head": subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, check=True, capture_output=True, text=True
        ).stdout.strip(),
    })
    manifest_files = [
        {"path": path.name, "sha256": sha(path), "bytes": path.stat().st_size,
         "record_count": len(read_jsonl(path)) if path.suffix == ".jsonl" else 1}
        for path in sorted(OUT.iterdir()) if path.is_file() and path.name != "manifest.json"
    ]
    write_json(OUT / "manifest.json", {
        "required_artifact_count": len(OUTPUTS),
        "files": manifest_files,
        "protocol_sha256": EXPECTED_PROTOCOL_HASH,
        "network_authorized": False,
        "network_calls": 0,
        "provider_calls": 0,
        "llm_calls": 0,
        "downloads": 0,
        "extraction_calls": 0,
    })
    print(json.dumps(read_json(OUT / "summary.json"), indent=2))
    fail_if(not all(validation.values()), "Offline preflight validation failed")


if __name__ == "__main__":
    main()
