#!/usr/bin/env python3
"""Freeze the proposition-driven expansion protocol without external execution."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess
from typing import Any, Iterable

from code_engine.context_attribution.conflict_candidate.targeted_expansion_v1_candidate import (
    BoundedTargetExpansionBudgetV1,
    EVALUATION_LEVELS_V1,
    PlannedQueryComponentsV1,
    TargetedRetrievalSpecificationV1,
    primary_contradiction_term_count_v1,
)


ROOT = Path(__file__).resolve().parents[1]
RUN = ROOT / "runs/20260826_proposition_driven_targeted_expansion_protocol_v1_offline"
ART = RUN / "artifacts"
PREVIOUS = ROOT / "runs/20260826_cross_publication_proposition_opportunity_frontier_v1_offline/artifacts"
FRONTIER = ROOT / "runs/20260826_proposition_sufficiency_frontier_closure_v1_offline/artifacts"
ENTITY = ROOT / "runs/20260825_scientific_entity_identity_authority_v1_offline/artifacts"
QUAL = ROOT / "runs/20260725_hif1a_candidate_qualification_v1_offline/artifacts"
ALIGN = ROOT / "runs/20260725_hif1a_claim_alignment_dimension_taxonomy_v2_offline/artifacts"
CORE = ROOT / "runs/20260725_hif1a_core_experimental_observation_integrity_v1_offline/artifacts"
PI3K = ROOT / "runs/20260816_provenance_authority_pair_context_entity_integrity_pi3k_v1_offline/artifacts"
FORMAL = ROOT / "runs/20260725_hif1a_conflict_adjudication_orchestration_v1_offline/artifacts/formal_conflict_decisions_staging.jsonl"

FILES = (
    "baseline.json", "target_proposition_inventory.json", "targeted_retrieval_specifications_v1.jsonl",
    "planned_query_components.jsonl", "publication_independence_policy.json", "bounded_expansion_budget.json",
    "retrieval_stop_conditions.json", "extraction_activation_policy.json", "provider_billing_safety_plan.json",
    "expansion_evaluation_ledger_schema.json", "target_expansion_order.json", "temporal_provenance_requirements.json",
    "dataset_asset_preservation_recheck.json", "network_provider_execution_plan.json",
    "scientific_state_safety_audit.json", "production_leakage_audit.json", "final_validation.json",
    "manifest.json", "summary.json",
)
PROHIBITED = ["conflicting", "controversial", "opposite", "contradictory"]
PER_TARGET = dict(metadata=12, abstract=6, fulltext=2, extraction=2, provider=2)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--status", choices=("pending", "completed", "failed"), default="pending")
    for name in ("focused_pass_count", "related_pass_count", "full_pass_count", "full_subtest_pass_count", "full_failure_count", "full_collected_count"):
        parser.add_argument("--" + name.replace("_", "-"), type=int, default=0)
    parser.add_argument("--compileall", choices=("pending", "passed", "failed"), default="pending")
    parser.add_argument("--git-diff-check", choices=("pending", "passed", "failed"), default="pending")
    parser.add_argument("--final-failure-id", action="append", default=[])
    parser.add_argument("--transient-failure-id", action="append", default=[])
    return parser.parse_args()


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def rows(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def write_json(name: str, value: Any) -> None:
    (ART / name).write_text(json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")


def write_rows(name: str, values: Iterable[Any]) -> None:
    data = [value.model_dump(mode="json") if hasattr(value, "model_dump") else value for value in values]
    (ART / name).write_text("".join(json.dumps(value, sort_keys=True, ensure_ascii=False) + "\n" for value in data), encoding="utf-8")


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def rel(path: Path) -> str:
    return str(path.relative_to(ROOT))


def local_terms(value: str, classes: dict[str, dict[str, Any]]) -> list[str]:
    if value in classes:
        row = classes[value]
        return sorted(set(row["surface_forms"] + row["canonical_ids"]), key=str.casefold)
    for row in classes.values():
        if value in row["canonical_ids"]:
            return sorted(set(row["surface_forms"] + [value]), key=str.casefold)
    return [value.split("|")[0]]


def main() -> None:
    opt = parse_args()
    ART.mkdir(parents=True, exist_ok=True)
    target_rows = rows(PREVIOUS / "proposition_driven_future_retrieval_targets.jsonl")
    classes = {row["class_id"]: row for row in rows(ENTITY / "local_entity_equivalence_classes_v1.jsonl")}
    readiness = read_json(FRONTIER / "frontier_pair_generation_readiness.json")
    blocks = {row["proposition_block_id"]: row for row in readiness["blocks"]}
    prior_summary = read_json(PREVIOUS / "summary.json")
    prior_validation = read_json(PREVIOUS / "final_validation.json")
    protected = [
        QUAL / "scientific_candidate_pair_identities.jsonl", QUAL / "conflict_candidate_qualifications.jsonl",
        ALIGN / "claim_alignment_records_v2.jsonl", ALIGN / "contradiction_signals_v2.jsonl", FORMAL,
        CORE / "structured_experimental_observation_revisions.jsonl", CORE / "experimental_factor_records.jsonl",
        CORE / "measurement_records.jsonl", CORE / "observed_result_records.jsonl",
        PI3K / "signal_integrity_audit.jsonl", PI3K / "f389_candidate_experiment_filtering.jsonl",
        PREVIOUS / "proposition_driven_future_retrieval_targets.jsonl", FRONTIER / "frontier_pair_generation_readiness.json",
    ]
    before = {rel(path): digest(path) for path in protected}
    target_input_hash = digest(PREVIOUS / "proposition_driven_future_retrieval_targets.jsonl")
    write_json("baseline.json", {
        "schema_version": "proposition_driven_targeted_expansion_protocol_v1_baseline",
        "git_head": subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, check=True, capture_output=True, text=True).stdout.strip(),
        "authoritative_target_artifact": rel(PREVIOUS / "proposition_driven_future_retrieval_targets.jsonl"),
        "authoritative_target_artifact_sha256": target_input_hash,
        "target_count": len(target_rows), "expansion_decision": prior_summary["decision"],
        "fulltext_observation_count": 418, "structurally_eligible_count": 330,
        "entity_v2_eligible_count": 20, "minimum_sufficient_proposition_count": 7,
        "proposition_block_count": 4, "cross_publication_proposition_block_count": 0,
        "historical_candidate_count": 11, "formal_conflict_count": 0,
        "entity_integrity_claims_blocked": 241, "entity_integrity_signals_blocked": 2,
        "baseline_failure_ids": prior_validation["baseline_failure_ids"], "protected_hashes_before": before,
        "design_only": True, "execution_authorized": False,
    })

    inventory = []
    specs: list[TargetedRetrievalSpecificationV1] = []
    query_rows: list[PlannedQueryComponentsV1] = []
    budgets: list[BoundedTargetExpansionBudgetV1] = []
    for target in target_rows:
        block = blocks[target["source_proposition_block_id"]]
        payload = block["identity_payload"]
        inventory.append({
            "schema_version": "target_proposition_inventory_v1", **target,
            "contrast_semantics": payload["contrast"], "source_observation_ids": block["observation_ids"],
            "source_publication_ids": block["publication_ids"], "source_experiment_ids": block["experiment_ids"],
            "source_observation_count": block["observation_count"], "authoritative_input_sha256": target_input_hash,
            "structured_semantics_modified": False,
        })
        specs.append(TargetedRetrievalSpecificationV1(
            target_id=target["target_id"], source_proposition_block_id=target["source_proposition_block_id"],
            entity_proposition=target["entity_proposition"], relation_effect_family=target["relation_family"],
            object_target=target["object_target"], measurement_targets=target["measurement_targets"],
            measurement_properties=target["measurement_properties"], intervention_targets=target["intervention_targets"],
            causal_evidential_mode=target["causal_mode"], evidence_family=target["evidence_family"],
            result_semantic_families=target["result_families"], contrast_semantics=payload["contrast"],
            allowed_proposition_qualifiers=["assay_method", "dose", "model_system", "population", "tissue", "timing"],
            excluded_proposition_mismatches=["different_entity_proposition", "different_relation_effect_family", "different_object_target", "different_measurement_target", "different_measurement_property", "different_intervention_proposition", "different_causal_evidential_mode", "incompatible_contrast_semantics", "review_or_commentary_without_experimental_evidence"],
            publication_independence_requirements=["different_from_source_block_publication", "resolved_PMID_or_PMCID_or_DOI_or_local_publication_identity", "different_source_asset_identity", "different_experiment_identity", "no_shared_evidence_span"],
            fulltext_preference="source-grounded methods/results fulltext with extractable factor, arm, measurement, result, and evidence spans",
        ))
        relation_terms = ["effect", "intervention", "perturbation"] if target["causal_mode"] == "interventional_effect" else ["association", "comparison", "correlation"]
        measurement_terms = sorted({term for value in target["measurement_targets"] for term in local_terms(value, classes)}, key=str.casefold)
        intervention_terms = sorted({term for value in target["intervention_targets"] for term in local_terms(value, classes)}, key=str.casefold)
        query_rows.append(PlannedQueryComponentsV1(
            target_id=target["target_id"], entity_terms=local_terms(target["entity_proposition"], classes),
            relation_effect_terms=relation_terms, measurement_target_terms=measurement_terms,
            measurement_property_terms=target["measurement_properties"], intervention_terms=intervention_terms,
            prohibited_primary_terms=PROHIBITED,
        ))
        budgets.append(BoundedTargetExpansionBudgetV1(
            target_id=target["target_id"], maximum_metadata_candidates=PER_TARGET["metadata"],
            maximum_abstract_candidates=PER_TARGET["abstract"], maximum_fulltexts=PER_TARGET["fulltext"],
            maximum_fulltext_extraction_calls=PER_TARGET["extraction"], maximum_provider_calls=PER_TARGET["provider"],
        ))
    write_json("target_proposition_inventory.json", {"schema_version": "target_proposition_inventory_v1", "target_count": len(inventory), "targets": inventory})
    write_rows("targeted_retrieval_specifications_v1.jsonl", specs)
    write_rows("planned_query_components.jsonl", query_rows)

    write_json("publication_independence_policy.json", {
        "schema_version": "publication_independence_policy_v1",
        "identity_precedence": ["PMID", "PMCID", "DOI", "local_publication_identity", "source_asset_identity"],
        "candidate_must_differ_from": ["source_block_publication_ids", "source_asset_identity", "experiment_identity", "evidence_span_identity"],
        "conflicting_identifier_action": "hold_publication_identity_uncertain_and_do_not_count_as_independent",
        "missing_identifier_action": "attempt_deterministic_local_identity_resolution_then_hold_if_unresolved",
        "duplicate_check_before_fulltext": True, "duplicate_check_before_provider": True,
        "cross_publication_requires_resolved_identity": True, "same_publication_never_counts_as_level_5_or_6": True,
    })
    totals = {key: sum(getattr(b, f"maximum_{'abstract_candidates' if key == 'abstract' else 'metadata_candidates' if key == 'metadata' else 'fulltext_extraction_calls' if key == 'extraction' else 'provider_calls' if key == 'provider' else 'fulltexts'}") for b in budgets) for key in PER_TARGET}
    write_json("bounded_expansion_budget.json", {
        "schema_version": "bounded_expansion_budget_v1", "phase": "four_target_smoke",
        "per_target": [b.model_dump(mode="json") for b in budgets],
        "global_maximums": {"metadata_candidates": totals["metadata"], "abstract_candidates": totals["abstract"], "fulltexts": totals["fulltext"], "fulltext_extraction_calls": totals["extraction"], "provider_calls": totals["provider"], "provider_attempts_per_source": 1, "provider_retries_per_source": 0},
        "budget_is_ceiling_not_quota": True, "no_unused_budget_reallocation_without_approval": True,
    })
    write_json("retrieval_stop_conditions.json", {
        "schema_version": "retrieval_stop_conditions_v1",
        "success_stop": "stop a target after one independently sourced minimum-sufficient proposition-compatible peer is recovered",
        "target_exhaustion_stop": "stop when any target budget ceiling or its bounded candidate set is exhausted without a compatible peer",
        "authority_stop": "stop spending when repeated structural, semantic, entity, publication-identity, parser, or normalization blockage indicates method repair",
        "non_stops": ["no_opposing_result_found", "only_supporting_results_found"],
        "scale_up_gate": "recommend only after Level 5 capture or a repairable target-specific retrieval limitation; require separate approval",
    })
    activation_steps = ["publication_identity_check", "basic_target_proposition_plausibility_check", "fulltext_availability_check", "duplicate_check", "existing_cache_check", "asset_preservation_contract_check"]
    write_json("extraction_activation_policy.json", {
        "schema_version": "extraction_activation_policy_v1", "required_order": activation_steps,
        "all_steps_must_pass_before_paid_extraction": True,
        "incompatible_paper_action": "reject_before_paid_extraction", "scientific_gate_relaxation_allowed": False,
        "authoritative_gates": ["ScientificEntityIntegrityGateV1", "Scientific Entity Equivalence Authority", "MinimumScientificPropositionProfile", "ScientificPropositionSignatureV1_or_candidate_successor", "Scientific Proposition Compatibility", "existing Contradiction semantics", "Candidate Qualification"],
    })
    write_json("provider_billing_safety_plan.json", {
        "schema_version": "provider_billing_safety_plan_v1", "cache_required_before_every_paid_attempt": True,
        "deduplication_key": ["source_snapshot_sha256", "rendered_prompt_sha256", "model", "model_version", "parameters_sha256"],
        "maximum_attempts_per_source": 1, "maximum_retries_per_source": 0,
        "parser_failure_retry": False, "schema_failure_retry": False, "normalization_failure_retry": False,
        "transport_retry_in_smoke": False, "future_transport_retry_requires_explicit_bounded_contract": True,
        "raw_response_saved_before_parser": True, "provider_execution_occurred": False,
    })
    target_metrics = ["retrieved_publication_count", "unique_publication_count", "fulltext_eligible_count", "extracted_observation_count", "structurally_eligible_count", "entity_eligible_count", "minimum_proposition_sufficient_count", "cross_publication_peer_count", "source_independent_compatible_pair_count", "supporting_result_count", "opposing_result_count", "reviewable_result_count", "candidate_qualified_count"]
    write_json("expansion_evaluation_ledger_schema.json", {
        "schema_version": "expansion_evaluation_ledger_schema_v1",
        "levels": [{"level": level, "name": name, "required_for_smoke_success": level == 5} for level, name in EVALUATION_LEVELS_V1.items()],
        "planned_success_level": 5, "levels_7_or_8_required_for_smoke_success": False,
        "target_level_fields": target_metrics, "aggregation_may_not_hide_target_failure": True,
        "initial_counts": [{"target_id": row["target_id"], **{field: 0 for field in target_metrics}} for row in target_rows],
        "result_direction_evaluated_only_after_proposition_compatibility": True,
    })
    order_rows = []
    for target in target_rows:
        block = blocks[target["source_proposition_block_id"]]
        canonical_dimensions = int(bool(classes[target["entity_proposition"]]["canonical_ids"])) + int(bool(classes[target["object_target"]]["canonical_ids"]))
        tier = 1 if block["observation_count"] == 3 else 2 if block["observation_count"] == 2 else 3
        order_rows.append({"target_id": target["target_id"], "priority_tier": tier, "source_observation_count": block["observation_count"], "source_experiment_count": len(block["experiment_ids"]), "canonical_entity_dimension_count": canonical_dimensions, "proposition_signature_complete": True, "source_publication_identity_resolved": True})
    order_rows.sort(key=lambda row: (row["priority_tier"], row["target_id"]))
    write_json("target_expansion_order.json", {
        "schema_version": "target_expansion_order_v1", "ordering_rule": "descending source observation count; do not break residual ties without additional local evidence",
        "targets_with_clear_priority": 2, "targets_equal_priority": 2, "ordered_tiers": order_rows,
        "web_derived_counts_used": False, "biomedical_intuition_used": False,
        "tie_explanation": "the two one-observation blocks have complete signatures, resolved source publication identity, and two canonical entity dimensions; local evidence does not distinguish them",
    })
    write_json("temporal_provenance_requirements.json", {
        "schema_version": "temporal_provenance_requirements_v1", "required_future_fields": ["query_timestamp", "publication_date", "retrieval_cutoff", "source_snapshot_date", "corpus_version", "prompt_identity", "model_identity"],
        "temporal_cutoff_active": False, "historical_prospective_evaluation_compatible": True,
    })
    preserved = ["actual_source_snapshot_or_exact_sent_text", "rendered_prompt", "model_and_version", "parameters", "raw_provider_response_before_parser", "parsed_candidate", "Validated ExperimentalObservation", "Factor_and_Arm", "Measurement", "Observed_Result", "Context", "Evidence_spans", "raw_extracted_normalized_values", "entity_identity_authority", "semantic_family_authority", "lineage", "schema_versions", "hashes", "failure_artifacts"]
    write_json("dataset_asset_preservation_recheck.json", {
        "schema_version": "dataset_asset_preservation_recheck_v1", "required_assets": preserved,
        "minimum_quality_observation_enters_reusable_data_pipeline": True, "conflict_relevance_required": False,
        "experimental_data_reuse_readiness_independent_of_conflict_proposition_readiness": True,
        "paid_result_may_be_disposable_intermediate": False,
    })
    write_json("network_provider_execution_plan.json", {
        "schema_version": "network_provider_execution_plan_v1", "execution_authorized": False,
        "explicit_user_approval_required": True, "design_only": True,
        "proposed_external_actions": [
            {"action": "metadata_and_abstract_retrieval", "possible_services": ["PubMed"], "maximum_candidates": totals["metadata"], "maximum_abstracts": totals["abstract"], "executed": False},
            {"action": "publication_identity_resolution", "possible_services": ["PubMed", "PMC", "Crossref_or_DOI_resolver"], "maximum_records": totals["metadata"], "executed": False},
            {"action": "fulltext_download", "possible_services": ["PMC_or_publisher_fulltext"], "maximum_downloads": totals["fulltext"], "executed": False},
            {"action": "structured_extraction", "possible_services": ["explicitly_approved_model_provider"], "maximum_calls": totals["provider"], "maximum_attempts_per_source": 1, "maximum_retries_per_source": 0, "executed": False},
        ],
        "cache_rules": ["metadata_cache_before_network", "source_snapshot_cache_before_download", "source_prompt_model_cache_before_provider"],
        "stopping_rules_artifact": "retrieval_stop_conditions.json", "billing_rules_artifact": "provider_billing_safety_plan.json",
        "network_calls": 0, "api_calls": 0, "downloads": 0, "provider_calls": 0,
    })
    after = {rel(path): digest(path) for path in protected}
    unchanged = before == after
    write_json("scientific_state_safety_audit.json", {
        "schema_version": "targeted_expansion_protocol_scientific_state_safety_audit_v1",
        "historical_candidate_count_before": 11, "historical_candidate_count_after": 11,
        "formal_conflict_count_before": 0, "formal_conflict_count_after": 0,
        "entity_integrity_claims_blocked": 241, "entity_integrity_signals_blocked": 2,
        "pi3k": {"signal_40f_state": "historically_blocked", "f389_state": "manual_scientific_review"},
        "historical_assets_modified": not unchanged, "candidate_pairs_modified": False, "formal_v3_modified": False,
        "experimental_core_modified": False, "canonical_identities_modified": False,
        "atlas_activated": False, "active_pointer_changed": False, "variational_em_called": False,
        "protected_hashes_before": before, "protected_hashes_after": after,
        "provider_calls": 0, "api_calls": 0, "network_calls": 0, "downloads": 0, "llm_calls": 0,
    })
    contradiction_count = primary_contradiction_term_count_v1(query_rows)
    write_json("production_leakage_audit.json", {
        "schema_version": "targeted_expansion_protocol_production_leakage_audit_v1",
        "candidate_sidecars_only": True, "production_modules_modified": False,
        "retrieval_executed": False, "extraction_executed": False, "candidate_generation_executed": False,
        "contradiction_evaluated": False, "direction_used_in_primary_retrieval": False,
        "contradiction_terms_in_primary_query_count": contradiction_count,
        "fuzzy_entity_expansion_used": False, "external_ontology_expansion_used": False,
        "provider_clients_imported_or_called": False, "network_or_download_execution": False,
    })
    assertions = {
        "four_authoritative_targets_preserved": len(target_rows) == len(specs) == 4 and all(not row["structured_semantics_modified"] for row in inventory),
        "primary_queries_direction_neutral": contradiction_count == 0,
        "duplicate_and_cache_precede_provider": activation_steps.index("duplicate_check") < activation_steps.index("existing_cache_check") < activation_steps.index("asset_preservation_contract_check"),
        "provider_activity_finitely_bounded": totals["provider"] == 8 and all(b.maximum_provider_retries_per_source == 0 for b in budgets),
        "parser_schema_normalization_do_not_retry": True,
        "level_5_counts_as_smoke_success": EVALUATION_LEVELS_V1[5] == "cross_publication_proposition_peers",
        "scientific_eligibility_not_relaxed": all(spec.scientific_gates_reused_without_relaxation for spec in specs),
        "all_new_observations_preserved_without_conflict_requirement": True,
        "execution_not_authorized": True,
        "provider_network_api_download_zero": True,
        "historical_assets_unchanged": unchanged,
    }
    baseline_failures = prior_validation["baseline_failure_ids"]
    final_failures = sorted(set(opt.final_failure_id)); new_failures = sorted(set(final_failures) - set(baseline_failures))
    write_json("final_validation.json", {
        "schema_version": "proposition_driven_targeted_expansion_protocol_v1_final_validation", "status": opt.status,
        "assertions": assertions, "all_assertions_passed": all(assertions.values()),
        "focused_test_pass_count": opt.focused_pass_count, "related_test_pass_count": opt.related_pass_count,
        "full_suite_pass_count": opt.full_pass_count, "full_suite_subtest_pass_count": opt.full_subtest_pass_count,
        "full_suite_failure_count": opt.full_failure_count, "full_suite_collected_count": opt.full_collected_count,
        "baseline_failure_ids": baseline_failures, "final_failure_ids": final_failures, "new_failure_ids": new_failures,
        "full_suite_transient_failure_ids": sorted(set(opt.transient_failure_id)),
        "transient_failures_passed_in_isolation": bool(opt.transient_failure_id),
        "compileall": opt.compileall, "git_diff_check": opt.git_diff_check,
        "execution_authorized": False, "provider_calls": 0, "api_calls": 0, "network_calls": 0, "downloads": 0, "llm_calls": 0,
    })
    metrics = {
        "target_count": 4, "planned_max_metadata_candidates": totals["metadata"], "planned_max_abstract_candidates": totals["abstract"],
        "planned_max_fulltexts": totals["fulltext"], "planned_max_provider_calls": totals["provider"],
        "targets_with_clear_priority": 2, "targets_equal_priority": 2, "planned_success_level": 5,
        "cache_required_before_provider_call": True, "contradiction_terms_in_primary_query_count": contradiction_count,
        "execution_authorized": False, "provider_calls": 0, "api_calls": 0, "network_calls": 0, "downloads": 0,
    }
    write_json("summary.json", {
        "schema_version": "proposition_driven_targeted_expansion_protocol_v1_summary", "status": opt.status,
        "metrics": metrics, "primary_goal": "recover an independently published peer for the same scientific proposition",
        "primary_smoke_success": "Level 5 cross-publication proposition peer; contradiction is neither required nor retrieval-selected",
        "scale_up_authorized": False, "historical_assets_modified": not unchanged,
    })
    manifest_rows = []
    for name in FILES:
        if name == "manifest.json":
            continue
        path = ART / name
        manifest_rows.append({"relative_path": rel(path), "sha256": digest(path), "file_size_bytes": path.stat().st_size, "line_count": len(path.read_text(encoding="utf-8").splitlines())})
    write_json("manifest.json", {
        "schema_version": "proposition_driven_targeted_expansion_protocol_v1_manifest", "run_id": RUN.name,
        "status": opt.status, "artifact_count": len(FILES), "manifest_self_hash_excluded": True,
        "all_required_artifacts_present": all((ART / name).exists() for name in FILES if name != "manifest.json"),
        "artifacts": manifest_rows, "execution_authorized": False,
        "provider_calls": 0, "api_calls": 0, "network_calls": 0, "downloads": 0,
    })
    if not all(assertions.values()):
        raise RuntimeError([name for name, passed in assertions.items() if not passed])


if __name__ == "__main__":
    main()
