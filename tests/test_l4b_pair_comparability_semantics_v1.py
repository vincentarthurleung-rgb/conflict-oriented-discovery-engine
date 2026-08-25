import pytest
from pydantic import ValidationError

from code_engine.extraction_assets.context.pair_requirements_v2 import (
    ContextSideValueV2,
    L4bUpstreamEligibilityV1,
    PairContextTriggerFactV2,
    activate_pair_dimension_v2,
    build_dimension_evidence_v2,
    evaluate_l4b_comparability_v1,
    l4a_descriptive_state_v1,
    satisfaction_for_pair_v2,
)


PAIR = "generic-pair"
CONSUMER = "l4b_comparability"


def _side(value, *, authority="validated_source_grounded", scope="adequate", provenance=None):
    return ContextSideValueV2(
        value_state="present",
        value=value,
        source_authority=authority,
        source_scope_adequacy=scope,
        provenance=provenance or [f"source#{value}"],
        inheritance_scope_validated=authority == "safe_scope_inherited",
        deterministic_rule_identity=("rule-v1" if authority == "authorized_deterministic_derived" else None),
    )


def _unknown(*, scope="unresolved", provenance=None):
    return ContextSideValueV2(
        value_state="unknown",
        source_scope_adequacy=scope,
        provenance=provenance or [],
    )


def _not_reported(ref="source#audited"):
    return ContextSideValueV2(
        value_state="not_mentioned",
        source_scope_adequacy="adequate",
        provenance=[ref],
    )


def _fact(
    dimension="genotype",
    role="comparison_required",
    *,
    consumer=CONSUMER,
    family="experimental_factor_scope",
    structurally_established=True,
    role_determinable=True,
    **extra,
):
    return PairContextTriggerFactV2(
        pair_id=PAIR,
        consumer=consumer,
        dimension=dimension,
        trigger_family=family,
        structurally_established=structurally_established,
        decision_role=role if role_determinable else None,
        role_determinable=role_determinable,
        trigger_evidence={"validated_factor": dimension},
        source_contract_ref="generic-scientific-contract-v1",
        source_code_ref="generic-structured-source#factor",
        **extra,
    )


def _activation(dimension="genotype", facts=None, consumer=CONSUMER):
    return activate_pair_dimension_v2(
        pair_id=PAIR,
        consumer=consumer,
        consumer_version="v2",
        dimension=dimension,
        trigger_facts=facts if facts is not None else [_fact(dimension, consumer=consumer)],
    )


def _evidence(dimension, side_a, side_b):
    return build_dimension_evidence_v2(
        pair_id=PAIR,
        dimension=dimension,
        side_a=side_a,
        side_b=side_b,
    )


def _upstream(**overrides):
    payload = {
        "pair_id": PAIR,
        "entity_integrity_eligible": True,
        "alignment_eligible": True,
        "contradiction_signal_valid": True,
        "candidate_qualification_eligible": True,
        "entity_integrity_state": "eligible",
        "alignment_state": "aligned",
        "contradiction_signal_state": "validated",
        "candidate_qualification_state": "qualified",
    }
    payload.update(overrides)
    return L4bUpstreamEligibilityV1(**payload)


def _result(activations, evidence, upstream=None):
    return evaluate_l4b_comparability_v1(
        pair_id=PAIR,
        upstream=upstream or _upstream(),
        activations=activations,
        dimension_evidence=evidence,
    )


# Scientific examples A-J.
def test_required_genotype_wt_vs_wt_is_resolved_matched_and_comparable():
    evidence = _evidence("genotype", _side("WT"), _side("WT"))
    result, satisfaction = _result([_activation()], [evidence])
    assert satisfaction[0].satisfaction_status == "satisfied_resolved_matched"
    assert result.l4b_state == "comparable_all_required_context_resolved"


def test_required_genotype_wt_vs_ko_is_resolved_different_and_comparable():
    evidence = _evidence("genotype", _side("WT"), _side("KO"))
    result, satisfaction = _result([_activation()], [evidence])
    assert satisfaction[0].satisfaction_status == "satisfied_resolved_different"
    assert result.l4b_state == "comparable_with_context_divergence"
    assert result.comparable is True


