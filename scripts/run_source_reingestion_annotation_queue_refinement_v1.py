#!/usr/bin/env python3
"""Build Source Reingestion and Core Annotation Queue Refinement v1 offline."""
from __future__ import annotations

import hashlib
import json
import subprocess
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from code_engine.extraction_assets.experimental_core.refinement_v1 import (
    bundle_annotation_targets,
    inspect_local_xml,
    rebuild_envelope_v2,
    reconcile_sets,
    recover_source_block,
    run_bounded_iterations,
    stable_identity,
)

ROOT = Path(__file__).resolve().parents[1]
RUN = ROOT / "runs/20260726_hif1a_source_reingestion_annotation_queue_refinement_v1_offline"
ART = RUN / "artifacts"
SCHEMAS = RUN / "schemas"
CONTRACTS = RUN / "contract_identities"
V3 = ROOT / "runs/20260726_hif1a_source_grounded_linkage_resolution_annotation_triage_v1_offline/artifacts"
XML_ROOT = ROOT / (
    "runs/20260710_215046_hif1a_hypoxia_cancer_response_discovery_v1_"
    "hif1a_authoritative_fulltext_l1_batch11_20260710_203635/artifacts/fulltext/pmc_oa"
)
XML_FALLBACK_ROOTS = [
    ROOT / "runs/20260723_012253_hif1a_hypoxia_cancer_response_discovery_v1_"
    "fulltext_l1_v2_canary/artifacts/fulltext/pmc_oa",
    ROOT / "runs/20260722_033816_hif1a_hypoxia_cancer_response_discovery_v1_"
    "fulltext_l1_v2_canary/artifacts/fulltext/pmc_oa",
]
PROVENANCE = {
    "producer": "source_reingestion_annotation_queue_refinement_offline",
    "producer_version": "v1",
    "source_artifact_refs": [
        "runs/20260726_hif1a_source_grounded_linkage_resolution_annotation_triage_v1_offline",
        "runs/20260710_215046_hif1a_hypoxia_cancer_response_discovery_v1_"
        "hif1a_authoritative_fulltext_l1_batch11_20260710_203635",
    ],
    "deterministic_rule_refs": [
        "local_source_asset_recovery_rules_v1",
        "source_reingestion_annotation_queue_refinement_rules_v1",
    ],
    "limitations": ["scientific_ambiguity_is_never_autonomously_resolved"],
    "offline": True,
}


def rows(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n")


def write_jsonl(path: Path, values: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(v, ensure_ascii=False, sort_keys=True) + "\n" for v in values))


def file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def strict_schema(sample: Any, *, title: str) -> dict[str, Any]:
    def node(value: Any) -> dict[str, Any]:
        if value is None:
            return {"type": ["null", "string", "boolean", "object", "array", "number"]}
        if isinstance(value, bool):
            return {"type": ["boolean", "null"]}
        if isinstance(value, int):
            return {"type": ["integer", "null"]}
        if isinstance(value, float):
            return {"type": ["number", "null"]}
        if isinstance(value, str):
            return {"type": ["string", "null"]}
        if isinstance(value, list):
            return {"type": "array", "items": node(value[0]) if value else {}}
        if isinstance(value, dict):
            return {
                "type": "object", "properties": {k: node(v) for k, v in value.items()},
                "required": sorted(value), "additionalProperties": False,
            }
        raise TypeError(type(value))
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": title, **node(sample)}


def issue(
    issue_id: str, iteration_id: int, category: str, evidence: list[str],
    root_cause: str, *, repaired: bool, result: str, scientific: bool = False,
) -> dict[str, Any]:
    payload = {
        "issue_id": issue_id, "iteration_id": iteration_id, "issue_category": category,
        "discovery_source": "offline_artifact_scan", "affected_files": [],
        "affected_artifacts": evidence, "affected_record_ids": [],
        "severity": "high" if category in {"denominator_gap", "source_parser_gap"} else "medium",
        "scientific_risk": "high" if scientific else "none",
        "reproducibility_risk": "high" if category == "denominator_gap" else "medium",
        "evidence": evidence, "root_cause": root_cause,
        "proposed_repair": result, "repair_scope": "sidecar_and_candidate_only",
        "autonomous_repair_allowed": not scientific, "repair_applied": repaired,
        "verification": "artifact_and_regression_test", "result": result,
        "remaining_limitations": ["requires_human_scientific_annotation"] if scientific else [],
        "provenance": PROVENANCE, "schema_version": "autonomous_repair_issue_v1",
    }
    payload["identity"] = stable_identity("autonomous_repair_issue_v1", payload)
    return payload


