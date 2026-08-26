import copy
import json
from pathlib import Path

from code_engine.context_attribution.conflict_candidate.proposition_authority_v1_candidate import (
    ObservationScientificReadinessAxesV1,
    evaluate_minimum_proposition_sufficiency_v1,
    measurement_semantic_family_v1,
    profile_for_observation_type_v1,
    recover_exact_local_alias_v1,
    repository_proposition_profiles_v1,
)


ROOT = Path(__file__).resolve().parents[1]
RUN = ROOT / "runs/20260825_proposition_authority_coverage_decomposition_v1_offline"
ART = RUN / "artifacts"


def _resolved_fields(profile):
    return {field: "resolved" for field in profile.required_fields}


def _valid_entities(profile):
    return {role: "valid" for role in profile.required_entity_roles}


def test_not_applicable_field_does_not_make_profile_incomplete():
    profile = profile_for_observation_type_v1("observational_comparison")
    assessment = evaluate_minimum_proposition_sufficiency_v1(
        observation_id="observation:1",
        profile=profile,
        field_states={
            **_resolved_fields(profile),
            "intervention_proposition": "unresolved",
        },
        entity_role_states=_valid_entities(profile),
    )
    assert assessment.field_states["intervention_proposition"] == "not_applicable"
    assert assessment.minimum_profile_satisfied


def test_required_field_missing_does_make_profile_incomplete():
    profile = profile_for_observation_type_v1("interventional_experiment")
    fields = _resolved_fields(profile)
    fields["result_semantic_family"] = "unresolved"
    assessment = evaluate_minimum_proposition_sufficiency_v1(
        observation_id="observation:1",
        profile=profile,
        field_states=fields,
        entity_role_states=_valid_entities(profile),
    )
    assert assessment.proposition_readiness_state == "reviewable"
    assert assessment.unresolved_required_fields == ["result_semantic_family"]


def test_observational_profile_does_not_require_intervention():
    profile = profile_for_observation_type_v1("observational_comparison")
    assert "intervention_proposition" not in profile.required_fields
    assert "intervention_proposition" in profile.not_applicable_fields


def test_interventional_profile_requires_intervention_semantics():
    profile = profile_for_observation_type_v1("interventional_experiment")
    assert "intervention_proposition" in profile.required_fields
    assert profile.required_intervention_semantics


def test_descriptive_profile_does_not_invent_contrast_requirement():
    profile = profile_for_observation_type_v1("descriptive_measurement")
    assert "experimental_contrast" not in profile.required_fields
    assert "experimental_contrast" in profile.not_applicable_fields


def test_existing_measurement_maps_through_deterministic_semantic_authority():
    assert measurement_semantic_family_v1("abundance_expression") == "abundance"


def test_unmapped_measurement_property_remains_unresolved():
    assert measurement_semantic_family_v1("totally novel abundance-like state") is None


def test_noncritical_entity_warning_does_not_block_observation():
    profile = profile_for_observation_type_v1("descriptive_measurement")
    assessment = evaluate_minimum_proposition_sufficiency_v1(
        observation_id="observation:1",
        profile=profile,
        field_states=_resolved_fields(profile),
        entity_role_states={**_valid_entities(profile), "metadata_mention": "noncritical_warning"},
    )
    assert assessment.minimum_profile_satisfied
    assert assessment.noncritical_entity_warnings == ["metadata_mention"]


def test_proposition_critical_unresolved_entity_blocks():
    profile = profile_for_observation_type_v1("descriptive_measurement")
    entities = _valid_entities(profile)
    entities["measurement_target"] = "unresolved"
    assessment = evaluate_minimum_proposition_sufficiency_v1(
        observation_id="observation:1",
        profile=profile,
        field_states=_resolved_fields(profile),
        entity_role_states=entities,
    )
    assert assessment.proposition_readiness_state == "blocked"
    assert assessment.blocking_entity_roles == ["measurement_target"]


def test_offline_exact_alias_recovery_never_changes_source_object():
    historical = {"target": "  CSN8 ", "canonical_identity": None, "immutable": True}
    before = copy.deepcopy(historical)
    state, identity = recover_exact_local_alias_v1(
        historical["target"], {"csn8": "EntrezGene:10920"}
    )
    assert (state, identity) == ("recovered", "EntrezGene:10920")
    assert historical == before