def test_required_genotype_wt_vs_unknown_is_not_authoritatively_comparable():
    evidence = _evidence("genotype", _side("WT"), _unknown())
    result, _ = _result([_activation()], [evidence])
    assert evidence.dimension_state == "unresolved_b"
    assert result.l4b_state == "reviewable_required_context_gap"
    assert result.authoritative_l4b_result is False


def test_genotype_difference_not_decision_relevant_does_not_block():
    activation = _activation(facts=[])
    evidence = _evidence("genotype", _side("WT"), _side("KO"))
    result, _ = _result([activation], [evidence])
    assert activation.primary_role == "not_decision_relevant"
    assert result.l4b_state == "comparable_no_context_sensitive_requirement"


def test_missing_timepoint_without_temporal_trigger_creates_no_requirement():
    activation = _activation("temporal", facts=[])
    evidence = _evidence("temporal", _unknown(), _unknown())
    result, _ = _result([activation], [evidence])
    assert activation.primary_role == "not_decision_relevant"
    assert result.l4b_state == "comparable_no_context_sensitive_requirement"


def test_required_timepoint_with_unresolved_b_is_a_gap():
    activation = _activation("temporal")
    evidence = _evidence("temporal", _side("24 h"), _unknown())
    result, _ = _result([activation], [evidence])
    assert result.unresolved_required_dimensions == ["temporal"]
    assert result.l4b_state == "reviewable_required_context_gap"


def test_localization_specific_proposition_can_activate_resolved_difference():
    fact = _fact("localization", family="proposition_scope")
    activation = _activation("localization", [fact])
    evidence = _evidence("localization", _side("nucleus"), _side("cytoplasm"))
    result, _ = _result([activation], [evidence])
    assert result.l4b_state == "comparable_with_context_divergence"


def test_localization_difference_without_sensitive_proposition_is_non_relevant():
    activation = _activation("localization", [])
    evidence = _evidence("localization", _side("nucleus"), _side("cytoplasm"))
    result, _ = _result([activation], [evidence])
    assert result.l4b_state == "comparable_no_context_sensitive_requirement"


def test_population_cannot_be_invented_outside_authoritative_registry():
    with pytest.raises(ValidationError):
        PairContextTriggerFactV2(
            pair_id=PAIR,
            consumer=CONSUMER,
            dimension="population",
            trigger_family="evidence_family_scope",
            structurally_established=True,
            decision_role="comparison_required",
            trigger_evidence={"cohort": "unrelated"},
            source_contract_ref="clinical-contract",
            source_code_ref="source#cohort",
        )


def test_unrelated_control_arm_cannot_satisfy_design_requirement():
    activation = _activation("experimental_design")
    wrong_scope = _unknown(scope="insufficient", provenance=["unrelated-arm#control"])
    evidence = _evidence("experimental_design", _side("vehicle"), wrong_scope)
    result, _ = _result([activation], [evidence])
    assert evidence.dimension_state == "source_scope_insufficient_b"
    assert result.l4b_state == "blocked_source_scope"


# Anti-overfitting and layer-authority cases.
def test_all_context_present_does_not_override_upstream_alignment_block():
    dimensions = [
        "biological_model", "intervention", "temporal", "genotype",
        "localization", "measurement", "disease", "experimental_design",
    ]
    activations = [_activation(dimension, []) for dimension in dimensions]
    evidence = [_evidence(dimension, _side("same"), _side("same")) for dimension in dimensions]
    result, _ = _result(
        activations,
        evidence,
        _upstream(alignment_eligible=False, alignment_state="blocked"),
    )
    assert result.l4b_state == "blocked_upstream_alignment"
    assert result.comparable is None


def test_one_context_missing_does_not_automatically_make_pair_incomparable():
    activation = _activation("temporal", [])
    evidence = _evidence("temporal", _side("24 h"), _unknown())
    result, _ = _result([activation], [evidence])
    assert result.comparable is True


