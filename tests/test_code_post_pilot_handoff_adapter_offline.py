"""Focused offline acceptance for the immutable handoff adapter."""

from __future__ import annotations

import copy
from pathlib import Path

import pytest

from code_engine.construction import handoff_adapter as adapter
from scripts import run_code_post_pilot_handoff_to_construction_adapter_offline as runner


@pytest.fixture(scope="module")
def state():
    bundle = adapter.load_verified_evidence_bundle(runner.CONFIG)
    token = adapter.issue_opaque_source_token(runner.CONFIG)
    return bundle, token


def rejected(bundle, token, reason):
    with pytest.raises(adapter.AdapterValidationError) as caught:
        adapter.adapt_evidence_bundle(bundle, token, runner.ROOT)
    assert caught.value.reason == reason


def test_a_valid_immutable_handoff_creates_schema_valid_document(state) -> None:
    bundle, token = state
    envelope = adapter.adapt_evidence_bundle(bundle, token, runner.ROOT)
    document = envelope["construction_document"]
    adapter.validate_construction_document(document, token["opaque_source_token"])
    assert document["schema_version"] == "ConstructionEvidenceDocumentV1"
    assert envelope["controller_private_provenance"]["handoff_sha256"] == runner.CONFIG.handoff_sha256


def test_b_repeated_adaptation_is_identical(state) -> None:
    bundle, token = state
    first = adapter.adapt_evidence_bundle(bundle, token, runner.ROOT)
    second = adapter.adapt_evidence_bundle(copy.deepcopy(bundle), copy.deepcopy(token), runner.ROOT)
    assert adapter.canonical(first) == adapter.canonical(second)


@pytest.mark.parametrize(("field", "wrong"), [
    ("pmid", "1"), ("pmcid", "PMC1"), ("doi", "10.0000/wrong")])
def test_c_wrong_identity_rejected(state, field, wrong) -> None:
    bundle, token = state
    changed = copy.deepcopy(bundle)
    changed["source"][field] = wrong
    rejected(changed, token, "SOURCE_IDENTITY_MISMATCH")


@pytest.mark.parametrize(("field", "reason"), [
    ("normalized_jats", "NORMALIZED_JATS_HASH_MISMATCH"),
    ("canonical_body", "CANONICAL_BODY_HASH_MISMATCH")])
def test_d_wrong_jats_or_body_hash_rejected(state, field, reason) -> None:
    bundle, token = state
    changed = copy.deepcopy(bundle)
    changed[field] += b" "
    rejected(changed, token, reason)


def test_e_uncommitted_terminal_rejected(state) -> None:
    bundle, token = state
    changed = copy.deepcopy(bundle)
    changed["handoff"]["sources"][0]["terminal"]["journal_entry_hash"] = "0" * 64
    rejected(changed, token, "UNCOMMITTED_TERMINAL_REJECTED")


def test_f_failed_oa_or_jats_gate_rejected(state) -> None:
    bundle, token = state
    jats = copy.deepcopy(bundle)
    jats["gates"]["actual"]["eligible"] = False
    rejected(jats, token, "JATS_GATE_NOT_ELIGIBLE")
    oa = copy.deepcopy(bundle)
    oa["barrier"]["oa_outcomes"][0]["eligibility"]["eligible"] = False
    rejected(oa, token, "OA_ACTIVATION_GATE_FAILED")


def test_g_missing_or_incorrect_opaque_token_rejected(state) -> None:
    bundle, token = state
    rejected(bundle, None, "MISSING_OPAQUE_SOURCE_TOKEN_AUTHORITY")
    wrong = copy.deepcopy(token)
    wrong["opaque_source_token"] = "src_invalid"
    rejected(bundle, wrong, "OPAQUE_SOURCE_TOKEN_INVALID")


def test_h_partial_or_quarantined_body_rejected(state) -> None:
    bundle, token = state
    changed = copy.deepcopy(bundle)
    changed["capture"]["body"].update({
        "completion_state": "BODY_PARTIAL_QUARANTINED",
        "read_returned_normally": False,
        "partial_body_artifact_path": "quarantine/partial.bin",
        "partial_body_sha256": "1" * 64,
    })
    rejected(changed, token, "PARTIAL_OR_QUARANTINED_BODY_REJECTED")


def test_i_altered_evidence_reference_rejected(state) -> None:
    bundle, token = state
    changed = copy.deepcopy(bundle)
    changed["handoff"]["sources"][0]["gates"]["artifact_path"] = "/altered/gates.json"
    rejected(changed, token, "HANDOFF_GATE_REFERENCE_MISMATCH")


def test_j_downstream_deterministic_consumer_preserves_provenance(state) -> None:
    bundle, token = state
    envelope = adapter.adapt_evidence_bundle(bundle, token, runner.ROOT)
    result = adapter.verify_downstream_deterministic_consumer(envelope)
    assert result["status"] == "PASS"
    assert result["source_identity_preserved_controller_private"] is True
    assert result["scientific_candidate_created"] is False


def test_token_authority_uses_frozen_os_randomness_mechanism(state) -> None:
    _, token = state
    assert token["generation"]["mechanism"] == "secrets.token_hex(32)"
    assert token["generation"]["derived_from_source_identity"] is False
    assert Path(runner.ROOT / adapter.TOKEN_AUTHORITY_PATH).is_file()
