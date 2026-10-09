"""Execute frozen R1.1 identity oracles at their specified admission stages."""

import copy
import platform
from pathlib import Path
from unittest.mock import patch

from code_engine import runtime_identity_capture_r2 as identity
from scripts import search_plan_v24_alpha322r2_repair_fixtures as fixtures

h, j, t, o = fixtures.h, fixtures.j, fixtures.t, fixtures.o
R11 = h.ROOT / "runs/20261009_search_plan_v24_dev_alpha3_22r11_runtime_identity_failure_audit_offline"


def construction():
    actual_version = platform.python_version()
    with patch.object(identity.platform, "python_version", wraps=platform.python_version) as observed:
        captured = identity.capture_runtime_identity(o.SecretRedactorV1())
        calls = observed.call_count
    record = captured.record()
    try:
        raise ConnectionResetError("synthetic R2 schema construction")
    except ConnectionResetError as exc:
        outcome = o.ExceptionProvenanceV1.capture(exc, t.AttemptContextV1("synthetic:RI", j.sha(b"RI payload"), 1),
                                                o.SecretRedactorV1(), runtime_identity=record)
    t.require(outcome.provenance is not None, "R2_IDENTITY_CAPTURE_UNAVAILABLE")
    signal = outcome.provenance.record()
    o.validate_schema(signal, identity.exception_schema())
    checks = {"exact_fields": set(record) == {"python_version", "client_module", "client_version", "client_code_sha256"},
        "actual_interpreter_version": record["python_version"] == actual_version and bool(actual_version),
        "python_version_type": type(record["python_version"]) is str,
        "client_module_type": type(record["client_module"]) is str,
        "client_version_type": record["client_version"] is None,
        "client_code_sha256_type": type(record["client_code_sha256"]) is str,
        "bound_client_module": record["client_module"] == "urllib.request/http.client.HTTPResponse",
        "bound_client_hash": record["client_code_sha256"] == j.b.BOUND_CLIENT_IDENTITY_SHA256,
        "capture_once": calls == 1, "exception_schema_admitted": True,
        "same_identity_in_exception": signal["runtime_identity"] == record}
    return {"passed": all(checks.values()), "runtime_identity": record, "checks": checks,
            "python_version_capture_calls": calls, "exception_payload": signal,
            "frozen_exception_schema_sha256": identity.SCHEMA_SHA256}


def negative(directory, spec):
    key = spec["fixture_id"]
    with j.AppendOnlyAttemptJournalV2(directory, h.manifest(), create=True) as writer:
        item = h.failed_attempt(writer, h.start(writer), commit=False)
        mapped = item["observation"].record()
        original = copy.deepcopy(mapped["observation"]["exception_provenance"])
        o.validate_schema(original, identity.exception_schema())
        signal = mapped["observation"]["exception_provenance"]
        stage = spec["admission_stage"]
        if key == "RI01":
            signal.pop("runtime_identity")
        elif key == "RI02":
            signal["runtime_identity"].pop("python_version")
        elif key == "RI03":
            signal["runtime_identity"]["python_version"] = 13
        elif key == "RI04":
            signal["schema_version"] = "WrongSchemaVersion"
        elif key == "RI05":
            # Serialize a complete pending event first, then deliberately lose
            # the parent at the serialization boundary. Schema admission is the
            # isolated pre-append stage named by the frozen RI05 specification.
            data = fixtures.payload(item)
            last = writer.verified().events[-1].record()
            pending = copy.deepcopy(last)
            pending.update(sequence_number=last["sequence_number"] + 1, previous_entry_hash=last["entry_hash"],
                           event_type="ATTEMPT_TERMINAL", event_payload=data)
            pending.pop("entry_hash")
            pending["entry_hash"] = j.sha(j.canonical(pending))
            complete = j.JournalEventV2(j.canonical(pending)).record()
            before_loss = complete["event_payload"]["mapped_observation"]["observation"]["exception_provenance"]
            o.validate_schema(before_loss, identity.exception_schema())
            before_loss.pop("runtime_identity")
            complete.pop("entry_hash")
            complete["entry_hash"] = j.sha(j.canonical(complete))
            raw = j.canonical(complete)
            event = j.JournalEventV2(raw).record()
            mapped = event["event_payload"]["mapped_observation"]
            signal = mapped["observation"]["exception_provenance"]
            j.atomic_freeze(directory / "serialized_pending_event.json", raw)
        elif key == "RI06":
            signal["attempt_ordinal"] = 2
        else:
            raise AssertionError("UNKNOWN_FROZEN_RI_FIXTURE")
        input_path = directory / "malformed_admission_input.json"
        input_raw = j.canonical(mapped if key == "RI06" else signal)
        j.atomic_freeze(input_path, input_raw)
        journal_path = directory / "segment-0001.jsonl"
        before_journal = j.read_bytes(journal_path)
        before_malformed = copy.deepcopy(mapped)
        reason = None
        try:
            if key == "RI06":
                # Default phase_binding_verified=False. Context rejection is
                # before phase comparison; no invented phase authority.
                j.validate_mapped_observation(mapped, item["lifecycle"].context,
                    writer.manifest.request(item["lifecycle"].context.logical_request_id), item["decision"].record()["retry"])
            else:
                o.validate_schema(signal, identity.exception_schema())
        except t.TransportContractError as exc:
            reason = str(exc)
        unchanged = j.read_bytes(input_path) == input_raw and before_malformed == mapped
        no_append = j.read_bytes(journal_path) == before_journal
        terminal_count = sum(event.record()["event_type"] == "ATTEMPT_TERMINAL" for event in writer.verified().events)
        actual = {"durable_terminal_commit": bool(terminal_count), "retry_dispatches": item["retry_dispatches"],
                  "parser_invocations": item["parser_invocations"]}
        return {"fixture_id": key, "admission_stage": stage, "expected_first_rejection": spec["expected_first_rejection"],
            "actual_first_rejection": reason, "expected": spec["expected"], "actual": actual,
            "passed": reason == spec["expected_first_rejection"] and actual == spec["expected"] and unchanged and no_append,
            "serialized_input_unchanged": unchanged, "journal_unchanged_by_rejection": no_append,
            "input_artifact": {"artifact_path": str(input_path.relative_to(h.ROOT)), "sha256": j.sha(input_raw)},
            "baseline_runtime_identity": original["runtime_identity"],
            "isolated_specified_admission_stage_not_full_terminal_first_error_claim": True,
            "verifier_silent_repair": False}
