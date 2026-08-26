import copy
import json
from pathlib import Path

from code_engine.context_attribution.conflict_candidate.proposition_authority_v1_candidate import (
    evaluate_minimum_proposition_sufficiency_v1,
    profile_for_observation_type_v1,
)
from code_engine.context_attribution.conflict_candidate.proposition_frontier_v1_candidate import (
    deterministic_measurement_property_family_v1,
    deterministic_relation_effect_family_v1,
    deterministic_result_semantic_family_v1,
    field_is_required_v2_candidate,
)


ROOT = Path(__file__).resolve().parents[1]
ART = ROOT / "runs/20260826_proposition_sufficiency_frontier_closure_v1_offline/artifacts"


def test_descriptive_profile_does_not_require_intervention():
    profile = profile_for_observation_type_v1("descriptive_measurement")
    assert "intervention_proposition" not in profile.required_fields
    assert "intervention_proposition" in profile.not_applicable_fields


def test_descriptive_profile_does_not_require_experimental_contrast():
    profile = profile_for_observation_type_v1("descriptive_measurement")
    assert "experimental_contrast" not in profile.required_fields
    assert not field_is_required_v2_candidate(profile.profile_id, "experimental_contrast")


def test_observational_profile_does_not_require_intervention():
    profile = profile_for_observation_type_v1("observational_comparison")
    assert "intervention_proposition" not in profile.required_fields
    assert not field_is_required_v2_candidate(profile.profile_id, "intervention_proposition")


def test_interventional_profile_requires_intervention_proposition():
    profile = profile_for_observation_type_v1("interventional_experiment")
    assert "intervention_proposition" in profile.required_fields
    assert field_is_required_v2_candidate(profile.profile_id, "intervention_proposition")


def test_missing_assay_method_is_only_a_qualifier():
    profile = profile_for_observation_type_v1("interventional_experiment")
    fields = {field: "resolved" for field in profile.required_fields}
    fields["assay_method"] = "unresolved"
    assessment = evaluate_minimum_proposition_sufficiency_v1(
        observation_id="o1", profile=profile, field_states=fields,
        entity_role_states={role: "valid" for role in profile.required_entity_roles},
    )
    assert assessment.minimum_profile_satisfied
    assert assessment.qualifier_warnings == ["assay_method", "granularity_qualifiers", "unit_representation"]


def test_measurement_property_missing_blocks_when_required():
    profile = profile_for_observation_type_v1("descriptive_measurement")
    fields = {field: "resolved" for field in profile.required_fields}
    fields["measurement_property_semantic_family"] = "unresolved"
    assessment = evaluate_minimum_proposition_sufficiency_v1(
        observation_id="o1", profile=profile, field_states=fields,
        entity_role_states={role: "valid" for role in profile.required_entity_roles},
    )
    assert not assessment.minimum_profile_satisfied


def test_result_direction_is_excluded_from_result_semantic_identity():
    positive = deterministic_result_semantic_family_v1(
        "abundance", has_qualitative=True, has_quantitative=False, direction="positive"
    )
    negative = deterministic_result_semantic_family_v1(
        "abundance", has_qualitative=True, has_quantitative=False, direction="negative"
    )
    assert positive == negative == ("abundance:qualitative_result", "result_semantic_family_v1")


def test_result_semantic_level_remains_required():
    assert field_is_required_v2_candidate("observational_association", "result_semantic_family")
    assert deterministic_result_semantic_family_v1(
        None, has_qualitative=True, has_quantitative=False
    )[0] is None


def test_exact_structured_property_maps_deterministically():
    assert deterministic_measurement_property_family_v1(
        "abundance_expression", "anything"
    ) == ("abundance", "measurement_property_family_v1")


def test_existing_exact_endpoint_contract_maps_overall_survival():
    assert deterministic_measurement_property_family_v1(
        "unknown", "overall survival"
    ) == ("clinical_outcome", "existing_exact_endpoint_type_contract_v1")


def test_raw_endpoint_without_semantic_authority_remains_unresolved():
    assert deterministic_measurement_property_family_v1(
        "unknown", "vaguely abundance-like endpoint"
    ) == (None, "unresolved")


def test_projection_missing_is_distinct_from_semantic_family_unmapped():
    blockers = ART / "frontier_proposition_blockers_v1.jsonl"
    if not blockers.exists():
        return
    rows = [json.loads(line) for line in blockers.read_text().splitlines()]
    assert {row["blocker_type"] for row in rows} >= {
        "projection_missing", "semantic_family_unmapped"
    }
    assert all(
        row["recoverability"] == "deterministic_existing_authority"
        for row in rows if row["blocker_type"] == "projection_missing"
    )


def test_requirements_do_not_relax_because_pass_count_is_zero():
    assert field_is_required_v2_candidate(
        "interventional_effect", "measurement_property_semantic_family"
    )
    path = ART / "minimum_profile_overconstraint_audit.json"
    if path.exists():
        audit = json.loads(path.read_text())
        assert audit["requirements_relaxed_due_to_zero_pass_count"] is False


def test_entity_v2_local_authority_remains_accepted_without_external_id():
    path = ART / "frontier_observation_inventory.jsonl"
    if not path.exists():
        return
    rows = [json.loads(line) for line in path.read_text().splitlines()]
    local = [row for row in rows if row["entity_authority"] == "eligible_local_exact_authority"]
    assert len(local) == 7
    assert any(not row["external_canonicalization_ready"] for row in local)


def test_causal_mode_mapping_preserves_evidence_family():
    assert deterministic_relation_effect_family_v1("interventional_experiment") == "interventional_effect"
    assert deterministic_relation_effect_family_v1("observational_comparison") == "observational_association"
    assert deterministic_relation_effect_family_v1("descriptive_measurement") == "descriptive_observation"


def test_recovery_does_not_mutate_inputs():
    source = {"semantic_level": "abundance_expression", "endpoint": "SOX2 expression"}
    before = copy.deepcopy(source)
    deterministic_measurement_property_family_v1(source["semantic_level"], source["endpoint"])
    assert source == before


def test_completed_run_preserves_historical_scientific_objects():
    path = ART / "scientific_state_safety_audit.json"
    if not path.exists():
        return
    safety = json.loads(path.read_text())
    assert safety["historical_assets_modified"] is False
    assert safety["historical_candidate_count_after"] == 11
    assert safety["formal_conflict_count_after"] == 0
    assert safety["entity_integrity_claims_blocked"] == 241
    assert safety["entity_integrity_signals_blocked"] == 2


def test_completed_run_has_no_llm_fuzzy_network_or_candidate_generation():
    path = ART / "production_leakage_audit.json"
    if not path.exists():
        return
    leakage = json.loads(path.read_text())
    safety = json.loads((ART / "scientific_state_safety_audit.json").read_text())
    assert leakage["free_text_inference_used"] is False
    assert leakage["fuzzy_matching_used"] is False
    assert leakage["llm_used"] is False
    assert leakage["case_specific_rules"] == []
    assert safety["network_calls"] == safety["provider_calls"] == safety["llm_calls"] == 0
    assert safety["candidate_generation_executed"] is False


def test_completed_frontier_explains_all_twenty_and_does_not_reextract():
    path = ART / "frontier_proposition_sufficiency_replay.jsonl"
    if not path.exists():
        return
    rows = [json.loads(line) for line in path.read_text().splitlines()]
    assert len(rows) == 20
    assert all(row["minimum_profile_satisfied"] or row["final_blocker_ids"] for row in rows)
    summary = json.loads((ART / "summary.json").read_text())
    assert summary["metrics"]["frontier_future_extraction_required_count"] == 0
