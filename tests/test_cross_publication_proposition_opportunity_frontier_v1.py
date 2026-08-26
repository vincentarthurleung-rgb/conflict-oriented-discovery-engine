import json
from pathlib import Path

from code_engine.context_attribution.conflict_candidate.cross_publication_frontier_v1_candidate import (
    PROPOSITION_CRITICAL_DIMENSIONS,
    PartialDimensionV1,
    PartialScientificPropositionSignatureV1,
    compare_cross_publication_envelope_v1,
)


ROOT = Path(__file__).resolve().parents[1]
ART = ROOT / "runs/20260826_cross_publication_proposition_opportunity_frontier_v1_offline/artifacts"


def signature(name, publication, *, experiment=None, unresolved=(), changes=None, spans=()):
    values = {
        "entity_proposition": "Entrez:1", "relation_family": "interventional_effect",
        "object_target": "Entrez:2", "measurement_target": ["Entrez:2"],
        "measurement_property": ["abundance"],
        "result_semantic_level": ["abundance:qualitative_result"],
        "intervention_proposition": {"target": "Entrez:1", "operation": "perturbation"},
        "causal_evidential_mode": "interventional_effect", "contrast_role": "experimental_vs_reference",
        "granularity_qualifiers": None,
    }
    values.update(changes or {})
    dimensions = {}
    for field, value in values.items():
        dimensions[field] = PartialDimensionV1(
            state="unresolved" if field in unresolved else "resolved",
            value=None if field in unresolved else value,
            authority="test",
        )
    return PartialScientificPropositionSignatureV1(
        observation_id=name, publication_id=publication,
        experiment_id=experiment or f"experiment:{name}", evidence_span_ids=list(spans),
        profile="interventional_effect", entity_integrity_permits_comparison=True,
        dimensions=dimensions,
    )


def test_same_publication_pair_cannot_be_cross_publication_opportunity():
    result = compare_cross_publication_envelope_v1(
        signature("a", "pmid:1", unresolved=("measurement_property",)),
        signature("b", "pmid:1"),
    )
    assert result.envelope_state == "blocked_same_publication"
    assert not result.source_independent


def test_duplicate_experiment_cannot_be_independent_opportunity():
    result = compare_cross_publication_envelope_v1(
        signature("a", "pmid:1", experiment="exp:1"),
        signature("b", "pmid:2", experiment="exp:1"),
    )
    assert result.envelope_state == "blocked_duplicate_or_same_experiment"


def test_shared_evidence_span_cannot_be_independent_opportunity():
    result = compare_cross_publication_envelope_v1(
        signature("a", "pmid:1", spans=("span:1",)),
        signature("b", "pmid:2", spans=("span:1",)),
    )
    assert result.envelope_state == "blocked_duplicate_or_same_experiment"


def test_resolved_proposition_mismatch_blocks_envelope():
    result = compare_cross_publication_envelope_v1(
        signature("a", "pmid:1"), signature("b", "pmid:2", changes={"object_target": "Entrez:9"})
    )
    assert result.envelope_state == "blocked_resolved_proposition_mismatch"
    assert "object_target" in result.resolved_mismatches


def test_one_unresolved_field_creates_single_gap_opportunity():
    result = compare_cross_publication_envelope_v1(
        signature("a", "pmid:1", unresolved=("measurement_property",)), signature("b", "pmid:2")
    )
    assert result.envelope_state == "potential_match_if_single_gap_resolved"
    assert result.unresolved_gap_count == 1


def test_two_unresolved_fields_create_multi_gap_not_single_gap():
    result = compare_cross_publication_envelope_v1(
        signature("a", "pmid:1", unresolved=("measurement_property", "result_semantic_level")),
        signature("b", "pmid:2"),
    )
    assert result.envelope_state == "potential_match_if_multiple_gaps_resolved"
    assert result.unresolved_gap_count == 2


