import hashlib
import json
from pathlib import Path

import pytest

from code_engine.context_attribution.claim_alignment.scientific_proposition_v1_candidate import (
    CausalEvidentialModeV1,
    ExperimentalContrastSemanticsV1,
    InterventionPropositionV1,
    StructuredSemanticValueV1,
    make_scientific_proposition_signature_v1,
)
from code_engine.context_attribution.conflict_candidate.scientific_regeneration_v1_candidate import (
    DiagnosticFulltextPairV1,
    FulltextScientificObservationV1,
    ScientificConflictCandidateV2Candidate,
    assess_source_independence_v1,
    diagnostic_pair_to_candidate_v2,
    generate_bounded_diagnostic_pairs_v1,
)


def _value(value, identity=None, family=None, authority=None):
    return StructuredSemanticValueV1(
        value=value,
        canonical_identity=identity,
        semantic_family=family,
        authority_state=authority or (
            "validated_canonical" if identity is not None else "structured_only"
        ),
        source_refs=["generic-authority"],
    )


def _signature(
    observation_id,
    *,
    subject="entity:subject",
    relation="effect:regulation",
    object_target="entity:object",
    measurement_target="measurement:target",
    endpoint="endpoint:abundance",
    property_family="abundance",
    result_family="abundance:qualitative_result",
    assay="assay:a",
    intervention_target="entity:subject",
):
    result_identity = None if result_family is None else f"result:{result_family}"
    return make_scientific_proposition_signature_v1(
        observation_id=observation_id,
        subject_identity=subject,
        relation_effect_family=relation,
        object_target_identity=object_target,
        measurement_targets=[_value("target", measurement_target)],
        measured_properties=[
            _value("endpoint", endpoint, property_family)
        ],
        assay_methods=[_value("assay", assay)],
        result_semantics=[
            _value(
                result_family or "unknown",
                result_identity,
                result_family,
                "controlled_vocabulary" if result_family else "structured_only",
            )
        ],
        intervention_proposition=InterventionPropositionV1(
            intervention_mode="single",
            factor_families=["genetic_perturbation"],
            target_values=[_value("subject", intervention_target)],
            authority_state="resolved" if intervention_target else "unresolved",
        ),
        causal_evidential_mode=CausalEvidentialModeV1(
            observation_type="interventional_experiment",
            mode_family="interventional_effect",
            authority_state="resolved",
        ),
        experimental_contrast=ExperimentalContrastSemanticsV1(
            contrast_role="experimental_vs_reference",
            comparison_link_count=1,
            authority_state="resolved",
        ),
        source_refs=["generic-validated-core"],
    )


def _observation(
    observation_id,
    *,
    publication="publication:a",
    source_document=None,
    experiment=None,
    spans=None,
    text_hashes=None,
    direction="positive",
    entity_state="eligible",
    signature=None,
):
    return FulltextScientificObservationV1(
        observation_id=observation_id,
        publication_id=publication,
        source_document_id=source_document or f"source:{publication}",
        experiment_id=experiment or f"experiment:{observation_id}",
        evidence_span_ids=spans or [f"span:{observation_id}"],
        evidence_text_hashes=text_hashes or [f"hash:{observation_id}"],
        validation_state="validated",
        statement_role="current_study_experiment",
        entity_integrity_state=entity_state,
        provenance_complete=True,
        direction=direction,
        signature=signature or _signature(observation_id),
    )


def _pair(left, right):
    blocks, pairs, collapsed = generate_bounded_diagnostic_pairs_v1([left, right])
    return blocks, pairs, collapsed


def test_proposition_compatible_opposite_result_pair_survives_lane_b():
    _, pairs, _ = _pair(
        _observation("a", publication="publication:a", direction="positive"),
        _observation("b", publication="publication:b", direction="negative"),
    )
    assert len(pairs) == 1
    assert pairs[0].diagnostic_conflict_opportunity_state == "diagnostic_candidate_strong"
    assert pairs[0].direction_result_relation == "opposed"
    assert diagnostic_pair_to_candidate_v2(pairs[0]).qualification_state == "diagnostic_only_strong"


def test_same_topic_but_different_canonical_target_does_not_pair():
    left = _observation("a", signature=_signature("a", object_target="entity:target-a"))
    right = _observation(
        "b",
        publication="publication:b",
        direction="negative",
        signature=_signature("b", object_target="entity:target-b"),
    )
    _, pairs, _ = _pair(left, right)
    assert pairs == []


