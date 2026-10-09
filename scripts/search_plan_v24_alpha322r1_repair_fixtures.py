"""R1 execution of literal frozen R0 oracles, never the 22D matrix.

Each corruption has its own synthetic journal. Expectations are read from the
pre-implementation R0 files, not inferred from the implementation under test.
"""

import copy
import dataclasses
import json
import os
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

from scripts import search_plan_v24_alpha322r1_versioned_phase_binding_integration as h

j, f, t, p, o, b = h.j, h.f, h.t, h.p, h.o, h.b


def snapshot(directory):
    return {str(path.relative_to(directory)): j.sha(j.read_bytes(path)) for path in directory.rglob("*") if path.is_file()}


def source_spec(name):
    return j.strict_json(j.read_bytes(f.R0 / (name + ".json")))


def write_json(path, record):
    return dict(j.atomic_freeze(path, j.canonical(record)).__dict__)


def payload(item):
    retry = item["decision"].record()["retry"]
    return {"outcome": "RETRYABLE_FAILURE_WITH_BUDGET" if retry["retry_authorized"] else retry["terminal_state"],
        "mapped_observation": item["observation"].record(), "retry_decision": retry,
        "raw_artifact": dict(item["artifact"].__dict__) if item["artifact"] else None,
        "validation": None, "eligibility": None, "failure_phase_binding": item["binding"].record()}


def candidate(writer, data, prefix=None):
    """Use the complete V2 verifier for an uncommitted terminal proposal."""
    prefix = list(writer.verified().events) if prefix is None else list(prefix)
    last = prefix[-1].record()
    record = copy.deepcopy(last)
    record.update(sequence_number=len(prefix) + 1, previous_entry_hash=last["entry_hash"],
        event_type="ATTEMPT_TERMINAL", timestamp=h.NOW, event_payload=data)
    record.pop("entry_hash")
    record["entry_hash"] = j.sha(j.canonical(record))
    return j.JournalIntegrityVerifierV2.verify_events(tuple(prefix + [j.JournalEventV2(j.canonical(record))]), writer.manifest, writer.directory)


def positive(directory, mode="reset"):
    with j.AppendOnlyAttemptJournalV2(directory, h.manifest(), create=True) as writer:
        item = h.failed_attempt(writer, h.start(writer), mode=mode)
        journal = writer.verified()
        plan = p.DeterministicResumePlannerV2().build(journal).record()
        binding = item["binding"].record()
        if item["response"] is not None:
            invoked = []
            try:
                t.guarded_parse(item["response"], lambda raw: invoked.append(raw))
                raise AssertionError("PARTIAL_PARSER_ADMITTED")
            except t.TransportContractError:
                pass
            assert not invoked
        first = plan["requests"][0]
        actual = {"semantic_failure_class": item["decision"].record()["mapping"]["semantic_failure_class"],
            "retry_authorized": item["decision"].record()["retry"]["retry_authorized"],
            "durable_terminal_committed": journal.events[-1].record()["event_type"] == "ATTEMPT_TERMINAL",
            "terminal_logical_state": first["current_derived_state"], "attempts_consumed": first["attempts_consumed"],
            "remaining_attempts": first["remaining_attempts"], "next_attempt_ordinal": first["next_authorized_ordinal"],
            "backoff_seconds": first["backoff_seconds"], **{key: binding["raw_admission"][key] for key in
                ("raw_artifact_frozen", "body_complete", "authoritative", "parser_eligible")},
            "parser_invocations": 0, "network_calls": 0}
        expected = source_spec("repair_positive_fixture_specification")["expected"]
        phases = {"occurrence": binding["occurrence_evidence"]["failure_occurrence_phase"],
                  "mapping": binding["mapping_evidence"]["mapping_evidence_phase"],
                  "persistence": binding["terminal_persistence_phase"]}
        raw = j.read_bytes(Path(item["artifact"].artifact_path))
        return {"fixture_id": "R0_P01" if mode == "reset" else "R1_NONEMPTY_PARTIAL_SUPPLEMENT",
            "expected": expected, "actual": actual, "passed": actual == expected,
            "phases": phases, "raw_byte_count": len(raw), "raw_sha256": j.sha(raw),
            "journal_event_count": len(journal.events), "parser_rejection_verified": True,
            "raw_partial_body_artifact_path": item["artifact"].artifact_path}