def test_context_difference_does_not_automatically_block():
    evidence = _evidence("biological_model", _side("mouse"), _side("human"))
    result, _ = _result([_activation("biological_model")], [evidence])
    assert result.comparable is True


def test_context_match_does_not_override_candidate_qualification_block():
    evidence = _evidence("genotype", _side("WT"), _side("WT"))
    result, _ = _result(
        [_activation()],
        [evidence],
        _upstream(
            candidate_qualification_eligible=False,
            candidate_qualification_state="blocked_alignment",
        ),
    )
    assert result.l4b_state == "blocked_upstream_candidate_qualification"


def test_missing_field_does_not_activate_requirement():
    activation = _activation(facts=[])
    evidence = _evidence("genotype", _unknown(), _unknown())
    assert activation.primary_role == "not_decision_relevant"
    assert satisfaction_for_pair_v2(activation, evidence).satisfaction_status == "not_applicable"


def test_unestablished_trigger_does_not_activate_requirement():
    activation = _activation(facts=[_fact(structurally_established=False)])
    assert activation.primary_role == "not_decision_relevant"
    assert activation.trigger_fact_ids == []


def test_different_resolved_satisfies_comparison_requirement():
    evidence = _evidence("genotype", _side("WT"), _side("KO"))
    row = satisfaction_for_pair_v2(_activation(), evidence)
    assert row.resolved_for_comparison is True
    assert row.satisfaction_status == "satisfied_resolved_different"


def test_ambiguous_required_context_cannot_satisfy():
    ambiguous = ContextSideValueV2(
        value_state="ambiguous",
        source_scope_adequacy="adequate",
        provenance=["source#competing-values"],
    )
    evidence = _evidence("genotype", _side("WT"), ambiguous)
    result, _ = _result([_activation()], [evidence])
    assert result.l4b_state == "blocked_required_context_ambiguous"


def test_source_scope_insufficient_required_context_cannot_satisfy():
    evidence = _evidence(
        "genotype",
        _side("WT"),
        _unknown(scope="insufficient", provenance=["truncated-source"]),
    )
    result, _ = _result([_activation()], [evidence])
    assert result.l4b_state == "blocked_source_scope"


def test_wrong_scope_inheritance_is_rejected_before_satisfaction():
    with pytest.raises(ValidationError, match="validated_scope"):
        ContextSideValueV2(
            value_state="present",
            value="WT",
            source_authority="safe_scope_inherited",
            source_scope_adequacy="adequate",
            provenance=["unrelated-experiment#genotype"],
            inheritance_scope_validated=False,
        )


def test_divergence_explanatory_role_is_not_comparison_required():
    activation = _activation(facts=[_fact(role="divergence_explanatory")])
    evidence = _evidence("genotype", _unknown(), _unknown())
    result, satisfaction = _result([activation], [evidence])
    assert activation.primary_role == "divergence_explanatory"
    assert satisfaction[0].satisfaction_status == "not_applicable"
    assert result.comparable is True


def test_comparison_required_difference_is_not_automatically_explanatory():
    activation = _activation()
    evidence = _evidence("genotype", _side("WT"), _side("KO"))
    result, _ = _result([activation], [evidence])
    assert result.l4b_state == "comparable_with_context_divergence"
    assert result.resolved_context_difference_candidates == []
    assert result.divergence_explanation_decided is False


def test_explicit_explanatory_secondary_role_emits_candidate_only_handoff():
    facts = [
        _fact(role="comparison_required"),
        _fact(role="divergence_explanatory", family="source_grounded_pair_difference"),
    ]
    activation = _activation(facts=facts)
    evidence = _evidence("genotype", _side("WT"), _side("KO"))
    result, _ = _result([activation], [evidence])
    assert activation.secondary_roles == ["divergence_explanatory"]
    assert len(result.resolved_context_difference_candidates) == 1
    handoff = result.resolved_context_difference_candidates[0]
    assert handoff.eligibility_for_divergence_explanation == "eligible_candidate_only"
    assert handoff.causal_explanation_asserted is False


