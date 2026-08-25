from pathlib import Path

from code_engine.extraction_assets.context.pair_requirements_v2 import (
    L4bUpstreamEligibilityV1,
)
from code_engine.extraction_assets.context.pair_requirements_v3_candidate import (
    CONTEXT_DIMENSIONS,
    PairContextDimensionEvidenceV3Candidate,
    activate_pair_dimension_v3_candidate,
    audit_trigger_coverage_v1,
    evaluate_l4b_v3_candidate,
    make_projection_gap_v1,
    make_requirement_authority_v1,
    make_trigger_fact_v1,
    satisfaction_for_pair_v3_candidate,
    stable_v3,
)


PAIR = "generic-pair"
CONSUMER = "l4b_comparability"


def _fact(dimension="measurement", state="different"):
    values_a = ["assay-a"]
    values_b = ["assay-b"] if state == "different" else ["assay-a"]
    return make_trigger_fact_v1(
        pair_id=PAIR,
        dimension=dimension,
        fact_type="measurement_scope",
        side_a_object_refs=["measurement-a"],
        side_b_object_refs=["measurement-b"],
        source_artifact_refs=["structured-core.jsonl"],
        fact_state=state,
        authority="validated_experimental_core",
        trigger_eligible=True,
        trigger_type="comparison_required",
        structured_values_a=values_a,
        structured_values_b=values_b,
        reason="validated linked measurement scopes require resolution",
    )


def _authority(dimension, state):
    return make_requirement_authority_v1(
        pair_id=PAIR,
        consumer=CONSUMER,
        dimension=dimension,
        authority_state=state,
        authority=(
            "explicit_consumer_contract"
            if state == "explicit_not_decision_relevant"
            else "structural_inapplicability_rule"
        ),
        contract_refs=["generic-consumer-contract-v1"],
        reason="affirmative generic contract authority",
    )


def _activation(dimension="measurement", facts=(), authorities=()):
    return activate_pair_dimension_v3_candidate(
        pair_id=PAIR,
        consumer=CONSUMER,
        dimension=dimension,
        trigger_facts=list(facts),
        requirement_authorities=list(authorities),
    )


