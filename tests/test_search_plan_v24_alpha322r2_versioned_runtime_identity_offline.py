# R2 mechanical version fork; original R1 remains byte-frozen.
"""Bounded V2 integrity regressions, separate from frozen 22D scenarios."""

import copy
import os
from pathlib import Path
from unittest.mock import patch

import pytest

from scripts import search_plan_v24_alpha322r2_versioned_runtime_identity_integration as h
from scripts import search_plan_v24_alpha322r2_repair_fixtures as fixtures
from code_engine import append_only_attempt_journal_v1 as legacy
from code_engine import deterministic_resume_planner_v1 as old_resume
from code_engine import stage_barrier_snapshot_v2_r2 as barrier

j, f, t, p = h.j, h.f, h.t, h.p


@pytest.fixture(autouse=True)
def offline():
    with h.r0.d.master.prior.offline_guard():
        yield


def new_writer(tmp_path, frozen=None):
    return j.AppendOnlyAttemptJournalV2(tmp_path / "journal", frozen or h.manifest(), create=True)


def test_explicit_versions_reject_cross_version_manifests_events_and_readers(tmp_path):
    from scripts import run_search_plan_v24_alpha322c_attempt_journal_resume_offline as c
    old = c.manifest()
    with pytest.raises(t.TransportContractError):
        j.FrozenRequestManifestV2(old.serialized)
    with pytest.raises(t.TransportContractError):
        legacy.FrozenRequestManifestV1(h.manifest().serialized)
    with new_writer(tmp_path) as writer:
        h.start(writer)
        verified = writer.verified()
        with pytest.raises(t.TransportContractError):
            old_resume.DeterministicResumePlannerV1().build(verified)
        with pytest.raises(t.TransportContractError):
            legacy.JournalEventV1(verified.events[0].serialized)
    with legacy.AppendOnlyAttemptJournalV1(tmp_path / "v1", old, create=True) as writer:
        c.start(writer)
        with pytest.raises(t.TransportContractError):
            p.DeterministicResumePlannerV2().build(writer.verified())
        with pytest.raises(t.TransportContractError):
            j.JournalEventV2(writer.verified().events[0].serialized)


def test_wal_fsync_precedes_ack_and_original_prefix_is_append_only(tmp_path):
    with new_writer(tmp_path) as writer:
        calls, real_sync = [], os.fsync
        def recorded(fd):
            calls.append(fd)
            return real_sync(fd)
        with patch.object(j.os, "fsync", recorded):
            token = writer.start_attempt("repair:OA:0", timestamp=h.NOW)
        assert writer._fd in calls and writer.dispatch_authorized(token)
        before = j.read_bytes(writer.directory / "segment-0001.jsonl")
        life = t.TransportLifecycleV2(token.context)
        life.start_attempt(token.entry_hash, timestamp=h.NOW)
        writer.record_lifecycle(life, timestamp=h.NOW)
        assert j.read_bytes(writer.directory / "segment-0001.jsonl").startswith(before)


def test_failed_start_fsync_never_authorizes_dispatch(tmp_path):
    with new_writer(tmp_path) as writer:
        with patch.object(j.os, "fsync", side_effect=OSError("synthetic start durability")):
            with pytest.raises(OSError):
                writer.start_attempt("repair:OA:0", timestamp=h.NOW)
        with pytest.raises(t.TransportContractError, match="UNCERTAIN"):
            writer.verified()


def test_writer_and_reader_exclusion(tmp_path):
    with new_writer(tmp_path) as writer:
        with pytest.raises(t.TransportContractError, match="ALREADY_OWNED"):
            j.AppendOnlyAttemptJournalV2(writer.directory, writer.manifest)
        with pytest.raises(t.TransportContractError, match="WRITER_ACTIVE"):
            h.read_plan(writer.directory)


@pytest.mark.parametrize("field,value", [("sequence_number", 2), ("previous_entry_hash", "0" * 64),
    ("run_epoch", "other"), ("stage_id", "other"), ("frozen_request_hash", "0" * 64),
    ("attempt_ordinal", 2), ("runtime_contract_sha256", "0" * 64),
    ("runtime_v2_implementation_manifest_sha256", "0" * 64)])
def test_rehashed_semantic_chain_tamper_denied(tmp_path, field, value):
    with new_writer(tmp_path) as writer:
        writer.start_attempt("repair:OA:0", timestamp=h.NOW)
        record = writer.verified().events[0].record()
        record[field] = value
        record.pop("entry_hash")
        record["entry_hash"] = j.sha(j.canonical(record))
        with pytest.raises(t.TransportContractError):
            j.JournalIntegrityVerifierV2.verify_events((j.JournalEventV2(j.canonical(record)),), writer.manifest, writer.directory)


