import pytest
from pydantic import ValidationError

from code_engine.extraction_assets.context.pair_requirements_v1 import (
    PairContextRequirementActivationV1,
    PairContextRequirementProfileV1,
    PairContextRequirementSatisfactionV1,
    readiness_for_pair,
    satisfaction_for_pair,
)
from code_engine.extraction_assets.forensics.abstract_claim_integrity import (
    AbstractClaimEntityIntegrityAuditV1,
    ExperimentCompatibilityFactsV1,
    ManualScientificReviewResponseV1,
    classify_entity_chain,
    filter_experiment_candidate,
    signal_integrity_for,
)
from code_engine.extraction_assets.provenance_authority import (
    classify_collision,
    closure_authority_for,
)


def _collision(**overrides):
    payload = {
        "identifier_type": "pmid",
        "identifier_value": "123",
        "incompatible_values": ["doi:a", "doi:b"],
        "evidence_rows": [{
            "internal_source_id": "paper-a",
            "asset_sha256": "hash-a",
            "record_kind": "local_xml_metadata",
            "source_path": "local.xml",
            "title_normalized": "title",
            "publication_year": "2020",
        }],
    }
    payload.update(overrides)
    return classify_collision(**payload)


def _activation(status="required_active", identity="requirement-1"):
    return PairContextRequirementActivationV1(
        pair_id="pair-1", consumer="consumer", consumer_version="v1",
        dimension="biological_model", activation_status=status,
        trigger_state="unconditional", trigger_evidence={}, blocking_semantics="blocking",
        source_contract_ref="contract", source_code_ref="code", requirement_identity=identity,
    )


def _satisfaction(status, side_a="unresolved", side_b="unresolved", identity="requirement-1"):
    return PairContextRequirementSatisfactionV1(
        pair_id="pair-1", consumer="consumer", dimension="biological_model",
        requirement_identity=identity, activation_status="required_active",
        side_a_evidence_state=side_a, side_b_evidence_state=side_b,
        satisfaction_status=status,
    )


def _facts(**overrides):
    payload = {
        "experiment_scope_id": "experiment-1",
        "observation_ids": ["observation-1"],
        "entity_compatible": True,
        "relation_compatible": True,
        "measurement_compatible": True,
        "result_compatible": True,
        "evidence_family_compatible": True,
    }
    payload.update(overrides)
    return ExperimentCompatibilityFactsV1(**payload)


# Provenance authority negative cases 1-7.
def test_internal_publication_parent_is_not_external_verification():
    assert closure_authority_for(
        publication_identity_closed=True, publication_identity_status="unresolved",
        has_external_identifier=False,
    ) == "closed_internal_publication_only"


def test_unresolved_external_publication_can_still_have_object_closure():
    assert closure_authority_for(
        publication_identity_closed=True, publication_identity_status="unresolved",
        has_external_identifier=True,
    ) == "closed_to_unresolved_external_identity"


def test_historical_alias_is_not_exact_verification():
    assert closure_authority_for(
        publication_identity_closed=True, publication_identity_status="historical_alias_preserved",
        has_external_identifier=True,
    ) == "closed_historical_alias"


def test_benign_duplicate_and_true_collision_are_separate():
    benign = _collision(
        evidence_rows=[
            {"internal_source_id": "a", "record_kind": "local_xml_metadata", "source_path": "a.xml", "title_normalized": "same", "publication_year": "2020"},
            {"internal_source_id": "b", "record_kind": "local_xml_metadata", "source_path": "b.xml", "title_normalized": "same", "publication_year": "2020"},
        ],
        publication_identity_ids=["publication-1"],
    )
    conflict = _collision(evidence_rows=[
        {"source_path": "a", "title_normalized": "first", "publication_year": "2020"},
        {"source_path": "b", "title_normalized": "second", "publication_year": "2021"},
    ])
    assert benign.primary_classification == "benign_duplicate_internal_mapping"
    assert conflict.primary_classification == "cross_publication_identifier_conflict"
    assert conflict.resolution_status == "fail_closed"