def test_unresolved_is_never_treated_as_already_compatible():
    result = compare_cross_publication_envelope_v1(
        signature("a", "pmid:1", unresolved=("measurement_target",)), signature("b", "pmid:2")
    )
    assert result.envelope_state != "cross_publication_match_already_supported"
    assert "measurement_target" not in result.resolved_compatible_dimensions


def test_assay_difference_alone_does_not_block_proposition():
    left = signature("a", "pmid:1")
    right = signature("b", "pmid:2")
    assert "assay_method" not in PROPOSITION_CRITICAL_DIMENSIONS
    assert compare_cross_publication_envelope_v1(left, right).envelope_state == "cross_publication_match_already_supported"


def test_different_measurement_target_blocks_compatibility():
    result = compare_cross_publication_envelope_v1(
        signature("a", "pmid:1"),
        signature("b", "pmid:2", changes={"measurement_target": ["Entrez:8"]}),
    )
    assert result.envelope_state == "blocked_resolved_proposition_mismatch"
    assert "measurement_target" in result.resolved_mismatches


def test_result_direction_is_not_part_of_partial_signature_identity():
    assert "direction" not in PROPOSITION_CRITICAL_DIMENSIONS
    assert "polarity" not in PROPOSITION_CRITICAL_DIMENSIONS


def test_profile_or_causal_mismatch_blocks():
    right = signature("b", "pmid:2", changes={"causal_evidential_mode": "observational_association"})
    result = compare_cross_publication_envelope_v1(signature("a", "pmid:1"), right)
    assert result.envelope_state == "blocked_profile_or_causal_mode"


def test_unresolved_publication_cannot_establish_independence():
    result = compare_cross_publication_envelope_v1(signature("a", None), signature("b", "pmid:2"))
    assert result.envelope_state == "insufficient_shared_authority"
    assert not result.source_independent


def test_human_review_priority_contains_no_answer_or_preference():
    path = ART / "frontier_human_review_priority.jsonl"
    if not path.exists(): return
    rows = [json.loads(line) for line in path.read_text().splitlines()]
    assert all(row["answer_suggestion"] is None for row in rows)
    assert all(row["preferred_answer"] is None for row in rows)
    assert all(row["review_answered"] is False for row in rows)


def test_reviewable_without_cross_publication_partner_is_not_high_value():
    path = ART / "reviewable_value_of_resolution_triage.jsonl"
    if not path.exists(): return
    rows = [json.loads(line) for line in path.read_text().splitlines()]
    assert all(
        not row["primary_triage_state"].startswith("high_value_")
        for row in rows if not row["cross_publication_partner_ids"]
    )


def test_existing_ready_blocks_are_all_audited_for_extension():
    path = ART / "existing_proposition_block_extension_audit.json"
    if not path.exists(): return
    audit = json.loads(path.read_text())
    assert audit["current_block_count"] == 4
    assert len(audit["blocks"]) == 4
    assert all("cross_publication_extension_possible" in row for row in audit["blocks"])


def test_no_candidate_l4_formal_or_network_execution():
    path = ART / "scientific_state_safety_audit.json"
    if not path.exists(): return
    safety = json.loads(path.read_text())
    leakage = json.loads((ART / "production_leakage_audit.json").read_text())
    assert safety["candidate_generation_executed"] is False
    assert safety["contradiction_evaluated"] is False
    assert safety["l4_executed"] is False
    assert safety["formal_conflict_count_after"] == 0
    assert safety["provider_calls"] == safety["network_calls"] == safety["llm_calls"] == 0
    assert leakage["hardcoded_frontier_ids"] == []


def test_completed_run_preserves_historical_integrity_and_pi3k_states():
    path = ART / "scientific_state_safety_audit.json"
    if not path.exists(): return
    safety = json.loads(path.read_text())
    assert safety["historical_assets_modified"] is False
    assert safety["entity_integrity_claims_blocked"] == 241
    assert safety["entity_integrity_signals_blocked"] == 2
    assert safety["pi3k"]["signal_40f_state"] == "historically_blocked"
    assert safety["pi3k"]["f389_state"] == "manual_scientific_review"
