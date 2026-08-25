import copy

import pytest

from code_engine.context_attribution.claim_alignment.adapters import (
    align_legacy_candidate_endpoints,
)
from code_engine.context_attribution.claim_alignment.v2 import align_semantic_views
from code_engine.context_attribution.conflict_adjudication.comparability.service import (
    create_pending_factor_comparability,
)
from code_engine.context_attribution.conflict_adjudication.decision.service import (
    adjudicate_pair_staging,
)
from code_engine.context_attribution.conflict_adjudication.divergence_explanation.service import (
    create_pending_divergence_explanation,
)
from code_engine.context_attribution.conflict_candidate.contradiction_v2 import (
    build_contradiction_signal_v2,
)
from code_engine.context_attribution.conflict_candidate.qualification.service import (
    build_scientific_pair, qualify_candidate,
)
from code_engine.context_attribution.conflict_judgment.gate import (
    stage_formal_conflict_decision,
)
from code_engine.context_attribution.context_difference.adapters import (
    adapt_legacy_pair_to_context_difference,
)
from code_engine.extraction_assets.context.pair_requirements_v1 import (
    PairContextRequirementActivationV1,
    PairContextRequirementSatisfactionV1,
    PairContextTriggerFactV1,
    conditional_activation_for,
    readiness_for_pair,
    satisfaction_for_pair,
)
from code_engine.extraction_assets.scientific_entity_integrity import (
    ScientificEntityIntegrityBlocked,
    ScientificEntityIntegrityGateV1,
    ScientificEntityIntegrityStateV1,
    require_scientific_entity_integrity,
)


GATE = ScientificEntityIntegrityGateV1()


def _state(status, role="object", field="object"):
    return ScientificEntityIntegrityStateV1(
        object_id="claim-generic",
        object_type="claim",
        entity_integrity_status=status,
        affected_field=field,
        scientific_role=role,
        source_refs=["local-sidecar#row"],
    )


def _claim_decision(status="entity_integrity_valid", role="object", field="object"):
    return GATE.evaluate(
        object_id="claim-generic",
        object_type="claim",
        consumer="claim_qualification",
        entity_states=[_state(status, role, field)],
    )


def _activation(status="required_active", identity="req-1"):
    return PairContextRequirementActivationV1(
        pair_id="pair-generic",
        consumer="l4b_comparability",
        consumer_version="v1",
        dimension="genotype",
        activation_status=status,
        activation_class=status,
        trigger_state="matched" if status == "conditionally_required_active" else "unconditional",
        trigger_type="experimental_contrast",
        trigger_evidence={"factor_structure_validated": True},
        blocking_semantics="blocking_when_active",
        source_contract_ref="contract-ref",
        source_code_ref="code-ref",
        requirement_identity=identity,
    )


def _satisfaction(side_a, side_b, status=None):
    return PairContextRequirementSatisfactionV1(
        pair_id="pair-generic",
        consumer="l4b_comparability",
        dimension="genotype",
        requirement_identity="req-1",
        activation_status="required_active",
        side_a_evidence_state=side_a,
        side_b_evidence_state=side_b,
        satisfaction_status=status or satisfaction_for_pair("required_active", side_a, side_b),
    )


# ENTITY robustness cases 1-7.
def test_invalid_proposition_entity_blocks_claim():
    result = _claim_decision("entity_integrity_invalidated")
    assert result.eligibility_status == "blocked_upstream_entity_integrity"
    assert result.authoritative_for_scientific_promotion is False


def test_unresolved_proposition_entity_blocks_claim():
    result = _claim_decision("entity_integrity_unresolved")
    assert result.eligibility_status == "blocked_upstream_entity_integrity"


def test_noncritical_metadata_warning_does_not_block_claim():
    result = _claim_decision("entity_integrity_unresolved", "metadata", "source_label")
    assert result.eligibility_status == "eligible_with_historical_warning"
    assert result.authoritative_for_scientific_promotion is True
    assert result.affected_fields == ["source_label"]