def mutate_ref(writer, old, label, callback):
    value = j.strict_json(j.read_bytes(Path(old["artifact_path"])))
    callback(value)
    return write_json(writer.directory / (label + ".json"), value)


def update_occurrence(writer, binding, label, callback):
    ref = binding["occurrence_evidence"]["artifact"]
    value = j.strict_json(j.read_bytes(Path(ref["artifact_path"])))
    callback(value)
    # Synthetic tamper only: preserve original bytes alongside the corrupted
    # file, which intentionally keeps the controller's required physical path.
    write_json(writer.directory / (label + "-original.json"), j.strict_json(j.read_bytes(Path(ref["artifact_path"]))))
    raw = j.canonical(value)
    with Path(ref["artifact_path"]).open("wb") as handle:
        handle.write(raw)
        handle.flush()
        os.fsync(handle.fileno())
    new = {"artifact_path": ref["artifact_path"], "sha256": j.sha(raw), "byte_count": len(raw)}
    binding["occurrence_evidence"]["artifact"] = new
    binding["failure_event_id"] = new["sha256"]
    return value


def negative(directory, spec):
    key = spec["fixture_id"]
    safe = key != "N13"
    mode = "unknown" if key == "N12" else "reset"
    reason, accepted, extra = None, False, {}
    with j.AppendOnlyAttemptJournalV2(directory, h.manifest(safe=safe), create=True) as writer:
        if key == "N14":
            for _ in range(3):
                h.failed_attempt(writer, h.start(writer))
        item = h.failed_attempt(writer, h.start(writer), mode=mode, commit=False)
        data = payload(item)
        binding = data["failure_phase_binding"]
        prefix = None
        if key == "N01":
            binding["occurrence_evidence"]["failure_occurrence_phase"] = "RESPONSE_BODY_COMPLETE"
        elif key == "N02":
            binding["mapping_evidence"].pop("mapping_evidence_phase")
        elif key in {"N03", "N18"}:
            binding["lifecycle_trace"] = None if key == "N03" else {"timestamps": [h.NOW, h.NOW]}
        elif key == "N04":
            def bad_edge(trace):
                trace["committed_progress_events"][-2]["event_payload"]["lifecycle_event"]["state"] = "RAW_RESPONSE_FROZEN"
            binding["lifecycle_trace"]["artifact"] = mutate_ref(writer, binding["lifecycle_trace"]["artifact"], "illegal-edge", bad_edge)
            binding["lifecycle_trace"]["lifecycle_trace_id"] = binding["lifecycle_trace"]["artifact"]["sha256"]
        elif key == "N05":
            binding["terminal_persistence_phase"] = "RESPONSE_BODY_READING"
        elif key in {"N06", "N07"}:
            field, value = ("attempt_ordinal", 2) if key == "N06" else ("logical_request_id", "repair:OA:other")
            binding["mapping_evidence"]["artifact"] = mutate_ref(writer, binding["mapping_evidence"]["artifact"], "other-identity",
                lambda value_record: value_record["attempt_identity"].update({field: value}))
        elif key == "N08":
            binding["mapping_evidence"]["mapping_table_sha256"] = "0" * 64
        elif key == "N09":
            occurrence_path = Path(binding["occurrence_evidence"]["artifact"]["artifact_path"])
            j.atomic_freeze(writer.directory / "preserved-occurrence.json", j.read_bytes(occurrence_path))
            with occurrence_path.open("ab") as handle:
                handle.write(b" ")
                handle.flush()
                os.fsync(handle.fileno())
        elif key == "N10":
            raw_path = Path(item["artifact"].artifact_path)
            j.atomic_freeze(writer.directory / "preserved-partial.xml", j.read_bytes(raw_path))
            with raw_path.open("ab") as handle:
                handle.write(b"corruption")
                handle.flush()
                os.fsync(handle.fileno())
        elif key == "N11":
            binding["raw_admission"]["authoritative"] = True
        elif key in {"N12", "N13", "N14"}:
            data["retry_decision"]["retry_authorized"] = True
        elif key == "N15":
            update_occurrence(writer, binding, "other-run", lambda value: value["attempt_identity"].update(run_epoch="other-epoch"))
        elif key == "N16":
            occurrence = j.strict_json(j.read_bytes(Path(binding["occurrence_evidence"]["artifact"]["artifact_path"])))
            ref = mutate_ref(writer, occurrence["mapping_input_facts"], "other-stage",
                lambda value: value["attempt_identity"].update(stage_id="synthetic:other-stage"))
            update_occurrence(writer, binding, "stage-tamper", lambda value: value.update(mapping_input_facts=ref))
            binding["occurrence_evidence"]["mapping_input_facts_sha256"] = ref["sha256"]
        elif key == "N17":
            h.commit_failure(writer, item)
        elif key == "N19":
            occurrence_path = Path(binding["occurrence_evidence"]["artifact"]["artifact_path"])
            occurrence_path.rename(writer.directory / "withheld-orphan-occurrence.json")
        elif key == "N20":
            occurrence = j.strict_json(j.read_bytes(Path(binding["occurrence_evidence"]["artifact"]["artifact_path"])))
            ref = mutate_ref(writer, occurrence["mapping_input_facts"], "lost-facts",
                lambda value: value["facts"].update(headers_trusted=False))
            update_occurrence(writer, binding, "facts-tamper", lambda value: value.update(mapping_input_facts=ref))
            binding["occurrence_evidence"]["mapping_input_facts_sha256"] = ref["sha256"]
        elif key == "N22":
            # Coherent hash chain and actual prefix, but contradictory scientific-
            # independent lifecycle completion. This reaches the intended rule.
            records = [event.record() for event in writer.verified().events]
            previous = writer.manifest.sha256
            for record in records:
                if record["event_type"] == "LIFECYCLE_PROGRESS":
                    edge = record["event_payload"]["lifecycle_event"]
                    if edge["state"] == "RESPONSE_BODY_INTERRUPTED":
                        edge["state"] = "RESPONSE_BODY_COMPLETE"
                    if edge["previous_state"] == "RESPONSE_BODY_INTERRUPTED":
                        edge["previous_state"] = "RESPONSE_BODY_COMPLETE"
                record["previous_entry_hash"] = previous
                record.pop("entry_hash")
                record["entry_hash"] = j.sha(j.canonical(record))
                previous = record["entry_hash"]
            prefix = tuple(j.JournalEventV2(j.canonical(record)) for record in records)
            trace = j.strict_json(j.read_bytes(Path(binding["lifecycle_trace"]["artifact"]["artifact_path"])))
            trace["committed_progress_events"] = [record for record in records if record["event_type"] == "LIFECYCLE_PROGRESS"]
            trace_ref = write_json(writer.directory / "contradictory-trace.json", trace)
            binding["lifecycle_trace"].update(artifact=trace_ref, lifecycle_trace_id=trace_ref["sha256"],
                ordered_progress_event_refs=[f.event_ref(record) for record in trace["committed_progress_events"]],
                persistence_anchor=f.event_ref(records[-1]))
        try:
            if key == "N21":
                real_fsync = j.os.fsync
                def uncertain(fd):
                    if fd == writer._fd:
                        raise OSError("synthetic terminal durability uncertainty")
                    return real_fsync(fd)
                with patch.object(j.os, "fsync", uncertain):
                    h.commit_failure(writer, item)
                accepted = True
            else:
                candidate(writer, data, prefix)
                accepted = True
        except t.TransportContractError as exc:
            reason = str(exc)
            if key == "N21":
                extra["original_io_cause_preserved"] = isinstance(exc.__cause__, OSError)
                extra["writer_poisoned"] = writer._poisoned
                try:
                    writer.verified()
                    extra["further_ack_denied"] = False
                except t.TransportContractError:
                    extra["further_ack_denied"] = True
        actual = {"accept_invalid_record": accepted, "retry_dispatches": 0, "parser_invocations": 0,
                  "failure": "FAIL_CLOSED" if not accepted else "INVALID_ACCEPTANCE", "proposed_reason_code": reason}
        return {"fixture_id": key, "independent_perturbation": spec["independent_perturbation"],
            "expected": spec["expected"], "actual": actual, "expected_first_rejection_reason": spec["expected"]["proposed_reason_code"],
            "actual_first_rejection_reason": reason, "passed": actual == spec["expected"], **extra}


