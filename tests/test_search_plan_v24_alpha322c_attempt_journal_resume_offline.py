"""22C durability/reconstruction tests; independent 22D remains deferred."""

import os
import urllib.error
from unittest.mock import patch

import pytest

from scripts import run_search_plan_v24_alpha322c_attempt_journal_resume_offline as c

j, p, s, t, o, b = c.j, c.p, c.s, c.t, c.o, c.b


@pytest.fixture(autouse=True)
def offline():
    with c.master.prior.offline_guard():
        yield


@pytest.fixture
def frozen():
    return c.manifest()


def open_new(tmp_path, frozen):
    return j.AppendOnlyAttemptJournalV1(tmp_path / "journal", frozen, create=True,
                                      redactor=o.SecretRedactorV1(("synthetic-private-credential",)))


def snapshot(directory):
    return {str(path.relative_to(directory)): path.read_bytes() for path in directory.rglob("*") if path.is_file()}


def altered_manifest(frozen, callback):
    record = frozen.record()
    callback(record)
    return j.FrozenRequestManifestV1(c.canonical(record))


def test_all_frozen_authorities_and_actual_A_B_interfaces():
    authority = c.verify_authority()
    assert authority["master"]["verified"] and authority["alpha322a"]["verified"] and authority["alpha322b"]["verified"]
    assert authority["closure"]["verified"] and authority["counts"] == c.master.COUNTS
    assert j.POLICY.maximum_attempts == 4 and j.POLICY.timeout_seconds == 60 and j.POLICY.backoff_seconds == (2, 4, 8)
    assert len(j._observation_schemas()) == 5


@pytest.mark.parametrize("field,value", [("run_id", "alpha3.21 continuation"), ("run_epoch", "ALPHA3_21"),
    ("stage_id", "alpha-3-21D2"), ("authority", {}), ("schema_version", "wrong"), ("activation_contract_sha256", "bad")])
def test_bad_manifest_authority_and_historical_execution_denied(frozen, field, value):
    with pytest.raises(t.TransportContractError):
        altered_manifest(frozen, lambda record: record.update({field: value}))


@pytest.mark.parametrize("field,value", [("replay_safe", 1), ("maximum_attempts", 5), ("execution_order", True),
    ("stage", "OTHER"), ("request_payload_sha256", "0" * 64), ("validity_authority_sha256", "bad")])
def test_request_binding_rejects_hash_policy_and_type_drift(frozen, field, value):
    with pytest.raises(t.TransportContractError):
        altered_manifest(frozen, lambda record: record["requests"][0].update({field: value}))


def test_manifest_unknown_ID_secret_duplicate_and_noncanonical_rejected(frozen):
    with pytest.raises(t.TransportContractError, match="UNKNOWN"):
        frozen.request("new request")
    with pytest.raises(t.TransportContractError):
        j.FrozenRequestManifestV1(frozen.serialized.rstrip())
    with pytest.raises(t.TransportContractError):
        altered_manifest(frozen, lambda record: record["requests"].append(record["requests"][0]))
    with pytest.raises(t.TransportContractError):
        altered_manifest(frozen, lambda record: record.update({"run_id": "token=secret"}))
    with pytest.raises(t.TransportContractError, match="DUPLICATE_JSON_KEY"):
        j.strict_json(b'{"x":1,"x":2}')


def test_fsync_precedes_ack_and_lifecycle_dispatch_binding(tmp_path, frozen):
    with open_new(tmp_path, frozen) as writer:
        calls = []
        real_sync = os.fsync
        def recording(fd):
            calls.append(fd)
            return real_sync(fd)
        with patch.object(j.os, "fsync", recording):
            token = writer.start_attempt("synthetic:OA:0", timestamp=c.NOW)
        assert calls and writer.dispatch_authorized(token)
        event = writer.verified().events[0].record()
        assert event["event_type"] == "ATTEMPT_STARTED" and event["attempt_ordinal"] == 1
        assert event["event_payload"]["authority"] == j.AUTHORITY
        lifecycle = t.TransportLifecycleV2(token.context)
        lifecycle.start_attempt(token.entry_hash, timestamp=c.NOW)
        writer.record_lifecycle(lifecycle, timestamp=c.NOW)
        assert len(writer.verified().events) == 2


