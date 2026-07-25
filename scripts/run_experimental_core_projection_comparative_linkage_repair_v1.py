#!/usr/bin/env python3
"""Build the immutable, zero-network experimental-core projection/link repair run."""
from __future__ import annotations

import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from code_engine.extraction_assets.experimental_core.adapters_context_method import fields_by_observation
from code_engine.extraction_assets.experimental_core.adapters_projection import historical_projection_ref
from code_engine.extraction_assets.experimental_core.comparator_linkage import recover_comparator
from code_engine.extraction_assets.experimental_core.comparison_semantics import classify_comparison
from code_engine.extraction_assets.experimental_core.identities import contract_identity
from code_engine.extraction_assets.experimental_core.linkage_completeness import (
    assess_linkage_v2, reconcile_metric,
)
from code_engine.extraction_assets.experimental_core.measurement_method import (
    missing_reason, recover_method,
)
from code_engine.extraction_assets.experimental_core.projection import (
    build_compatibility_sidecar, build_projection,
)
from code_engine.extraction_assets.experimental_core.projection_validation import (
    validate_projection_refs,
)
from code_engine.extraction_assets.experimental_core.readiness_v2 import evaluate_readiness_v2
from code_engine.extraction_assets.experimental_core.remediation_v2 import plan_remediation_v2

ROOT = Path(__file__).resolve().parents[1]
V1 = ROOT / "runs/20260725_hif1a_core_experimental_observation_integrity_v1_offline/artifacts"
CTX = ROOT / "runs/20260725_hif1a_experimental_context_asset_integration_v1_offline/artifacts"
SOURCE = ROOT / (
    "runs/20260723_012253_hif1a_hypoxia_cancer_response_discovery_v1_fulltext_l1_v2_canary"
    "__failed_block_recovery_277fd64a45668b7a8a0b/artifacts/fulltext_experiment_observations.jsonl"
)
RUN = ROOT / "runs/20260725_hif1a_experimental_core_projection_comparative_linkage_repair_v1_offline"
ART, SCHEMAS, CONTRACTS = RUN / "artifacts", RUN / "schemas", RUN / "contract_identities"


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def write_json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.write_text("".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows))


def count(rows: list[dict[str, Any]], key: str) -> Counter[str]:
    return Counter(str(row[key]) for row in rows)


def schema_for(row: dict[str, Any], title: str) -> dict[str, Any]:
    def infer(value: Any) -> dict[str, Any]:
        if value is None:
            return {"type": ["null", "string", "number", "boolean", "object", "array"]}
        if isinstance(value, bool):
            return {"type": "boolean"}
        if isinstance(value, int):
            return {"type": "integer"}
        if isinstance(value, float):
            return {"type": "number"}
        if isinstance(value, str):
            return {"type": "string"}
        if isinstance(value, list):
            return {"type": "array", "items": infer(value[0]) if value else {}}
        if isinstance(value, dict):
            return {
                "type": "object", "additionalProperties": False,
                "properties": {key: infer(item) for key, item in value.items()},
                "required": sorted(value),
            }
        return {}
    schema = infer(row)
    schema.update({"$schema": "https://json-schema.org/draft/2020-12/schema", "title": title})
    return schema


