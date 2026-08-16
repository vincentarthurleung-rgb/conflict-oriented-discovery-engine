from __future__ import annotations

from pathlib import Path
import re

import pytest

from code_engine.extraction_assets.experimental_core.models import CoreProvenance
from code_engine.extraction_assets.experimental_core.repair_v1 import (
    ExperimentalArmRecordV1, MeasurementKind, SourceGroundedLinkageCandidateV1,
    annotation_task_validity_gate, candidate_completeness_gate,
    classify_measurement_kind, inspect_measurement_semantics, inspect_observed_result,
    machine_reuse_readiness_v5, materialize_linkage,
)


PROVENANCE = CoreProvenance(
    producer="offline_test", producer_version="v1", source_artifact_refs=["fixture"],
    deterministic_rule_refs=["test_rule_v1"], offline=True,
)


def candidate(**updates) -> SourceGroundedLinkageCandidateV1:
    payload = {
        "observation_identity": "observation:1",
        "relation_type": "result_compared_against_reference_arm",
        "source_ref": "result:1", "target_ref": "arm:1", "source_identity": "source:1",
        "evidence_refs": ["span:1"], "explicit_source_semantics": True,
        "deterministic_grounding_version": "explicit_source_grounding_v1",
        "competing_candidate_refs": [], "candidate_completeness_status": "complete",
        "structural_integrity_passed": True, "authority_state": "validated_source_grounded",
        "role_metadata_only": False, "candidate_cardinality_only": False,
        "identity": "candidate:1", "provenance": PROVENANCE,
    }
    payload.update(updates)
    return SourceGroundedLinkageCandidateV1.model_validate(payload)


def test_explicit_unique_grounding_materializes_result_to_arm():
    decision = materialize_linkage(candidate())
    assert decision.status == "materialized"
    assert decision.linkage.relation_type == "result_compared_against_reference_arm"
    assert decision.linkage.source_ref == "result:1"
    assert decision.linkage.target_ref == "arm:1"


@pytest.mark.parametrize("update,reason", [
    ({"role_metadata_only": True}, "role_metadata_not_authority"),
    ({"candidate_cardinality_only": True}, "candidate_cardinality_not_authority"),
    ({"explicit_source_semantics": False}, "explicit_comparison_or_applicability_absent"),
    ({"competing_candidate_refs": ["arm:2"]}, "competing_candidate_unresolved"),
    ({"evidence_refs": []}, "invalid_evidence_refs"),
    ({"candidate_completeness_status": "incomplete_reference_arm"}, "candidate_completeness_gate_failed"),
    ({"structural_integrity_passed": False}, "structural_integrity_gate_failed"),
])
def test_materializer_fails_closed(update, reason):
    decision = materialize_linkage(candidate(**update))
    assert decision.status == "rejected"
    assert reason in decision.reason_codes


def test_factor_measurement_exact_relation_materializes():
    decision = materialize_linkage(candidate(
        relation_type="factor_applies_to_measurement", source_ref="factor:1", target_ref="measurement:1",
    ))
    assert decision.linkage.source_ref == "factor:1"
    assert decision.linkage.target_ref == "measurement:1"


@pytest.mark.parametrize("value,state", [
    ("not reported", "not_reported"), ("none reported", "not_reported"),
    ("not available", "not_available"), ("unavailable", "not_available"),
    ("unknown", "unknown"), ("N/A", "legacy_sentinel"), ("NA", "legacy_sentinel"),
])
def test_exact_missingness_tokens_are_not_scientific_results(value, state):
    audit = inspect_observed_result(
        source_result_identity="result:1", qualitative_result=value, provenance=PROVENANCE,
    )
    assert audit.result_value_state == state
    assert audit.observed_result_value is None
    assert audit.eligibility == "structurally_incomplete"


def test_full_scientific_sentence_containing_not_reported_is_preserved():
    text = "The endpoint was not reported in controls but increased after treatment."
    audit = inspect_observed_result(
        source_result_identity="result:1", qualitative_result=text, provenance=PROVENANCE,
    )
    assert audit.result_value_state == "scientific_result_value"
    assert audit.observed_result_value == text


def test_quantitative_value_overrides_legacy_text_token():
    audit = inspect_observed_result(
        source_result_identity="result:1", qualitative_result="NA", quantitative_value=2.1,
        provenance=PROVENANCE,
    )
    assert audit.eligibility == "structurally_valid"


@pytest.mark.parametrize("kind", ["clinical_outcome", "phenotype", "survival_outcome", "association_endpoint"])
def test_exposure_outcome_merge_is_structurally_invalid(kind):
    audit = inspect_measurement_semantics(
        source_measurement_identity="measurement:1", measured_entity="exposure biomarker",
        endpoint="patient endpoint", measurement_kind=MeasurementKind(kind),
        exposure_identity="factor:1", association_explicit=True, provenance=PROVENANCE,
    )
    assert audit.status == "invalid_merged_exposure_outcome"