def test_fsync_failure_does_not_authorize_dispatch_and_poison_writer(tmp_path, frozen):
    with open_new(tmp_path, frozen) as writer:
        with patch.object(j.os, "fsync", side_effect=OSError("synthetic durability failure")):
            with pytest.raises(OSError):
                writer.start_attempt("synthetic:OA:0", timestamp=c.NOW)
        with pytest.raises(t.TransportContractError, match="UNCERTAIN"):
            writer.verified()
    # Conservatively consumed if a whole record survived; never reused.
    first = c.read_plan(tmp_path / "journal")["requests"][0]
    assert first["attempts_consumed"] == 1 and first["next_authorized_ordinal"] == 2


def test_crash_during_append_preserves_torn_tail_no_dispatch_or_repair(tmp_path, frozen):
    with open_new(tmp_path, frozen) as writer:
        real_write = os.write
        def partial(fd, raw):
            real_write(fd, raw[:17])
            raise OSError("synthetic crash")
        with patch.object(j.os, "write", partial):
            with pytest.raises(OSError):
                writer.start_attempt("synthetic:OA:0", timestamp=c.NOW)
    directory = tmp_path / "journal"
    before = snapshot(directory)
    with pytest.raises(t.TransportContractError, match="TORN"):
        j.AppendOnlyAttemptJournalV1(directory, frozen)
    with pytest.raises(t.TransportContractError, match="TORN"):
        c.read_plan(directory)
    report = j.JournalIntegrityVerifierV1.integrity_report(directory, frozen)
    assert report["verified_prefix_count"] == 0 and not report["recovery_authorized"]
    assert snapshot(directory) == before


def test_whole_tail_line_without_newline_is_not_committed(frozen, tmp_path):
    with open_new(tmp_path, frozen) as writer:
        writer.start_attempt("synthetic:OA:0", timestamp=c.NOW)
    source = tmp_path / "journal"
    copied = tmp_path / "corrupt"
    with j.AppendOnlyAttemptJournalV1(copied, frozen, create=True):
        pass
    raw = (source / "segment-0001.jsonl").read_bytes().rstrip(b"\n")
    with (copied / "segment-0001.jsonl").open("ab") as handle:
        handle.write(raw)
    with pytest.raises(t.TransportContractError, match="TORN"):
        c.read_plan(copied)


def test_exclusive_writer_and_reader_contention_fail_closed(tmp_path, frozen):
    with open_new(tmp_path, frozen) as writer:
        with pytest.raises(t.TransportContractError, match="ALREADY_OWNED"):
            j.AppendOnlyAttemptJournalV1(writer.directory, frozen)
        with pytest.raises(t.TransportContractError, match="WRITER_ACTIVE"):
            c.read_plan(writer.directory)
        assert not writer.verified().events
    with j.AppendOnlyAttemptJournalV1(tmp_path / "journal", frozen) as reopened:
        assert not reopened.verified().events


def test_no_overwrite_symlink_or_manifest_drift(tmp_path, frozen):
    with open_new(tmp_path, frozen):
        pass
    with pytest.raises(t.TransportContractError):
        open_new(tmp_path, frozen)
    with pytest.raises(t.TransportContractError):
        j.atomic_freeze(tmp_path / "journal/request_manifest.json", b"rewrite")
    other = altered_manifest(frozen, lambda record: record.update({"run_epoch": "different"}))
    with pytest.raises(t.TransportContractError, match="MANIFEST_CHANGED"):
        j.AppendOnlyAttemptJournalV1(tmp_path / "journal", other)
    (tmp_path / "alias").symlink_to(tmp_path / "journal", target_is_directory=True)
    with pytest.raises(t.TransportContractError, match="SYMLINK"):
        j.AppendOnlyAttemptJournalV1(tmp_path / "alias", frozen)


