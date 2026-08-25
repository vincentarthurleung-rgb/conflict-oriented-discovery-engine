import hashlib
import json
from pathlib import Path

import pytest

from code_engine.context_attribution.claim_alignment.scientific_proposition_v1_candidate import (
    CausalEvidentialModeV1,
    ExperimentalContrastSemanticsV1,
    GranularityQualifierV1,
    InterventionPropositionV1,
    StructuredSemanticValueV1,
    evaluate_scientific_proposition_compatibility_v1,
    make_scientific_proposition_signature_v1,
    ScientificPropositionCompatibilityV1,
    ScientificPropositionSignatureV1,
)
from code_engine.extraction_assets.scientific_entity_integrity import (
    ScientificEntityIntegrityBlocked,
    ScientificEntityIntegrityGateResultV1,
)


def _value(value, identity=None, family=None, state=None):
    return StructuredSemanticValueV1(
        value=value,
        canonical_identity=identity,
        semantic_family=family,
        authority_state=state or ("validated_canonical" if identity else "structured_only"),
        source_refs=["generic-structured-authority"],
    )


def _intervention(mode="single"):
    if mode == "none":
        return InterventionPropositionV1(
            intervention_mode="none", authority_state="not_applicable"
        )
    return InterventionPropositionV1(
        intervention_mode=mode,
        factor_families=["controlled_perturbation"],
        target_values=[_value("perturbation target", "factor:target")],
        authority_state="resolved",
    )


def _mode(family="interventional_effect"):
    types = {
        "interventional_effect": "interventional_experiment",
        "observational_association": "observational_comparison",
        "descriptive_observation": "descriptive_measurement",
    }
    return CausalEvidentialModeV1(
        observation_type=types[family],
        mode_family=family,
        authority_state="resolved",
        source_refs=["generic-observation-type"],
    )


def _contrast(role="experimental_vs_reference", label="reference A"):
    authority = "not_applicable" if role == "no_explicit_contrast" else "resolved"
    return ExperimentalContrastSemanticsV1(
        contrast_role=role,
        reference_labels=[_value(label)] if label else [],
        comparison_link_count=0 if role == "no_explicit_contrast" else 1,
        authority_state=authority,
        source_refs=["generic-result-link"],
    )


def _signature(
    observation_id,
    *,
    target="target",
    target_identity="target:1",
    endpoint="endpoint",
    endpoint_identity="endpoint:1",
    result_family="abundance:qualitative_result",
    method="assay A",
    method_identity="method:a",
    causal_family="interventional_effect",
    intervention_mode="single",
    contrast_role="experimental_vs_reference",
    contrast_label="reference A",
    qualifiers=(),
):
    return make_scientific_proposition_signature_v1(
        observation_id=observation_id,
        subject_identity="subject:1",
        relation_effect_family="effect:1",
        object_target_identity="object:1",
        measurement_targets=[_value(target, target_identity)],
        measured_properties=[
            _value(
                endpoint,
                endpoint_identity,
                result_family.split(":")[0] if result_family else None,
            )
        ],
        assay_methods=[_value(method, method_identity)],
        result_semantics=[
            _value(
                result_family,
                f"result:{result_family}" if result_family else None,
                result_family,
                "controlled_vocabulary" if result_family else "structured_only",
            )
        ],
        intervention_proposition=_intervention(intervention_mode),
        causal_evidential_mode=_mode(causal_family),
        experimental_contrast=_contrast(contrast_role, contrast_label),
        granularity_qualifiers=qualifiers,
        source_refs=["generic-validated-core"],
    )


def _evaluate(a, b):
    return evaluate_scientific_proposition_compatibility_v1(
        pair_id="generic-pair",
        signature_a=a,
        signature_b=b,
        historical_alignment_v2_identity="historical-v2",
        historical_alignment_v2_state="aligned",
    )


def test_same_target_endpoint_and_different_assay_may_align():
    result = _evaluate(
        _signature("a", method="assay A", method_identity="method:a"),
        _signature("b", method="assay B", method_identity="method:b"),
    )
    assert result.measurement_compatibility.assay_method.semantic_role == "compatibility_qualifier"
    assert result.measurement_compatibility.assay_difference_is_proposition_mismatch is False
    assert result.alignment_v3_candidate_state == "aligned_compatible"