def test_exact_alias_recovery_is_not_fuzzy():
    assert recover_exact_local_alias_v1(
        "CSN-8", {"CSN8": "EntrezGene:10920"}
    ) == ("unresolved", None)


def test_conflicting_exact_alias_authorities_are_ambiguous():
    assert recover_exact_local_alias_v1(
        "CSN8", {"CSN8": "EntrezGene:10920", "csn8 ": "Other:1"}
    ) == ("ambiguous", None)


def test_profile_set_uses_only_repository_observation_types():
    profiles = repository_proposition_profiles_v1()
    assert {row.profile_id for row in profiles} == {
        "interventional_effect", "observational_association", "descriptive_observation",
    }
    assert all(row.direction_required_for_identity is False for row in profiles)


def test_data_reuse_readiness_is_independent_of_conflict_readiness():
    axes = ObservationScientificReadinessAxesV1(
        observation_id="observation:1",
        experimental_core_reuse_state="machine_reusable_candidate",
        proposition_readiness_state="blocked",
        entity_integrity_state="blocked_upstream_entity_integrity",
        provenance_state="complete",
    )
    assert axes.experimental_core_reuse_state == "machine_reusable_candidate"
    assert axes.proposition_readiness_state == "blocked"


def test_zero_universal_complete_is_not_a_scientifically_negative_classification():
    profile = profile_for_observation_type_v1("observational_comparison")
    fields = _resolved_fields(profile)
    fields["relation_effect_family"] = "unresolved"
    assessment = evaluate_minimum_proposition_sufficiency_v1(
        observation_id="observation:1",
        profile=profile,
        field_states=fields,
        entity_role_states=_valid_entities(profile),
    )
    assert assessment.proposition_readiness_state == "reviewable"
    assert "scientifically_negative" not in assessment.proposition_readiness_state


def test_completed_artifacts_preserve_historical_candidate_and_formal_counts():
    summary_path = ART / "summary.json"
    if not summary_path.exists():
        return
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    assert summary["metrics"]["historical_candidate_object_count"] == 11
    assert summary["metrics"]["formal_conflict_count"] == 0
    assert summary["safety"]["historical_assets_modified"] is False


def test_completed_authority_taxonomy_partitions_all_prior_gaps_once():
    taxonomy_path = ART / "authority_gap_taxonomy_v1.json"
    if not taxonomy_path.exists():
        return
    taxonomy = json.loads(taxonomy_path.read_text(encoding="utf-8"))
    assert taxonomy["gap_record_count"] == 1099
    assert taxonomy["unclassified_gap_record_count"] == 0
    assert sum(row["count"] for row in taxonomy["categories"]) == 1099
    assert all(row["primary_category_code"] for row in taxonomy["rows"])


def test_completed_recovery_sidecars_are_offline_exact_and_non_mutating():
    recovery_path = ART / "proposition_authority_recovery_candidates_v1.jsonl"
    if not recovery_path.exists():
        return
    rows = [json.loads(line) for line in recovery_path.read_text(encoding="utf-8").splitlines()]
    assert len(rows) == 1099
    assert sum(row["recovery_state"] in {"recovered", "partially_recovered"} for row in rows) == 129
    assert all(row["historical_object_modified"] is False for row in rows)
    assert all(row["fuzzy_matching_used"] is False for row in rows)
    assert all(row["llm_used"] is False and row["provider_used"] is False for row in rows)


def test_completed_sufficiency_partition_and_pair_readiness_are_exact():
    readiness_path = ART / "pair_generation_readiness_v1.json"
    if not readiness_path.exists():
        return
    readiness = json.loads(readiness_path.read_text(encoding="utf-8"))
    assert readiness["pair_generation_ready_observation_count"] == 0
    assert readiness["reviewable_observation_count"] == 10
    assert readiness["blocked_observation_count"] == 320
    assert readiness["candidate_regeneration_executed"] is False
    assert readiness["l4_executed"] is False


def test_completed_state_c_reclassification_is_not_scientifically_negative():
    state_path = ART / "state_c_reclassification.json"
    if not state_path.exists():
        return
    state = json.loads(state_path.read_text(encoding="utf-8"))
    assert state["reclassified_state"] == "C3"
    assert state["c5_rejected"] is True
    assert state["scientifically_negative_conclusion"] is False