@pytest.mark.parametrize("field,value", [("sequence_number", 2), ("previous_entry_hash", "0" * 64),
    ("run_epoch", "another"), ("frozen_request_hash", "0" * 64), ("attempt_ordinal", 2), ("runtime_contract_sha256", "0" * 64)])
def test_rehashed_tampering_still_rejected_by_semantic_integrity(tmp_path, frozen, field, value):
    with open_new(tmp_path, frozen) as writer:
        writer.start_attempt("synthetic:OA:0", timestamp=c.NOW)
        record = writer.verified().events[0].record()
        record[field] = value
        record["entry_hash"] = j.sha(c.canonical({k: v for k, v in record.items() if k != "entry_hash"}))
        with pytest.raises(t.TransportContractError):
            j.JournalIntegrityVerifierV1.verify_events((j.JournalEventV1(c.canonical(record)),), frozen, writer.directory)


@pytest.mark.parametrize("safe", [True, False])
@pytest.mark.parametrize("ordinal", [1, 2, 3, 4])
def test_abandoned_budget_no_ordinal_reuse_and_no_unknown_reclassification(tmp_path, safe, ordinal):
    frozen = c.manifest(safe=safe)
    # Replay-unsafe requests cannot reach ordinal >1; recovery pure contract can
    # nevertheless reject all consumed ordinals without assuming favorable facts.
    recovery = p.abandoned_recovery(frozen.request("synthetic:OA:0"), ordinal)
    assert recovery.continuation_authorized is (safe and ordinal < 4)
    assert recovery.next_ordinal == (ordinal + 1 if safe and ordinal < 4 else None)
    assert recovery.backoff_seconds == ((2, 4, 8)[ordinal - 1] if safe and ordinal < 4 else 0)
    assert recovery.state == j.ABANDONED
    if safe or ordinal == 1:
        with open_new(tmp_path, frozen) as writer:
            for consumed in range(1, ordinal + 1):
                lifecycle = c.start(writer)
                if consumed != ordinal:
                    c.terminal(writer, lifecycle, failure="timeout")
        before = c.read_plan(tmp_path / "journal")
        first = before["requests"][0]
        assert first["current_derived_state"] == j.ABANDONED and first["attempts_consumed"] == ordinal
        assert first["next_authorized_ordinal"] == recovery.next_ordinal
        with j.AppendOnlyAttemptJournalV1(tmp_path / "journal", frozen) as writer:
            writer.classify_abandoned(timestamp=c.NOW)
            if recovery.continuation_authorized:
                next_attempt = c.start(writer)
                assert next_attempt.context.attempt_ordinal == ordinal + 1
            else:
                with pytest.raises(t.TransportContractError):
                    c.start(writer)


@pytest.mark.parametrize("failure,expected", [("timeout", "RETRYABLE_FAILURE_WITH_BUDGET"),
    ("unknown", "TERMINAL_TECHNICAL_FAILURE"), ("invalid", "TERMINAL_RESPONSE_VALIDITY_FAILURE"),
    ("partial", "RETRYABLE_FAILURE_WITH_BUDGET")])
def test_persisted_A_B_decision_reused_not_exception_message_reclassified(tmp_path, frozen, failure, expected):
    with open_new(tmp_path, frozen) as writer:
        decision = c.terminal(writer, c.start(writer), failure=failure)
    recovered = c.read_plan(tmp_path / "journal")
    assert recovered["requests"][0]["current_derived_state"] == expected
    assert recovered["requests"][0]["next_authorized_ordinal"] == decision["retry"]["next_attempt_ordinal"]
    assert recovered["requests"][0]["backoff_seconds"] == decision["retry"]["backoff_selected_seconds"]
    if failure == "unknown":
        assert decision["mapping"]["semantic_failure_class"] == "UNKNOWN_RUNTIME_FAILURE"
        with j.AppendOnlyAttemptJournalV1(tmp_path / "journal", frozen) as writer:
            writer.classify_abandoned(timestamp=c.NOW)
            with pytest.raises(t.TransportContractError):
                c.start(writer)


