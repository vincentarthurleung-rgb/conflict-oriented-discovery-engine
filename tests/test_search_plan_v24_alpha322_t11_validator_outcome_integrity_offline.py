"""Additional narrow integrity checks for the structured validator route."""

import copy
from pathlib import Path

import pytest

from scripts import search_plan_v24_alpha322_t11_validator_outcome_fixtures_v1 as f

h, j, t = f.h, f.j, f.t


@pytest.fixture(autouse=True)
def offline():
    with h.dr.master.prior.offline_guard():
        yield


@pytest.mark.parametrize("tamper,reason", [
    ("accepted_conflict", "VALIDATOR_OUTCOME_CONFLICT"),
    ("unsupported_actual_result", "UNSUPPORTED_VALIDATOR_RESULT"),
    ("other_request", "REQUEST_IDENTITY_MISMATCH"),
    ("other_attempt", "ATTEMPT_IDENTITY_MISMATCH"),
    ("other_raw", "RAW_ARTIFACT_HASH_MISMATCH")])
def test_actual_result_receipt_tampering_rejected_at_exact_rule(tmp_path, tamper, reason):
    with j.AppendOnlyAttemptJournalV2(tmp_path / "journal", h.manifest(), create=True) as writer:
        lifecycle, response = h.prepare_complete(writer)
        item = h.prepare_result(writer, lifecycle, False, response=response)
        data = f.payload(item)
        reference = data["validator_outcome"]
        path = Path(reference["artifact_path"])
        original = j.read_bytes(path)
        saved = j.strict_json(original)
        if tamper == "accepted_conflict":
            saved["accepted"] = True
        elif tamper == "unsupported_actual_result":
            saved["actual_validator_result"] = 0
        elif tamper == "other_request":
            saved["attempt_identity"]["logical_request_id"] = "different-request"
        elif tamper == "other_attempt":
            saved["attempt_identity"]["attempt_ordinal"] = 2
        else:
            saved["raw_artifact"]["sha256"] = "0" * 64
        j.atomic_freeze(writer.directory / "preserved-original-receipt.json", original)
        # Deliberately corrupt only this new isolated test fixture.
        damaged = j.canonical(saved)
        path.write_bytes(damaged)
        reference.update(sha256=j.sha(damaged), byte_count=len(damaged))
        with pytest.raises(t.TransportContractError, match="^" + reason + "$"):
            f.candidate(writer, data)


@pytest.mark.parametrize("tamper,reason", [
    ("unknown_mapping", "VALIDATOR_RESULT_CANNOT_REPLACE_TRANSPORT_FAILURE"),
    ("numeric_false_retry", "PERSISTED_RETRY_DECISION_INCONSISTENT"),
    ("eligibility_for_failure", "VALIDITY_FAILURE_OUTCOME_CONFLICT")])
def test_unknown_transport_and_inconsistent_terminal_cannot_be_laundered(tmp_path, tamper, reason):
    with j.AppendOnlyAttemptJournalV2(tmp_path / "journal", h.manifest(), create=True) as writer:
        lifecycle, response = h.prepare_complete(writer)
        item = h.prepare_result(writer, lifecycle, False, response=response)
        data = f.payload(item)
        if tamper == "unknown_mapping":
            data["mapped_observation"]["mapping"]["semantic_failure_class"] = "UNKNOWN_RUNTIME_FAILURE"
        elif tamper == "numeric_false_retry":
            data["retry_decision"]["retry_authorized"] = 0
        else:
            data["eligibility"] = {"authority_sha256": writer.manifest.record()["requests"][0]["eligibility_authority_sha256"], "eligible": True}
        unchanged = copy.deepcopy(data)
        with pytest.raises(t.TransportContractError, match="^" + reason + "$"):
            f.candidate(writer, data)
        assert data["mapped_observation"] == unchanged["mapped_observation"]


def test_actual_nonempty_partial_response_never_invokes_validator(tmp_path):
    with j.AppendOnlyAttemptJournalV2(tmp_path / "journal", h.manifest(), create=True) as writer:
        item = h.r2.failed_attempt(writer, h.r2.start(writer), mode="partial", commit=False)
        calls = []
        with pytest.raises(t.TransportContractError):
            t.guarded_parse(item["response"], lambda raw: calls.append(raw))
        assert calls == []
        with pytest.raises(t.TransportContractError, match="^VALIDATION_REQUIRES_AUTHORITATIVE_COMPLETE_RESPONSE$"):
            h.validity.record_result(writer, item["lifecycle"], False, kind="literal_boolean", timestamp=h.NOW,
                                     response=item["response"])


def test_no_validator_contract_switch_after_request_freeze(tmp_path):
    with j.AppendOnlyAttemptJournalV2(tmp_path / "journal", h.manifest(), create=True) as writer:
        lifecycle, response = h.prepare_complete(writer)
        actual = {"schema_version": "JATSPrimarySourceIdentityContractV2", "source_identity_allows_progression": False}
        with pytest.raises(t.TransportContractError, match="^VALIDATOR_AUTHORITY$"):
            h.validity.record_result(writer, lifecycle, actual, kind="jats_primary_identity_v2", timestamp=h.NOW, response=response)