def test_authorized_derived_difference_resolves_but_is_not_source_grounded_handoff():
    facts = [
        _fact(role="comparison_required"),
        _fact(role="divergence_explanatory", family="measurement_result_scope"),
    ]
    evidence = _evidence(
        "genotype",
        _side("WT", authority="authorized_deterministic_derived"),
        _side("KO", authority="authorized_deterministic_derived"),
    )
    result, _ = _result([_activation(facts=facts)], [evidence])
    assert result.l4b_state == "comparable_with_context_divergence"
    assert result.resolved_context_difference_candidates == []


def test_l4b_never_generates_formal_conflict():
    evidence = _evidence("genotype", _side("WT"), _side("KO"))
    result, _ = _result([_activation()], [evidence])
    assert result.formal_conflict_generated is False


def test_l4a_remains_descriptive_and_has_no_blocking_state():
    evidence = _evidence("genotype", _side("WT"), _unknown())
    assert l4a_descriptive_state_v1(evidence) == "unresolved"


def test_formal_cannot_invent_context_requirement_without_explicit_contract():
    with pytest.raises(ValidationError, match="explicit_formal_contract"):
        _fact(consumer="formal_judgment")


def test_l4a_cannot_activate_l4b_or_explanation_role():
    with pytest.raises(ValidationError, match="l4a_cannot_activate"):
        _fact(consumer="l4a_context_difference")


def test_claim_qualification_is_not_a_duplicate_context_engine():
    with pytest.raises(ValidationError, match="proposition_identity_contract"):
        _fact(consumer="claim_qualification")


def test_llm_output_cannot_activate_requirement():
    with pytest.raises(ValidationError):
        _fact(llm_output_used_as_trigger=True)


def test_adequate_source_not_reported_is_reviewable_gap():
    evidence = _evidence("genotype", _side("WT"), _not_reported())
    result, _ = _result([_activation()], [evidence])
    assert evidence.dimension_state == "not_reported_b"
    assert result.l4b_state == "reviewable_required_context_gap"


def test_not_reported_cannot_be_claimed_without_adequate_source_scope():
    with pytest.raises(ValidationError, match="adequately_inspected"):
        ContextSideValueV2(
            value_state="not_mentioned",
            source_scope_adequacy="insufficient",
            provenance=["truncated-source"],
        )


def test_requirement_semantics_unresolved_is_reviewable():
    fact = _fact(role_determinable=False)
    activation = _activation(facts=[fact])
    result, _ = _result([activation], [])
    assert activation.primary_role == "requirement_unresolved"
    assert result.l4b_state == "reviewable_requirement_semantics_unresolved"


@pytest.mark.parametrize(
    ("override", "expected"),
    [
        ({"entity_integrity_eligible": False}, "blocked_upstream_entity_integrity"),
        ({"alignment_eligible": False}, "blocked_upstream_alignment"),
        ({"contradiction_signal_valid": False}, "blocked_upstream_contradiction_signal"),
        (
            {"candidate_qualification_eligible": False},
            "blocked_upstream_candidate_qualification",
        ),
    ],
)
def test_upstream_preconditions_block_before_context_evaluation(override, expected):
    evidence = _evidence("genotype", _side("WT"), _side("WT"))
    result, satisfaction = _result([_activation()], [evidence], _upstream(**override))
    assert result.l4b_state == expected
    assert result.authoritative_l4b_result is False
    assert result.comparable is None
    assert result.l4a_descriptive_input_consumed is False
    assert satisfaction == []


def test_pair_identity_mismatch_cannot_evaluate_arbitrary_pair():
    with pytest.raises(ValueError, match="pair_identity_mismatch"):
        evaluate_l4b_comparability_v1(
            pair_id=PAIR,
            upstream=_upstream(pair_id="another-pair"),
            activations=[],
            dimension_evidence=[],
        )
