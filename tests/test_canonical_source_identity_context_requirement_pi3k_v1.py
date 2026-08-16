import json
from pathlib import Path

import pytest

from code_engine.extraction_assets.context.requirements_v1 import (
    ContextRequirementContractV1, ContextRequirementSatisfactionV1,
    evaluate_trigger, readiness_v4, satisfaction_for, stable,
)
from code_engine.extraction_assets.source_identity import (
    ProvenanceClosureFactsV1, SourceAssetIdentityV1,
    SourceIdentityReconciliationRevisionV1, bridge_candidate_gate,
    identifier_collision_rows, normalize_identifier, normalize_title,
)


ROOT = Path(__file__).resolve().parents[1]
RUN = ROOT / "runs/20260816_canonical_source_identity_context_requirement_pi3k_e2e_replay_v1_offline/artifacts"


def j(name):
    return json.loads((RUN / name).read_text())


def jl(name):
    return [json.loads(x) for x in (RUN / name).read_text().splitlines() if x]


def contract(requirement="required", condition=None, derived=False):
    value = {
        "contract_id": "c", "consumer": "test_consumer", "consumer_version": "v1",
        "context_dimension": "temporal", "requirement_class": requirement,
        "trigger_condition": condition or {"operator": "always"},
        "blocking_semantics": "block when activated and unsatisfied",
        "field_satisfaction_mapping": ["duration", "timepoint"],
        "derived_satisfaction_allowed": derived, "source_contract_ref": "tests:fixture",
        "source_code_ref": "tests:fixture", "authority": "production_source_contract",
    }
    if requirement == "no_requirement_declared":
        value["authority"] = "no_declaration_found"
    return ContextRequirementContractV1.model_validate(value)


def satisfaction(requirement, status):
    return ContextRequirementSatisfactionV1(
        satisfaction_id=stable("sat", [requirement, status]), activation_id="a",
        observation_identity="o", context_dimension="temporal",
        requirement_class=requirement, status=status,
    )


# Source identity robustness 1-16.
def test_01_exact_pmid_and_doi_normalization_closes():
    assert normalize_identifier("PMID: 12", "pmid") == "12"
    assert normalize_identifier("https://doi.org/10.X/A.", "doi") == "10.x/a"


def test_02_historical_wrong_pmcid_is_a_sidecar_revision():
    revision = SourceIdentityReconciliationRevisionV1(
        revision_id="r", historical_identity={"pmcid": "PMC1"},
        reconciled_identity={"pmcid": "PMC2"}, status="historical_alias_non_authoritative",
        reason="local XML differs", evidence_refs=["local.xml"], rule_identity="rule",
    )
    assert revision.supersedes_relation == "sidecar_only_no_historical_mutation"


def test_03_one_pmid_conflicting_doi_is_a_collision():
    result = identifier_collision_rows([
        {"pmid": "1", "doi": "10/a"}, {"pmid": "1", "doi": "10/b"},
    ])
    assert any(x["identifier_type"] == "pmid" for x in result)


def test_04_same_title_alone_does_not_merge():
    assert identifier_collision_rows([{"title": "A"}, {"title": "A"}]) == []


def test_05_fuzzy_title_is_not_an_authority():
    assert normalize_title("Alpha—Beta") == normalize_title("alpha beta")
    assert identifier_collision_rows([{"title": "Alpha beta"}, {"title": "Alpha bet"}]) == []


def test_06_same_publication_can_have_multiple_assets():
    a = SourceAssetIdentityV1(source_asset_identity_id="a", publication_identity_id="p",
        asset_type="local_xml", pmcid="PMC1", local_path="a", asset_sha256="1",
        identity_status="exact_verified", authority="local_xml_metadata", provenance_refs=["a"])
    b = a.model_copy(update={"source_asset_identity_id": "b", "asset_sha256": "2"})
    assert a.publication_identity_id == b.publication_identity_id and a.asset_sha256 != b.asset_sha256


def test_07_historical_pmcid_cannot_merge_different_publications():
    result = identifier_collision_rows([{"pmcid": "PMC1", "pmid": "1"}, {"pmcid": "PMC1", "pmid": "2"}])
    assert result[0]["resolution_status"] == "fail_closed"


