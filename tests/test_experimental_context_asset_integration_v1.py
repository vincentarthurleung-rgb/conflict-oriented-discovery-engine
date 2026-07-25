from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from code_engine.extraction_assets.context.consolidation import resolve_field
from code_engine.extraction_assets.context.evidence import provider_offsets_are_authoritative
from code_engine.extraction_assets.context.experiment_scope import (
    same_paragraph_is_scope, scope_authority, similar_text_is_scope,
)
from code_engine.extraction_assets.context.field_registry import build_registry
from code_engine.extraction_assets.context.migration import (
    map_legacy_field, migrated_semantic_authority,
)
from code_engine.extraction_assets.context.models import (
    AssetProvenance, ContextAssetScopedAuthority, ContextFieldEvidence,
    ContextProviderCallPolicy, ContextValueStateBasis,
    ExperimentalContextCandidateRevision, SourceContextEnvelope,
)
from code_engine.extraction_assets.context.normalization import normalization_view
from code_engine.extraction_assets.context.propagation import propagate
from code_engine.extraction_assets.context.value_state import (
    classify_missing_provider_field, legacy_null_basis,
)


PROV = AssetProvenance(producer="test", producer_version="1")
ROOT = Path(__file__).resolve().parents[1]
RUN = ROOT / "runs/20260725_hif1a_experimental_context_asset_integration_v1_offline/artifacts"


def candidate(**updates):
    base = dict(
        context_candidate_revision_id="r", observation_candidate_identity="o",
        context_schema_name="legacy", context_schema_version="1",
        extractor_name="migration", extractor_version="1",
        extraction_contract_identity="contract", raw_context_payload={"species": "mouse"},
        raw_context_payload_sha256="h", parse_status="migrated",
        schema_status="valid", immutable=True, identity="candidate:1", provenance=PROV,
    )
    base.update(updates)
    return ExperimentalContextCandidateRevision(**base)


def evidence(**updates):
    basis = ContextValueStateBasis(
        value_state="present", state_basis_type="direct",
        source_evidence_refs=["S1"], state_authority="authoritative",
    )
    base = dict(
        context_field_evidence_id="f", context_candidate_revision_identity="c",
        observation_candidate_identity="o", field_id="species", field_path="context.species",
        raw_text="mouse", provider_value="mouse", extracted_value="mouse",
        canonical_value="Mus musculus", value_state="present",
        value_origin="direct_local_evidence", value_state_basis=basis,
        evidence_anchor_ids=["S1"], source_sentence_ids=["S1"],
        anchor_precision="sentence", anchor_validation_status="validated",
        context_validation_status="validated", normalization_status="resolved",
        authority_status="validated", identity="field:1", provenance=PROV,
    )
    base.update(updates)
    return ContextFieldEvidence(**base)


def test_candidate_is_immutable_and_separate_from_validated_context():
    row = candidate()
    assert row.schema_version == "experimental_context_candidate_revision_v1"
    with pytest.raises(ValidationError):
        row.parse_status = "parsed"
    assert "semantic_validation_status" not in type(row).model_fields


@pytest.mark.parametrize("field", [
    "comparison_status", "comparability", "comparability_effect",
    "explains_divergence", "formal_conflict", "formal_conflict_status",
])
def test_context_candidate_rejects_derived_reasoning_recursively(field):
    with pytest.raises(ValidationError):
        candidate(raw_context_payload={"nested": {field: True}})


def test_raw_extracted_and_canonical_values_remain_separate_after_rejection():
    row = evidence(
        provider_value="mice?", extracted_value="mice?", canonical_value=None,
        value_state="invalid", context_validation_status="rejected",
        rejection_reason_codes=["unsupported_normalization"],
    )
    assert row.raw_text == "mouse"
    assert row.extracted_value == row.provider_value == "mice?"
    assert row.canonical_value is None