def test_blocked_claim_blocks_contradiction_promotion():
    claim = _claim_decision("entity_integrity_invalidated")
    signal = GATE.evaluate(
        object_id="signal-generic", object_type="contradiction_signal",
        consumer="contradiction_signal", upstream_results=[claim],
    )
    assert signal.eligibility_status == "blocked_upstream_claim_integrity"


def test_blocked_claim_cannot_enter_alignment():
    claim = _claim_decision("entity_integrity_unresolved")
    alignment = GATE.evaluate(
        object_id="alignment-generic", object_type="claim_alignment",
        consumer="claim_alignment", upstream_results=[claim],
    )
    with pytest.raises(ScientificEntityIntegrityBlocked):
        require_scientific_entity_integrity("claim_alignment", [alignment])


def test_blocked_signal_cannot_enter_candidate_qualification():
    claim = _claim_decision("entity_integrity_invalidated")
    signal = GATE.evaluate(
        object_id="signal-generic", object_type="contradiction_signal",
        consumer="contradiction_signal", upstream_results=[claim],
    )
    candidate = GATE.evaluate(
        object_id="candidate-generic", object_type="bridge_candidate",
        consumer="candidate_qualification", upstream_results=[signal],
    )
    with pytest.raises(ScientificEntityIntegrityBlocked):
        require_scientific_entity_integrity("candidate_qualification", [candidate])


def test_historical_state_unchanged_and_visible_after_gate():
    historical = {"canonical_entity": "historical-value", "invalid": True}
    before = copy.deepcopy(historical)
    result = _claim_decision("entity_integrity_invalidated")
    assert historical == before
    assert result.historical_invalid_state_visible is True
    assert result.historical_object_modified is False


def test_corrupted_claim_cannot_build_scientific_bridge_pair():
    blocked = _claim_decision("entity_integrity_unresolved")
    with pytest.raises(ScientificEntityIntegrityBlocked):
        build_scientific_pair(
            claim_a="claim-a", claim_b="claim-b", core_a="core-a", core_b="core-b",
            signal_type="opposite_direction", contract_identity="contract",
            entity_integrity_decisions=[blocked],
        )


def test_valid_claim_continues_normally():
    valid = _claim_decision()
    pair = build_scientific_pair(
        claim_a="claim-a", claim_b="claim-b", core_a="core-a", core_b="core-b",
        signal_type="opposite_direction", contract_identity="contract",
        entity_integrity_decisions=[valid],
    )
    assert pair.endpoint_claim_identity_a == "claim-a"


@pytest.mark.parametrize("consumer_call", [
    lambda blocked: align_legacy_candidate_endpoints(
        {}, candidate=None, entity_integrity_decisions=[blocked]
    ),
    lambda blocked: align_semantic_views(
        observation_a_id="a", observation_b_id="b", core_a=None, core_b=None,
        bridges=[], legacy_identity="legacy", role_taxonomy_identity="roles",
        entity_integrity_decisions=[blocked],
    ),
    lambda blocked: build_contradiction_signal_v2(
        alignment=None, result_a=None, result_b=None, historical_candidate=False,
        entity_integrity_decisions=[blocked],
    ),
    lambda blocked: qualify_candidate(
        candidate={}, alignment={}, signal={}, pair=None, contract_identity="contract",
        generation_policy_identity="policy", entity_integrity_decisions=[blocked],
    ),
    lambda blocked: adapt_legacy_pair_to_context_difference(
        {}, candidate=None, context_a=None, context_b=None,
        factor_registry_identity="registry", legacy_prompt_identity=None,
        entity_integrity_decisions=[blocked],
    ),
    lambda blocked: create_pending_factor_comparability(
        difference=None, difference_binding=None, factor_id="factor",
        entity_integrity_decisions=[blocked],
    ),
    lambda blocked: create_pending_divergence_explanation(
        difference=None, difference_binding=None, signal=None, factor_id="factor",
        entity_integrity_decisions=[blocked],
    ),
    lambda blocked: adjudicate_pair_staging(
        alignment=None, signal=None, candidate=None, difference=None,
        difference_binding=None, bundle=None, comparability=[], explanations=[],
        entity_integrity_decisions=[blocked],
    ),
    lambda blocked: stage_formal_conflict_decision(
        candidate=None, difference=None, comparability=None,
        entity_integrity_decisions=[blocked],
    ),
])
def test_every_production_consumer_rejects_before_materialization(consumer_call):
    blocked = _claim_decision("entity_integrity_invalidated")
    with pytest.raises(ScientificEntityIntegrityBlocked):
        consumer_call(blocked)