def test_different_canonical_target_does_not_align_due_to_related_topic():
    result = _evaluate(
        _signature("a", target="target A", target_identity="target:a"),
        _signature("b", target="target B", target_identity="target:b"),
    )
    assert result.measurement_compatibility.compatibility_state == "incompatible_target"
    assert result.alignment_v3_candidate_state == "blocked_measurement_target_mismatch"
    assert result.string_inequality_used_as_incompatibility is False


def test_same_target_abundance_and_activity_are_not_automatically_equivalent():
    result = _evaluate(
        _signature("a", result_family="abundance:qualitative_result"),
        _signature("b", result_family="activity:qualitative_result"),
    )
    assert result.measurement_compatibility.compatibility_state == "incompatible_result_semantics"
    assert result.alignment_v3_candidate_state == "blocked_result_semantic_mismatch"


def test_result_direction_is_outside_proposition_identity():
    result = _evaluate(_signature("a"), _signature("b"))
    assert "direction" in _signature("a").excluded_result_identity_fields
    assert result.result_direction_used_as_identity is False
    assert result.alignment_v3_candidate_state == "aligned_exact"


def test_observational_and_interventional_modes_are_not_silently_equivalent():
    result = _evaluate(
        _signature(
            "a",
            causal_family="observational_association",
            contrast_role="observational_group_vs_reference",
        ),
        _signature("b"),
    )
    assert result.causal_evidential_mode.compatibility_state == "incompatible"
    assert not result.alignment_v3_candidate_state.startswith("aligned_")


def test_generic_and_specific_intervention_families_require_review_authority():
    left = _signature("a")
    right = _signature("b")
    right_intervention = right.intervention_proposition.model_copy(update={
        "factor_families": ["genetic_perturbation"]
    })
    right = right.model_copy(update={"intervention_proposition": right_intervention})
    result = _evaluate(left, right)
    assert result.intervention_proposition.compatibility_state == "unresolved"
    assert result.alignment_v3_candidate_state == "partial_reviewable"


def test_different_reference_labels_are_compatible_when_contrast_roles_match():
    result = _evaluate(
        _signature("a", contrast_label="untreated group"),
        _signature("b", contrast_label="reference group"),
    )
    assert result.experimental_contrast.compatibility_state == "compatible_exact"
    assert result.alignment_v3_candidate_state == "aligned_exact"


def test_unresolved_measurement_property_is_reviewable_not_aligned():
    result = _evaluate(
        _signature("a", result_family="abundance:qualitative_result"),
        _signature("b", result_family=None),
    )
    assert result.measurement_compatibility.result_semantic_level.compatibility_state == "unresolved"
    assert result.alignment_v3_candidate_state == "partial_reviewable"


def test_context_only_genotype_difference_does_not_block_alignment():
    left = _signature("a")
    right = _signature("b")
    assert next(row for row in left.semantic_roles if row.dimension_id == "genotype").semantic_role == "context_only"
    assert _evaluate(left, right).alignment_v3_candidate_state == "aligned_exact"


def test_explicitly_proposition_scoped_genotype_affects_alignment():
    left_q = GranularityQualifierV1(
        dimension_id="genotype",
        value="genotype A",
        canonical_identity="genotype:a",
        bridge_status="unresolved",
        semantic_role="proposition_critical",
    )
    right_q = left_q.model_copy(update={"value": "genotype B", "canonical_identity": "genotype:b"})
    result = _evaluate(
        _signature("a", qualifiers=[left_q]),
        _signature("b", qualifiers=[right_q]),
    )
    assert result.alignment_v3_candidate_state == "partial_reviewable"
    assert "genotype" in result.unresolved_dimensions


def test_l4b_context_cannot_repair_proposition_mismatch():
    result = _evaluate(
        _signature("a", target="target A", target_identity="target:a"),
        _signature("b", target="target B", target_identity="target:b"),
    )
    assert result.context_comparability_evaluated is False
    assert result.alignment_v3_candidate_state == "blocked_measurement_target_mismatch"