@pytest.mark.parametrize("eligible", [True, False])
def test_success_and_valid_noneligible_terminal_skip_forever(tmp_path, frozen, eligible):
    with open_new(tmp_path, frozen) as writer:
        c.terminal(writer, c.start(writer), eligible=eligible)
    before = snapshot(tmp_path / "journal")
    for _ in range(3):
        recovered = c.read_plan(tmp_path / "journal")
        assert recovered["stage_complete"] and not recovered["executable_request_ids"]
        assert recovered["requests"][0]["current_derived_state"] == ("VALID_SUCCESS" if eligible else "VALID_NONELIGIBLE_RESPONSE")
    assert snapshot(tmp_path / "journal") == before
    with j.AppendOnlyAttemptJournalV1(tmp_path / "journal", frozen) as writer:
        with pytest.raises(t.TransportContractError):
            c.start(writer)


@pytest.mark.parametrize("defect", ["missing", "corrupt", "symlink"])
def test_committed_success_raw_must_remain_verified_no_refresh(tmp_path, frozen, defect):
    with open_new(tmp_path, frozen) as writer:
        c.terminal(writer, c.start(writer))
    source = next((tmp_path / "journal").glob("raw-*.xml"))
    preserved = tmp_path / "preserved.xml"
    source.rename(preserved)
    if defect == "corrupt":
        j.atomic_freeze(source, b"different bytes")
    elif defect == "symlink":
        source.symlink_to(preserved)
    with pytest.raises((t.TransportContractError, FileNotFoundError)):
        c.read_plan(tmp_path / "journal")


def test_orphan_complete_raw_is_abandoned_not_success(tmp_path, frozen):
    with open_new(tmp_path, frozen) as writer:
        response = c.frozen_body(writer, c.start(writer))
    before = c.read_plan(tmp_path / "journal")
    assert before["requests"][0]["current_derived_state"] == j.ABANDONED
    assert response.artifact.verified_bytes() == b"<synthetic/>"
    with j.AppendOnlyAttemptJournalV1(tmp_path / "journal", frozen) as writer:
        writer.classify_abandoned(timestamp=c.NOW)
        c.terminal(writer, c.start(writer))
    assert c.read_plan(tmp_path / "journal")["stage_complete"]
    assert response.artifact.verified_bytes() == b"<synthetic/>"


def test_frozen_order_rejects_unresolved_request_reordering(tmp_path):
    frozen = c.manifest(3)
    with open_new(tmp_path, frozen) as writer:
        with pytest.raises(t.TransportContractError, match="FIRST_AUTHORIZED"):
            c.start(writer, "synthetic:OA:1")
        c.terminal(writer, c.start(writer, "synthetic:OA:0"))
        assert c.plan(writer.verified())["next_executable_request_id"] == "synthetic:OA:1"


def test_duplicate_terminal_and_lifecycle_after_terminal_denied(tmp_path, frozen):
    with open_new(tmp_path, frozen) as writer:
        c.terminal(writer, c.start(writer))
        saved = writer.verified().events[-1].record()
        with pytest.raises(t.TransportContractError, match="TERMINAL"):
            writer._append("ATTEMPT_TERMINAL", saved["logical_request_id"], saved["attempt_ordinal"], saved["event_payload"], c.NOW)


