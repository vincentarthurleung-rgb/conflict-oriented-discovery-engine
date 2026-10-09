#!/usr/bin/env python3
"""Offline crash fixtures and append-only 22C implementation freeze."""

from __future__ import annotations

import ast
import json
import os
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from unittest.mock import patch

from code_engine import append_only_attempt_journal_v1 as j
from code_engine import deterministic_resume_planner_v1 as p
from code_engine import stage_barrier_snapshot_v1 as s
from scripts import run_search_plan_v24_alpha322b_exception_mapping_offline as prior


ROOT, master, t, o, b = prior.ROOT, prior.master, prior.t, prior.o, prior.mapping
OUT = ROOT / "runs/20261008_search_plan_v24_dev_alpha3_22c_attempt_journal_resume_offline"
ROOT_MARKER = "search_plan_v24_dev_alpha3_22c_sha256"
CLASSIFICATION = "APPEND_ONLY_ATTEMPT_JOURNAL_AND_DETERMINISTIC_PROCESS_RESUME_IMPLEMENTED_OFFLINE"
STAGE = "POST_ALPHA3_21_DURABLE_JOURNAL_AND_PROCESS_RESUME_IMPLEMENTATION"
NEXT = "EXECUTE_ALPHA3_22D_OFFLINE_TRANSPORT_AND_CRASH_FAULT_INJECTION_MATRIX"
TEST = ROOT / "tests/test_search_plan_v24_alpha322c_attempt_journal_resume_offline.py"
COMPONENTS = [Path(j.__file__), Path(p.__file__), Path(s.__file__)]
NOW = "2000-01-01T00:00:00Z"
canonical, digest, ref, obj, require = o.canonical_bytes, prior.digest, prior.ref, prior.obj, t.require
NO_CALLS = dict(prior.NO_CALLS)
MARKERS = {"append_only_attempt_journal_v1_implementation_sha256": "append_only_attempt_journal_implementation_manifest",
           "deterministic_resume_planner_v1_implementation_sha256": "deterministic_resume_planner_implementation_manifest",
           "stage_barrier_snapshot_v1_contract_sha256": "stage_barrier_snapshot_contract",
           "alpha3_22c_reproducibility_bundle_sha256": "alpha3_22c_reproducibility_bundle"}
REQUIRED = tuple("""alpha3_22_master_root_verification alpha3_22a_root_verification alpha3_22b_root_verification
alpha3_21_closure_binding_verification alpha3_22c_scope_boundary journal_storage_contract_v1 journal_event_schema_v1
journal_event_transition_contract journal_hash_chain_contract journal_durability_contract journal_single_writer_contract
journal_integrity_verifier_contract journal_integrity_test_results attempt_started_write_ahead_contract
attempt_ordinal_consumption_contract abandoned_attempt_resolution_contract raw_response_commit_order_contract
raw_artifact_integrity_contract logical_request_execution_state_contract terminal_outcome_semantics_contract
append_only_attempt_journal_implementation_manifest deterministic_resume_planner_contract
deterministic_resume_planner_implementation_manifest resume_plan_schema_v1 resume_order_preservation_contract
successful_request_skip_audit terminal_noneligible_skip_audit attempt_budget_resume_audit stage_barrier_snapshot_contract
frozen_activation_manifest_contract stage_barrier_resume_test_results crash_recovery_fault_matrix
crash_recovery_fault_matrix_results synthetic_two_phase_replay_manifest synthetic_two_phase_replay_results
journal_secret_redaction_audit journal_observability_schema_binding resume_determinism_audit journal_concurrent_writer_audit
alpha3_21_continuation_prohibition_audit legacy_runtime_preservation_audit production_runtime_nonwiring_audit
scientific_policy_firewall_audit contamination_baseline_immutability_audit historical_preservation_audit
scientific_state_safety_audit validation summary""".split())
CRASH_CASES = ("before_start", "after_start", "during_headers", "after_headers", "partial_body", "orphan_complete_raw",
    "success_before_summary", "between_failure_and_next", "after_fourth", "torn_append", "barrier_persistence",
    "barrier_before_activation", "activation_before_dispatch", "some_jats_success", "unsafe_abandoned",
    "duplicate_ordinal", "missing_success_raw", "hash_tampering", "writer_contention", "repeat_readonly_resume")


def verify_authority():
    authority = prior.verify_authority()
    authority["alpha322b"] = master.prior.root_check(prior.OUT, prior.ROOT_MARKER, j.AUTHORITY["alpha322b_sha256"])
    for marker, expected in (("transport_exception_mapping_v2_table_sha256", b.MAPPING_TABLE_SHA256),
                            ("transport_exception_mapping_v2_implementation_sha256", "d601568d4154134a6550234c260e7fdced90d38b0ba381ee1333a3fb169df7ed"),
                            ("retry_orchestration_v2_contract_sha256", j.AUTHORITY["retry_orchestration_contract_sha256"])):
        path = prior.OUT / (prior.MARKERS[marker] + ".json")
        require(digest(path) == expected == (prior.OUT / marker).read_text().strip(), "FROZEN_22B_MEMBER_MISMATCH")
        master.d2.d1.d.checked_tree(obj(path))
    for stem, expected in j.OBSERVATION_SCHEMA_HASHES.items():
        require(digest(prior.prior.OUT / (stem + ".json")) == expected, "FROZEN_OBSERVABILITY_SCHEMA_MISMATCH")
    prior.client_identity(authority)
    authority["alpha322b_sources"] = [ref(path, "unchanged_frozen_22B_code") for path in (prior.COMPONENT, Path(prior.__file__), prior.TEST)]
    return authority


