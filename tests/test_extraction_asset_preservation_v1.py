from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from code_engine.extraction_assets.archive import RawResponseArchive
from code_engine.extraction_assets.call_ledger import CallLedger, transition
from code_engine.extraction_assets.coverage import source_presence
from code_engine.extraction_assets.field_evidence import reconstruct_exact_anchor
from code_engine.extraction_assets.identities import (
    call_dedup_identity, sha256_bytes, source_snapshot_identity,
)
from code_engine.extraction_assets.models import (
    AttemptStatus, ExtractionFieldEvidence, IdentityProvenance,
    ParsedExtractionCandidateRevision, ProviderCallAttempt,
    ProviderCallSpecification, SourcePresence, SourceSnapshot, ValueState,
)
from code_engine.extraction_assets.reextraction import deduplicate_by_block
from code_engine.extraction_assets.replayability import classify_replayability
from code_engine.extraction_assets.service import CrashAfterRawPersistence, ExtractionAssetService
from code_engine.extraction.deepseek_client import _error_metadata
from code_engine.extraction.l1_response import GenericJSONResponseError


PROV = IdentityProvenance(producer="test", producer_version="1")


def attempt(status=AttemptStatus.provider_in_flight):
    return ProviderCallAttempt(
        provider_call_attempt_id="a1", provider_call_spec_identity="spec:1",
        call_dedup_identity="dedup:1", attempt_sequence=1, status=status,
        real_api_call=True, identity="attempt:1", provenance=PROV,
    )


def test_source_snapshot_requires_text_when_complete_and_hash_recomputes():
    text = "actually sent"
    row = SourceSnapshot(
        source_snapshot_id="s", document_id="d", source_kind="block", block_id="b",
        input_text=text, input_text_sha256=sha256_bytes(text.encode()), extraction_scope="fulltext_l1",
        source_snapshot_completeness="complete", identity="snapshot:1", provenance=PROV,
    )
    assert row.input_text == text
    with pytest.raises(ValidationError):
        SourceSnapshot(
            source_snapshot_id="s", document_id="d", source_kind="block", block_id="b",
            input_text=None, input_text_sha256=None, extraction_scope="fulltext_l1",
            source_snapshot_completeness="complete", identity="snapshot:1", provenance=PROV,
        )


def test_snapshot_identity_excludes_absolute_path_but_source_hash_changes_identity():
    base = {"block_id": "b", "input_text_sha256": "1", "source_file_path": "/one/a"}
    assert source_snapshot_identity(base) == source_snapshot_identity({**base, "source_file_path": "/two/a"})
    assert source_snapshot_identity(base) != source_snapshot_identity({**base, "input_text_sha256": "2"})


def test_call_identity_binds_prompt_model_params_but_not_parser():
    args = ("snapshot:1", "prompt-hash", "p", "m", {"temperature": 0}, "schema:1", None)
    first = call_dedup_identity(*args)
    assert first != call_dedup_identity("snapshot:1", "new-prompt", "p", "m", {"temperature": 0}, "schema:1", None)
    assert first != call_dedup_identity("snapshot:1", "prompt-hash", "p", "m2", {"temperature": 0}, "schema:1", None)


def test_specification_rejects_secret_fields():
    base = dict(
        provider_call_spec_id="s", source_snapshot_identity="snap", prompt_identity="p",
        prompt_template_identity="pt", rendered_prompt_sha256="h", response_schema_identity="r",
        model_provider="x", model_name="m", parser_contract_identity="parser",
        call_dedup_identity="d", identity="i",
    )
    ProviderCallSpecification(**base, non_secret_parameters={"temperature": 0})
    with pytest.raises(ValidationError):
        ProviderCallSpecification(**base, non_secret_parameters={"api_key": "secret"})
    with pytest.raises(ValidationError):
        ProviderCallSpecification(**base, authorization_header="Bearer secret")


def test_raw_bytes_persist_atomically_before_parser_and_invalid_json_survives(tmp_path):
    archive = RawResponseArchive(tmp_path)
    seen = []
    def parser(raw):
        seen.append(list(tmp_path.rglob("*.raw"))[0].read_bytes())
        return json.loads(raw)
    state, parsed, error, _ = ExtractionAssetService(archive).persist_then_parse(
        attempt(), b'{"x": 1}', parser,
    )
    assert state.status == AttemptStatus.parsed and parsed == {"x": 1} and error is None
    assert seen == [b'{"x": 1}']
    failed, parsed, error, _ = ExtractionAssetService(archive).persist_then_parse(
        attempt(), b'not-json', parser,
    )
    assert failed.status == AttemptStatus.parse_failed and parsed is None and error
    assert any(path.read_bytes() == b"not-json" for path in tmp_path.rglob("*.raw"))


def test_parse_failure_cannot_transition_to_provider_and_dedup_is_cacheable(tmp_path):
    archive = RawResponseArchive(tmp_path)
    failed, _, _, raw_id = ExtractionAssetService(archive).persist_then_parse(
        attempt(), b"x", lambda _: (_ for _ in ()).throw(ValueError("bad")),
    )
    with pytest.raises(ValueError):
        transition(failed, AttemptStatus.provider_in_flight)
    ledger = CallLedger([failed])
    assert ledger.reusable_raw_identity("dedup:1") == raw_id
    assert not ledger.should_call_provider("dedup:1")