@pytest.mark.parametrize("corruption", ["retry", "missing_retry", "authority", "eligibility", "validation", "body", "context"])
def test_terminal_provenance_tampering_rehashed_still_fails_closed(tmp_path, frozen, corruption):
    with open_new(tmp_path, frozen) as writer:
        c.terminal(writer, c.start(writer))
        verified = writer.verified()
        record = verified.events[-1].record()
        payload = record["event_payload"]
        if corruption == "retry":
            payload["retry_decision"]["retry_authorized"] = True
        elif corruption == "missing_retry":
            payload["mapped_observation"]["observation"]["retry_decision_provenance"] = None
        elif corruption == "authority":
            payload["mapped_observation"]["mapping"]["mapping_table_sha256"] = "0" * 64
        elif corruption == "eligibility":
            payload["eligibility"]["eligible"] = False
        elif corruption == "validation":
            payload["validation"]["accepted"] = False
        elif corruption == "body":
            payload["mapped_observation"]["observation"]["body_read_provenance"]["completion_state"] = "BODY_INTERRUPTED"
        else:
            payload["mapped_observation"]["observation"]["logical_request_id"] = "unknown"
        record["entry_hash"] = j.sha(c.canonical({k: v for k, v in record.items() if k != "entry_hash"}))
        with pytest.raises(t.TransportContractError):
            j.JournalIntegrityVerifierV1.verify_events((*verified.events[:-1], j.JournalEventV1(c.canonical(record))), frozen, writer.directory)


def ready_barrier(tmp_path, *, activate=True):
    frozen = c.manifest(2, two_phase=True)
    writer = open_new(tmp_path, frozen)
    c.terminal(writer, c.start(writer, "synthetic:OA:0"))
    c.terminal(writer, c.start(writer, "synthetic:OA:1"), eligible=False)
    barrier = s.StageBarrierSnapshotV1.freeze(writer, timestamp=c.NOW)
    activation = s.FrozenActivationManifestV1.freeze(writer, timestamp=c.NOW) if activate else None
    return writer, frozen, barrier, activation


def test_barrier_and_activation_exact_reuse_no_recomputation(tmp_path):
    writer, frozen, barrier, activation = ready_barrier(tmp_path)
    with writer:
        before = snapshot(writer.directory)
        assert s.StageBarrierSnapshotV1.freeze(writer, timestamp=c.NOW) == barrier
        assert s.FrozenActivationManifestV1.freeze(writer, timestamp=c.NOW) == activation
        assert snapshot(writer.directory) == before
        assert activation.record()["activated_request_ids"] == ["synthetic:JATS:0"]
        assert activation.record()["not_required_request_ids"] == ["synthetic:JATS:1"]
        recovered = c.plan(writer.verified())
        assert recovered["requests"][3]["current_derived_state"] == "NOT_REQUIRED"
        with pytest.raises(t.TransportContractError):
            c.start(writer, "synthetic:JATS:1")


@pytest.mark.parametrize("which", ["stage_barrier.json", "activation_manifest.json"])
def test_missing_committed_barrier_or_activation_fails_closed(tmp_path, which):
    writer, frozen, _, _ = ready_barrier(tmp_path)
    writer.close()
    source = tmp_path / "journal" / which
    source.rename(tmp_path / ("preserved-" + which))
    with pytest.raises((t.TransportContractError, FileNotFoundError)):
        c.read_plan(tmp_path / "journal")


def test_prebarrier_JATS_and_partial_barrier_not_admitted(tmp_path):
    frozen = c.manifest(1, two_phase=True)
    with open_new(tmp_path, frozen) as writer:
        with pytest.raises(t.TransportContractError):
            c.start(writer, "synthetic:JATS:0")
        with pytest.raises(t.TransportContractError, match="NOT_COMPLETE"):
            s.StageBarrierSnapshotV1.freeze(writer, timestamp=c.NOW)
        c.terminal(writer, c.start(writer))
        j.atomic_freeze(writer.directory / "stage_barrier.json", b'{"partial":')
        with pytest.raises(t.TransportContractError, match="PARTIAL"):
            s.StageBarrierSnapshotV1.freeze(writer, timestamp=c.NOW)
        with pytest.raises(t.TransportContractError):
            c.start(writer, "synthetic:JATS:0")