def manifest(count=1, *, two_phase=False, safe=True):
    requests = []
    for stage in (("OA", "JATS") if two_phase else ("OA",)):
        for n in range(count):
            payload = {"synthetic_source": n, "route": "offline:" + stage}
            if stage == "JATS":
                payload["oa_request_id"] = f"synthetic:OA:{n}"
            requests.append({"request_id": f"synthetic:{stage}:{n}", "request_payload": payload,
                "request_payload_sha256": j.sha(canonical(payload)), "stage": stage, "execution_order": len(requests),
                "replay_safe": safe, "maximum_attempts": j.POLICY.maximum_attempts,
                "validity_authority_sha256": j.sha(b"synthetic XML identity validator; no scientific inference"),
                "eligibility_authority_sha256": j.sha(b"synthetic fixture boolean eligibility authority")})
    return j.FrozenRequestManifestV1(canonical({"schema_version": "FrozenRequestManifestV1", "run_id": "synthetic:alpha322c",
        "run_epoch": "synthetic:epoch-1", "stage_id": "synthetic:OA-JATS", "authority": j.AUTHORITY,
        "activation_contract_sha256": j.sha(b"activate JATS iff frozen parent OA terminal VALID_SUCCESS"), "requests": requests}))


def plan(journal):
    return p.DeterministicResumePlannerV1().build(journal).record()


def start(writer, key="synthetic:OA:0"):
    token = writer.start_attempt(key, timestamp=NOW)
    require(writer.dispatch_authorized(token), "SYNTHETIC_DISPATCH_NOT_AUTHORIZED")
    lifecycle = t.TransportLifecycleV2(token.context)
    lifecycle.start_attempt(token.entry_hash, timestamp=NOW)
    writer.record_lifecycle(lifecycle, timestamp=NOW)
    return lifecycle


def headers(writer, lifecycle):
    lifecycle.receive_headers(200, trustworthy=True, evidence_reference="synthetic:trusted_headers", timestamp=NOW)
    writer.record_lifecycle(lifecycle, timestamp=NOW)


def frozen_body(writer, lifecycle, *, partial=False, invalid=False):
    headers(writer, lifecycle)
    lifecycle.start_body("synthetic:body_read", timestamp=NOW)
    writer.record_lifecycle(lifecycle, timestamp=NOW)
    raw = b"<synthetic/>" if not partial and not invalid else b"<synthetic>"
    completion = t.assess_body_completion(raw, read_returned_normally=not partial,
        expected_content_length=len(raw) if not partial else len(raw) + 20, expected_length_trustworthy=True,
        expected_length_representation=t.ByteRepresentation.WIRE,
        interruption_class=t.SemanticFailure.RESPONSE_BODY_TRANSPORT_INTERRUPTION if partial else None,
        interruption_reason="synthetic body interruption" if partial else None, timestamp=NOW)
    lifecycle.record_body(completion, "synthetic:body_result", timestamp=NOW)
    writer.record_lifecycle(lifecycle, timestamp=NOW)
    artifact = j.atomic_freeze(writer.directory / ("raw-" + str(lifecycle.context.attempt_ordinal) + "-" + lifecycle.context.logical_request_id.replace(":", "-") + ".xml"), raw)
    response = lifecycle.freeze_response(artifact, timestamp=NOW)
    writer.record_lifecycle(lifecycle, timestamp=NOW)
    return response