def test_value_state_basis_is_fail_closed():
    with pytest.raises(ValidationError):
        ContextValueStateBasis(
            value_state="not_mentioned", state_basis_type="provider_missing",
            state_authority="candidate",
        )
    with pytest.raises(ValidationError):
        ContextValueStateBasis(
            value_state="not_applicable", state_basis_type="null",
            state_authority="candidate",
        )
    assert classify_missing_provider_field(prompt_requested=True).value == "not_extracted"
    assert classify_missing_provider_field(prompt_requested=False).value == "unknown"
    assert legacy_null_basis().value_state.value == "legacy_null_unresolved"


def test_legacy_null_is_migration_only_and_does_not_resolve():
    basis = legacy_null_basis()
    with pytest.raises(ValidationError):
        evidence(
            raw_text=None, provider_value=None, extracted_value=None, canonical_value=None,
            value_state="legacy_null_unresolved", value_origin="unresolved_legacy",
            value_state_basis=basis, migration_record=False,
        )
    assert evidence(
        raw_text=None, provider_value=None, extracted_value=None, canonical_value=None,
        value_state="legacy_null_unresolved", value_origin="unresolved_legacy",
        value_state_basis=basis, migration_record=True,
    ).value_state.value == "legacy_null_unresolved"


def test_provider_offsets_never_become_authority_and_incomplete_envelope_is_honest():
    assert not provider_offsets_are_authoritative([(1, 3)])
    with pytest.raises(ValidationError):
        SourceContextEnvelope(
            source_context_envelope_id="e", primary_observation_block=None,
            envelope_construction_policy="p", truncation_status="unknown",
            completeness_status="incomplete", authority_status="authoritative",
            identity="e:1", provenance=PROV,
        )


def test_scope_is_not_inferred_from_proximity_similarity_or_downstream_pair():
    assert not same_paragraph_is_scope("a", "b")
    assert not similar_text_is_scope("same", "same")
    assert scope_authority("downstream_pair") == "candidate_only"
    assert scope_authority("stable_experiment_index") == "authoritative"
    assert scope_authority("stable_experiment_index", source_conflict=True) == "blocked"


def test_scope_propagation_requires_all_guards_and_preserves_origin():
    shared = {"extracted_value": "mouse", "evidence_anchor_ids": ["S1"]}
    ok = propagate(
        shared, scope_validated=True, registry_allows=True,
        observation_is_member=True, same_document=True,
    )
    assert ok["value_origin"] == "deterministic_scope_inheritance"
    for update, reason in [
        ({"scope_validated": False}, "scope_not_validated"),
        ({"registry_allows": False}, "registry_propagation_forbidden"),
        ({"observation_is_member": False}, "observation_not_in_scope"),
        ({"same_document": False}, "cross_document_forbidden"),
        ({"local_conflict": True}, "local_value_conflict"),
        ({"scope_conflict": True}, "scope_value_conflict"),
    ]:
        args = dict(scope_validated=True, registry_allows=True,
                    observation_is_member=True, same_document=True)
        args.update(update)
        assert reason in propagate(shared, **args)["blockers"]


def test_direct_context_precedes_inherited_and_conflict_is_unresolved():
    inherited = {
        "validation_status": "validated", "resolution_method": "validated_scope_inheritance",
        "extracted_value": "mouse",
    }
    direct = {
        "validation_status": "validated", "resolution_method": "validated_direct_local",
        "extracted_value": "human",
    }
    assert resolve_field([inherited, direct])["selected"] == direct
    conflict = resolve_field([direct, {**direct, "extracted_value": "mouse"}])
    assert conflict["selected"] is None and conflict["conflict_status"] == "conflict"


def test_normalization_never_discards_unresolved_source_layers():
    row = normalization_view(
        raw_text="HCT 116", extracted_value="HCT 116", canonical_value=None,
        status="unresolved", unresolved_reason="ambiguous",
    )
    assert row["raw_text"] == row["extracted_value"] == "HCT 116"
    assert row["canonical_value"] is None


def test_migration_keeps_candidate_and_semantic_authority_independent_from_raw():
    assert migrated_semantic_authority(validated=True, candidate_present=True) == "validated_legacy"
    assert migrated_semantic_authority(validated=False, candidate_present=True) == "candidate_only"
    assert map_legacy_field("mystery", {})["mapping_status"] == "unresolved"