def test_crash_after_response_can_resume_from_raw(tmp_path):
    service = ExtractionAssetService(RawResponseArchive(tmp_path))
    with pytest.raises(CrashAfterRawPersistence):
        service.persist_then_parse(attempt(), b'{"ok":true}', json.loads, crash_after_persist=True)
    assert next(tmp_path.rglob("*.raw")).read_bytes() == b'{"ok":true}'


def test_parsed_revision_is_immutable_and_rejects_downstream_science():
    base = dict(
        parsed_candidate_revision_id="r", raw_response_identity="raw:1",
        source_snapshot_identity="snap:1", provider_call_spec_identity="spec:1",
        parser_name="p", parser_version="1", parser_contract_identity="pc:1",
        extraction_schema_name="obs", extraction_schema_version="1",
        parsed_payload_sha256="h", parse_status="parsed", identity="r:1", provenance=PROV,
    )
    row = ParsedExtractionCandidateRevision(**base, parsed_payload={"subject": "x"})
    with pytest.raises(ValidationError):
        row.parser_version = "2"
    for key in ("formal_conflict", "comparability", "hypothesis_validity", "claim_alignment"):
        with pytest.raises(ValidationError):
            ParsedExtractionCandidateRevision(**base, parsed_payload={key: "yes"})


def _field(**updates):
    base = dict(
        field_evidence_id="f", parsed_candidate_revision_identity="r",
        observation_candidate_id="o", field_path="context.species", field_role="context",
        raw_text=None, extracted_value=None, provider_value=None,
        value_state=ValueState.legacy_null_unresolved, evidence_anchor_ids=[],
        source_snapshot_identity="s", source_block_id="b", anchor_status="not_supplied",
        anchor_validation_status="not_assessed", field_schema_status="legacy",
        field_validation_status="not_assessed", normalization_status="not_assessed",
        migration_record=True, identity="f:1", provenance=PROV,
    )
    base.update(updates)
    return ExtractionFieldEvidence(**base)


def test_value_states_are_distinct_and_legacy_null_is_migration_only():
    assert _field().value_state == ValueState.legacy_null_unresolved
    with pytest.raises(ValidationError):
        _field(migration_record=False)
    with pytest.raises(ValidationError):
        _field(value_state=ValueState.not_applicable, migration_record=False)
    with pytest.raises(ValidationError):
        _field(value_state=ValueState.not_mentioned, migration_record=False)
    assert _field(
        value_state=ValueState.invalid, provider_value="bad", migration_record=False,
    ).provider_value == "bad"


def test_provider_missing_defaults_source_presence_unknown():
    assert source_presence(returned_by_provider=False) == SourcePresence.unknown
    assert source_presence(returned_by_provider=False, deterministic_source_audit="absent") == SourcePresence.confirmed_absent


def test_exact_anchor_reconstruction_is_strict_and_hash_bound():
    text = "alpha beta"
    digest = sha256_bytes(text.encode())
    assert reconstruct_exact_anchor(text, "beta", expected_source_sha256=digest)["status"] == "exact"
    assert reconstruct_exact_anchor("x x", "x", expected_source_sha256=sha256_bytes(b"x x"))["status"] == "ambiguous"
    assert reconstruct_exact_anchor(text, "gamma", expected_source_sha256=digest)["status"] == "unresolved"
    assert reconstruct_exact_anchor(text, "beta", expected_source_sha256="bad")["reason"] == "source_hash_mismatch"


def test_replayability_and_block_dedup_are_conservative():
    assert classify_replayability(
        source_available=True, source_complete=True, raw_available=True,
        raw_hash_valid=True, parsed_available=True, parser_identity_available=True,
    ).value == "fully_replayable_zero_api"
    assert classify_replayability(
        source_available=True, source_complete=False, raw_available=False,
        raw_hash_valid=False, parsed_available=True, parser_identity_available=True,
    ).value == "replayable_from_parsed_candidate_only"
    rows = deduplicate_by_block([
        {"source_snapshot_identity": "s", "block_id": "b", "observation_candidate_ids": ["o1"], "missing_capture_profile_fields": ["dose"]},
        {"source_snapshot_identity": "s", "block_id": "b", "observation_candidate_ids": ["o2"], "missing_capture_profile_fields": ["route"]},
    ])
    assert len(rows) == rows[0]["estimated_call_count"] == 1
    assert rows[0]["observation_candidate_ids"] == ["o1", "o2"]
    assert not rows[0]["provider_call_authorized"]


def test_provider_parser_and_schema_failures_are_not_paid_retryable():
    error = GenericJSONResponseError(
        "json_parse_failed", "invalid provider JSON", raw_response="{", parsed_json_type="string",
    )
    assert _error_metadata(error) == ("malformed_json", False, None)