def test_same_target_but_incompatible_endpoint_does_not_survive():
    left = _observation("a", signature=_signature("a", endpoint="endpoint:a"))
    right = _observation(
        "b",
        publication="publication:b",
        direction="negative",
        signature=_signature("b", endpoint="endpoint:b"),
    )
    _, pairs, _ = _pair(left, right)
    assert len(pairs) == 1
    assert pairs[0].diagnostic_conflict_opportunity_state == "blocked_proposition_incompatibility"


def test_different_assay_alone_does_not_block():
    left = _observation("a", signature=_signature("a", assay="assay:a"))
    right = _observation(
        "b",
        publication="publication:b",
        direction="negative",
        signature=_signature("b", assay="assay:b"),
    )
    _, pairs, _ = _pair(left, right)
    assert pairs[0].diagnostic_conflict_opportunity_state == "diagnostic_candidate_strong"
    assert pairs[0].measurement_compatibility == "compatible_with_granularity_qualification"


def test_context_only_genotype_difference_does_not_change_grouping():
    left = _observation("a")
    right = _observation("b", publication="publication:b", direction="negative")
    assert next(
        row.semantic_role for row in left.signature.semantic_roles if row.dimension_id == "genotype"
    ) == "context_only"
    blocks, pairs, _ = _pair(left, right)
    assert len(blocks) == len(pairs) == 1


def test_invalid_entity_blocks_observation_before_pairing():
    left = _observation("a", entity_state="blocked_upstream_entity_integrity")
    right = _observation("b", publication="publication:b", direction="negative")
    _, pairs, _ = _pair(left, right)
    assert pairs == []


def test_duplicate_same_evidence_is_collapsed_before_pairing():
    left = _observation("a", spans=["span:same"], text_hashes=["hash:same"])
    right = _observation(
        "b",
        spans=["span:same"],
        text_hashes=["hash:same"],
        experiment=left.experiment_id,
    )
    _, pairs, collapsed = generate_bounded_diagnostic_pairs_v1([left, right])
    assert pairs == []
    assert collapsed


def test_same_publication_does_not_become_fake_contradiction():
    left = _observation("a", publication="publication:a", direction="positive")
    right = _observation("b", publication="publication:a", direction="negative")
    _, pairs, _ = _pair(left, right)
    assert pairs[0].source_independence == "same_publication"
    assert pairs[0].diagnostic_conflict_opportunity_state == "blocked_same_source_or_duplicate"


def test_unknown_semantic_authority_becomes_reviewable_not_incompatible():
    left = _observation("a", signature=_signature("a", result_family=None))
    right = _observation(
        "b",
        publication="publication:b",
        direction="negative",
        signature=_signature("b", result_family=None),
    )
    _, pairs, _ = _pair(left, right)
    assert pairs[0].proposition_signature_compatibility.alignment_v3_candidate_state == "partial_reviewable"
    assert pairs[0].diagnostic_conflict_opportunity_state == "diagnostic_candidate_reviewable"


def test_lane_b_evaluation_does_not_mutate_lane_a_inputs():
    lane_a = [{"signal_id": "generic-signal", "state": "validated"}]
    before = json.dumps(lane_a, sort_keys=True)
    _pair(
        _observation("a"),
        _observation("b", publication="publication:b", direction="negative"),
    )
    assert json.dumps(lane_a, sort_keys=True) == before


def test_candidate_contract_prevents_lane_b_production_activation():
    with pytest.raises(ValueError, match="diagnostic_lane_cannot_activate"):
        ScientificConflictCandidateV2Candidate(
            candidate_id="candidate",
            observation_refs=["a", "b"],
            publication_refs=["p1", "p2"],
            proposition_signature_refs=["s1", "s2"],
            alignment_state="aligned_exact",
            contradiction_state="opposed",
            entity_integrity_state="eligible",
            source_independence_state="independent",
            provenance_state="complete",
            qualification_state="candidate_qualified",
            origin_lane="diagnostic_fulltext",
        )


def test_production_contract_has_no_case_hardcoding():
    path = (
        Path(__file__).resolve().parents[1]
        / "src/code_engine/context_attribution/conflict_candidate/scientific_regeneration_v1_candidate.py"
    )
    text = path.read_text(encoding="utf-8").lower()
    prohibited = (
        "hif1a", "pi3k", "weak-3ca", "weak-256", "ebd5", "40f", "f389",
        "par1", "tcf20", "csn8",
    )
    assert not [literal for literal in prohibited if literal in text]


ROOT = Path(__file__).resolve().parents[1]
RUN = ROOT / "runs/20260825_scientific_candidate_regeneration_fulltext_opportunity_v1_offline/artifacts"