def terminal(writer, lifecycle, *, eligible=True, failure=None):
    exception, response, validation, eligibility, http, body = None, None, None, None, None, None
    request = writer.manifest.request(lifecycle.context.logical_request_id)
    redactor = writer.redactor
    if failure in {None, "invalid", "partial"}:
        response = frozen_body(writer, lifecycle, partial=failure == "partial", invalid=failure == "invalid")
        if failure == "partial":
            invoked = []
            require(prior.prior.expect_denied(lambda: t.guarded_parse(response, lambda raw: invoked.append(raw))), "PARTIAL_ADMISSION")
            require(not invoked, "PARTIAL_PARSER_CALLED")
        else:
            accepted = True
            try:
                t.guarded_parse(response, ET.fromstring)
            except ET.ParseError as exc:
                exception, accepted = exc, False
            lifecycle.record_validation(valid=accepted, evidence_reference=request["validity_authority_sha256"], timestamp=NOW)
            writer.record_lifecycle(lifecycle, timestamp=NOW)
            validation = {"authority_sha256": request["validity_authority_sha256"], "accepted": accepted}
            eligibility = {"authority_sha256": request["eligibility_authority_sha256"], "eligible": eligible} if accepted else None
        http = o.HttpResponseProvenanceV1.capture(lifecycle.context, redactor, method="GET", status=200, trusted=True,
            status_origin="BOUND_HTTP_RESPONSE", headers=(("Content-Length", str(response.completion.expected_content_length)),
            ("Set-Cookie", "synthetic-private-credential")), request_url="https://synthetic.invalid/?api_key=synthetic-private-credential")
        body = o.BodyReadProvenanceV1.capture(lifecycle.context, redactor, response.completion, response.artifact, parser_invoked=failure != "partial")
    else:
        exception = TimeoutError("synthetic-private-credential") if failure == "timeout" else RuntimeError("timeout-like text not authority")
    facts = b.TransportMappingFactsV2(lifecycle.state, b.BOUND_CLIENT_IDENTITY_SHA256,
        headers_trusted=response is not None, http_status=200 if response else None,
        http_status_origin="BOUND_HTTP_RESPONSE" if response else None, body_completion=lifecycle.completion)
    decision = b.classify_transport_failure_and_decide_retry_v2(exception, facts,
        request_replay_safe=request["replay_safe"], attempt_ordinal=lifecycle.context.attempt_ordinal)
    observation = b.mapped_observation_v2(decision, lifecycle, redactor, original_exception=exception, http=http, body=body,
        replay_safety_authority={"manifest_sha256": writer.manifest.sha256, "request_id": request["request_id"]} if request["replay_safe"] else None)
    writer.commit_terminal(lifecycle, decision, observation, artifact=response.artifact if response else None,
        validation=validation, eligibility=eligibility, timestamp=NOW)
    return decision.record()


def read_plan(directory):
    frozen = j.FrozenRequestManifestV1(j.read_bytes(Path(directory) / "request_manifest.json"))
    return plan(j.JournalIntegrityVerifierV1.read(directory, frozen))


def fresh_process_plan(directory):
    result = subprocess.run([sys.executable, "-m", "scripts.run_search_plan_v24_alpha322c_attempt_journal_resume_offline", "--inspect-journal", str(directory)],
        cwd=ROOT, capture_output=True, text=True, check=False)
    if result.returncode:
        return {"failed_closed": True, "error": result.stderr.strip(), "exit_code": result.returncode}
    return json.loads(result.stdout)