def test_molecular_measurement_remains_valid():
    audit = inspect_measurement_semantics(
        source_measurement_identity="measurement:1", measured_entity="protein abundance",
        endpoint="expression", measurement_kind=MeasurementKind.MOLECULAR_MEASUREMENT,
        exposure_identity=None, association_explicit=False, provenance=PROVENANCE,
    )
    assert audit.status == "valid"


@pytest.mark.parametrize("endpoint,kind", [
    ("patient survival", "survival_outcome"), ("tumor stage", "clinical_outcome"),
    ("lymph node metastasis", "phenotype"),
])
def test_generic_clinical_endpoint_taxonomy(endpoint, kind):
    assert classify_measurement_kind(endpoint) == kind


def test_arm_composes_atomic_factors_but_is_a_distinct_identity():
    arm = ExperimentalArmRecordV1(
        arm_id="arm:1", arm_label_raw="compound genotype reference", factor_refs=["factor:a", "factor:b"],
        component_raw_values=["allele A", "allele B"], genotype="compound genotype",
        source_evidence_refs=["caption:1"], group_definition_refs=["caption:1"],
        role_candidate="reference", role_authority="explicit_source", validation_status="validated",
        derived_from=["observation:1"], repair_reason="missing arm representation",
        repair_rule_identity="explicit_group_definition_v1", identity="arm:1", provenance=PROVENANCE,
    )
    assert arm.factor_refs == ["factor:a", "factor:b"]
    assert arm.arm_id not in arm.factor_refs


def test_role_candidate_without_evidence_cannot_be_explicit_authority():
    with pytest.raises(ValueError, match="requires evidence"):
        ExperimentalArmRecordV1(
            arm_id="arm:1", arm_label_raw="control", source_evidence_refs=[], group_definition_refs=[],
            role_candidate="control", role_authority="explicit_source", validation_status="validated",
            derived_from=["observation:1"], repair_reason="test",
            repair_rule_identity="rule:v1", identity="arm:1", provenance=PROVENANCE,
        )


def test_candidate_gate_distinguishes_missing_arm_from_source_gap():
    missing = candidate_completeness_gate(
        observation_identity="o", candidate_ids=["factor:x"], source_scope_sufficient=True,
        source_declares_reference_arm=True, reference_arm_candidate_present=False,
        factor_candidates_valid=True, provenance=PROVENANCE,
    )
    gap = candidate_completeness_gate(
        observation_identity="o", candidate_ids=["factor:x"], source_scope_sufficient=False,
        source_declares_reference_arm=True, reference_arm_candidate_present=False,
        factor_candidates_valid=True, provenance=PROVENANCE,
    )
    assert missing.status == "incomplete_reference_arm"
    assert missing.route == "structural_remediation"
    assert gap.status == "source_scope_insufficient"
    assert gap.route == "source_recovery"


@pytest.mark.parametrize("kwargs,expected", [
    ({"source_scope_sufficient": False}, "source_scope_insufficient"),
    ({"observation_structure_valid": False}, "observation_structure_invalid"),
    ({"semantic_structure_valid": False}, "structural_remediation_required"),
    ({"candidate_status": "incomplete_reference_arm"}, "candidate_set_incomplete"),
    ({"deterministically_resolvable": True}, "already_deterministically_resolvable"),
])
def test_annotation_validity_routing_precedence(kwargs, expected):
    base = dict(source_scope_sufficient=True, candidate_status="complete",
                observation_structure_valid=True, semantic_structure_valid=True,
                deterministically_resolvable=False)
    base.update(kwargs)
    record = annotation_task_validity_gate(observation_identity="o", provenance=PROVENANCE, **base)
    assert record.status == expected
    assert record.status != "valid_for_annotation"


def test_readiness_checks_all_core_blockers_after_one_link_is_repaired():
    record = machine_reuse_readiness_v5(
        observation_identity="o", v4_readiness_identity="v4:o",
        prior_status="machine_reusable_with_core_annotation_pending",
        core_blockers=["linkage_unresolved"], nonblocking_limitations=[], provenance=PROVENANCE,
    )
    assert record.status == "structured_core_linkage_unresolved"


def test_optional_method_enrichment_is_nonblocking():
    record = machine_reuse_readiness_v5(
        observation_identity="o", v4_readiness_identity="v4:o",
        prior_status="machine_reusable_candidate", core_blockers=[],
        nonblocking_limitations=["method"], provenance=PROVENANCE,
    )
    assert record.status == "machine_reusable_with_method_limitation"
    assert record.active_v4_replaced is False


def test_runtime_module_has_no_fixture_loader_or_frozen_scientific_special_cases():
    text = Path("src/code_engine/extraction_assets/experimental_core/repair_v1.py").read_text()
    forbidden = ("reference_inputs", "reference_gold", "source_grounded_reference", "CSN8")
    assert all(token not in text for token in forbidden)
    assert re.search(r"core_[0-9a-f]{20}", text) is None