def test_torn_append_preserved_fail_closed_and_no_repair(tmp_path):
    with new_writer(tmp_path) as writer:
        real_write = os.write
        def torn(fd, raw):
            real_write(fd, raw[:17])
            raise OSError("synthetic torn write")
        with patch.object(j.os, "write", torn):
            with pytest.raises(OSError):
                writer.start_attempt("repair:OA:0", timestamp=h.NOW)
    directory = tmp_path / "journal"
    before = fixtures.snapshot(directory)
    with pytest.raises(t.TransportContractError, match="TORN"):
        h.read_plan(directory)
    frozen = j.FrozenRequestManifestV2(j.read_bytes(directory / "request_manifest.json"))
    report = j.JournalIntegrityVerifierV2.integrity_report(directory, frozen)
    assert report["verified_prefix_count"] == 0 and not report["recovery_authorized"]
    assert fixtures.snapshot(directory) == before


@pytest.mark.parametrize("eligible", [True, False])
def test_success_and_noneligible_skip_no_refresh(tmp_path, eligible):
    with new_writer(tmp_path) as writer:
        h.success(writer, h.start(writer), eligible=eligible)
        frozen = writer.manifest
    before = fixtures.snapshot(tmp_path / "journal")
    one = h.read_plan(tmp_path / "journal")
    two = h.read_plan(tmp_path / "journal")
    assert one == two and one["stage_complete"] and not one["executable_request_ids"]
    assert one["requests"][0]["current_derived_state"] == ("VALID_SUCCESS" if eligible else "VALID_NONELIGIBLE_RESPONSE")
    assert fixtures.snapshot(tmp_path / "journal") == before
    with j.AppendOnlyAttemptJournalV2(tmp_path / "journal", frozen) as writer:
        with pytest.raises(t.TransportContractError):
            h.start(writer)


def test_committed_unknown_never_reclassified_abandoned_or_retried(tmp_path):
    with new_writer(tmp_path) as writer:
        h.failed_attempt(writer, h.start(writer), mode="unknown")
        writer.classify_abandoned(timestamp=h.NOW)
        plan = p.DeterministicResumePlannerV2().build(writer.verified()).record()
        assert plan["requests"][0]["current_derived_state"] == "TERMINAL_TECHNICAL_FAILURE"
        assert plan["requests"][0]["next_authorized_ordinal"] is None
        with pytest.raises(t.TransportContractError):
            h.start(writer)


@pytest.mark.parametrize("safe", [True, False])
@pytest.mark.parametrize("consumed", [1, 2, 3, 4])
def test_frozen_abandoned_rule_preserves_budget_ordinals_and_backoff(safe, consumed):
    saved = p.abandoned_recovery({"replay_safe": safe}, consumed)
    expected = safe and consumed < 4
    assert saved.continuation_authorized is expected
    assert saved.next_ordinal == (consumed + 1 if expected else None)
    assert saved.backoff_seconds == ((2, 4, 8)[consumed - 1] if expected else 0)


def test_barrier_activation_order_and_not_required_preserved(tmp_path):
    keys = ("repair:OA:0", "repair:OA:1", "repair:JATS:0", "repair:JATS:1")
    with new_writer(tmp_path, h.manifest(keys)) as writer:
        with pytest.raises(t.TransportContractError):
            h.start(writer, keys[2])
        with pytest.raises(t.TransportContractError):
            barrier.StageBarrierSnapshotV2.freeze(writer, timestamp=h.NOW)
        h.success(writer, h.start(writer, keys[0]))
        h.success(writer, h.start(writer, keys[1]), eligible=False)
        with pytest.raises(t.TransportContractError):
            h.start(writer, keys[2])
        saved = barrier.StageBarrierSnapshotV2.freeze(writer, timestamp=h.NOW)
        activated = barrier.FrozenActivationManifestV2.freeze(writer, timestamp=h.NOW)
        assert saved.record()["authority"] == legacy.AUTHORITY
        assert activated.record()["activated_request_ids"] == [keys[2]]
        assert activated.record()["not_required_request_ids"] == [keys[3]]
        h.success(writer, h.start(writer, keys[2]))
        plan = p.DeterministicResumePlannerV2().build(writer.verified()).record()
        assert plan["stage_complete"] and plan["requests"][-1]["current_derived_state"] == "NOT_REQUIRED"


def test_no_symlink_or_manifest_overwrite(tmp_path):
    with new_writer(tmp_path) as writer:
        frozen = writer.manifest
    with pytest.raises(t.TransportContractError):
        new_writer(tmp_path)
    with pytest.raises(t.TransportContractError):
        j.atomic_freeze(tmp_path / "journal/request_manifest.json", b"overwrite")
    (tmp_path / "alias").symlink_to(tmp_path / "journal", target_is_directory=True)
    with pytest.raises(t.TransportContractError, match="SYMLINK"):
        j.AppendOnlyAttemptJournalV2(tmp_path / "alias", frozen)


def test_schema_extra_fields_and_invalid_types_fail_closed():
    rule = {"type": "object", "additionalProperties": False,
            "properties": {"value": {"type": "integer", "minimum": 1}}, "required": ["value"]}
    f.validate_schema({"value": 1}, rule)
    for value in ({"value": True}, {"value": 0}, {"value": 1, "extra": 0}, {}):
        with pytest.raises(t.TransportContractError):
            f.validate_schema(value, rule)