def test_scoped_authority_cannot_be_decided_by_llm_extra_field():
    base = dict(
        observation_identity="o", semantic_authority="validated_legacy",
        evidence_authority="exact_sentence_anchor", provenance_authority="legacy_incomplete",
        replayability_authority="structured_artifact_replayable",
        downstream_use_authority="allowed_for_exploratory_graph",
        downstream_authority_source="existing_entry_gate", identity="a",
    )
    ContextAssetScopedAuthority(**base)
    with pytest.raises(ValidationError):
        ContextAssetScopedAuthority(**base, llm_downstream_authority="allowed_for_l4_entry")


def test_registry_is_versioned_explicit_and_does_not_claim_all_fields_supported():
    rows = build_registry()
    assert len(rows) == len({r.field_id for r in rows})
    assert any(not r.currently_supported for r in rows)
    assert next(r for r in rows if r.field_id == "subcellular_localization").legacy_aliases == ["localization"]


def test_provider_policy_disables_bulk_retry_and_execution():
    policy = ContextProviderCallPolicy(identity="policy:1")
    assert not policy.bulk_secondary_context_calls_allowed
    assert not policy.automatic_context_retry_allowed
    assert not policy.provider_call_authorized


def test_offline_run_has_required_artifacts_and_preserves_scientific_states():
    required = [
        "historical_context_asset_inventory.jsonl",
        "experimental_context_candidate_revisions.jsonl",
        "context_field_evidence_records.jsonl",
        "context_asset_coverage_ledger.jsonl",
        "context_asset_remediation_requirements_v2.jsonl",
        "context_asset_multi_axis_readiness.jsonl",
        "experimental_context_asset_integration_manifest.json",
    ]
    assert all((RUN / name).is_file() for name in required)
    assert json.loads((RUN / "weak_3ca_context_asset_audit.json").read_text())[
        "difference_authority_status"] == "ready_not_materialized"
    assert json.loads((RUN / "weak_256_context_asset_audit.json").read_text())[
        "context_entry_status"] == "blocked_context_b_unavailable"
    assert json.loads((RUN / "ebd5_context_asset_audit.json").read_text())[
        "candidate_qualification_status"] == "blocked_alignment"
    assert json.loads((RUN / "context_17b_asset_audit.json").read_text())["candidate_payload_preserved"]
    assert json.loads((RUN / "context_41f_asset_audit.json").read_text())["candidate_payload_preserved"]


def test_generated_schemas_are_strict_and_candidate_contract_is_not_active():
    schemas = list((ROOT / "docs/contracts").glob("*context*_v1.schema.json"))
    assert schemas
    candidate_schema = json.loads(
        (ROOT / "docs/contracts/experimental_context_candidate_revision_v1.schema.json").read_text()
    )
    assert candidate_schema["additionalProperties"] is False
    contract = json.loads((RUN / "candidate_observation_context_contract.json").read_text())
    assert contract["validation_status"] == "pending_smoke_validation"
    assert contract["production_status"] == "not_activated"
    assert not contract["conflict_judgment_requested_from_llm"]


def test_dependency_boundary_has_no_provider_network_or_derived_imports():
    package = ROOT / "src/code_engine/extraction_assets/context"
    forbidden = (
        "deepseek_client", "requests", "httpx", "context_difference",
        "conflict_candidate", "divergence_explanation",
    )
    for path in package.glob("*.py"):
        if path.name == "validation.py":
            continue  # it exposes forbidden tokens solely for the boundary test API
        text = path.read_text()
        assert not any(f"import {token}" in text or f"from {token}" in text for token in forbidden)


def test_manifest_reports_zero_external_activity_and_unchanged_candidates():
    manifest = json.loads((RUN / "experimental_context_asset_integration_manifest.json").read_text())
    assert manifest["candidate_count_before"] == manifest["candidate_count_after"] == 11
    assert not manifest["candidate_identity_changed"]
    assert manifest["formal_conflict_count_before"] == manifest["formal_conflict_count_after"] == 0
    assert manifest["provider_calls"] == manifest["api_calls"] == manifest["network_calls"] == 0
    assert not manifest["credential_values_read"]
    assert not manifest["historical_context_payloads_modified"]