# PAIR CONTEXT robustness cases 8-20.
def test_no_requirement_contract_is_neither_ready_nor_blocked():
    status = readiness_for_pair([], [])
    assert status == "reviewable_no_requirement_contract"
    assert not status.startswith(("ready_", "blocked_"))


def test_condition_trigger_activates_matching_requirement():
    fact = PairContextTriggerFactV1(
        pair_id="pair-generic", dimension="genotype",
        trigger_type="experimental_contrast", structurally_established=True,
        trigger_evidence={"validated_factor": "genotype"},
        source_contract_ref="contrast-contract", source_code_ref="contrast-code",
    )
    assert conditional_activation_for(dimension="genotype", trigger_facts=[fact]) == (
        "conditionally_required_active", "matched", "experimental_contrast"
    )


def test_absent_or_unestablished_trigger_does_not_activate():
    fact = PairContextTriggerFactV1(
        pair_id="pair-generic", dimension="temporal",
        trigger_type="proposition_scope", structurally_established=False,
        trigger_evidence={}, source_contract_ref="contract", source_code_ref="code",
    )
    assert conditional_activation_for(dimension="temporal", trigger_facts=[fact]) == (
        "not_activated", "not_matched", None
    )


@pytest.mark.parametrize("side_b", ["direct", "safe_inherited", "derived_authorized"])
def test_authorized_value_states_satisfy(side_b):
    assert satisfaction_for_pair("required_active", "direct", side_b) == "satisfied"


def test_wrong_scope_inheritance_cannot_satisfy():
    row = _satisfaction("direct", "source_scope_insufficient")
    assert row.satisfaction_status == "partially_satisfied"
    assert readiness_for_pair([_activation()], [row]) == "blocked_source_scope"


@pytest.mark.parametrize("state,expected", [
    ("unresolved", "blocked_required_context_missing"),
    ("ambiguous", "blocked_required_context_ambiguous"),
])
def test_unresolved_or_ambiguous_required_dimension_does_not_satisfy(state, expected):
    row = _satisfaction(state, state)
    assert row.satisfaction_status == "unsatisfied"
    assert readiness_for_pair([_activation()], [row]) == expected


def test_nonrequired_missing_dimension_does_not_block():
    assert readiness_for_pair([_activation("not_required_explicit")], []) == "not_context_sensitive"


def test_context_difference_does_not_automatically_activate_requirement():
    assert conditional_activation_for(dimension="localization", trigger_facts=[]) == (
        "not_activated", "not_matched", None
    )


def test_requirement_does_not_imply_difference():
    matched_values = _satisfaction("direct", "direct")
    assert matched_values.satisfaction_status == "satisfied"
    assert readiness_for_pair([_activation()], [matched_values]) == (
        "ready_all_active_requirements_satisfied"
    )


def test_formal_consumer_does_not_invent_requirements_without_trigger():
    assert conditional_activation_for(dimension="experimental_design", trigger_facts=[]) == (
        "not_activated", "not_matched", None
    )


def test_legacy_derived_state_is_not_authorized_to_satisfy():
    assert satisfaction_for_pair("required_active", "direct", "derived") == "partially_satisfied"