def _evidence(fact):
    payload = {
        "pair_id": PAIR,
        "dimension": fact.dimension,
        "dimension_state": fact.fact_state,
        "value_a": fact.structured_values_a,
        "value_b": fact.structured_values_b,
        "side_a_object_refs": fact.side_a_object_refs,
        "side_b_object_refs": fact.side_b_object_refs,
        "authority": [fact.authority],
        "authoritative_two_sided_support": True,
    }
    return PairContextDimensionEvidenceV3Candidate(
        **payload,
        evidence_identity=stable_v3("generic_evidence", payload),
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


def _complete_activations(overrides=None):
    overrides = overrides or {}
    return [
        overrides.get(
            dimension,
            _activation(
                dimension,
                authorities=[_authority(dimension, "not_applicable")],
            ),
        )
        for dimension in CONTEXT_DIMENSIONS
    ]


def test_absence_of_trigger_evidence_defaults_to_requirement_unresolved():
    activation = _activation()
    assert activation.activation_state == "requirement_unresolved"
    assert activation.reason == "absence_of_trigger_evidence_defaults_to_requirement_unresolved"


def test_absence_of_trigger_evidence_is_not_explicit_irrelevance():
    activation = _activation()
    assert activation.activation_state != "explicit_not_decision_relevant"
    assert activation.authority_refs == []


def test_explicit_irrelevant_contract_is_affirmative_and_nonblocking():
    authority = _authority("measurement", "explicit_not_decision_relevant")
    activation = _activation(authorities=[authority])
    assert activation.activation_state == "explicit_not_decision_relevant"
    assert activation.authority_refs == [authority.authority_id]
    assert activation.blocking_semantics == "affirmatively_nonblocking"


def test_structurally_inapplicable_dimension_requires_authority():
    authority = _authority("measurement", "not_applicable")
    activation = _activation(authorities=[authority])
    coverage = audit_trigger_coverage_v1(
        pair_id=PAIR,
        dimension="measurement",
        facts=[],
        authorities=[authority],
    )
    assert activation.activation_state == "not_applicable"
    assert coverage.coverage_state == "not_applicable_with_authority"


def test_supported_upstream_structured_fact_can_generate_trigger():
    fact = _fact()
    activation = _activation(facts=[fact])
    coverage = audit_trigger_coverage_v1(
        pair_id=PAIR,
        dimension="measurement",
        facts=[fact],
    )
    assert activation.activation_state == "comparison_required"
    assert activation.trigger_fact_ids == [fact.trigger_fact_id]
    assert coverage.coverage_state == "fully_materialized"


def test_upstream_fact_without_adapter_is_detected_as_engineering_gap():
    coverage = audit_trigger_coverage_v1(
        pair_id=PAIR,
        dimension="measurement",
        facts=[],
        upstream_object_refs=["validated-core#measurement"],
    )
    gap = make_projection_gap_v1(
        pair_id=PAIR,
        dimension="measurement",
        upstream_object="validated-core#measurement",
        available_fact="validated measurement scope",
        missing_adapter_or_projection="measurement-to-trigger adapter absent",
        downstream_requirement_consumer=CONSUMER,
        resolved_in_v3_candidate_sidecar=False,
    )
    assert coverage.coverage_state == "present_upstream_but_not_materialized"
    assert gap.upstream_object == "validated-core#measurement"


def test_missing_context_does_not_activate_requirement():
    activation = _activation(facts=[])
    satisfaction = satisfaction_for_pair_v3_candidate(activation, None)
    assert activation.activation_state == "requirement_unresolved"
    assert satisfaction.satisfaction_status == "not_evaluated_not_activated"


def test_resolved_difference_satisfies_comparison_required():
    fact = _fact(state="different")
    activation = _activation(facts=[fact])
    satisfaction = satisfaction_for_pair_v3_candidate(activation, _evidence(fact))
    assert satisfaction.resolved_for_comparison is True
    assert satisfaction.satisfaction_status == "satisfied_resolved_different"


def test_requirement_unresolved_cannot_produce_no_requirement_comparability():
    unresolved = _activation("measurement")
    result, _ = evaluate_l4b_v3_candidate(
        pair_id=PAIR,
        upstream=_upstream(),
        activations=_complete_activations({"measurement": unresolved}),
        dimension_evidence=[],
    )
    assert result.l4b_state == "reviewable_requirement_semantics_unresolved"
    assert result.comparable is None


def test_all_dimensions_affirmatively_irrelevant_or_inapplicable_may_be_no_requirement():
    activations = []
    for index, dimension in enumerate(CONTEXT_DIMENSIONS):
        state = "explicit_not_decision_relevant" if index % 2 else "not_applicable"
        activations.append(_activation(
            dimension,
            authorities=[_authority(dimension, state)],
        ))
    result, _ = evaluate_l4b_v3_candidate(
        pair_id=PAIR,
        upstream=_upstream(),
        activations=activations,
        dimension_evidence=[],
    )
    assert result.l4b_state == "comparable_no_context_sensitive_requirement"
    assert result.comparable is True


def test_historical_weak_ids_are_not_used_in_production_logic():
    root = Path(__file__).resolve().parents[1]
    text = (
        root / "src/code_engine/extraction_assets/context/pair_requirements_v3_candidate.py"
    ).read_text(encoding="utf-8")
    assert "weak-3ca" not in text
    assert "weak-256" not in text


def test_entity_integrity_gate_remains_upstream_of_requirement_semantics():
    result, satisfaction = evaluate_l4b_v3_candidate(
        pair_id=PAIR,
        upstream=_upstream(
            entity_integrity_eligible=False,
            entity_integrity_state="blocked_claim_entity_integrity",
        ),
        activations=_complete_activations({"measurement": _activation("measurement")}),
        dimension_evidence=[],
    )
    assert result.l4b_state == "blocked_upstream_entity_integrity"
    assert result.authoritative_l4b_result is False
    assert all(row.satisfaction_status == "not_evaluated_upstream_blocked" for row in satisfaction)