def test_complete_orphan_barrier_and_activation_recovered_only_by_exact_identity(tmp_path):
    frozen = c.manifest(1, two_phase=True)
    with open_new(tmp_path, frozen) as writer:
        c.terminal(writer, c.start(writer))
        states, _, _ = j._reduce(writer.verified().events, frozen)
        expected = c.canonical(s.barrier_record(frozen, states))
        j.atomic_freeze(writer.directory / "stage_barrier.json", expected)
    before = (tmp_path / "journal/stage_barrier.json").read_bytes()
    with j.AppendOnlyAttemptJournalV1(tmp_path / "journal", frozen) as writer:
        barrier = s.StageBarrierSnapshotV1.freeze(writer, timestamp=c.NOW)
        assert barrier.serialized == before
        j.atomic_freeze(writer.directory / "activation_manifest.json", c.canonical(s.activation_record(frozen, barrier)))
    with j.AppendOnlyAttemptJournalV1(tmp_path / "journal", frozen) as writer:
        s.FrozenActivationManifestV1.freeze(writer, timestamp=c.NOW)
        assert c.plan(writer.verified())["next_executable_request_id"] == "synthetic:JATS:0"


def test_secret_redaction_precedes_hash_and_preserves_A_schema(tmp_path, frozen):
    with open_new(tmp_path, frozen) as writer:
        c.terminal(writer, c.start(writer), failure="timeout")
        records = [r.record() for r in writer.verified().events]
    raw = (tmp_path / "journal/segment-0001.jsonl").read_bytes()
    assert b"synthetic-private-credential" not in raw and b"[REDACTED]" in raw
    mapped = records[-1]["event_payload"]["mapped_observation"]
    c.prior.prior.validate_observation(mapped["observation"])
    assert mapped["observation"]["journal_persistence_implemented"] is False
    assert mapped["observation"]["process_resume_implemented"] is False
    j.JournalEventV1(c.canonical(records[-1]))


@pytest.mark.parametrize("form", ["wrapped_timeout", "http_retry", "http_terminal"])
def test_consumes_existing_B_wrapper_and_HTTP_mapping_without_new_matrix(tmp_path, frozen, form):
    with open_new(tmp_path, frozen) as writer:
        lifecycle = c.start(writer)
        if form == "wrapped_timeout":
            exception = urllib.error.URLError(TimeoutError("synthetic-private-credential"))
            facts = b.TransportMappingFactsV2(lifecycle.state, b.BOUND_CLIENT_IDENTITY_SHA256)
            http = None
        else:
            status = 503 if form == "http_retry" else 404
            exception = urllib.error.HTTPError("https://synthetic.invalid/", status, "synthetic status", {}, None)
            facts = b.TransportMappingFactsV2(lifecycle.state, b.BOUND_CLIENT_IDENTITY_SHA256, True, status, "BOUND_HTTP_ERROR")
            http = o.HttpResponseProvenanceV1.capture(lifecycle.context, writer.redactor, method="GET", status=status, trusted=True, status_origin="BOUND_HTTP_ERROR")
        decision = b.classify_transport_failure_and_decide_retry_v2(exception, facts, request_replay_safe=True, attempt_ordinal=1)
        observation = b.mapped_observation_v2(decision, lifecycle, writer.redactor, original_exception=exception, http=http,
            replay_safety_authority={"manifest_sha256": frozen.sha256, "request_id": lifecycle.context.logical_request_id})
        writer.commit_terminal(lifecycle, decision, observation, timestamp=c.NOW)
    recovered = c.read_plan(tmp_path / "journal")
    assert recovered["requests"][0]["retry_continuation_eligible"] is (form != "http_terminal")


def test_raw_file_and_directory_sync_before_terminal_append(tmp_path, frozen):
    with open_new(tmp_path, frozen) as writer:
        sequence = []
        real_sync, real_append = os.fsync, writer._append
        def sync(fd):
            sequence.append("sync")
            real_sync(fd)
        def append(kind, *args):
            sequence.append(kind)
            return real_append(kind, *args)
        with patch.object(j.os, "fsync", sync), patch.object(writer, "_append", append):
            c.terminal(writer, c.start(writer))
        terminal_position = sequence.index("ATTEMPT_TERMINAL")
        assert sequence[terminal_position - 1] == "sync"
        assert sequence[terminal_position + 1] == "sync"