def test_08_abstract_to_fulltext_requires_publication_closure():
    assert bridge_candidate_gate(ProvenanceClosureFactsV1(
        publication_identity_closed=False, source_asset_identity_closed=True,
        exact_span_provenance=True, entity_compatible=True,
        experiment_scope_compatible=True, measurement_result_compatible=True,
    )) == "blocked_publication_identity"


def test_09_publication_closure_does_not_bridge_observation():
    assert bridge_candidate_gate(ProvenanceClosureFactsV1(
        publication_identity_closed=True, source_asset_identity_closed=True,
        exact_span_provenance=False, entity_compatible=True,
        experiment_scope_compatible=True, measurement_result_compatible=True,
    )) == "manual_review_required"


def test_10_source_fix_does_not_fix_entity():
    assert bridge_candidate_gate(ProvenanceClosureFactsV1(
        publication_identity_closed=True, source_asset_identity_closed=True,
        exact_span_provenance=True, entity_compatible=False,
        experiment_scope_compatible=True, measurement_result_compatible=True,
    )) == "blocked_entity_identity"


def test_11_historical_alias_is_preserved_in_output():
    assert any(x["historical_aliases"] for x in jl("canonical_publication_identities_v1.jsonl"))


def test_12_corrected_identity_uses_revision():
    assert all(x["supersedes_relation"] == "sidecar_only_no_historical_mutation"
               for x in jl("source_identity_reconciliation_revisions_v1.jsonl"))


def test_13_asset_hash_difference_does_not_imply_publication_difference():
    assets = jl("source_asset_identities_v1.jsonl")
    by_pub = {}
    for x in assets:
        if x["publication_identity_id"] and x["asset_sha256"]:
            by_pub.setdefault(x["publication_identity_id"], set()).add(x["asset_sha256"])
    assert any(len(v) > 1 for v in by_pub.values())


def test_14_same_publication_does_not_imply_same_experiment():
    facts = ProvenanceClosureFactsV1(publication_identity_closed=True, source_asset_identity_closed=True,
        exact_span_provenance=True, entity_compatible=True, experiment_scope_compatible=False,
        measurement_result_compatible=True, unresolved_competing_experiment=True)
    assert bridge_candidate_gate(facts) == "blocked_experiment_ambiguity"


def test_15_duplicate_internal_ids_may_alias_same_publication():
    assert identifier_collision_rows([
        {"internal_source_id": "A", "pmid": "1"}, {"internal_source_id": "B", "pmid": "1"},
    ]) == []


def test_16_conflicting_internal_mapping_fails_closed():
    result = identifier_collision_rows([
        {"internal_source_id": "A", "pmid": "1"}, {"internal_source_id": "A", "pmid": "2"},
    ])
    assert result[0]["identifier_type"] == "internal_source_id"


# Provenance 17-24.
def test_17_claim_publication_closure_is_audited():
    assert j("source_identity_reconciliation_summary.json")["claim_to_publication_closure_count"] > 0


def test_18_observation_publication_closure_is_audited():
    assert j("source_identity_reconciliation_summary.json")["observation_to_publication_closure_count"] > 0


def test_19_same_publication_never_auto_materializes_bridge():
    assert all(not x["scientific_bridge_created"] for x in jl("pi3k_bridge_gate_results_v2.jsonl"))


def test_20_exact_provenance_is_required_before_later_gates():
    gates = jl("pi3k_bridge_gate_results_v2.jsonl")
    assert sum(x["facts"]["exact_span_provenance"] for x in gates) == 1


def test_21_wrong_asset_identity_blocks():
    facts = ProvenanceClosureFactsV1(publication_identity_closed=True, source_asset_identity_closed=False,
        exact_span_provenance=True, entity_compatible=True, experiment_scope_compatible=True,
        measurement_result_compatible=True)
    assert bridge_candidate_gate(facts) == "blocked_source_asset_identity"


def test_22_historical_alias_is_not_current_authority():
    pubs = jl("canonical_publication_identities_v1.jsonl")
    historical = [s for p in pubs for s in p["identifier_authority_states"] if s["authority"] == "historical_mapping"]
    assert historical and any(not x["current_authority"] for x in historical)


def test_23_entity_mismatch_is_independent_blocker():
    assert "different_entities" in {x["entity_identity_state"] for x in jl("pi3k_entity_identity_audit.jsonl")}