def test_entity_integrity_gate_remains_upstream():
    blocked = ScientificEntityIntegrityGateResultV1(
        object_id="claim-a",
        object_type="claim",
        consumer="claim_alignment",
        eligibility_status="blocked_upstream_entity_integrity",
        authoritative_for_scientific_promotion=False,
        affected_fields=["subject"],
        scientific_roles=["subject"],
        blocking_reasons=["unresolved subject"],
        source_refs=["entity-sidecar"],
    )
    with pytest.raises(ScientificEntityIntegrityBlocked):
        evaluate_scientific_proposition_compatibility_v1(
            pair_id="generic-pair",
            signature_a=_signature("a"),
            signature_b=_signature("b"),
            historical_alignment_v2_identity="historical-v2",
            historical_alignment_v2_state="aligned",
            entity_integrity_decisions=[blocked],
        )


def test_production_contract_has_no_case_pair_entity_or_publication_literals():
    path = (
        Path(__file__).resolve().parents[1]
        / "src/code_engine/context_attribution/claim_alignment/scientific_proposition_v1_candidate.py"
    )
    text = path.read_text(encoding="utf-8").lower()
    prohibited = (
        "weak-3ca", "weak-256", "ebd5", "17b", "41f", "40f", "f389",
        "par1", "tcf20", "csn8", "hif1a", "33643917",
    )
    assert not [literal for literal in prohibited if literal in text]


ROOT = Path(__file__).resolve().parents[1]
RUN = ROOT / "runs/20260825_scientific_proposition_compatibility_strengthening_v1_offline/artifacts"


def _json(name):
    return json.loads((RUN / name).read_text(encoding="utf-8"))


def _rows(name):
    return [json.loads(line) for line in (RUN / name).read_text(encoding="utf-8").splitlines() if line]


@pytest.mark.parametrize("name", [
    "baseline.json",
    "scientific_proposition_signature_contract_snapshot.json",
    "measurement_semantic_family_inventory.json",
    "result_semantic_family_inventory.json",
    "causal_mode_inventory.json",
    "contrast_role_inventory.json",
    "alignment_semantic_coverage_audit_v3.jsonl",
    "alignment_owned_projection_gap_audit.jsonl",
    "claim_alignment_v3_candidate_results.jsonl",
    "eligible_pair_alignment_audit.json",
    "historical_alignment_v2_v3_comparison.json",
    "candidate_qualification_eligibility_replay.jsonl",
    "l4_entry_candidate_replay.jsonl",
    "context_ownership_regression.json",
    "entity_integrity_gate_recheck.json",
    "scientific_state_safety_audit.json",
    "production_leakage_audit.json",
    "autonomous_iteration_ledger.jsonl",
    "final_validation.json",
    "manifest.json",
    "summary.json",
])
def test_required_offline_artifact_exists(name):
    assert (RUN / name).is_file()


def test_all_candidate_contract_records_validate():
    rows = _rows("claim_alignment_v3_candidate_results.jsonl")
    assert len(rows) == 11
    for row in rows:
        ScientificPropositionSignatureV1.model_validate(row["signature_a"])
        ScientificPropositionSignatureV1.model_validate(row["signature_b"])
        ScientificPropositionCompatibilityV1.model_validate(
            row["scientific_proposition_compatibility"]
        )


def test_two_historically_eligible_pairs_receive_independent_v3_review():
    audit = _json("eligible_pair_alignment_audit.json")
    assert audit["pair_count"] == 2
    assert {row["candidate_id"] for row in audit["pairs"]} == {
        "weak-3ca38dc452f5816bcb50",
        "weak-256ac5981f2df16f7f33",
    }
    for row in audit["pairs"]:
        assert row["alignment_v2_state"] == "aligned"
        assert row["alignment_v3_candidate_state"] == "blocked_intervention_proposition_mismatch"
        assert row["causal_evidential_mode"]["compatibility_state"] == "incompatible"
        assert row["raw_string_inequality_used_as_incompatibility"] is False


def test_eleven_pair_replay_is_fail_closed_and_candidate_only():
    summary = _json("summary.json")
    metrics = summary["metrics"]
    assert metrics["pair_count"] == 11
    assert metrics["alignment_v3_reviewable_count"] == 9
    assert metrics["alignment_v3_blocked_count"] == 2
    assert metrics["alignment_v3_aligned_exact_count"] == 0
    assert metrics["alignment_v3_aligned_compatible_count"] == 0
    assert metrics["candidate_qualification_v3_eligible_count"] == 0
    assert metrics["l4_entry_v3_eligible_count"] == 0