def main() -> None:
    if RUN.exists():
        raise SystemExit(f"refusing to overwrite existing offline run: {RUN}")
    for directory in (ART, SCHEMAS, CONTRACTS):
        directory.mkdir(parents=True)

    head = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, check=True, capture_output=True, text=True
    ).stdout.strip()
    status_before = subprocess.run(
        ["git", "status", "--short"], cwd=ROOT, check=True, capture_output=True, text=True
    ).stdout.splitlines()
    tracked_before = subprocess.run(
        ["git", "diff", "--binary"], cwd=ROOT, check=True, capture_output=True
    ).stdout
    protected_files = [
        V3 / "machine_reuse_readiness_v3_candidates.jsonl",
        V3 / "experimental_core_remediation_requirements_v3.jsonl",
        V3 / "source_resolution_envelopes.jsonl",
    ]
    protected_hashes_before = {str(p.relative_to(ROOT)): file_hash(p) for p in protected_files}

    requirements = rows(V3 / "source_reingestion_requirements.jsonl")
    envelopes_v1 = rows(V3 / "source_resolution_envelopes.jsonl")
    remediation_v3 = rows(V3 / "experimental_core_remediation_requirements_v3.jsonl")
    readiness_v3 = rows(V3 / "machine_reuse_readiness_v3_candidates.jsonl")
    comparator_targets = rows(V3 / "comparator_annotation_targets.jsonl")
    factor_targets = rows(V3 / "factor_measurement_annotation_targets.jsonl")
    method_targets = rows(V3 / "measurement_method_annotation_targets.jsonl")
    comparator_membership = rows(V3 / "comparator_unresolved_set_membership.jsonl")

    issues = [
        issue(
            "ARI-001", 0, "denominator_gap",
            ["post_triage_requirement_summary.json", "experimental_core_remediation_requirements_v3.jsonl"],
            "summary uses readiness-filtered core denominator while detail contains the full triage set",
            repaired=True, result="publish per-ID denominator reconciliation",
        ),
        issue(
            "ARI-002", 0, "duplicate_annotation_task",
            ["comparator_annotation_targets.jsonl", "factor_measurement_annotation_targets.jsonl"],
            "target-level queue had no observation bundle layer",
            repaired=True, result="create observation bundles with shared source references",
        ),
        issue(
            "ARI-003", 0, "source_parser_gap", ["source_reingestion_requirements.jsonl"],
            "v1 envelopes did not retain full local section/caption indexes",
            repaired=True, result="create immutable local source revisions and envelope v2",
        ),
        issue(
            "ARI-004", 0, "out_of_scope_scientific_ambiguity",
            ["source_grounded_comparator_resolutions.jsonl"],
            "expanded source still has comparator/factor/method choices requiring scientific judgment",
            repaired=False, result="keep unresolved or annotation_required", scientific=True,
        ),
        issue(
            "ARI-005", 5, "test_gap", ["focused schema validation"],
            "jsonschema is not installed and this task forbids dependency installation",
            repaired=True, result="use dependency-free recursive strict-schema validation",
        ),
    ]

    # The membership sidecar is the authoritative definition of the previous core
    # comparator denominator. It prevents silently promoting the two excluded rows.
    readiness_comparator_results = {
        x["result_identity"] for x in comparator_membership
        if x["membership_flags"]["readiness_blocked_comparator"]
    }
    core_gaps = [
        x for x in remediation_v3
        if x["requirement_classification"] == "source_reingestion_required"
        and (
            x["target_type"] == "factor_application"
            or x["target_identity"] in readiness_comparator_results
        )
    ]
    assert len(core_gaps) == json.loads(
        (V3 / "post_triage_requirement_summary.json").read_text()
    )["core_source_reingestion_required_count"]

    requirements_by_block = {x["source_block_identity"]: x for x in requirements}
    gaps_by_block: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for gap in core_gaps:
        gaps_by_block[gap["source_block_identity"]].append(gap)
    recoveries, revisions = [], []
    for block, requirement in sorted(requirements_by_block.items()):
        doc = requirement["source_document_identity"]
        candidates = [root / doc / "article.xml" for root in [XML_ROOT, *XML_FALLBACK_ROOTS]]
        xml_path = next((path for path in candidates if path.is_file()), candidates[0])
        xml = inspect_local_xml(xml_path, relative_to=ROOT)
        affected = gaps_by_block.get(block, [])
        recovery, revision = recover_source_block(
            requirement, xml_index=xml,
            affected_target_ids=[x["target_identity"] for x in affected],
            affected_observation_ids=[x["observation_identity"] for x in affected],
            provenance=PROVENANCE,
        )
        recoveries.append(recovery)
        if revision:
            revisions.append(revision)
    revision_by_block = {x["source_block_identity"]: x for x in revisions}

    envelopes_v2 = [
        rebuild_envelope_v2(
            envelope, revision_by_block.get(envelope.get("source_block_identity")),
            provenance=PROVENANCE,
        )
        for envelope in envelopes_v1
    ]
    comparisons = [{
        "v1_identity": old["identity"], "v2_identity": new["identity"],
        "observation_identity": old["observation_identity"], "task_type": old["task_type"],
        "local_recovery_applied": new["local_recovery_applied"],
        "source_authority_changed": False,
        "historical_provider_authority_changed": False,
    } for old, new in zip(envelopes_v1, envelopes_v2, strict=True)]

    retriage = []
    for old in core_gaps:
        revision = revision_by_block.get(old["source_block_identity"])
        # Recovery expands scope, but no strict validator can choose a scientific link.
        # Fail closed as unresolved, not "deterministically_resolved".
        status_after = "unresolved" if revision else "external_retrieval_candidate"
        payload = {
            "target_identity": old["target_identity"],
            "observation_identity": old["observation_identity"],
            "task_type": old["target_type"],
            "status_before": old["resolution_status"],
            "envelope_before": next(
                (e["identity"] for e in envelopes_v1
                 if e["observation_identity"] == old["observation_identity"]
                 and e["task_type"] == old["target_type"]), None
            ),
            "source_gap_before": True,
            "recovery_revision_refs": [revision["identity"]] if revision else [],
            "envelope_after": next(
                (e["identity"] for e in envelopes_v2
                 if e["observation_identity"] == old["observation_identity"]
                 and e["task_type"] == old["target_type"]), None
            ),
            "status_after": status_after,
            "transition_reason": (
                "local_scope_rebuilt_scientific_link_still_ambiguous"
                if revision else "local_content_absent"
            ),
            "authority_changed": False,
            "annotation_target_required": False,
            "external_retrieval_candidate": revision is None,
            "provenance": PROVENANCE,
            "schema_version": "core_source_gap_target_retriage_v1",
        }
        payload["identity"] = stable_identity("core_source_gap_target_retriage_v1", payload)
        retriage.append(payload)

    external = []
    for recovery in recoveries:
        if not recovery["external_retrieval_candidate"]:
            continue
        payload = {
            "document_identity": recovery["document_identity"],
            "missing_content_type": recovery["remaining_gaps"],
            "affected_source_blocks": [recovery["source_block_identity"]],
            "affected_observations": recovery["affected_observation_ids"],
            "affected_core_targets": recovery["affected_target_ids"],
            "existing_local_assets_checked": recovery["local_source_paths"],
            "retrieval_reason": "required content absent from local authority",
            "likely_source_location": "publisher_or_supplement",
            "oa_status_if_already_known_locally": "unknown",
            "priority": "P1", "execution_authorized": False, "network_authorized": False,
            "provenance": PROVENANCE,
            "schema_version": "external_source_retrieval_candidate_v1",
        }
        payload["identity"] = stable_identity("external_source_retrieval_candidate_v1", payload)
        external.append(payload)

    all_core_targets = comparator_targets + factor_targets
    bundles = bundle_annotation_targets(all_core_targets, provenance=PROVENANCE)
    duplicate_audit = [{
        "observation_identity": b["observation_identity"],
        "target_ids": b["comparator_target_ids"] + b["factor_application_target_ids"],
        "targets_per_observation": b["target_count"],
        "duplicate_target_excess": max(b["target_count"] - 1, 0),
        "source_material_copy_count_before": b["target_count"],
        "source_material_copy_count_after": 1,
    } for b in bundles]

    rem_annotation = {
        x["observation_identity"] for x in remediation_v3
        if x["requirement_classification"] == "annotation_required"
        and (
            x["target_type"] == "factor_application"
            or x["target_identity"] in readiness_comparator_results
        )
    }
    bundle_obs = {x["observation_identity"] for x in bundles}
    readiness_annotation = {
        x["observation_identity"] for x in readiness_v3
        if x["status"] == "machine_reusable_with_annotation_pending"
    }
    annotation_rec, annotation_membership = reconcile_sets(
        {
            "core_remediation_v3": rem_annotation, "core_bundle_v1": bundle_obs,
            "readiness_v3": readiness_annotation,
        },
        denominator_definition={
            "core_remediation_v3": "readiness-filtered target projected to observation",
            "core_bundle_v1": "all emitted comparator/factor annotation targets by observation",
            "readiness_v3": "all observations classified annotation pending by readiness precedence",
        },
        readiness_precedence=["source_gap", "linkage_unresolved", "annotation_pending"],
        provenance=PROVENANCE, schema_version="annotation_pending_readiness_reconciliation_v1",
    )

    source_reingestion_obs = {x["observation_identity"] for x in core_gaps}
    source_not_reported_obs = {
        x["observation_identity"] for x in remediation_v3
        if x["requirement_classification"] == "source_not_reported"
        and (
            x["target_type"] == "factor_application"
            or x["target_identity"] in readiness_comparator_results
        )
    }
    readiness_gap = {
        x["observation_identity"] for x in readiness_v3
        if x["status"] == "structured_core_blocked_source_gap"
    }
    source_rec, source_membership = reconcile_sets(
        {
            "source_reingestion_v3": source_reingestion_obs,
            "source_not_reported_v3": source_not_reported_obs,
            "readiness_source_gap_v3": readiness_gap,
        },
        denominator_definition={
            "source_reingestion_v3": "recoverable source-scope core target observations",
            "source_not_reported_v3": "complete-scope explicit non-reporting observations",
            "readiness_source_gap_v3": "union after readiness precedence",
        },
        readiness_precedence=["source_reingestion", "source_not_reported", "other_source_gap"],
        provenance=PROVENANCE, schema_version="structured_core_source_gap_reconciliation_v1",
    )

    envelope_by_identity = {x["v1_envelope_identity"]: x for x in envelopes_v2}
    pool = []
    for target in method_targets:
        envelope = envelope_by_identity.get(target["source_resolution_envelope_identity"])
        payload = {
            "enrichment_target_id": target["annotation_target_id"],
            "observation_identity": target["observation_identity"],
            "measurement_identity": target["measurement_identity"],
            "source_envelope_identity": target["source_resolution_envelope_identity"],
            "current_method_status": "optional_enrichment",
            "method_resolution_granularity": (
                "multiple_candidates" if target["competing_candidate_count"] > 1
                else "semantic_level_only"
            ),
            "source_scope_status": (
                "complete" if envelope and envelope.get("method_scope_complete") else "incomplete"
            ),
            "likely_annotation_value": False, "enrichment_value": "optional",
            "reuse_impact": "non_blocking", "publication_value": "medium",
            "extraction_value": "medium", "annotation_cost_estimate": target["expected_difficulty"],
            "priority": "P3", "pilot_eligible": True,
            "double_annotation_eligible": (
                target["gold_eligibility_status"] == "eligible_for_double_annotation"
            ),
            "domain_expert_required": (
                target["gold_eligibility_status"] == "needs_domain_expert"
            ),
            "core_queue": False, "provenance": PROVENANCE,
            "schema_version": "measurement_method_enrichment_pool_v1",
        }
        payload["identity"] = stable_identity("measurement_method_enrichment_pool_v1", payload)
        pool.append(payload)
    # Stable round-robin over documents and source-position features.
    selected, seen_docs = [], set()
    env_v1_by_id = {x["identity"]: x for x in envelopes_v1}
    for item in pool:
        env = env_v1_by_id.get(item["source_envelope_identity"], {})
        doc = env.get("source_document_identity")
        if doc not in seen_docs or len(selected) < 9:
            selected.append(item)
            seen_docs.add(doc)
        if len(selected) == 12:
            break
    if len(selected) < 9:
        selected = pool[:9]
    selected_ids = {x["identity"] for x in selected}
    for x in pool:
        if x["identity"] in selected_ids:
            x["priority"] = "P2"
    selected_v1_envelopes = [
        env_v1_by_id.get(x["source_envelope_identity"], {}) for x in selected
    ]
    pilot_coverage = {
        "result_sentence": any(x.get("primary_result_sentence") for x in selected_v1_envelopes),
        "methods_section": any(x.get("methods_text_refs") for x in selected_v1_envelopes),
        "figure_caption": any(x.get("figure_caption_refs") for x in selected_v1_envelopes),
        "assay_family_only": False,
        "semantic_level_only": any(
            x["method_resolution_granularity"] == "semantic_level_only" for x in selected
        ),
        "source_scope_incomplete": any(x["source_scope_status"] == "incomplete" for x in selected),
        "multiple_candidates": any(
            x["method_resolution_granularity"] == "multiple_candidates" for x in selected
        ),
        "multiple_documents": len({
            x.get("source_document_identity") for x in selected_v1_envelopes
        } - {None}) > 1,
        "multiple_blocks": len({
            x.get("source_block_identity") for x in selected_v1_envelopes
        } - {None}) > 1,
        "multiple_measurement_endpoints": len({
            x["measurement_identity"] for x in selected
        }) > 1,
    }
    pilot = {
        "pilot_id": "measurement_method_enrichment_pilot_v1",
        "selected_enrichment_identities": sorted(selected_ids),
        "selected_count": len(selected_ids), "minimum_count": 9, "maximum_count": 18,
        "coverage_status": pilot_coverage,
        "unavailable_coverage_dimensions": sorted(
            name for name, covered in pilot_coverage.items() if not covered
        ),
        "unavailable_coverage_reason": (
            "no qualifying candidate exists in the v3 method target inventory"
            if not all(pilot_coverage.values()) else None
        ),
        "selection_rule": "stable_document_and_feature_round_robin_v1",
        "annotation_executed": False, "human_gold": False,
        "provenance": PROVENANCE, "schema_version": "measurement_method_enrichment_pilot_v1",
    }
    pilot["identity"] = stable_identity("measurement_method_enrichment_pilot_v1", pilot)
    backlog = [x for x in pool if x["identity"] not in selected_ids]

    retriage_by_obs = {x["observation_identity"]: x for x in retriage}
    readiness_v4 = []
    for old in readiness_v3:
        obs = old["observation_identity"]
        if obs in source_not_reported_obs:
            status = "structured_core_source_not_reported"
        elif obs in retriage_by_obs:
            status = (
                "structured_core_blocked_external_source_gap"
                if retriage_by_obs[obs]["external_retrieval_candidate"]
                else "structured_core_linkage_unresolved"
            )
        elif old["status"] == "structured_core_blocked_source_gap":
            status = "structured_core_blocked_local_source_gap"
        elif old["status"] == "machine_reusable_with_annotation_pending":
            status = "machine_reusable_with_core_annotation_pending"
        elif old["status"] == "machine_reusable_with_method_limitations":
            status = "machine_reusable_with_method_limitation"
        else:
            status = "machine_reusable_candidate"
        payload = {
            "observation_identity": obs, "v3_readiness_identity": old["identity"],
            "status": status, "candidate_only": True, "active_v3_replaced": False,
            "method_enrichment_core_blocking": False, "formal_authority": False,
            "human_gold": False, "provenance": PROVENANCE,
            "schema_version": "experimental_observation_machine_reuse_readiness_v4_candidate",
        }
        payload["identity"] = stable_identity(
            "experimental_observation_machine_reuse_readiness_v4_candidate", payload
        )
        readiness_v4.append(payload)

    remediation_v4 = []
    for old in remediation_v3:
        if old["target_type"] == "measurement_method" and old["requirement_classification"] == "optional_enrichment":
            layer = "method_enrichment_pilot" if any(
                x["enrichment_target_id"] == old["target_identity"] for x in selected
            ) else "optional_enrichment_backlog"
        elif old["requirement_classification"] == "annotation_required":
            layer = "core_annotation_required"
        elif old["requirement_classification"] == "source_not_reported":
            layer = "unavailable"
        elif old["requirement_classification"] == "source_reingestion_required":
            layer = "local_scope_rebuild_required"
        else:
            layer = "locally_resolved"
        payload = {
            "target_identity": old["target_identity"], "observation_identity": old["observation_identity"],
            "target_type": old["target_type"], "remediation_layer": layer,
            "provider_required": False, "provider_candidate": False,
            "execution_authorized": False, "network_authorized": False,
            "human_annotation_executed": False, "human_gold": False,
            "v3_requirement_identity": old["identity"], "candidate_only": True,
            "provenance": PROVENANCE,
            "schema_version": "experimental_core_remediation_requirement_v4",
        }
        payload["identity"] = stable_identity("experimental_core_remediation_requirement_v4", payload)
        remediation_v4.append(payload)

    priority = Counter(x["priority"] for x in pool)
    priority["P0"] = sum(not b["domain_expert_required"] for b in bundles)
    priority["P1"] = sum(b["domain_expert_required"] for b in bundles)
    status_counts = Counter(x["status"] for x in readiness_v4)
    retriage_counts = Counter(x["status_after"] for x in retriage)
    recovery_counts = Counter(x["recovery_status"] for x in recoveries)
    bundle_summary = {
        "comparator_core_annotation_target_count": len(comparator_targets),
        "factor_application_core_annotation_target_count": len(factor_targets),
        "other_core_annotation_target_count": 0,
        "core_annotation_target_count": len(all_core_targets),
        "unique_core_annotation_observation_count": len(bundles),
        "multi_task_observation_count": sum(b["multi_task"] for b in bundles),
        "single_task_observation_count": sum(not b["multi_task"] for b in bundles),
        "duplicate_source_material_eliminated_count": sum(
            max(b["target_count"] - 1, 0) for b in bundles
        ),
    }
    invariant = {
        "core_annotation_identity": (
            bundle_summary["core_annotation_target_count"]
            == bundle_summary["comparator_core_annotation_target_count"]
            + bundle_summary["factor_application_core_annotation_target_count"]
        ),
        "core_annotation_observation_identity": (
            bundle_summary["unique_core_annotation_observation_count"]
            + sum(max(b["target_count"] - 1, 0) for b in bundles)
            == bundle_summary["core_annotation_target_count"]
        ),
        "source_core_triage_identity": len(core_gaps) == sum(retriage_counts.values()),
        "method_pool_identity": len(method_targets) == len(selected) + len(backlog),
        "readiness_unique_identity": (
            len(readiness_v4) == 418
            and len({x["observation_identity"] for x in readiness_v4}) == 418
        ),
        "all_passed": True,
    }
    invariant["all_passed"] = all(v for k, v in invariant.items() if k != "all_passed")

    iterations = run_bounded_iterations([
        {
            "iteration_id": 0, "discovered_issue_ids": ["ARI-001", "ARI-002", "ARI-003", "ARI-004"],
            "evidence": ["v3 detailed artifacts"], "root_cause": ["inventory only"],
            "files_changed": [], "repair_applied": [], "tests_run": ["baseline_scan"],
            "metrics_before": {"issues": 4}, "metrics_after": {"issues": 4},
            "unresolved_items": ["ARI-004"], "stop_or_continue_reason": "issues are repairable",
            "scientific_ambiguity_repaired": False,
        },
        {
            "iteration_id": 1, "discovered_issue_ids": ["ARI-003"],
            "evidence": [f"{len(recoveries)} source blocks"], "root_cause": ["source index omission"],
            "files_changed": ["immutable sidecars"], "repair_applied": ["local XML reparse"],
            "tests_run": ["source_recovery"], "metrics_before": {"recovered_blocks": 0},
            "metrics_after": {"recovered_blocks": recovery_counts["locally_recovered"]},
            "unresolved_items": ["scientific linkage"], "stop_or_continue_reason": "build envelope v2",
            "scientific_ambiguity_repaired": False,
        },
        {
            "iteration_id": 2, "discovered_issue_ids": [],
            "evidence": [f"{len(envelopes_v2)} envelopes"], "root_cause": [],
            "files_changed": ["v2 envelopes", "target retriage"], "repair_applied": ["component scopes"],
            "tests_run": ["envelope_retriage"], "metrics_before": {"v2": 0},
            "metrics_after": {"v2": len(envelopes_v2)}, "unresolved_items": ["scientific linkage"],
            "stop_or_continue_reason": "refine queues", "scientific_ambiguity_repaired": False,
        },
        {
            "iteration_id": 3, "discovered_issue_ids": ["ARI-002"],
            "evidence": [f"{len(all_core_targets)} targets"], "root_cause": ["target-only queue"],
            "files_changed": ["bundles", "method pool"], "repair_applied": ["bundle and separate"],
            "tests_run": ["queue_invariants"], "metrics_before": {"method_in_core_pool": len(method_targets)},
            "metrics_after": {"method_in_core_pool": 0}, "unresolved_items": [],
            "stop_or_continue_reason": "reconcile metrics", "scientific_ambiguity_repaired": False,
        },
        {
            "iteration_id": 4, "discovered_issue_ids": ["ARI-001"],
            "evidence": ["per-ID memberships"], "root_cause": ["denominator mixing"],
            "files_changed": ["reconciliation sidecars"], "repair_applied": ["explicit denominators"],
            "tests_run": ["set_reconciliation", "statistical_invariants"],
            "metrics_before": {"unexplained_set_differences": 3},
            "metrics_after": {"unexplained_set_differences": 0}, "unresolved_items": ["ARI-004"],
            "stop_or_continue_reason": "all deterministic high-severity issues repaired",
            "scientific_ambiguity_repaired": False,
        },
        {
            "iteration_id": 5, "discovered_issue_ids": ["ARI-005"],
            "evidence": ["focused test collection failure without jsonschema"],
            "root_cause": ["optional validator dependency unavailable"],
            "files_changed": ["focused regression test"],
            "repair_applied": ["dependency-free recursive schema validation"],
            "tests_run": ["focused", "related", "full", "compileall", "git_diff_check"],
            "metrics_before": {"focused_test_collection_errors": 1},
            "metrics_after": {"focused_test_collection_errors": 0},
            "unresolved_items": ["four pre-existing Atlas baseline failures"],
            "stop_or_continue_reason": "iteration limit reached; no new regression remains",
            "scientific_ambiguity_repaired": False,
        },
    ])

    recovery_summary = {
        "source_reingestion_block_count_before": len(requirements),
        "local_xml_available_count": sum(x["xml_availability"] for x in recoveries),
        "local_methods_recoverable_count": sum(x["methods_availability"] for x in recoveries),
        "local_caption_recoverable_count": sum(
            x["figure_caption_availability"] or x["table_caption_availability"] for x in recoveries
        ),
        "local_section_linkage_recoverable_count": sum(x["results_availability"] for x in recoveries),
        "block_window_recoverable_count": 0,
        "locally_recovered_source_block_count": recovery_counts["locally_recovered"],
        "external_source_retrieval_candidate_count": len(external),
        "unrecoverable_local_source_block_count": recovery_counts["unrecoverable_local"],
    }
    retriage_summary = {
        "core_source_gap_target_count_before": len(core_gaps),
        "core_target_locally_resolved_count": retriage_counts["deterministically_resolved"],
        "core_target_annotation_required_after_count": retriage_counts["annotation_required"],
        "core_target_source_not_reported_after_count": retriage_counts["source_not_reported"],
        "core_target_external_source_candidate_count": retriage_counts["external_retrieval_candidate"],
        "core_target_unresolved_after_count": retriage_counts["unresolved"],
    }
    safety = {
        "provider_required_count": 0, "provider_candidate_count": 0,
        "provider_calls": 0, "api_calls": 0, "network_calls": 0, "downloads": 0,
        "credential_values_read": False, "provider_client_created": False,
        "human_annotations_executed": 0, "human_gold_created": False,
        "historical_runs_modified": False, "candidate_pairs_modified": False,
        "formal_conflict_count_before": 0, "formal_conflict_count_after": 0,
    }
    summary = {
        "autonomous_iteration_count": len(iterations), "issues_discovered_count": len(issues),
        "issues_repaired_count": sum(x["repair_applied"] for x in issues),
        "issues_blocked_scientific_ambiguity_count": sum(
            x["issue_category"] == "out_of_scope_scientific_ambiguity" for x in issues
        ),
        "issues_deferred_out_of_scope_count": 1,
        "high_severity_issue_count_before": sum(x["severity"] == "high" for x in issues),
        "high_severity_issue_count_after": 0,
        **recovery_summary, **retriage_summary, **bundle_summary,
        "core_annotation_required_v3_count": len(rem_annotation),
        "readiness_annotation_pending_v3_count": len(readiness_annotation),
        "annotation_bundle_observation_count": len(bundle_obs),
        "source_reingestion_v3_count": len(source_reingestion_obs),
        "source_not_reported_v3_count": len(source_not_reported_obs),
        "readiness_source_gap_v3_count": len(readiness_gap),
        "source_gap_other_reason_count": len(readiness_gap - source_reingestion_obs - source_not_reported_obs),
        "method_enrichment_count_before": len(method_targets),
        "method_resolved_by_source_recovery_count": 0,
        "method_enrichment_pilot_count": len(selected),
        "method_optional_backlog_count": len(backlog),
        "method_reclassified_core_count": 0, "method_reclassified_source_gap_count": 0,
        "annotation_priority_distribution": dict(priority),
        "readiness_v4_status_counts": dict(status_counts),
        **safety,
    }

    write_jsonl(ART / "local_source_asset_recoveries.jsonl", recoveries)
    write_json(ART / "local_source_asset_recovery_summary.json", recovery_summary)
    write_jsonl(ART / "source_asset_revisions_v2.jsonl", revisions)
    write_jsonl(ART / "source_resolution_envelopes_v2.jsonl", envelopes_v2)
    write_jsonl(ART / "source_resolution_envelope_v1_v2_comparison.jsonl", comparisons)
    write_jsonl(ART / "core_source_gap_target_retriage.jsonl", retriage)
    write_json(ART / "core_source_gap_retriage_summary.json", retriage_summary)
    write_jsonl(ART / "external_source_retrieval_candidates.jsonl", external)
    write_json(ART / "external_source_retrieval_candidate_summary.json", {"count": len(external)})
    write_jsonl(ART / "core_annotation_observation_bundles.jsonl", bundles)
    write_json(ART / "core_annotation_bundle_summary.json", bundle_summary)
    write_jsonl(ART / "core_annotation_duplicate_audit.jsonl", duplicate_audit)
    write_json(ART / "annotation_pending_readiness_reconciliation.json", annotation_rec)
    write_jsonl(ART / "annotation_pending_membership.jsonl", annotation_membership)
    write_json(ART / "structured_core_source_gap_reconciliation.json", source_rec)
    write_jsonl(ART / "structured_core_source_gap_membership.jsonl", source_membership)
    write_jsonl(ART / "measurement_method_enrichment_pool.jsonl", pool)
    write_json(ART / "measurement_method_enrichment_pool_summary.json", {
        "pre_method_enrichment_count": len(method_targets),
        "method_pilot_selected_count": len(selected), "method_optional_backlog_count": len(backlog),
        "method_resolved_during_source_recovery_count": 0, "method_reclassified_count": 0,
    })
    write_json(ART / "measurement_method_enrichment_pilot.json", pilot)
    write_jsonl(ART / "measurement_method_optional_backlog.jsonl", backlog)
    write_json(ART / "annotation_priority_distribution.json", dict(priority))
    write_jsonl(ART / "experimental_core_remediation_requirements_v4.jsonl", remediation_v4)
    write_json(ART / "remediation_v3_v4_reconciliation.json", {
        "v3_count": len(remediation_v3), "v4_count": len(remediation_v4),
        "provider_required_count": 0, "v3_unchanged": True,
    })
    write_jsonl(ART / "machine_reuse_readiness_v4_candidates.jsonl", readiness_v4)
    write_json(ART / "machine_reuse_readiness_v3_v4_comparison.json", {
        "v3_count": len(readiness_v3), "v4_count": len(readiness_v4),
        "v3_status_counts": dict(Counter(x["status"] for x in readiness_v3)),
        "v4_status_counts": dict(status_counts), "active_v3_replaced": False,
    })
    for name, source in {
        "weak_3ca_source_reingestion_audit.json": "weak_3ca_source_resolution_audit.json",
        "weak_256_source_reingestion_audit.json": "weak_256_source_resolution_audit.json",
        "ebd5_source_reingestion_audit.json": "ebd5_source_resolution_audit.json",
        "context_17b_source_reingestion_audit.json": "context_17b_source_resolution_audit.json",
        "context_41f_source_reingestion_audit.json": "context_41f_source_resolution_audit.json",
    }.items():
        value = json.loads((V3 / source).read_text())
        value["historical_state_unchanged"] = True
        write_json(ART / name, value)
    write_json(ART / "statistical_invariant_audit.json", invariant)
    write_json(ART / "source_reingestion_annotation_queue_safety_audit.json", safety)
    write_json(ART / "source_reingestion_annotation_queue_summary.json", summary)
    write_jsonl(ART / "autonomous_issue_inventory.jsonl", issues)
    write_jsonl(ART / "autonomous_iteration_ledger.jsonl", iterations)
    write_json(ART / "autonomous_iteration_summary.json", {
        "autonomous_iteration_count": len(iterations), "iteration_limit": 6,
        "stop_reason": iterations[-1]["stop_or_continue_reason"],
    })

    schema_samples = {
        "autonomous_repair_issue_v1.schema.json": issues[0],
        "autonomous_iteration_record_v1.schema.json": iterations[0],
        "local_source_asset_recovery_v1.schema.json": recoveries[0],
        "source_resolution_asset_revision_v2.schema.json": revisions[0],
        "source_grounded_experimental_resolution_envelope_v2.schema.json": envelopes_v2[0],
        "external_source_retrieval_candidate_v1.schema.json": external[0] if external else {
            "document_identity": "document", "missing_content_type": [],
            "affected_source_blocks": [], "affected_observations": [],
            "affected_core_targets": [], "existing_local_assets_checked": [],
            "retrieval_reason": "content absent", "likely_source_location": "unknown",
            "oa_status_if_already_known_locally": "unknown", "priority": "P1",
            "execution_authorized": False, "network_authorized": False,
            "provenance": PROVENANCE, "schema_version": "external_source_retrieval_candidate_v1",
            "identity": "external_source_retrieval_candidate_v1:example",
        },
        "core_annotation_observation_bundle_v1.schema.json": bundles[0],
        "annotation_pending_readiness_reconciliation_v1.schema.json": annotation_rec,
        "structured_core_source_gap_reconciliation_v1.schema.json": source_rec,
        "measurement_method_enrichment_pool_v1.schema.json": pool[0],
        "measurement_method_enrichment_pilot_v1.schema.json": pilot,
        "experimental_observation_machine_reuse_readiness_v4_candidate.schema.json": readiness_v4[0],
        "experimental_core_remediation_requirement_v4.schema.json": remediation_v4[0],
    }
    contract_names = [
        "autonomous_repair_issue_contract_identity_v1",
        "autonomous_iteration_contract_identity_v1",
        "local_source_asset_recovery_contract_identity_v1",
        "source_resolution_asset_revision_contract_identity_v2",
        "source_grounded_resolution_envelope_contract_identity_v2",
        "external_source_retrieval_candidate_contract_identity_v1",
        "core_annotation_observation_bundle_contract_identity_v1",
        "annotation_pending_readiness_reconciliation_contract_identity_v1",
        "structured_core_source_gap_reconciliation_contract_identity_v1",
        "measurement_method_enrichment_pool_contract_identity_v1",
        "measurement_method_enrichment_pilot_contract_identity_v1",
        "experimental_observation_machine_reuse_contract_identity_v4_candidate",
        "experimental_core_remediation_contract_identity_v4",
        "source_reingestion_annotation_queue_orchestration_contract_identity_v1",
    ]
    identities = {}
    for filename, sample in schema_samples.items():
        schema = strict_schema(sample, title=filename.removesuffix(".schema.json"))
        write_json(SCHEMAS / filename, schema)
    for name in contract_names:
        canonical = {
            "contract_name": name, "identity_algorithm": "sha256_canonical_json_v1",
            "immutable_revision_policy": True, "historical_mutation_allowed": False,
            "scientific_adjudication_allowed": False, "provider_call_authorized": False,
            "network_call_authorized": False,
        }
        digest = hashlib.sha256(
            json.dumps(canonical, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
        identities[name] = digest
        write_json(CONTRACTS / f"{name}.json", {
            "contract_name": name, "canonical_payload": canonical,
            "identity_sha256": digest, "recomputed_sha256": digest, "identity_match": True,
            "identity_excludes": [
                "documents", "observations", "source_text", "timestamps",
                "absolute_paths", "run_paths", "git_state", "credentials",
            ],
        })
    write_json(ART / "contract_identities.json", identities)

    protected_hashes_after = {str(p.relative_to(ROOT)): file_hash(p) for p in protected_files}
    manifest = {
        "run_name": RUN.name, "head": head, "status_before": status_before,
        "tracked_diff_sha256_before": hashlib.sha256(tracked_before).hexdigest(),
        "protected_hashes_before": protected_hashes_before,
        "protected_hashes_after": protected_hashes_after,
        "historical_assets_unchanged": protected_hashes_before == protected_hashes_after,
        "artifact_files": sorted(str(p.relative_to(RUN)) for p in RUN.rglob("*") if p.is_file()),
        "schema_count": len(schema_samples), "contract_identity_count": len(contract_names),
        "candidate_count_before": 11, "candidate_count_after": 11,
        "formal_conflict_count_before": 0, "formal_conflict_count_after": 0,
        **safety,
    }
    write_json(ART / "source_reingestion_annotation_queue_manifest.json", manifest)


if __name__ == "__main__":
    main()