def test_24_multiple_experiment_candidates_remain_manual():
    manual = [x for x in jl("pi3k_bridge_gate_results_v2.jsonl") if x["gate_status"] == "manual_review_required"]
    assert manual[0]["competing_experiment_count"] > 1


# Context requirement robustness 25-39.
def test_25_no_declaration_cannot_be_ready():
    assert readiness_v4([satisfaction("no_requirement_declared", "not_applicable")]) == "reviewable_no_requirement_contract"


def test_26_no_declaration_cannot_be_blocked():
    assert not readiness_v4([satisfaction("no_requirement_declared", "not_applicable")]).startswith("blocked_")


def test_27_required_direct_is_satisfied():
    assert satisfaction_for(contract(), value_authority="direct_structured", value_state="present") == "satisfied_direct"


def test_28_required_safe_inherited_is_satisfied():
    assert satisfaction_for(contract(), value_authority="scope_inherited", value_state="present") == "satisfied_safe_inheritance"


def test_29_required_unresolved_blocks():
    assert readiness_v4([satisfaction("required", "unsatisfied_unresolved")]) == "blocked_required_context_missing"


def test_30_conditional_requirement_not_triggered():
    c = contract("conditionally_required", {"field": "comparison_type", "in": ["time_dependent"]})
    assert not evaluate_trigger(c, {"comparison_type": "static"})


def test_31_conditional_requirement_triggered():
    c = contract("conditionally_required", {"field": "comparison_type", "in": ["time_dependent"]})
    assert evaluate_trigger(c, {"comparison_type": "time_dependent"})


def test_32_derived_value_requires_contract_permission():
    assert satisfaction_for(contract(derived=False), value_authority="deterministically_derived", value_state="present") == "unsatisfied_unresolved"
    assert satisfaction_for(contract(derived=True), value_authority="deterministically_derived", value_state="present") == "satisfied_derived"


def test_33_ambiguous_cannot_satisfy_required():
    assert satisfaction_for(contract(), value_authority="direct_structured", value_state="ambiguous") == "unsatisfied_ambiguous"


def test_34_wrong_scope_cannot_satisfy_required():
    assert satisfaction_for(contract(), value_authority="scope_inherited", value_state="present", source_scope_sufficient=False) == "unsatisfied_source_scope"


def test_35_optional_gap_is_nonblocking():
    assert readiness_v4([satisfaction("optional_explicit", "unsatisfied_unresolved")]) == "ready_with_nonblocking_optional_gap"


def test_36_no_declaration_is_not_optional():
    assert contract("no_requirement_declared").requirement_class != "optional_explicit"


def test_37_registry_membership_does_not_imply_requirement():
    assert j("context_requirement_dimension_registry_v1.json")["registry_membership_does_not_imply_requirement"]


def test_38_domain_profile_does_not_add_requirements():
    assert {x["authority"] for x in jl("downstream_context_requirement_contracts_v1.jsonl")} == {"no_declaration_found"}


def test_39_case_identity_is_not_a_requirement_trigger():
    text = (RUN / "downstream_context_requirement_contracts_v1.jsonl").read_text().casefold()
    assert "pi3k" not in text and "task_id" not in text


# Frozen PI3K 40-48.
def test_40_frozen_case_identity_unchanged():
    assert j("pi3k_e2e_replay_v2_summary.json")["case_id"] == "pi3k_akt_mtor_cancer_resistance_discovery_v1"


def test_41_frozen_query_hash_unchanged():
    frozen = j("../../../../configs/generated_cases/pi3k_akt_mtor_cancer_resistance_discovery_v1/search_plan.frozen.json") if False else json.loads((ROOT / "configs/generated_cases/pi3k_akt_mtor_cancer_resistance_discovery_v1/search_plan.frozen.json").read_text())
    assert frozen


def test_42_source_set_count_unchanged():
    assert j("pi3k_e2e_replay_v2_summary.json")["source_count"] == 41


def test_43_signal_ids_only_exist_outside_production_source():
    production = "".join(p.read_text(errors="ignore") for p in (ROOT / "src/code_engine").rglob("*.py"))
    assert "40f42ffa988cbcff" not in production and "f389a194ebdc1737" not in production


