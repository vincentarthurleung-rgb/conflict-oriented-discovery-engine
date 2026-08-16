from __future__ import annotations

import hashlib
import json
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RUN = ROOT / "runs/20260816_hif1a_reference_guided_experimental_core_repair_v1_offline"
ART = RUN / "artifacts"


def rows(name: str) -> list[dict]:
    return [json.loads(line) for line in (ART / name).read_text().splitlines() if line.strip()]


def value(name: str) -> dict:
    return json.loads((ART / name).read_text())


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_required_offline_artifacts_exist():
    required = {
        "reference_input_identity.json", "reference_baseline_validation.json",
        "autonomous_iteration_ledger.jsonl", "autonomous_issue_inventory.jsonl",
        "autonomous_iteration_summary.json", "observed_result_structural_integrity_audit.jsonl",
        "observed_result_repair_revisions.jsonl", "measurement_semantic_integrity_audit.jsonl",
        "measurement_repair_revisions.jsonl", "experimental_arm_records_v1.jsonl",
        "experimental_arm_reconstruction_audit.jsonl", "candidate_completeness_audit.jsonl",
        "candidate_set_revisions.jsonl", "source_grounded_linkage_materialization_candidates.jsonl",
        "source_grounded_materialized_linkages.jsonl", "linkage_materialization_rejections.jsonl",
        "annotation_task_validity_gate.jsonl", "annotation_task_routing_summary.json",
        "pmc7744182_local_source_recovery_audit.json", "pmc7744182_source_envelope_revisions.jsonl",
        "reference_regression_task_results.jsonl", "reference_regression_summary.json",
        "root_cause_before_after_reconciliation.json", "task_level_resolution_transition.jsonl",
        "machine_reuse_readiness_v5_candidates.jsonl", "machine_reuse_v4_v5_comparison.json",
        "special_core_877_audit.json", "reference_oracle_leakage_audit.json",
        "scientific_state_safety_audit.json", "reference_guided_experimental_core_repair_summary.json",
        "reference_guided_experimental_core_repair_manifest.json",
    }
    assert required <= {path.name for path in ART.iterdir()}


def test_frozen_zip_sha256_identities_match():
    assert sha(ROOT / "reference_inputs/core_reference_adjudication_v1.zip") == "11acfefae6fd98d0bfc58aa425b06bcba4013349e68f32313a72c915dc70d18e"
    assert sha(ROOT / "reference_inputs/system_vs_reference_root_cause_audit_v1.zip") == "e8ccb35bb998f561f420492c93fb2572e898b4e64f1f695eadf76f2ae0a95066"
    assert value("reference_input_identity.json")["status"] == "passed"


def test_reference_baseline_partition_is_exact_complete_and_disjoint():
    baseline = value("reference_baseline_validation.json")
    assert baseline["reference_task_count"] == 39
    assert baseline["task_type_counts"] == {"comparator": 34, "factor_application": 5}
    assert baseline["root_cause_counts"] == {
        "missing_link_materialization_only": 22,
        "invalid_result_record_plus_missing_link": 4,
        "measurement_model_error_plus_missing_link": 3,
        "reference_arm_missing_and_control_role_wrong": 4,
        "source_scope_insufficient_with_composite_control_candidate": 6,
    }
    assert baseline["partition_complete"] and baseline["partition_pairwise_disjoint"]


def test_previous_blocked_run_did_not_modify_files():
    manifest = value("reference_guided_experimental_core_repair_manifest.json")
    assert manifest["previous_blocked_run_modified_files"] is False
    assert manifest["task_start_tracked_diff_sha256"] == hashlib.sha256(b"").hexdigest()


def test_iteration_zero_is_scan_only_and_repair_loop_is_bounded():
    ledger = rows("autonomous_iteration_ledger.jsonl")
    assert ledger[0]["iteration_id"] == 0 and ledger[0]["files_changed"] == []
    assert [x["iteration_id"] for x in ledger] == list(range(6))
    assert value("autonomous_iteration_summary.json")["repair_iteration_count"] == 5
    assert "remaining ambiguity blocked" in ledger[-1]["stop_reason"]


def test_22_pure_missing_link_tasks_are_exact():
    records = [x for x in rows("reference_regression_task_results.jsonl")
               if x["root_cause_class"] == "missing_link_materialization_only"]
    assert len(records) == 22
    assert all(x["match"] and x["regression_status"] == "exact_match" for x in records)
    assert all(x["expected_source_identity"] == x["actual_source_identity"] for x in records)


def test_result_integrity_detects_and_revises_all_four_without_overwrite():
    audits = rows("observed_result_structural_integrity_audit.jsonl")
    repairs = rows("observed_result_repair_revisions.jsonl")
    assert len(audits) == len(repairs) == 4
    assert all(x["before_status"] == "invalid" and x["repair_required"] for x in audits)
    assert all(x["eligibility"] == "structurally_incomplete" and x["observed_result_value"] is None for x in repairs)
    assert all(x["supersedes"] == x["source_result_identity"] and x["immutable"] for x in repairs)