def test_alignment_owned_gap_audit_reclassifies_and_leaves_missing_authority():
    rows = _rows("alignment_owned_projection_gap_audit.jsonl")
    assert len(rows) == 11
    assert sum(row["audit_outcome"] == "already_consumed_by_existing_alignment" for row in rows) == 8
    assert sum(row["audit_outcome"] == "missing_structured_authority" for row in rows) == 3
    assert sum(row["deterministic_projection_added"] for row in rows) == 0


def test_coverage_and_role_metrics_are_complete():
    metrics = _json("summary.json")["metrics"]
    assert metrics["alignment_semantic_units_evaluated"] == 209
    classified = (
        metrics["proposition_critical_unit_count"]
        + metrics["compatibility_qualifier_unit_count"]
        + metrics["context_only_unit_count"]
        + metrics["semantic_role_unresolved_count"]
        + 11  # explicit not-applicable result-direction units
    )
    assert classified == 209


def test_context_ownership_and_entity_gate_regressions_pass():
    context = _json("context_ownership_regression.json")
    entity = _json("entity_integrity_gate_recheck.json")
    assert context["ordinary_context_universally_proposition_critical"] is False
    assert context["l4b_scientific_definition_changed"] is False
    assert entity["claims_blocked_after"] == 241
    assert entity["signals_blocked_after"] == 2
    assert entity["blocked_claim_rescued_by_alignment_v3"] is False


def test_historical_candidate_alignment_qualification_and_formal_hashes_are_unchanged():
    safety = _json("scientific_state_safety_audit.json")
    assert safety["protected_hashes_before"] == safety["protected_hashes_after"]
    for relative, expected in safety["protected_hashes_after"].items():
        actual = hashlib.sha256((ROOT / relative).read_bytes()).hexdigest()
        assert actual == expected
    assert safety["historical_assets_modified"] is False
    assert safety["candidate_pairs_modified"] is False
    assert safety["historical_alignment_modified"] is False
    assert safety["formal_v3_modified"] is False


def test_scientific_safety_preserves_reference_counts_and_manual_review():
    safety = _json("scientific_state_safety_audit.json")
    assert safety["core_reference_exact_match_count"] == 33
    assert safety["core_reference_fail_closed_match_count"] == 6
    assert safety["core_reference_mismatch_count"] == 0
    assert safety["candidate_count_before"] == safety["candidate_count_after"] == 11
    assert safety["formal_conflict_count_before"] == safety["formal_conflict_count_after"] == 0
    assert safety["pi3k"] == {
        "initial_experiment_candidate_count": 18,
        "deterministically_excluded_count": 11,
        "scientifically_plausible_candidate_count": 5,
        "insufficient_evidence_candidate_count": 2,
        "final_state": "manual_scientific_review_required",
        "experiment_auto_selected": False,
        "scientific_bridges_created": 0,
    }
    assert safety["f389_adjudicated"] is False


def test_production_leakage_and_runtime_activity_are_zero():
    leakage = _json("production_leakage_audit.json")
    safety = _json("scientific_state_safety_audit.json")
    for key in (
        "case_specific_production_rule_count", "hardcoded_pair_id_rule_count",
        "hardcoded_entity_rule_count", "hardcoded_pmid_rule_count",
    ):
        assert leakage[key] == 0
    for key in ("provider_calls", "api_calls", "network_calls", "downloads"):
        assert safety[key] == 0
    for key in ("atlas_activated", "active_pointer_changed", "variational_em_called"):
        assert safety[key] is False


def test_manifest_checksums_match_all_listed_artifacts():
    manifest = _json("manifest.json")
    assert manifest["offline"] is True
    assert manifest["file_count"] == len(manifest["files"])
    for row in manifest["files"]:
        path = ROOT / row["path"]
        assert path.stat().st_size == row["bytes"]
        assert hashlib.sha256(path.read_bytes()).hexdigest() == row["sha256"]
