from pathlib import Path

import pytest
from pydantic import ValidationError

from code_engine.extraction_assets.context.pair_requirements_v2 import (
    L4bUpstreamEligibilityV1,
)
from code_engine.extraction_assets.context.pair_requirements_v3_candidate import (
    PairSemanticTriggerCoverageV1,
    make_trigger_fact_v1,
    stable_v3,
)
from code_engine.extraction_assets.context.pair_scientific_compatibility_v1_candidate import (
    evaluate_l4b_v4_candidate,
    evaluate_scientific_dimension_satisfaction_v1,
    make_semantic_role_inventory_v1,
    project_pair_semantic_trigger_v1,
)


PAIR = "generic-scientific-pair"


def _inventory(
    name="genotype",
    role="context_explanatory",
    state="different",
    values_a=None,
    values_b=None,
    authority_status="supported",
):
    policies = {
        "proposition_alignment_critical": "upstream_alignment_required",
        "comparison_compatibility_critical": "compatibility_required",
        "context_explanatory": "resolution_only",
        "explicitly_not_decision_relevant": "not_decision_relevant",
        "semantic_role_unresolved": "semantic_role_unresolved",
    }
    return make_semantic_role_inventory_v1(
        pair_id=PAIR,
        dimension_or_semantic=name,
        scientific_role=role,
        satisfaction_policy=policies[role],
        authority="generic-versioned-contract-v1",
        authority_status=authority_status,
        source_refs=["generic-structured-source.jsonl"],
        structured_values_a=values_a if values_a is not None else ["WT"],
        structured_values_b=values_b if values_b is not None else ["KO"],
        semantic_state=state,
        reason="generic deterministic test role",
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


def _coverage(dimension="genotype", state="present_upstream_but_not_materialized"):
    payload = {
        "pair_id": PAIR,
        "dimension": dimension,
        "coverage_state": state,
        "trigger_fact_ids": [],
        "upstream_object_refs": ["validated-core#generic"],
        "authority_refs": [],
        "reason": "structured fact has no projection",
    }
    return PairSemanticTriggerCoverageV1(
        **payload,
        coverage_id=stable_v3("generic_coverage", payload),
    )


def _context_fact(dimension="genotype", state="different"):
    return make_trigger_fact_v1(
        pair_id=PAIR,
        dimension=dimension,
        fact_type="genotype_scope",
        side_a_object_refs=["context-a"],
        side_b_object_refs=["context-b"],
        source_artifact_refs=["validated-context.jsonl"],
        fact_state=state,
        authority="validated_context_direct_value",
        trigger_eligible=False,
        structured_values_a=["WT"],
        structured_values_b=["KO" if state == "different" else "WT"],
        reason="validated two-sided explanatory Context",
    )


def test_explanatory_wt_vs_ko_may_remain_comparable():
    satisfaction = evaluate_scientific_dimension_satisfaction_v1(_inventory())
    result = evaluate_l4b_v4_candidate(
        pair_id=PAIR,
        upstream=_upstream(),
        upstream_alignment_compatibility_outcome="upstream_alignment_supported",
        satisfactions=[satisfaction],
    )
    assert satisfaction.satisfaction_state == "satisfied_resolved_different"
    assert result.l4b_state == "comparable_with_context_divergence"
    assert result.comparable is True


def test_explanatory_matched_context_may_remain_comparable():
    satisfaction = evaluate_scientific_dimension_satisfaction_v1(
        _inventory(state="matched", values_b=["WT"])
    )
    result = evaluate_l4b_v4_candidate(
        pair_id=PAIR,
        upstream=_upstream(),
        upstream_alignment_compatibility_outcome="upstream_alignment_supported",
        satisfactions=[satisfaction],
    )
    assert satisfaction.satisfaction_state == "satisfied_resolved_matched"
    assert result.l4b_state == "comparable_all_required_context_resolved"


def test_measurement_target_mismatch_is_not_satisfied_merely_by_resolution():
    item = _inventory(
        name="measurement_target_identity",
        role="proposition_alignment_critical",
        state="different",
        values_a=["target-a"],
        values_b=["target-b"],
    )
    satisfaction = evaluate_scientific_dimension_satisfaction_v1(item)
    assert satisfaction.satisfied is False
    assert satisfaction.satisfaction_state == "unsatisfied_upstream_alignment_unresolved"


def test_incompatible_endpoint_semantics_cannot_use_resolution_only_policy():
    with pytest.raises(ValidationError, match="scientific_role_policy_mismatch"):
        make_semantic_role_inventory_v1(
            pair_id=PAIR,
            dimension_or_semantic="measurement_endpoint_type",
            scientific_role="proposition_alignment_critical",
            satisfaction_policy="resolution_only",
            authority="generic",
            authority_status="supported",
            source_refs=["core.jsonl"],
            structured_values_a=["endpoint-a"],
            structured_values_b=["endpoint-b"],
            semantic_state="different",
            reason="invalid policy routing",
        )


def test_proposition_critical_unresolved_semantic_returns_upstream_review():
    item = _inventory(
        name="result_semantic_level",
        role="proposition_alignment_critical",
        state="alignment_semantic_coverage_gap",
        authority_status="alignment_semantic_coverage_gap",
    )
    satisfaction = evaluate_scientific_dimension_satisfaction_v1(item)
    result = evaluate_l4b_v4_candidate(
        pair_id=PAIR,
        upstream=_upstream(),
        upstream_alignment_compatibility_outcome="alignment_semantic_coverage_gap",
        satisfactions=[satisfaction],
    )
    assert result.l4b_state == "reviewable_scientific_compatibility_unresolved"
    assert result.comparable is None


def test_l4b_does_not_re_adjudicate_claim_alignment():
    resolved_context = evaluate_scientific_dimension_satisfaction_v1(_inventory())
    result = evaluate_l4b_v4_candidate(
        pair_id=PAIR,
        upstream=_upstream(),
        upstream_alignment_compatibility_outcome="alignment_semantic_coverage_gap",
        satisfactions=[resolved_context],
    )
    assert result.upstream_alignment_re_adjudicated is False
    assert result.l4b_state == "reviewable_scientific_compatibility_unresolved"


def test_validated_alignment_compatibility_can_be_consumed_by_l4b():
    item = _inventory(
        name="canonical_endpoint_identity",
        role="proposition_alignment_critical",
        state="upstream_alignment_supported",
        values_a=["endpoint"],
        values_b=["endpoint"],
    )
    satisfaction = evaluate_scientific_dimension_satisfaction_v1(item)
    result = evaluate_l4b_v4_candidate(
        pair_id=PAIR,
        upstream=_upstream(),
        upstream_alignment_compatibility_outcome="upstream_alignment_supported",
        satisfactions=[satisfaction],
    )
    assert satisfaction.satisfaction_state == "satisfied_upstream_alignment"
    assert result.l4b_state == "comparable_all_required_context_resolved"


def test_upstream_structured_fact_missing_from_projection_is_detected():
    projection = project_pair_semantic_trigger_v1(
        coverage=_coverage(),
        inventory=_inventory(state="missing", values_a=[], values_b=[]),
        facts=[],
    )
    assert projection.gap_resolution_state == "cannot_project_missing_structured_authority"
    assert projection.after_projection_state == "not_materialized"


def test_deterministic_adapter_repairs_without_free_text_inference():
    fact = _context_fact()
    projection = project_pair_semantic_trigger_v1(
        coverage=_coverage(),
        inventory=_inventory(),
        facts=[fact],
    )
    assert projection.gap_resolution_state == "repaired_by_deterministic_projection"
    assert projection.projected_fact_state == "different"
    assert projection.source_fact_ids == [fact.trigger_fact_id]
    assert projection.free_text_inference_used is False
    assert projection.fuzzy_scientific_inference_used is False
    assert projection.llm_used is False


def test_missing_fact_cannot_manufacture_compatibility():
    item = _inventory(
        name="measurement_method",
        role="comparison_compatibility_critical",
        state="different",
        values_a=["assay-a"],
        values_b=["assay-b"],
    )
    satisfaction = evaluate_scientific_dimension_satisfaction_v1(item)
    assert satisfaction.satisfied is False
    assert satisfaction.satisfaction_state == "unsatisfied_compatibility_unresolved"
    assert satisfaction.compatibility_authority_refs == []


def test_context_difference_is_not_scientific_incompatibility():
    satisfaction = evaluate_scientific_dimension_satisfaction_v1(_inventory())
    assert satisfaction.satisfied is True
    assert satisfaction.satisfaction_state != "blocked_scientific_incompatibility"


def test_scientific_incompatibility_is_not_formal_conflict():
    item = _inventory(
        name="evidence_family",
        role="comparison_compatibility_critical",
        state="incompatible",
        values_a=["descriptive"],
        values_b=["interventional"],
    )
    satisfaction = evaluate_scientific_dimension_satisfaction_v1(
        item, compatibility_authority_refs=["versioned-incompatibility-policy-v1"]
    )
    result = evaluate_l4b_v4_candidate(
        pair_id=PAIR,
        upstream=_upstream(),
        upstream_alignment_compatibility_outcome="upstream_alignment_supported",
        satisfactions=[satisfaction],
    )
    assert result.l4b_state == "blocked_scientific_incompatibility"
    assert result.formal_conflict_generated is False


def test_no_historical_pair_id_hardcoding_in_candidate_module():
    root = Path(__file__).resolve().parents[1]
    text = (
        root
        / "src/code_engine/extraction_assets/context/pair_scientific_compatibility_v1_candidate.py"
    ).read_text(encoding="utf-8")
    assert "weak-3ca" not in text
    assert "weak-256" not in text
    assert "f389" not in text


def test_entity_gate_remains_upstream():
    result = evaluate_l4b_v4_candidate(
        pair_id=PAIR,
        upstream=_upstream(
            entity_integrity_eligible=False,
            entity_integrity_state="blocked_claim_entity_integrity",
        ),
        upstream_alignment_compatibility_outcome="upstream_alignment_supported",
        satisfactions=[],
    )
    assert result.l4b_state == "blocked_upstream_entity_integrity"
    assert result.authoritative_l4b_result is False