def test_started_prefix_plus_torn_progress_never_recovered_as_not_started(tmp_path, frozen):
    with open_new(tmp_path, frozen) as writer:
        lifecycle = c.start(writer)
        lifecycle.receive_headers(200, trustworthy=True, evidence_reference="synthetic", timestamp=c.NOW)
        real_write = os.write
        def partial(fd, raw):
            real_write(fd, raw[:11])
            raise OSError("synthetic append interruption")
        with patch.object(j.os, "write", partial):
            with pytest.raises(OSError):
                writer.record_lifecycle(lifecycle, timestamp=c.NOW)
    report = j.JournalIntegrityVerifierV1.integrity_report(tmp_path / "journal", frozen)
    assert report["verified_prefix_count"] == 2 and not report["recovery_authorized"]
    with pytest.raises(t.TransportContractError, match="TORN"):
        c.read_plan(tmp_path / "journal")


def test_unclassified_open_attempt_cannot_start_next_attempt(tmp_path, frozen):
    with open_new(tmp_path, frozen) as writer:
        c.start(writer)
        before = len(writer.verified().events)
        with pytest.raises(t.TransportContractError):
            c.start(writer)
        assert len(writer.verified().events) == before


def test_barrier_activation_same_writer_and_frozen_order(tmp_path):
    writer, frozen, barrier, activation = ready_barrier(tmp_path)
    with writer:
        c.terminal(writer, c.start(writer, "synthetic:JATS:0"))
        recovered = c.plan(writer.verified())
        assert recovered["stage_complete"] and recovered["activation_sha256"] == activation.sha256
        assert recovered["barrier_sha256"] == barrier.sha256


def test_invalid_phase_order_and_unfrozen_activation_parent_rejected():
    frozen = c.manifest(1, two_phase=True)
    with pytest.raises(t.TransportContractError):
        altered_manifest(frozen, lambda record: record["requests"][1]["request_payload"].update({"oa_request_id": "unknown"}))


def test_pure_planner_does_not_invoke_sleep_or_external_adapters(tmp_path, frozen):
    with open_new(tmp_path, frozen) as writer:
        c.terminal(writer, c.start(writer), failure="timeout")
    directory = tmp_path / "journal"
    before = snapshot(directory)
    verified = j.JournalIntegrityVerifierV1.read(directory, frozen)
    with patch.object(b, "classify_transport_failure_and_decide_retry_v2", side_effect=AssertionError("no remapping")):
        first = p.DeterministicResumePlannerV1().build(verified)
        second = p.DeterministicResumePlannerV1().build(verified)
    assert first.serialized == second.serialized and snapshot(directory) == before


def test_synthetic_two_phase_fresh_process_recovery(tmp_path):
    result = c.two_phase(tmp_path / "two_phase")
    assert result["check_passed"]
    assert result["before_resume"]["executable_request_ids"] == ["synthetic:JATS:1", "synthetic:JATS:2"]
    assert result["after_resume"]["stage_complete"]


def test_twenty_actual_process_crashes_and_readonly_recovery(tmp_path):
    matrix = c.crash_matrix(tmp_path / "matrix")
    assert matrix["case_count"] == matrix["pass_count"] == 20 and matrix["fail_count"] == 0
    assert {r["case_id"] for r in matrix["cases"]} == set(c.CRASH_CASES)
    assert all(r["fresh_process_crash_exit_code"] == 73 for r in matrix["cases"])


def test_boundary_audit_and_no_unfrozen_production_activation():
    assert c.boundary_audit()["check_passed"]
    assert j.RUNTIME_ACTIVATION_ALLOWED is False
    assert len(c.REQUIRED) == 48