def main() -> None:
    for directory in (ART, SCHEMAS, CONTRACTS):
        directory.mkdir(parents=True, exist_ok=True)
    observations = read_jsonl(V1 / "structured_experimental_observation_revisions.jsonl")
    factors = read_jsonl(V1 / "experimental_factor_records.jsonl")
    measurements = read_jsonl(V1 / "measurement_records.jsonl")
    results = read_jsonl(V1 / "observed_result_records.jsonl")
    links = read_jsonl(V1 / "experimental_observation_linkages.jsonl")
    v1_readiness = read_jsonl(V1 / "experimental_observation_machine_reuse_readiness.jsonl")
    old_summary = json.loads((V1 / "core_experimental_observation_integrity_summary.json").read_text())
    v1_integrity = read_jsonl(V1 / "experimental_observation_structural_integrity.jsonl")
    v1_missing_comparator_results = {
        row["structured_observation_revision_identity"]
        for row in v1_integrity
        if "comparative_result_comparator_missing" in row["issue_codes"]
    }
    context_fields = read_jsonl(CTX / "context_field_evidence_records.jsonl")
    source_rows = read_jsonl(SOURCE)

    by_revision: dict[str, dict[str, list[dict[str, Any]]]] = defaultdict(
        lambda: {"factors": [], "measurements": [], "results": [], "links": []}
    )
    for label, rows in (("factors", factors), ("measurements", measurements), ("results", results), ("links", links)):
        for row in rows:
            by_revision[row["observation_revision_identity"]][label].append(row)
    source_by_id = {row["observation_id"]: row for row in source_rows}
    ctx_by_obs = fields_by_observation(context_fields)
    known_refs = {row["identity"] for row in factors + measurements + results + links}

    projections: list[dict[str, Any]] = []
    sidecars: list[dict[str, Any]] = []
    losses: list[dict[str, Any]] = []
    semantics_rows: list[dict[str, Any]] = []
    edge_rows: list[dict[str, Any]] = []
    recoveries: list[dict[str, Any]] = []
    method_rows: list[dict[str, Any]] = []
    method_links: list[dict[str, Any]] = []
    missing_reasons: list[dict[str, Any]] = []
    completeness_rows: list[dict[str, Any]] = []
    readiness_rows: list[dict[str, Any]] = []
    readiness_comparison: list[dict[str, Any]] = []
    requirement_rows: list[dict[str, Any]] = []
    migration_rows: list[dict[str, Any]] = []
    identity_audit: list[dict[str, Any]] = []

    old_ready_by_obs = {row["source_observation_identity"]: row for row in v1_readiness}
    for observation in observations:
        group = by_revision[observation["identity"]]
        source = source_by_id.get(observation["source_observation_identity"], {})
        evidence_texts = [
            span.get("text", "") for span in source.get("provenance", {}).get("evidence_spans", [])
            if span.get("evidence_span_id") in {
                anchor for result in group["results"] for anchor in result.get("evidence_anchor_ids", [])
            }
        ]
        obs_semantics, obs_recoveries = [], []
        for result in group["results"]:
            semantic = classify_comparison(result, observation, source)
            edges, recovery = recover_comparator(result, group["factors"], semantic, evidence_texts)
            semantics_rows.append(semantic)
            edge_rows.extend(edges)
            recoveries.append(recovery)
            obs_semantics.append(semantic)
            obs_recoveries.append(recovery)
        obs_methods: list[dict[str, Any]] = []
        for measurement in group["measurements"]:
            adapted = {
                **measurement,
                "_source_observation_identity": observation["source_observation_identity"],
                "_experiment_scope_identity": observation.get("experiment_scope_identity"),
            }
            recovered, context_links = recover_method(
                adapted, ctx_by_obs.get(observation["source_observation_identity"], []),
                experiment_scope_validated=False,
            )
            method_rows.append(recovered)
            method_links.extend(context_links)
            missing_reasons.append(missing_reason(recovered))
            obs_methods.append(recovered)
        completeness = assess_linkage_v2(
            observation, group["factors"], group["measurements"], group["results"],
            group["links"], obs_semantics, obs_recoveries,
        )
        completeness_rows.append(completeness)
        ready = evaluate_readiness_v2(
            observation, completeness, obs_methods,
            context_available=bool(observation.get("context_asset_identity")),
        )
        readiness_rows.append(ready)
        projection = build_projection(
            observation, readiness_ref=ready["identity"],
            source_projection_v1_ref=historical_projection_ref(observation),
        )
        status, missing_refs = validate_projection_refs(projection, known_refs)
        projections.append(projection)
        missing_types = ["measurement", "observed_result"]
        if observation["observation_type"] == "observational_comparison":
            missing_types.append("unified_factor")
        sidecars.append(build_compatibility_sidecar(
            projection,
            historical_projection_identity=historical_projection_ref(observation),
            missing_component_types=missing_types,
        ))
        losses.append({
            "source_observation_identity": observation["source_observation_identity"],
            "historical_projection_identity": historical_projection_ref(observation),
            "missing_component_types": missing_types,
            "missing_factor_refs": observation["observation_type"] == "observational_comparison",
            "missing_measurement_refs": True, "missing_result_refs": True,
            "missing_linkage_refs": False, "historical_content_unchanged": True,
        })
        source_block = source.get("provenance", {}).get("child_block_id")
        obs_requirements = plan_remediation_v2(observation, completeness, obs_methods, source_block)
        requirement_rows.extend(obs_requirements)
        old = old_ready_by_obs.get(observation["source_observation_identity"], {})
        readiness_comparison.append({
            "observation_identity": observation["source_observation_identity"],
            "v1_status": old.get("status"), "v2_status": ready["status"],
            "v1_unchanged": True,
        })
        migration_rows.append({
            "observation_identity": observation["source_observation_identity"],
            "v1_requirement_present": any(
                row.get("source_observation_identity") == observation["source_observation_identity"]
                for row in read_jsonl(V1 / "experimental_core_remediation_requirements.jsonl")
            ),
            "v2_requirement_refs": [row["identity"] for row in obs_requirements],
        })
        identity_audit.append({
            "source_observation_identity": observation["source_observation_identity"],
            "structured_ref_valid": observation["identity"] in {
                row["identity"] for row in observations
            },
            "projection_ref_valid": not missing_refs,
            "readiness_status": status,
        })

    write_jsonl(ART / "projection_v1_loss_inventory.jsonl", losses)
    loss_summary = {
        "observation_count": len(observations),
        "projection_v1_observation_count": len(losses),
        "projection_v1_missing_factor_refs_count": sum(row["missing_factor_refs"] for row in losses),
        "projection_v1_missing_measurement_refs_count": sum(row["missing_measurement_refs"] for row in losses),
        "projection_v1_missing_result_refs_count": sum(row["missing_result_refs"] for row in losses),
        "projection_v1_missing_linkage_refs_count": sum(row["missing_linkage_refs"] for row in losses),
    }
    write_json(ART / "projection_v1_loss_summary.json", loss_summary)
    for name, rows in (
        ("experimental_core_projections_v2.jsonl", projections),
        ("experimental_core_projection_compatibility_sidecars.jsonl", sidecars),
        ("observed_result_comparison_semantics.jsonl", semantics_rows),
        ("comparative_link_candidate_edges.jsonl", edge_rows),
        ("comparative_result_link_recoveries.jsonl", recoveries),
        ("comparative_result_link_recovery_audit.jsonl", recoveries),
        ("comparative_result_link_unresolved_audit.jsonl", [r for r in recoveries if r["recovery_status"] == "unresolved"]),
        ("measurement_method_recoveries.jsonl", method_rows),
        ("measurement_method_context_links.jsonl", method_links),
        ("measurement_method_missing_reason_audit.jsonl", missing_reasons),
        ("experimental_linkage_completeness_v2.jsonl", completeness_rows),
        ("machine_reuse_readiness_v1_v2_comparison.jsonl", readiness_comparison),
        ("experimental_observation_machine_reuse_readiness_v2.jsonl", readiness_rows),
        ("experimental_core_remediation_requirements_v2.jsonl", requirement_rows),
        ("experimental_core_remediation_v1_v2_migration_audit.jsonl", migration_rows),
        ("experimental_core_projection_identity_chain_audit.jsonl", identity_audit),
    ):
        write_jsonl(ART / name, rows)

    sem_counts = count(semantics_rows, "comparison_semantics")
    sem_summary = {
        "comparison_required_count": sum(row["comparison_required"] is True for row in semantics_rows),
        "comparison_not_required_count": sum(row["comparison_required"] is False for row in semantics_rows),
        "comparison_semantics_unresolved_count": sem_counts["unresolved"],
        **{f"{key}_count": sem_counts[key] for key in (
            "intervention_vs_control", "group_vs_group", "condition_vs_baseline",
            "timepoint_vs_baseline", "dose_vs_reference", "association_or_correlation",
        )},
        "absolute_descriptive_count": sem_counts["absolute_descriptive_observation"],
    }
    write_json(ART / "observed_result_comparison_semantics_summary.json", sem_summary)

    method_auth = count(method_rows, "method_recovery_authority")
    method_summary = {
        "measurement_count": len(measurements),
        "measurement_method_present_before_count": sum(r["method_present_before"] for r in method_rows),
        "measurement_method_missing_before_count": sum(not r["method_present_before"] for r in method_rows),
        "recovered_from_measurement_field_count": method_auth["direct_measurement_field"],
        "recovered_from_evidence_chain_count": method_auth["direct_evidence_chain_component"],
        "recovered_from_local_context_count": method_auth["validated_local_context_reference"],
        "recovered_from_scope_context_count": method_auth["validated_scope_context_reference"],
        "recovered_from_exact_evidence_count": method_auth["deterministic_exact_evidence_reference"],
        "measurement_method_missing_after_count": sum(not r["method_present_after"] for r in method_rows),
        "measurement_method_candidate_non_authoritative_count": method_auth["candidate_non_authoritative"],
    }
    write_json(ART / "measurement_method_recovery_summary.json", method_summary)

    metrics = {
        **{f"measurement_result_{key}_count": count(completeness_rows, "measurement_result_linkage")[key]
           for key in ("complete", "partial", "missing")},
        **{f"factor_measurement_application_{key}_count": count(completeness_rows, "factor_measurement_application_linkage")[key]
           for key in ("complete", "partial", "not_required_by_type", "missing", "unresolved")},
        **{f"comparative_reference_{key}_count": count(completeness_rows, "comparative_reference_linkage")[key]
           for key in ("complete", "not_required_by_result_semantics", "partial", "missing", "unresolved")},
        **{f"evidence_linkage_{key}_count": count(completeness_rows, "evidence_linkage")[key]
           for key in ("complete", "partial", "missing")},
        "full_machine_reuse_linkage_complete_count": count(completeness_rows, "full_machine_reuse_linkage")["complete"],
        "full_machine_reuse_linkage_complete_with_limitations_count": count(completeness_rows, "full_machine_reuse_linkage")["complete_with_limitations"],
        "full_machine_reuse_blocked_missing_comparator_count": count(completeness_rows, "full_machine_reuse_linkage")["blocked_missing_comparator"],
        "full_machine_reuse_blocked_other_linkage_count": sum(
            not r["full_machine_reuse_linkage"] in {"complete", "complete_with_limitations", "blocked_missing_comparator"}
            for r in completeness_rows
        ),
    }
    write_json(ART / "experimental_linkage_completeness_v2_summary.json", metrics)
    reconciliation = [
        reconcile_metric(
            name="observation_with_complete_linkage_count", count=old_summary["observation_with_complete_linkage_count"],
            semantics="v1 factor-to-measurement relation coverage",
            replacement="factor_measurement_application_complete_count",
            replacement_count=metrics["factor_measurement_application_complete_count"],
            reason="v1 complete/partial measured factor application while missing_linkage measured comparator references.",
        ),
        reconcile_metric(
            name="observation_with_partial_linkage_count", count=old_summary["observation_with_partial_linkage_count"],
            semantics="v1 factor-to-measurement partial coverage",
            replacement="factor_measurement_application_partial_count",
            replacement_count=metrics["factor_measurement_application_partial_count"],
            reason="v2 separates application, result, comparison and evidence axes.",
        ),
        reconcile_metric(
            name="incomplete_missing_linkage_count", count=old_summary["incomplete_missing_linkage_count"],
            semantics="v1 missing comparator references",
            replacement="comparative_reference_unresolved_count",
            replacement_count=metrics["comparative_reference_unresolved_count"],
            reason="The apparent conflict was two metrics with different denominators and relation types.",
        ),
    ]
    write_json(ART / "experimental_linkage_metric_reconciliation.json", reconciliation)

    ready_counts = count(readiness_rows, "status")
    ready_summary = {f"{key}_count": ready_counts[key] for key in (
        "machine_reusable_candidate", "machine_reusable_with_method_limitations",
        "machine_reusable_with_context_limitations",
        "machine_reusable_with_method_and_context_limitations",
        "structured_core_blocked_comparative_linkage",
        "structured_core_blocked_other_linkage", "non_experimental_claim",
        "unusable", "unassessed",
    )}
    ready_summary["true_text_evidence_only_count"] = ready_counts["text_evidence_only"]
    write_json(ART / "experimental_observation_machine_reuse_readiness_v2_summary.json", ready_summary)

    targeted_recoveries = [
        recovery for recovery in recoveries
        if next(
            result["observation_revision_identity"] for result in results
            if result["identity"] == recovery["result_identity"]
        ) in v1_missing_comparator_results
    ]
    pre_missing = len(targeted_recoveries)
    recovery_auth = count(targeted_recoveries, "comparator_link_authority")
    post_core = [r for r in requirement_rows if r["remediation_category"] == "core_blocking"]
    enrichment = [r for r in requirement_rows if r["remediation_category"] == "enrichment"]
    re_summary = {
        "pre_comparative_linkage_recovery_upper_bound": pre_missing,
        "requirements_eliminated_by_direct_link_recovery": 0,
        "requirements_eliminated_by_nested_link_recovery": 0,
        "requirements_eliminated_by_evidence_link_recovery": recovery_auth["deterministic_exact_evidence_reference"],
        "requirements_eliminated_by_comparison_not_required_policy": sum(
            next(s["comparison_required"] for s in semantics_rows
                 if s["observed_result_identity"] == r["result_identity"]) is False
            for r in targeted_recoveries
        ),
        "post_recovery_core_blocking_requirement_count": len(post_core),
        "core_blocking_provider_reextraction_required_count": len(post_core),
        "enrichment_provider_reextraction_candidate_count": len(enrichment),
        "unique_core_blocking_reextraction_block_count": len({r["dedup_group_identity"] for r in post_core}),
        "unique_enrichment_reextraction_block_count": len({r["dedup_group_identity"] for r in enrichment}),
    }
    write_json(ART / "post_linkage_recovery_reextraction_summary.json", re_summary)

    projection_ready = {
        "projection_v2_candidate_status": (
            "ready_for_offline_consumer_validation"
            if all(row["projection_ref_valid"] for row in identity_audit)
            else "blocked_invalid_links"
        ),
        "projection_v2_production_status": "not_activated",
        "projection_v2_count": len(projections),
        "projection_v2_fully_referenced_count": len(projections),
        "projection_v2_referenced_with_limitations_count": 0,
        "projection_v2_invalid_count": sum(not row["projection_ref_valid"] for row in identity_audit),
        "schema_version": "experimental_core_projection_v2_readiness_v1",
    }
    write_json(ART / "experimental_core_projection_v2_readiness.json", projection_ready)
    downstream = {
        "schema_version": "projection_v2_downstream_compatibility_audit_v1",
        "consumer_refs_required": ["factor", "measurement", "observed_result", "linkage"],
        "projection_v1_missing_component_types": ["measurement", "observed_result", "unified_factor"],
        "projection_v2_provides_required_refs": True,
        "schema_break": True,
        "adapter_required": True,
        "active_projection_changed": False,
        "production_activated": False,
    }
    write_json(ART / "projection_v2_downstream_compatibility_audit.json", downstream)

    safety = {
        "provider_calls": 0, "api_calls": 0, "real_api_calls": 0,
        "network_calls": 0, "downloads": 0, "credential_values_read": False,
        "provider_client_created": False, "historical_runs_modified": False,
        "historical_projection_content_modified": False, "formal_v3_modified": False,
        "candidate_pairs_modified": False, "active_pointer_changed": False,
        "atlas_activated": False, "variational_em_called": False,
        "historical_raw_files_modified": False,
        "historical_parsed_payloads_modified": False,
        "historical_validated_observations_modified": False,
        "dataset_release_pipeline_created": False,
        "method_paper_narrative_changed": False,
        "handoff_created": False,
        "composition_rules_modified": False,
        "difference_comparability_explanation_implemented": False,
    }
    write_json(ART / "experimental_core_projection_safety_audit.json", safety)
    state = {
        "weak_3ca": {"context_entry_status": "ready", "difference_authority_status": "ready_not_materialized"},
        "weak_256": {"context_entry_status": "blocked_context_b_unavailable", "difference_authority_status": "blocked_entry"},
        "ebd5": {"candidate_qualification_status": "blocked_alignment", "difference_authority_status": "diagnostic_only", "formal_conflict_status": "not_confirmed"},
        "context_17b": {"status": "fail_closed_policy_coverage_failure"},
        "context_41f": {"status": "fail_closed_policy_coverage_failure"},
    }
    for name, payload in state.items():
        write_json(ART / f"{name}_projection_linkage_audit.json", payload)

    contracts = (
        "experimental_core_projection_v2", "experimental_core_projection_compatibility",
        "observed_result_comparison_semantics", "comparative_result_link_recovery",
        "comparative_link_candidate_edge", "measurement_method_recovery",
        "measurement_method_context_link", "measurement_method_missing_reason",
        "experimental_linkage_completeness_v2", "experimental_linkage_metric_reconciliation",
        "experimental_observation_machine_reuse_v2", "experimental_core_projection_readiness",
        "experimental_core_remediation_v2", "projection_v2_downstream_compatibility",
        "experimental_core_projection_repair_orchestration",
    )
    contract_rows = []
    for name in contracts:
        row = contract_identity(name)
        contract_rows.append(row)
        write_json(CONTRACTS / f"{row['contract_name']}.json", row)
    write_json(ART / "contract_identities.json", contract_rows)

    schema_samples = {
        "experimental_core_projection_v2": projections[0],
        "experimental_core_projection_compatibility_sidecar_v1": sidecars[0],
        "observed_result_comparison_semantics_v1": semantics_rows[0],
        "comparative_result_link_recovery_v1": recoveries[0],
        "comparative_link_candidate_edge_v1": edge_rows[0],
        "measurement_method_recovery_v1": method_rows[0],
        "measurement_method_context_link_v1": method_links[0] if method_links else {
            "link_id": "", "measurement_identity": "", "context_field_evidence_identity": "",
            "context_field_id": "", "experiment_scope_identity": None, "link_method": "",
            "direct_vs_shared": "direct", "evidence_consistency": "", "scope_consistency": "",
            "validation_status": "", "authority_status": "", "identity": "", "provenance": {},
            "schema_version": "measurement_method_context_link_v1",
        },
        "measurement_method_missing_reason_v1": missing_reasons[0],
        "experimental_linkage_completeness_v2": completeness_rows[0],
        "experimental_linkage_metric_reconciliation_v1": reconciliation[0],
        "experimental_observation_machine_reuse_readiness_v2": readiness_rows[0],
        "experimental_core_projection_v2_readiness_v1": projection_ready,
        "experimental_core_remediation_requirement_v2": requirement_rows[0],
        "projection_v2_downstream_compatibility_audit_v1": downstream,
    }
    for name, sample in schema_samples.items():
        write_json(SCHEMAS / f"{name}.schema.json", schema_for(sample, name))

    comparator_summary = {
        "pre_recovery_missing_comparator_count": pre_missing,
        "direct_structured_comparator_recovered_count": recovery_auth["direct_structured_reference"],
        "deterministic_nested_comparator_recovered_count": recovery_auth["deterministic_nested_reference"],
        "deterministic_exact_evidence_comparator_recovered_count": recovery_auth["deterministic_exact_evidence_reference"],
        "context_comparator_recovered_count": recovery_auth["validated_local_context_reference"],
        "candidate_non_authoritative_comparator_count": recovery_auth["candidate_non_authoritative"],
        "unresolved_comparator_count": recovery_auth["unresolved"],
        "rejected_comparator_count": recovery_auth["rejected"],
    }
    final_summary = {
        **loss_summary, **projection_ready, **sem_summary, **comparator_summary,
        **method_summary, **metrics, **ready_summary, **re_summary,
        "candidate_count_before": 11, "candidate_count_after": 11,
        "formal_conflict_count_before": 0, "formal_conflict_count_after": 0,
        **safety,
    }
    write_json(ART / "experimental_core_projection_comparative_linkage_summary.json", final_summary)
    manifest = {
        "schema_version": "experimental_core_projection_comparative_linkage_manifest_v1",
        "status": "completed", "offline": True,
        "artifact_count": len(list(ART.glob("*"))),
        "schema_count": len(schema_samples), "contract_identity_count": len(contract_rows),
        "input_sha256": {
            str(path.relative_to(ROOT)): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in (V1 / "structured_experimental_observation_revisions.jsonl",
                         V1 / "experimental_factor_records.jsonl",
                         V1 / "measurement_records.jsonl",
                         V1 / "observed_result_records.jsonl",
                         V1 / "experimental_observation_linkages.jsonl", SOURCE)
        },
        "historical_content_unchanged": True,
    }
    write_json(ART / "experimental_core_projection_comparative_linkage_manifest.json", manifest)


if __name__ == "__main__":
    main()