def _json(name):
    return json.loads((RUN / name).read_text(encoding="utf-8"))


def _rows(name):
    return [json.loads(line) for line in (RUN / name).read_text(encoding="utf-8").splitlines() if line]


@pytest.mark.parametrize("name", [
    "baseline.json",
    "local_fulltext_corpus_inventory.json",
    "eligible_fulltext_observations.jsonl",
    "scientific_proposition_blocks.jsonl",
    "lane_a_signal_bridge_audit.jsonl",
    "lane_a_scientific_candidate_results.jsonl",
    "lane_b_fulltext_pair_inventory.jsonl",
    "lane_b_diagnostic_conflict_opportunities.jsonl",
    "production_vs_diagnostic_bottleneck_attribution.jsonl",
    "historical_candidate_v3_comparison.json",
    "scientific_candidate_v2_candidate.jsonl",
    "missing_authority_ledger.json",
    "candidate_regeneration_summary.json",
    "scientific_state_safety_audit.json",
    "entity_integrity_gate_recheck.json",
    "production_leakage_audit.json",
    "autonomous_iteration_ledger.jsonl",
    "final_validation.json",
    "manifest.json",
    "summary.json",
])
def test_required_offline_artifacts_exist(name):
    assert (RUN / name).is_file()


def test_generated_contract_rows_validate():
    for row in _rows("lane_b_fulltext_pair_inventory.jsonl"):
        DiagnosticFulltextPairV1.model_validate(row)
    for row in _rows("scientific_candidate_v2_candidate.jsonl"):
        ScientificConflictCandidateV2Candidate.model_validate(row)


def test_historical_candidates_and_formal_objects_remain_unchanged():
    safety = _json("scientific_state_safety_audit.json")
    assert safety["historical_candidate_object_count_before"] == 11
    assert safety["historical_candidate_object_count_after"] == 11
    assert safety["historical_candidate_objects_modified"] is False
    assert safety["formal_conflict_count_before"] == 0
    assert safety["formal_conflict_count_after"] == 0
    assert safety["l4_executed"] is False
    assert safety["protected_hashes_before"] == safety["protected_hashes_after"]
    for relative, expected in safety["protected_hashes_after"].items():
        assert hashlib.sha256((ROOT / relative).read_bytes()).hexdigest() == expected


def test_summary_contains_required_metrics_and_accepts_zero_candidates():
    summary = _json("summary.json")
    required = {
        "historical_candidate_object_count",
        "historical_candidate_scientifically_eligible_v3_count",
        "fulltext_observation_count",
        "entity_eligible_observation_count",
        "proposition_signature_complete_observation_count",
        "proposition_block_count",
        "within_block_pair_count",
        "scientifically_compatible_pair_count",
        "opposing_result_pair_count",
        "source_independent_opposing_result_pair_count",
        "lane_a_signal_count",
        "lane_a_valid_signal_count",
        "lane_a_bridgeable_signal_count",
        "lane_a_scientifically_eligible_candidate_count",
        "lane_b_diagnostic_strong_count",
        "lane_b_diagnostic_reviewable_count",
        "captured_by_production_count",
        "missed_abstract_screen_count",
        "missed_fulltext_bridge_count",
        "missed_alignment_projection_count",
        "missing_authority_count",
    }
    assert required <= summary["metrics"].keys()
    assert summary["interpretation_state"] in {"A", "B", "C"}


def test_entity_core_and_pi3k_safety_invariants_are_preserved():
    safety = _json("scientific_state_safety_audit.json")
    assert safety["core_reference_exact_match_count"] == 33
    assert safety["core_reference_fail_closed_match_count"] == 6
    assert safety["core_reference_mismatch_count"] == 0
    assert safety["entity_integrity_claims_blocked"] == 241
    assert safety["entity_integrity_signals_blocked"] == 2
    assert safety["pi3k"]["scientific_bridges_created"] == 0
    assert safety["pi3k"]["manual_signal_adjudicated"] is False


def test_no_l4_formal_provider_network_or_activation_leakage():
    leakage = _json("production_leakage_audit.json")
    assert leakage["l4_execution_count"] == 0
    assert leakage["formal_objects_created"] == 0
    assert leakage["provider_calls"] == 0
    assert leakage["api_calls"] == 0
    assert leakage["network_calls"] == 0
    assert leakage["downloads"] == 0
    assert leakage["atlas_activated"] is False
    assert leakage["active_pointer_changed"] is False
    assert leakage["variational_em_called"] is False