def test_result_repair_regression_exact_four():
    matched = [x for x in rows("reference_regression_task_results.jsonl")
               if x["root_cause_class"] == "invalid_result_record_plus_missing_link" and x["match"]]
    assert len(matched) == 4


def test_measurement_semantics_detects_three_exposure_outcome_merges():
    audits = rows("measurement_semantic_integrity_audit.jsonl")
    assert len(audits) == 3
    assert all(x["status"] == "invalid_merged_exposure_outcome" for x in audits)
    assert {x["measurement_kind"] for x in audits} == {"clinical_outcome", "phenotype", "survival_outcome"}


def test_measurement_revisions_preserve_history_and_exact_links():
    revisions = rows("measurement_repair_revisions.jsonl")
    assert len(revisions) == 3
    assert all(x["supersedes"] == x["source_measurement_identity"] and x["immutable"] for x in revisions)
    assert all(x["association_relation"] == "factor_associated_with_measurement" for x in revisions)
    summary = value("reference_guided_experimental_core_repair_summary.json")
    assert summary["measurement_repair_reference_match_count"] == 3


def test_four_reference_arms_are_reconstructed_exactly():
    arm_audit = rows("experimental_arm_reconstruction_audit.jsonl")
    arms = rows("experimental_arm_records_v1.jsonl")
    assert len(arm_audit) == len(arms) == 4
    assert all(x["exact_raw_match"] for x in arm_audit)
    assert all(x["historical_control_disposition"] == "historical_role_not_authoritative_for_current_result" for x in arm_audit)
    assert all(x["role_authority"] == "explicit_source" and x["role_candidate"] == "reference" for x in arms)


def test_arm_candidate_revisions_add_without_deleting_history():
    revisions = rows("candidate_set_revisions.jsonl")
    assert len(revisions) == 4
    assert all(x["historical_wrong_control_role_preserved"] for x in revisions)
    assert all(set(x["historical_candidate_ids"]) <= set(x["candidate_ids_after"]) for x in revisions)


def test_candidate_completeness_gate_catches_four_missing_arms_and_six_source_gaps():
    audits = rows("candidate_completeness_audit.jsonl")
    before = Counter(x["status_before"] for x in audits)
    assert before["incomplete_reference_arm"] == 4
    assert before["source_scope_insufficient"] == 6
    assert sum(x["status_after"] == "complete" for x in audits) == 33


def test_materialization_total_and_fail_closed_total_reconcile():
    assert len(rows("source_grounded_linkage_materialization_candidates.jsonl")) == 39
    assert len(rows("source_grounded_materialized_linkages.jsonl")) == 33
    assert len(rows("linkage_materialization_rejections.jsonl")) == 6


def test_materialized_links_have_exact_endpoints_evidence_and_versioned_rule():
    links = rows("source_grounded_materialized_linkages.jsonl")
    assert all(x["source_ref"] and x["target_ref"] and x["evidence_refs"] for x in links)
    assert all(x["repair_rule_identity"] == "explicit_source_grounding_v1" for x in links)
    assert all(x["authority_state"] == "materialized_sidecar" and x["immutable"] for x in links)


def test_no_role_or_unique_candidate_shortcut_authorized_any_candidate():
    candidates = rows("source_grounded_linkage_materialization_candidates.jsonl")
    assert not any(x["role_metadata_only"] for x in candidates)
    assert not any(x["candidate_cardinality_only"] for x in candidates)


def test_annotation_task_validity_routing_matches_five_classes():
    assert value("annotation_task_routing_summary.json")["status_counts"] == {
        "already_deterministically_resolvable": 22,
        "candidate_set_incomplete": 4,
        "observation_structure_invalid": 4,
        "source_scope_insufficient": 6,
        "structural_remediation_required": 3,
    }
    assert not any(x["status"] == "valid_for_annotation" for x in rows("annotation_task_validity_gate.jsonl"))


def test_pmc7744182_only_local_source_was_reparsed():
    audit = value("pmc7744182_local_source_recovery_audit.json")
    assert audit["task_count"] == audit["local_source_recovered_count"] == 6
    assert audit["methods_available"] and audit["figure_captions_available"]
    assert audit["network_used"] is False and audit["downloads"] == 0


def test_pmc7744182_composite_controls_remain_fail_closed():
    tasks = value("pmc7744182_local_source_recovery_audit.json")["tasks"]
    assert all(x["exact_reference_arm_status"] == "blocked_competing_control_scopes" for x in tasks)
    assert all(not x["composite_control_accepted"] for x in tasks)
    assert all(not x["execution_authorized"] and not x["network_authorized"] for x in tasks)


def test_reference_regression_totals_are_33_exact_6_fail_closed_zero_mismatch():
    summary = value("reference_regression_summary.json")
    assert summary["reference_task_count"] == 39
    assert summary["reference_exact_match_count"] == 33
    assert summary["reference_fail_closed_match_count"] == 6
    assert summary["reference_mismatch_count"] == 0


def test_readiness_v5_covers_every_v4_observation_exactly_once():
    records = rows("machine_reuse_readiness_v5_candidates.jsonl")
    comparison = value("machine_reuse_v4_v5_comparison.json")
    assert len(records) == comparison["v4_count"] == comparison["v5_count"] == 418
    assert len({x["observation_identity"] for x in records}) == 418
    assert all(x["candidate_only"] and not x["active_v4_replaced"] for x in records)