def test_multiple_assets_for_one_publication_is_not_publication_conflict():
    result = _collision(
        evidence_rows=[
            {"asset_sha256": "a", "source_path": "a", "title_normalized": "same", "publication_year": "2020"},
            {"asset_sha256": "b", "source_path": "b", "title_normalized": "same", "publication_year": "2020"},
        ],
        publication_identity_ids=["publication-1"],
    )
    assert result.primary_classification == "multiple_source_assets_same_publication"
    assert result.resolution_status == "benign"


def test_local_xml_current_identifier_separates_historical_alias_collision():
    result = _collision(
        identifier_type="pmcid", identifier_value="PMC-current",
        incompatible_values=["111", "222"],
        evidence_rows=[
            {"record_kind": "local_xml_metadata", "source_path": "article.xml", "pmid": "111", "pmcid": "PMC-current", "title_normalized": "current", "publication_year": "2020"},
            {"record_kind": "abstract_claim_provenance", "source_path": "old.jsonl", "pmid": "222", "pmcid": "PMC-current", "title_normalized": "historical", "publication_year": "2019"},
        ],
    )
    assert result.primary_classification == "historical_alias_collision"
    assert result.resolution_status == "benign"


def test_conflicting_doi_cannot_be_automatically_benign():
    result = _collision(
        identifier_type="doi", identifier_value="10.1/example",
        evidence_rows=[
            {"source_path": "a", "title_normalized": "first", "publication_year": "2020"},
            {"source_path": "b", "title_normalized": "second", "publication_year": "2020"},
        ],
    )
    assert result.primary_classification == "cross_publication_identifier_conflict"
    assert result.resolution_status == "fail_closed"


def test_title_only_does_not_externally_verify_or_authorize_benign():
    result = _collision(evidence_rows=[
        {"source_path": "a", "title_normalized": "same", "publication_year": "2020"},
        {"source_path": "b", "title_normalized": "same", "publication_year": "2020"},
    ])
    assert result.primary_classification == "unresolved_collision"
    assert result.title_only_merge_forbidden is True


# Pair Context negative cases 8-15.
def test_observation_context_presence_does_not_satisfy_pair_requirement():
    assert satisfaction_for_pair("required_active", "direct", "unresolved") == "partially_satisfied"


def test_no_consumer_contract_is_reviewable_not_ready():
    assert readiness_for_pair([], []) == "reviewable_no_requirement_contract"


def test_activated_required_unresolved_blocks():
    assert readiness_for_pair([_activation()], [_satisfaction("unsatisfied")]) == "blocked_required_context_missing"


def test_nonactivated_dimension_does_not_block():
    inactive = _activation(status="not_activated")
    assert readiness_for_pair([inactive], []) == "not_context_sensitive"


def test_context_difference_can_exist_when_dimension_is_not_required():
    inactive = _activation(status="not_required_explicit")
    assert readiness_for_pair([inactive], []) == "not_context_sensitive"


def test_required_dimension_without_difference_is_ready_when_both_sides_resolved():
    satisfied = _satisfaction("satisfied", "direct", "safe_inherited")
    assert readiness_for_pair([_activation()], [satisfied]) == "ready_all_active_requirements_satisfied"


def test_wrong_scope_inheritance_cannot_satisfy_requirement():
    row = _satisfaction("unsatisfied", "direct", "source_scope_insufficient")
    assert readiness_for_pair([_activation()], [row]) == "blocked_source_scope"


def test_pair_requirement_profile_rejects_task_ids():
    with pytest.raises(ValidationError, match="forbidden_evaluation_input"):
        PairContextRequirementProfileV1(
            pair_id="pair", consumer="consumer", consumer_version="v1",
            validated_trigger_inputs={"task_id": "hidden"}, contract_ids=[],
            requirement_identity="requirement",
        )


