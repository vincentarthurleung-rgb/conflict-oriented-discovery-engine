from __future__ import annotations

import pytest
from pydantic import ValidationError

from code_engine.extraction_assets.context.closure_v2 import (
    ContextFieldValueV2, ContextInheritanceCandidateV1,
    ContextScopeCompatibilityProofV1, scope_closure_gate,
)
from code_engine.extraction_assets.context.models import AssetProvenance


PROV = AssetProvenance(producer="test", producer_version="v1", offline=True)


def proof(**updates):
    data = dict(
        same_document=True, experiment_scope="same", arm_identity="same",
        cohort="not_applicable", genotype="not_applicable", treatment="not_applicable",
        dose="not_applicable", timepoint="not_applicable", tissue_or_model="same",
        measurement_scope="not_applicable",
    )
    data.update(updates)
    return ContextScopeCompatibilityProofV1(**data)


def candidate(*, sensitive=True, **proof_updates):
    payload = dict(
        field_value_identity="field:1", field_name="genotype",
        parent_scope_type="arm", parent_scope_id="arm:1",
        child_scope_type="observation", child_scope_id="obs:1",
        field_scope_sensitive=sensitive, proof=proof(**proof_updates),
        identity="candidate:1", provenance=PROV,
    )
    return ContextInheritanceCandidateV1(**payload)


def test_same_experiment_same_arm_safe_inheritance():
    assert scope_closure_gate(candidate()).status == "accepted"


@pytest.mark.parametrize("updates,reason", [
    ({"arm_identity": "conflict"}, "arm_scope_not_closed"),
    ({"experiment_scope": "conflict"}, "experiment_scope_not_closed"),
    ({"cohort": "conflict"}, "cohort_not_compatible"),
    ({"timepoint": "conflict"}, "timepoint_not_compatible"),
    ({"dose": "conflict"}, "dose_not_compatible"),
    ({"treatment": "conflict"}, "treatment_not_compatible"),
    ({"competing_arm": True}, "competing_arm_blocked"),
    ({"contradictory_sibling_scope": True}, "contradictory_sibling_scope_blocked"),
    ({"ambiguous_group_definition": True}, "ambiguous_group_definition_blocked"),
    ({"wording_similarity_only": True}, "wording_similarity_only_blocked"),
    ({"proximity_only": True}, "proximity_only_blocked"),
    ({"same_document": False}, "cross_document_blocked"),
])
def test_unsafe_inheritance_is_fail_closed(updates, reason):
    decision = scope_closure_gate(candidate(**updates))
    assert decision.status == "rejected"
    assert reason in decision.reason_codes


def field(**updates):
    payload = dict(
        field_name="species", semantic_category="biological_system", value_raw="mouse",
        value_normalized="Mus musculus", value_state="present", scope_type="experiment",
        scope_id="exp:1", authority="direct_structured", source_evidence_refs=["span:1"],
        source_document_id="doc:1", inheritance_path=[], derivation_rule_id=None,
        normalization_rule_id="registry_v3", normalization_status="resolved",
        validation_status="validated", identity="field:1", provenance=PROV,
    )
    payload.update(updates)
    return ContextFieldValueV2(**payload)


def test_null_is_not_silently_upgraded_to_unknown():
    record = field(value_raw=None, value_normalized=None, value_state="unresolved",
                   authority="unresolved", source_evidence_refs=[], normalization_status="not_requested",
                   validation_status="unresolved")
    assert record.value_state == "unresolved"


def test_not_reported_and_unavailable_are_distinct():
    assert field(value_raw=None, value_normalized=None, value_state="not_reported", authority="unresolved",
                 source_evidence_refs=[], normalization_status="not_requested", validation_status="unresolved").value_state != (
        field(value_raw=None, value_normalized=None, value_state="unavailable", authority="unresolved",
              source_evidence_refs=[], normalization_status="not_requested", validation_status="unresolved").value_state
    )


def test_direct_field_requires_source_refs():
    with pytest.raises(ValidationError, match="source evidence"):
        field(source_evidence_refs=[])


def test_inherited_field_requires_path():
    with pytest.raises(ValidationError, match="parent-to-child"):
        field(authority="scope_inherited", source_evidence_refs=[])


def test_derived_field_requires_rule_identity():
    with pytest.raises(ValidationError, match="rule identity"):
        field(authority="deterministically_derived", source_evidence_refs=[])


def test_failed_normalization_preserves_raw_without_candidate_authority():
    record = field(value_raw="unmapped raw", value_normalized=None,
                   normalization_status="unresolved", normalization_rule_id="registry_v3")
    assert record.value_raw == "unmapped raw" and record.value_normalized is None