def test_readiness_v5_distribution_is_reconciled():
    assert Counter(x["status"] for x in rows("machine_reuse_readiness_v5_candidates.jsonl")) == {
        "machine_reusable_candidate": 224,
        "machine_reusable_with_method_limitation": 187,
        "structured_core_blocked_local_source_gap": 6,
        "structured_core_linkage_unresolved": 1,
    }


def test_special_core_877_comparator_repair_does_not_clear_second_blocker():
    audit = value("special_core_877_audit.json")
    assert audit["comparator_repaired"] is True
    assert audit["secondary_factor_measurement_or_local_scope_blocker"] is True
    assert audit["observation_machine_reusable"] is False
    assert audit["v5_status"] == "structured_core_linkage_unresolved"


def test_runtime_reference_leakage_audit_is_zero():
    audit = value("reference_oracle_leakage_audit.json")
    assert audit["status"] == "passed"
    assert audit["production_reference_import_count"] == 0
    assert audit["hardcoded_reference_task_id_count"] == 0
    assert audit["hardcoded_reference_answer_count"] == 0
    assert audit["runtime_reference_directory_reads"] == 0


def test_candidate_and_formal_scientific_state_is_unchanged():
    audit = value("scientific_state_safety_audit.json")
    assert audit["candidate_count_before"] == audit["candidate_count_after"] == 11
    assert not audit["candidate_identity_changed"] and not audit["candidate_order_changed"]
    assert not audit["scientific_pair_set_changed"]
    assert audit["formal_conflict_count_before"] == audit["formal_conflict_count_after"] == 0


def test_historical_scientific_assets_hashes_are_unchanged():
    audit = value("scientific_state_safety_audit.json")
    assert audit["protected_historical_sha256_before"] == audit["protected_historical_sha256_after"]
    assert audit["historical_assets_modified"] is False
    assert not audit["historical_raw_files_modified"]
    assert not audit["historical_validated_observations_modified"]
    assert not audit["historical_projection_content_modified"]


def test_special_candidate_and_policy_states_are_preserved():
    states = value("scientific_state_safety_audit.json")["special_scientific_states"]
    assert states["weak_3ca_source_reingestion_audit.json"]["difference_authority_status"] == "ready_not_materialized"
    assert states["weak_256_source_reingestion_audit.json"]["context_entry_status"] == "blocked_context_b_unavailable"
    assert states["ebd5_source_reingestion_audit.json"]["formal_conflict_status"] == "not_confirmed"
    assert states["context_17b_source_reingestion_audit.json"]["status"] == "fail_closed_policy_coverage_failure"
    assert states["context_41f_source_reingestion_audit.json"]["status"] == "fail_closed_policy_coverage_failure"


def test_provider_network_credentials_annotation_and_gold_are_all_zero_false():
    audit = value("scientific_state_safety_audit.json")
    assert audit["provider_calls"] == audit["api_calls"] == audit["network_calls"] == audit["downloads"] == 0
    assert not audit["credential_values_read"] and not audit["provider_client_created"]
    assert audit["human_annotations_executed"] == 0 and not audit["human_gold_created"]


def test_atlas_active_pointer_and_vem_remain_inactive():
    audit = value("scientific_state_safety_audit.json")
    assert not audit["atlas_activated"] and not audit["active_pointer_changed"]
    assert not audit["variational_em_called"]


def test_all_seven_contract_schemas_are_strict():
    schemas = list((RUN / "schemas").glob("*.schema.json"))
    assert len(schemas) == 7
    for path in schemas:
        schema = json.loads(path.read_text())
        assert schema["additionalProperties"] is False
        assert schema["required"]


def test_contract_identities_are_stable_and_runtime_fixture_access_is_false():
    contracts = list((RUN / "contract_identities").glob("*.contract_identity.json"))
    assert len(contracts) == 7
    for path in contracts:
        contract = json.loads(path.read_text())
        assert contract["identity_match"] is True
        assert contract["runtime_fixture_access"] is False
        assert contract["scientific_inference_authorized"] is False


def test_manifest_hashes_every_pre_manifest_artifact_correctly():
    manifest = value("reference_guided_experimental_core_repair_manifest.json")
    assert manifest["status"] == "completed"
    for entry in manifest["artifacts"]:
        path = RUN / entry["path"]
        assert path.is_file()
        assert sha(path) == entry["sha256"]


def test_full_test_baseline_is_recorded_without_hiding_failures():
    summary = value("reference_guided_experimental_core_repair_summary.json")
    assert summary["baseline_passed_count"] == 2142
    assert len(summary["baseline_failed_test_ids"]) == 6


def test_contract_document_states_authority_and_history_boundaries():
    text = (ROOT / "docs/contracts/reference_guided_experimental_core_repair_v1.md").read_text()
    assert "not Human Gold" in text
    assert "never load an evaluation fixture" in text
    assert "Historical Raw, Parsed, Validated" in text