# Abstract entity integrity negative cases 16-22.
def test_abstract_source_is_only_upstream_entity_repair_authority():
    with pytest.raises(ValidationError, match="fulltext_cannot_authorize"):
        AbstractClaimEntityIntegrityAuditV1(
            claim_id="claim", signal_id=None, audited_entity_role="object",
            source_text="A affects B.", source_ref="abstract", raw_extraction_payload_ref="l1",
            subject_raw="A", object_raw="B", normalized_subject="A", normalized_object="B",
            entity_resolution_authority={}, projected_proposition_core={},
            contradiction_representation={}, signal_object_identity=None,
            integrity_status="consistent", error_stage="none",
            fulltext_used_as_upstream_repair_authority=True,
        )


def test_fulltext_expectation_is_not_an_input_to_entity_chain_classifier():
    status, _ = classify_entity_chain(
        source_text="A affects B.", raw_entity="B", normalized_entity="B",
        projected_entity="B", signal_entity="B", source_binding_verified=True,
    )
    assert status == "consistent"


def test_raw_extraction_error_is_detected():
    assert classify_entity_chain(
        source_text="A affects B.", raw_entity="C", normalized_entity="C",
        projected_entity="C", signal_entity="C", source_binding_verified=True,
    ) == ("raw_extraction_entity_error", "raw_extraction")


def test_normalization_error_is_detected():
    assert classify_entity_chain(
        source_text="A affects B.", raw_entity="B", normalized_entity="C",
        projected_entity="C", signal_entity="C", source_binding_verified=True,
    ) == ("normalization_entity_error", "normalization")


def test_claim_projection_error_is_detected():
    assert classify_entity_chain(
        source_text="A affects B.", raw_entity="B", normalized_entity="B",
        projected_entity="C", signal_entity="C", source_binding_verified=True,
    ) == ("claim_projection_entity_error", "claim_projection")


def test_genuinely_different_entities_fail_closed():
    assert signal_integrity_for("scientifically_different_entities") == "blocked_upstream_claim_integrity"


def test_corrupted_claim_cannot_generate_validated_bridge():
    assert signal_integrity_for("normalization_entity_error") == "blocked_upstream_claim_integrity"


# Deterministic experiment filtering negative cases 23-28.
def test_same_publication_identifier_is_not_a_filtering_input():
    assert "pmid" not in ExperimentCompatibilityFactsV1.model_fields
    assert filter_experiment_candidate(_facts(measurement_compatible=None)).candidate_status == "insufficient_evidence"


def test_incompatible_entity_is_excluded():
    result = filter_experiment_candidate(_facts(entity_compatible=False))
    assert result.candidate_status == "excluded_deterministically"
    assert "entity_incompatible" in result.deterministic_exclusion_reasons


def test_incompatible_measurement_is_excluded():
    result = filter_experiment_candidate(_facts(measurement_compatible=False))
    assert result.candidate_status == "excluded_deterministically"
    assert "measurement_incompatible" in result.deterministic_exclusion_reasons


def test_weak_or_unknown_similarity_cannot_exclude():
    result = filter_experiment_candidate(_facts(relation_compatible=None))
    assert result.candidate_status == "insufficient_evidence"
    assert result.weak_similarity_used_for_exclusion is False


def test_multiple_plausible_candidates_require_manual_review_boundary():
    results = [filter_experiment_candidate(_facts(experiment_scope_id=f"experiment-{i}")) for i in range(2)]
    assert sum(item.candidate_status == "scientifically_plausible_candidate" for item in results) > 1


def test_manual_review_response_is_empty_and_contains_no_answer_or_score():
    payload = ManualScientificReviewResponseV1().model_dump()
    assert payload["selected_candidate_ids"] == []
    assert payload["confidence"] is None
    assert "preferred_candidate" not in payload
    assert "score" not in payload