def recovery(directory):
    directory.mkdir()
    committed = directory / "committed"
    keys = ("repair:OA:success", "repair:OA:0", "repair:OA:later")
    with j.AppendOnlyAttemptJournalV2(committed, h.manifest(keys), create=True) as writer:
        h.success(writer, h.start(writer, keys[0]))
        h.failed_attempt(writer, h.start(writer, keys[1]))
    before = snapshot(committed)
    plan = h.fresh_plan(committed)
    success, failed, later = plan["requests"]
    actual = {"success_state": success["current_derived_state"], "success_skipped": not success["execution_required"],
        "failure_state": failed["current_derived_state"], "failure_is_abandoned": failed["current_derived_state"] == j.ABANDONED,
        "failure_attempts_consumed": failed["attempts_consumed"], "failure_remaining_attempts": failed["remaining_attempts"],
        "failure_next_ordinal": failed["next_authorized_ordinal"], "failure_backoff_seconds": failed["backoff_seconds"],
        "executable_request_ids": plan["executable_request_ids"], "next_executable_request_id": plan["next_executable_request_id"],
        "later_next_ordinal": later["next_authorized_ordinal"], "journal_bytes_changed_by_planning": snapshot(committed) != before,
        "dispatches": 0}
    spec = source_spec("repair_recovery_fixture_specification")
    one = {"fixture_id": spec["fixture_id"], "expected": spec["expected"], "actual": actual,
           "passed": actual == spec["expected"], "fresh_process": True, "plan": plan}
    crashed = directory / "uncommitted"
    process = subprocess.run([sys.executable, "-m", h.__name__, "--crash-before-terminal", str(crashed)],
                             cwd=h.ROOT, capture_output=True, text=True, check=False)
    j.require(process.returncode == 73, "REAL_CRASH_FIXTURE_FAILED:" + process.stderr)
    before = snapshot(crashed)
    abandoned = h.fresh_plan(crashed)["requests"][0]
    frozen = j.FrozenRequestManifestV2(j.read_bytes(crashed / "request_manifest.json"))
    unchanged = snapshot(crashed) == before
    with j.AppendOnlyAttemptJournalV2(crashed, frozen) as writer:
        denied = False
        try:
            h.start(writer)
        except t.TransportContractError:
            denied = True
        writer.classify_abandoned(timestamp=h.NOW)
        next_lifecycle = h.start(writer)
        assert next_lifecycle.context.attempt_ordinal == 2
    actual2 = {"state": abandoned["current_derived_state"], "attempts_consumed": abandoned["attempts_consumed"],
        "next_ordinal": abandoned["next_authorized_ordinal"], "backoff_seconds": abandoned["backoff_seconds"],
        "replay_safe_required": p.abandoned_recovery({"replay_safe": False}, 1).continuation_authorized is False,
        "classification_append_required_before_next_start": denied,
        "infer_terminal_from_memory_or_orphan_occurrence": abandoned["current_derived_state"] != j.ABANDONED}
    spec2 = spec["crash_before_terminal_variant"]
    two = {"fixture_id": spec2["fixture_id"], "expected": spec2["expected"], "actual": actual2,
           "passed": actual2 == spec2["expected"] and unchanged, "fresh_process": True, "process_crash_exit_code": process.returncode,
           "read_only_planning_verified": unchanged}
    return [one, two]