def crash_setup(directory, case):
    """Executed in a disposable process; os._exit bypasses Python cleanup."""
    two_phase = case in {"barrier_persistence", "barrier_before_activation", "activation_before_dispatch", "some_jats_success"}
    frozen = manifest(5 if two_phase else 1, two_phase=two_phase, safe=case != "unsafe_abandoned")
    writer = j.AppendOnlyAttemptJournalV1(directory, frozen, create=True,
                                         redactor=o.SecretRedactorV1(("synthetic-private-credential",)))
    if case == "before_start":
        os._exit(73)
    if two_phase:
        for n in range(5):
            terminal(writer, start(writer, f"synthetic:OA:{n}"), eligible=n < 3)
        if case == "barrier_persistence":
            # Preserve truncated unpublished temporary bytes; no authoritative
            # destination and no stage event. Recovery derives only durable OA.
            j.atomic_freeze(writer.directory / ".pending-crash-barrier", b'{"schema_version":')
            os._exit(73)
        s.StageBarrierSnapshotV1.freeze(writer, timestamp=NOW)
        if case == "barrier_before_activation":
            os._exit(73)
        s.FrozenActivationManifestV1.freeze(writer, timestamp=NOW)
        if case == "activation_before_dispatch":
            os._exit(73)
        terminal(writer, start(writer, "synthetic:JATS:0"))
        frozen_body(writer, start(writer, "synthetic:JATS:1"), partial=True)
        os._exit(73)
    if case == "torn_append":
        real_write = os.write
        def interrupted(fd, raw):
            real_write(fd, raw[:len(raw) // 2])
            os._exit(73)
        with patch.object(j.os, "write", interrupted):
            start(writer)
        raise AssertionError("TORN_APPEND_NOT_INJECTED")
    if case == "after_fourth":
        for _ in range(4):
            terminal(writer, start(writer), failure="timeout")
        os._exit(73)
    lifecycle = start(writer)
    if case in {"after_start", "during_headers", "unsafe_abandoned"}:
        os._exit(73)
    if case == "after_headers":
        headers(writer, lifecycle)
        os._exit(73)
    if case in {"partial_body", "orphan_complete_raw"}:
        frozen_body(writer, lifecycle, partial=case == "partial_body")
        os._exit(73)
    if case == "between_failure_and_next":
        terminal(writer, lifecycle, failure="timeout")
        os._exit(73)
    terminal(writer, lifecycle)
    os._exit(73)


def expect_denied(callback):
    try:
        callback()
    except (t.TransportContractError, FileNotFoundError):
        return True
    raise AssertionError("EXPECTED_FAIL_CLOSED")


def crash_matrix(directory):
    directory.mkdir()
    results = []
    for case in CRASH_CASES:
        place = directory / case
        setup_case = "success_before_summary" if case in {"missing_success_raw", "hash_tampering", "repeat_readonly_resume"} else "after_start" if case in {"duplicate_ordinal", "writer_contention"} else case
        process = subprocess.run([sys.executable, "-m", "scripts.run_search_plan_v24_alpha322c_attempt_journal_resume_offline", "--synthetic-crash", str(place), "--case", setup_case], cwd=ROOT, capture_output=True, text=True)
        require(process.returncode == 73, "CRASH_FIXTURE_FAILED:" + case + ":" + process.stderr)
        frozen = j.FrozenRequestManifestV1(j.read_bytes(place / "request_manifest.json"))
        pre_manifest = j.read_bytes(place / "request_manifest.json")
        evidence = {"case_id": case, "fresh_process_crash_exit_code": 73}
        if case == "missing_success_raw":
            raw = next(place.glob("raw-*.xml"))
            # Keep the bytes recoverable and demonstrate a missing referenced path.
            raw.rename(place / "preserved-missing-raw.xml")
            evidence["failed_closed"] = fresh_process_plan(place)["failed_closed"]
        elif case == "hash_tampering":
            source = j.read_bytes(place / "segment-0001.jsonl")
            # A separate corrupted fixture, never rewriting original history.
            corrupt = directory / "separate-corrupted-fixture"
            with j.AppendOnlyAttemptJournalV1(corrupt, frozen, create=True):
                pass
            with (corrupt / "segment-0001.jsonl").open("ab") as handle:
                handle.write(source.replace(b'"sequence_number":1', b'"sequence_number":9', 1))
                handle.flush()
                os.fsync(handle.fileno())
            evidence["failed_closed"] = fresh_process_plan(corrupt)["failed_closed"]
            evidence["original_history_preserved"] = j.read_bytes(place / "segment-0001.jsonl") == source
        elif case == "torn_append":
            source = j.read_bytes(place / "segment-0001.jsonl")
            evidence["failed_closed"] = fresh_process_plan(place)["failed_closed"]
            evidence["integrity_report"] = j.JournalIntegrityVerifierV1.integrity_report(place, frozen)
            j.atomic_freeze(place / "corruption_recovery_sidecar.json", canonical(evidence["integrity_report"]))
            require(j.read_bytes(place / "segment-0001.jsonl") == source, "TORN_SEGMENT_WAS_MUTATED")
        elif case in {"duplicate_ordinal", "writer_contention"}:
            with j.AppendOnlyAttemptJournalV1(place, frozen) as writer:
                if case == "writer_contention":
                    evidence["failed_closed"] = expect_denied(lambda: j.AppendOnlyAttemptJournalV1(place, frozen))
                    require(fresh_process_plan(place)["failed_closed"], "READER_BYPASSED_WRITER_LOCK")
                else:
                    record = writer.verified().events[0].record()
                    evidence["failed_closed"] = expect_denied(lambda: writer._append("ATTEMPT_STARTED", record["logical_request_id"], 1, record["event_payload"], NOW))
        else:
            original_bytes = j.read_bytes(place / "segment-0001.jsonl")
            recovered = fresh_process_plan(place)
            require("failed_closed" not in recovered, "UNEXPECTED_CRASH_RECOVERY_FAILURE:" + case)
            again = fresh_process_plan(place)
            require(recovered == again and j.read_bytes(place / "segment-0001.jsonl") == original_bytes, "READONLY_RESUME_NONDETERMINISM")
            evidence["resume_plan"] = recovered
            first = recovered["requests"][0]
            if case == "before_start":
                require(first["attempts_consumed"] == 0 and first["next_authorized_ordinal"] == 1, "PRESTART_CONSUMED")
            elif case in {"success_before_summary", "repeat_readonly_resume"}:
                require(first["current_derived_state"] == "VALID_SUCCESS" and recovered["stage_complete"] and not recovered["executable_request_ids"], "SUCCESS_REFRESH")
            elif case == "after_fourth":
                require(first["current_derived_state"] == "TERMINAL_TECHNICAL_FAILURE" and first["attempts_consumed"] == 4 and first["next_authorized_ordinal"] is None, "FIFTH_ATTEMPT")
            elif case == "unsafe_abandoned":
                require(first["current_derived_state"] == j.ABANDONED and first["next_authorized_ordinal"] is None and recovered["blocking_reason"], "UNSAFE_REPLAY")
            elif case in {"barrier_persistence", "barrier_before_activation", "activation_before_dispatch", "some_jats_success"}:
                require(all(r["current_derived_state"] in {"VALID_SUCCESS", "VALID_NONELIGIBLE_RESPONSE"} for r in recovered["requests"][:5]), "OA_REFRESH")
                if case == "barrier_persistence":
                    require(recovered["barrier_sha256"] is None, "PARTIAL_BARRIER_ADMITTED")
                    with j.AppendOnlyAttemptJournalV1(place, frozen) as writer:
                        s.StageBarrierSnapshotV1.freeze(writer, timestamp=NOW)
                        s.FrozenActivationManifestV1.freeze(writer, timestamp=NOW)
                    evidence["mechanically_recovered_from_committed_OA_only"] = True
                elif case == "barrier_before_activation":
                    require(recovered["barrier_sha256"] is not None and recovered["activation_sha256"] is None, "BARRIER_LOST")
                elif case == "activation_before_dispatch":
                    require(recovered["executable_request_ids"] == [f"synthetic:JATS:{i}" for i in range(3)], "ACTIVATION_CHANGED")
                else:
                    require(recovered["executable_request_ids"] == ["synthetic:JATS:1", "synthetic:JATS:2"]
                            and recovered["requests"][6]["next_authorized_ordinal"] == 2, "JATS_RESUME_ORDER_OR_ORDINAL")
            else:
                require(first["attempts_consumed"] == 1 and first["next_authorized_ordinal"] == 2, "ABANDONED_OR_FAILED_ORDINAL_REUSED")
            evidence["repeated_readonly_plan_equivalent"] = True
        require(j.read_bytes(place / "request_manifest.json") == pre_manifest, "FROZEN_MANIFEST_MUTATED")
        require(evidence.get("failed_closed", True) is True, "FAULT_DID_NOT_FAIL_CLOSED")
        evidence["check_passed"] = True
        results.append(evidence)
    return {"case_count": len(results), "pass_count": len(results), "fail_count": 0, "cases": results,
            "full_alpha322d_release_matrix_substituted": False}


def two_phase(directory):
    frozen = manifest(5, two_phase=True)
    with j.AppendOnlyAttemptJournalV1(directory, frozen, create=True,
            redactor=o.SecretRedactorV1(("synthetic-private-credential",))) as writer:
        for n in range(5):
            terminal(writer, start(writer, f"synthetic:OA:{n}"), eligible=n < 3)
        barrier = s.StageBarrierSnapshotV1.freeze(writer, timestamp=NOW)
        activation = s.FrozenActivationManifestV1.freeze(writer, timestamp=NOW)
        terminal(writer, start(writer, "synthetic:JATS:0"))
        frozen_body(writer, start(writer, "synthetic:JATS:1"), partial=True)
    before = fresh_process_plan(directory)
    history = j.read_bytes(directory / "segment-0001.jsonl")
    require(before["executable_request_ids"] == ["synthetic:JATS:1", "synthetic:JATS:2"], "TWO_PHASE_PENDING_SET")
    with j.AppendOnlyAttemptJournalV1(directory, frozen,
            redactor=o.SecretRedactorV1(("synthetic-private-credential",))) as writer:
        writer.classify_abandoned(timestamp=NOW)
        require(s.StageBarrierSnapshotV1.freeze(writer, timestamp=NOW).serialized == barrier.serialized, "BARRIER_REFRESH")
        require(s.FrozenActivationManifestV1.freeze(writer, timestamp=NOW).serialized == activation.serialized, "ACTIVATION_REFRESH")
        terminal(writer, start(writer, "synthetic:JATS:1"))
        terminal(writer, start(writer, "synthetic:JATS:2"))
    after = fresh_process_plan(directory)
    require(after["stage_complete"] and not after["executable_request_ids"] and after["requests"][6]["attempts_consumed"] == 2, "TWO_PHASE_COMPLETION")
    require(j.read_bytes(directory / "segment-0001.jsonl").startswith(history), "OLD_HISTORY_CHANGED")
    require(after["barrier_sha256"] == before["barrier_sha256"] and after["activation_sha256"] == before["activation_sha256"], "STAGE_SNAPSHOT_CHANGED")
    manifest_reference = {"artifact_path": str(directory / "request_manifest.json"), "sha256": frozen.sha256,
                          "artifact_role": "synthetic_frozen_request_manifest", "immutable_frozen": True}
    return {"check_passed": True, "manifest": manifest_reference,
            "oa_source_count": 5, "oa_eligible_count": 3, "oa_noneligible_count": 2, "activated_jats_count": 3,
            "before_resume": before, "after_resume": after, "interrupted_ordinal_consumed": True,
            "historical_journal_prefix_preserved": True, "raw_orphan_preserved": True}


def boundary_audit():
    for path in COMPONENTS:
        tree = ast.parse(path.read_text())
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                require(not any(n.name.split(".")[0] in {"socket", "requests", "httpx", "openai", "time"} for n in node.names), "LIVE_IMPORT_FORBIDDEN")
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                require(node.func.attr not in {"urlopen", "connect", "sleep", "create_connection"}, "LIVE_CALL_FORBIDDEN")
    return {"check_passed": True, "production_runtime_v2_wiring_enabled": False,
            "source_files": [ref(path, "unwired_versioned_22C_component") for path in COMPONENTS]}


def build_documents(authority, matrix, replay, verification):
    scope = {"stage_identity": STAGE, "development_mode": True, "fresh_primary_attempt_started": False,
        "alpha3_21_reopened": False, "legacy_runtime_modified": False, "builder_v4_changed": False, "quality_v2_changed": False,
        "search_plan_scientific_architecture_changed": False, "historical_assets_modified": False,
        "production_runtime_v2_wiring_enabled": False, "scientific_policy_changed": False, **NO_CALLS}
    implementation = {"schema_version": "AppendOnlyAttemptJournalImplementationV1", "source_files": [ref(COMPONENTS[0], "new_unwired_journal")],
        "script": ref(Path(__file__), "offline_component_freeze_and_crash_fixtures"), "tests": ref(TEST, "focused_offline_tests"),
        "authority": j.AUTHORITY, "write_ahead": True, "append_only": True, "durability": "file fsync before ack; directory fsync on creation/companion publication",
        "single_writer": "POSIX nonblocking flock held over entire writer lifetime", "runtime_activation_allowed": False}
    resume_implementation = {"schema_version": "DeterministicResumePlannerImplementationV1", "source_files": [ref(path, "new_unwired_resume_or_barrier") for path in COMPONENTS[1:]],
        "journal": ref(COMPONENTS[0], "shared_verified_reducer"), "tests": ref(TEST, "focused_offline_tests"), "authority": j.AUTHORITY,
        "side_effects": [], "abandoned_restart_rule_owner": "frozen master process_restart_semantics", "numeric_retry_policy_owner": "alpha3.22A"}
    barrier_contract = {"schema_version": "StageBarrierSnapshotContractV1", "source": ref(COMPONENTS[2], "deterministic_barrier_and_activation"),
        "master_contract": ref(master.OUT / "two_phase_barrier_resume_contract.json", "unchanged_barrier_authority"),
        "complete_OA_terminal_events_required": True, "recorded_OA_raw_hashes_verified": True,
        "journal_commit_after_atomic_artifact_freeze": True, "barrier_reuse_byte_identical": True,
        "activation_set_derivation": "frozen request parent ID and frozen OA VALID_SUCCESS only",
        "missing_or_corrupt_committed_barrier": "FAIL_CLOSED_NO_JATS", "complete_uncommitted_companion": "exact deterministic equivalence to committed inputs required; no replacement"}
    summary = {"status": "completed", "search_plan_v24_dev_alpha3_22c_status": "completed", "alpha3_22c_classification": CLASSIFICATION,
        **scope, **authority["counts"], "alpha3_22_master_root_verified": True, "alpha3_22a_root_verified": True, "alpha3_22b_root_verified": True,
        "alpha3_21_closure_root_verified": True, "append_only_attempt_journal_implemented": True, "write_ahead_attempt_start_durable": True,
        "single_writer_enforced": True, "journal_integrity_hash_chain_enabled": True, "journal_integrity_verifier_implemented": True,
        "torn_journal_tail_fails_closed": True, "attempt_ordinal_reuse_allowed": False, "abandoned_attempt_consumes_ordinal": True,
        "abandoned_attempt_replay_requires_replay_safe": True, "raw_artifact_durable_before_terminal_success": True,
        "missing_success_artifact_fails_closed": True, "deterministic_resume_planner_implemented": True,
        "resume_planner_network_side_effects": False, "successful_request_refresh_allowed": False, "terminal_noneligible_refetch_allowed": False,
        "frozen_stage_barrier_reuse_implemented": True, "conditional_activation_manifest_immutable": True,
        "crash_fault_matrix_case_count": matrix["case_count"], "crash_fault_matrix_pass_count": matrix["pass_count"], "crash_fault_matrix_fail_count": matrix["fail_count"],
        "synthetic_two_phase_replay_passed": replay["check_passed"], "retry_policy_delegates_to_alpha3_22a": True,
        "exception_mapping_delegates_to_alpha3_22b": True, "duplicate_retry_policy_implemented": False, "next_stage_recommendation": NEXT}
    cases = {r["case_id"]: r for r in matrix["cases"]}
    binding = {"authority": j.AUTHORITY, "22A_schemas": [ref(prior.prior.OUT / (stem + ".json"), "unchanged_observability_schema") for stem in j.OBSERVATION_SCHEMA_HASHES],
        "22A_provenance_schema_modified": False, "22A_in_memory_flags_remain_false": True, "22C_journal_wrapper_owns_durability": True}
    docs = {
        "alpha3_22_master_root_verification": authority["master"], "alpha3_22a_root_verification": authority["alpha322a"],
        "alpha3_22b_root_verification": authority["alpha322b"], "alpha3_21_closure_binding_verification": authority["closure"],
        "alpha3_22c_scope_boundary": scope, "journal_storage_contract_v1": {**implementation, "format": "canonical UTF-8 JSONL with newline commit framing", "single_segment": True},
        "journal_event_schema_v1": j.journal_event_schema_v1(), "journal_event_transition_contract": {"event_kinds": list(j.EVENT_TYPES),
            "lifecycle_owner": "alpha3.22A.ALLOWED_TRANSITIONS", "same_ordinal_progress_requires_current_start": True,
            "single_terminal_per_attempt": True, "stage_commit_events_additive_not_lifecycle_states": True},
        "journal_hash_chain_contract": {"schema_version": "JournalHashChainContractV1", "canonicalization_owner": "22A.canonical_bytes",
            "genesis_hash": "exact frozen request manifest SHA256", "entry_hash": "SHA256(redacted canonical entry excluding entry_hash, including newline)",
            "sequence_continuity": "1..N", "previous_hash_link_required": True},
        "journal_durability_contract": {"assumptions": "local POSIX filesystem honoring fsync, O_APPEND, no-follow, atomic hard-link publication and flock; cooperative writers",
            "append_ack": "all bytes written and fsync returns successfully", "uncertain_append": "writer poisoned; no dispatch; fresh integrity review",
            "power_loss_guarantee": "no stronger than storage fsync implementation", "companion_publication": "mkstemp -> flush/fsync -> no-overwrite atomic link -> directory fsync"},
        "journal_single_writer_contract": {"mechanism": "nonblocking fcntl.flock LOCK_EX for writer lifetime; LOCK_SH for snapshots", "contention": "fail closed; no ordinal allocation"},
        "journal_integrity_verifier_contract": {"checks": ["schema", "canonical bytes", "run/epoch/stage", "manifest", "sequence", "entry hashes", "previous links", "transitions", "ordinals", "terminal uniqueness", "raw references", "barriers"],
            "torn_tail": "preserve damaged bytes and sidecar; committed prefix diagnostic only; no new chained segment without unique durable-prefix authority; this implementation fails closed"},
        "journal_integrity_test_results": {"check_passed": True, "evidence": [cases[k] for k in ("torn_append", "hash_tampering", "duplicate_ordinal", "missing_success_raw")]},
        "attempt_started_write_ahead_contract": {"token_type": "DurableAttemptStartV1", "no_ack_no_dispatch": True, "start_records_manifest_payload_ordinal_replay_retry_identity": True, "synthetic_dispatch_only": True},
        "attempt_ordinal_consumption_contract": obj(master.OUT / "attempt_consumption_contract.json"),
        "abandoned_attempt_resolution_contract": {"master_contract": ref(master.OUT / "process_restart_semantics.json", "sole_restart_authority"),
            "classification": j.ABANDONED, "not_mapped_to_transport_interruption": True, "completed_UNKNOWN_22A_decision_still_terminal": True,
            "conditions": ["verified journal", "unchanged frozen request", "explicit replay_safe", "remaining 22A policy budget"], "classification_event_required_before_new_start": True},
        "raw_response_commit_order_contract": {"order": ["complete raw bytes", "file and directory fsync", "raw hash/provenance", "unchanged response validation", "terminal append fsync"], "orphan_is_success": False},
        "raw_artifact_integrity_contract": {"missing_or_corrupt": "FAIL_CLOSED", "symlink": "FAIL_CLOSED", "byte_count_and_sha256_verified": True},
        "logical_request_execution_state_contract": {"states": list(p.LOGICAL_STATES), "frozen_master_contract": ref(master.OUT / "logical_request_state_contract.json", "unchanged_logical_state_authority"), "abandoned_is_explicit_recovery_state": True},
        "terminal_outcome_semantics_contract": {"transport_complete_not_response_valid": True, "response_valid_not_scientific_eligible": True, "eligibility_definition_changed": False},
        "append_only_attempt_journal_implementation_manifest": implementation,
        "deterministic_resume_planner_contract": {"pure_planner": True, "inputs": ["verified journal", "frozen request manifest", "verified barrier/activation", "22A/B bindings"], "writes": False, "network": False, "sleep": False},
        "deterministic_resume_planner_implementation_manifest": resume_implementation, "resume_plan_schema_v1": p.resume_plan_schema_v1(),
        "resume_order_preservation_contract": obj(master.OUT / "continuation_order_contract.json"),
        "successful_request_skip_audit": cases["success_before_summary"], "terminal_noneligible_skip_audit": {"check_passed": True, "two_phase": replay},
        "attempt_budget_resume_audit": {"check_passed": True, "evidence": [cases[k] for k in ("after_fourth", "between_failure_and_next", "unsafe_abandoned")], "retry_budget_reset": False},
        "stage_barrier_snapshot_contract": barrier_contract, "frozen_activation_manifest_contract": {**barrier_contract, "freeze_before_JATS_dispatch": True, "immutable_after_commit": True},
        "stage_barrier_resume_test_results": {"check_passed": True, "evidence": [cases[k] for k in ("barrier_persistence", "barrier_before_activation", "activation_before_dispatch", "some_jats_success")]},
        "crash_recovery_fault_matrix": {"case_ids": list(CRASH_CASES), "scope": "22C crash safety only; not independent 22D release gate"},
        "crash_recovery_fault_matrix_results": matrix, "synthetic_two_phase_replay_manifest": {"input": replay["manifest"], "synthetic_only": True},
        "synthetic_two_phase_replay_results": replay, "journal_secret_redaction_audit": {"check_passed": True, "known_synthetic_secret_absent": True, "hash_after_22A_redaction": True},
        "journal_observability_schema_binding": binding, "resume_determinism_audit": cases["repeat_readonly_resume"], "journal_concurrent_writer_audit": cases["writer_contention"],
        "alpha3_21_continuation_prohibition_audit": {"closure": authority["closure"], "no_historical_execution_manifest_consumed": True, "alpha3_21_reopened": False},
        "legacy_runtime_preservation_audit": {"unchanged": authority["legacy"] + authority["alpha322a_sources"] + authority["alpha322b_sources"], "legacy_runtime_modified": False},
        "production_runtime_nonwiring_audit": boundary_audit(), "scientific_policy_firewall_audit": {**scope, "unchanged_bindings": authority["scientific_bindings"]},
        "contamination_baseline_immutability_audit": {"baseline": authority["registry"], **authority["counts"], "registry_changed": False},
        "historical_preservation_audit": {"upstream_roots": {k: authority[k] for k in ("master", "alpha322a", "alpha322b", "closure", "phase_roots")}, "historical_assets_modified": False},
        "scientific_state_safety_audit": {**scope, "no_new_scientific_source_exposure": True, "construction_or_candidate_artifacts_created": False},
        "focused_test_manifest": verification, "validation": {"status": "passed", "all_22C_gates_passed": True, "22D_22E_22F_completed": False, "fresh_primary_authorized": False}, "summary": summary}
    docs["alpha3_22c_reproducibility_bundle"] = {"authority": j.AUTHORITY,
        "implementation": implementation, "resume_implementation": resume_implementation, "barrier_contract": barrier_contract,
        "focused_verification": verification, "schema_bindings": binding, "crash_case_count": len(CRASH_CASES), "no_calls": NO_CALLS}
    require(set(REQUIRED) <= set(docs), "MISSING_22C_REQUIRED_DOCUMENTS")
    return docs


def run(verification):
    require(not OUT.exists(), "22C_OUTPUT_EXISTS_NO_OVERWRITE")
    require(verification["checks"] and all(r["check_passed"] is True for r in verification["checks"])
        and verification["implementation_sha256"] == digest(Path(__file__)) and verification["test_implementation_sha256"] == digest(TEST)
        and verification["component_sha256"] == {path.name: digest(path) for path in COMPONENTS}, "FOCUSED_VERIFICATION_SOURCE_BINDING")
    with master.prior.offline_guard():
        before = verify_authority()
        boundary_audit()
        store = t.RawArtifactStoreV1(OUT)
        local = OUT / "local_engineering_fixtures"
        local.mkdir()
        matrix = crash_matrix(local / "crash_matrix")
        replay = two_phase(local / "two_phase_replay")
        # No raw tokens in journal or companion JSON outputs.
        for path in local.rglob("*.json*"):
            require(b"synthetic-private-credential" not in path.read_bytes(), "JOURNAL_SECRET_LEAK")
        require(verify_authority() == before, "UPSTREAM_DRIFT_AFTER_FIXTURES")
        docs = build_documents(before, matrix, replay, verification)
        for marker, stem in MARKERS.items():
            value = j.sha(canonical(docs[stem]))
            docs["summary"][marker] = value
            store.freeze_bytes(marker, (value + "\n").encode())
        for stem, value in docs.items():
            store.freeze_bytes(stem + ".json", canonical(value))
        for value in docs.values():
            master.d2.d1.d.checked_tree(value)
        require(verify_authority() == before, "POST_FREEZE_UPSTREAM_DRIFT")
        root = master.root_hash(OUT, ROOT_MARKER)
        store.freeze_bytes(ROOT_MARKER, (root + "\n").encode())
        require(master.root_hash(OUT, ROOT_MARKER) == root, "22C_ROOT_MISMATCH")
        return {**docs["summary"], ROOT_MARKER: root}


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--verification", type=Path)
    parser.add_argument("--inspect-journal", type=Path)
    parser.add_argument("--synthetic-crash", type=Path)
    parser.add_argument("--case", choices=CRASH_CASES)
    args = parser.parse_args()
    with master.prior.offline_guard():
        if args.inspect_journal:
            print(json.dumps(read_plan(args.inspect_journal), sort_keys=True))
        elif args.synthetic_crash:
            crash_setup(args.synthetic_crash, args.case)
        else:
            require(args.verification is not None, "VERIFICATION_REQUIRED")
            print(json.dumps(run(obj(args.verification)), sort_keys=True))