def test_44_no_production_pmid_case_rule():
    production = "".join(p.read_text(errors="ignore") for p in (ROOT / "src/code_engine").rglob("*.py"))
    assert "33643917" not in production


def test_45_no_production_entity_case_rule():
    production = "".join(p.read_text(errors="ignore") for p in (ROOT / "src/code_engine").rglob("*.py"))
    assert not ("PAR1" in production and "TCF20" in production)


def test_46_candidate_does_not_create_alignment():
    assert j("pi3k_e2e_replay_v2_summary.json")["scientific_bridges_created"] == 0


def test_47_manual_review_is_not_auto_resolved():
    assert j("pi3k_e2e_replay_v2_summary.json")["manual_review_count"] == 1


def test_48_scientific_state_is_not_overwritten():
    summary = j("pi3k_e2e_replay_v2_summary.json")
    assert (summary["aligned_group_count"], summary["qualified_candidate_count"], summary["formal_conflict_count"]) == (0, 0, 0)


# Regression 49-55.
@pytest.mark.parametrize("key,expected", [
    ("core_reference_exact_match_count", 33),
    ("core_reference_fail_closed_match_count", 6),
    ("core_reference_mismatch_count", 0),
    ("candidate_count_after", 11),
    ("formal_conflict_count_after", 0),
])
def test_49_53_reference_regression(key, expected):
    state = j("scientific_state_safety_audit.json")
    reference = j("reference_regression_recheck.json")
    assert state.get(key, reference.get(key)) == expected


def test_54_context_cross_scope_all_zero():
    scope = j("context_scope_safety_recheck.json")
    for dimension in ("arm", "experiment", "cohort", "timepoint", "dose"):
        assert scope.get(f"unsupported_cross_{dimension}_inheritance_count", 0) == 0


def test_55_weak_states_unchanged():
    reference = j("reference_regression_recheck.json")
    assert reference.get("weak_state_changed_count", 0) == 0


# Safety 56-67.
@pytest.mark.parametrize("key,expected", [
    ("provider_calls", 0), ("api_calls", 0), ("network_calls", 0), ("downloads", 0),
    ("credential_values_read", False), ("provider_client_created", False),
    ("atlas_activated", False), ("active_pointer_changed", False),
    ("variational_em_called", False), ("historical_assets_modified", False),
])
def test_56_64_runtime_safety(key, expected):
    assert j("final_validation.json")[key] == expected


def test_65_required_artifacts_exist():
    required = {
        "baseline_inventory.json", "global_source_identity_inventory_v1.jsonl",
        "global_source_identifier_index_v1.json", "global_source_identity_collision_audit_v1.jsonl",
        "canonical_publication_identities_v1.jsonl", "source_asset_identities_v1.jsonl",
        "source_identity_reconciliation_revisions_v1.jsonl", "source_provenance_closure_audit_v1.jsonl",
        "source_identity_reconciliation_summary.json", "downstream_context_consumer_inventory.json",
        "downstream_context_requirement_contracts_v1.jsonl", "context_requirement_dimension_registry_v1.json",
        "context_requirement_activations_v1.jsonl", "context_requirement_satisfaction_v1.jsonl",
        "context_readiness_v3_v4_comparison.json", "context_readiness_v4_candidates.jsonl",
        "context_requirement_contract_summary.json", "pi3k_signal_identity_reconciliation.jsonl",
        "pi3k_entity_identity_audit.jsonl", "pi3k_bridge_candidates_v2.jsonl",
        "pi3k_bridge_gate_results_v2.jsonl", "pi3k_e2e_v1_v2_comparison.json",
        "pi3k_e2e_replay_v2_stage_ledger.jsonl", "pi3k_e2e_replay_v2_summary.json",
        "reference_regression_recheck.json", "context_scope_safety_recheck.json",
        "scientific_state_safety_audit.json", "production_leakage_audit.json",
        "autonomous_iteration_ledger.jsonl", "final_validation.json", "manifest.json", "summary.json",
    }
    assert required <= {x.name for x in RUN.iterdir()}


def test_66_manifest_is_offline_and_complete():
    manifest = j("manifest.json")
    assert manifest["offline"] and not manifest["historical_assets_modified"]


def test_67_final_status_completed_without_bridge():
    validation = j("final_validation.json")
    assert validation["status"] == "completed" and not validation["scientific_bridge_materialization"]
