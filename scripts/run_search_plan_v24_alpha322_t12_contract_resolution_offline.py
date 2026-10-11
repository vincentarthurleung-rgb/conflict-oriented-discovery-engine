"""Offline validation-contract development, never an independent release gate.

Branch A: freeze a one-field Oracle V2 before executing the unchanged runtime.
The oracle is embedded in versioned_change_manifest.json to keep the requested
seven-report surface compact. Only original-oracle T12 failure evidence is
retained separately; successful synthetic execution artifacts are temporary.
"""

import argparse
import copy
import io
import json
import subprocess
import sys
import tempfile
from pathlib import Path

from scripts import run_search_plan_v24_alpha322_length_repair_full_59_diagnostic_offline as latest

repair, j, t, h, ROOT = latest.repair, latest.j, latest.t, latest.h, latest.ROOT
master = repair.previous.d.release.master
OUT = ROOT / "runs/20261010_search_plan_v24_dev_alpha3_22_t12_length_contract_resolution_offline"
MARKER = "search_plan_v24_dev_alpha3_22_t12_contract_resolution_sha256"
LATEST_SHA = "d5314eb4b2387cad9a7ab5318ee0ed6df7bf1b47a230ad97702bfc7035a05a04"
ORIGINAL_ORACLE_SHA = "b1d452438341fd2a01262f09a75649169dd726da119371b30388c4a464d6d817"
ORIGINAL_INPUT_SHA = "aed33640b5a88badd5a785b41019158ca369b656f20a5a150713b2e8f8eba23b"
ORIGINAL = ROOT / "runs/20261008_search_plan_v24_dev_alpha3_22d_independent_fault_injection_offline"
ORACLE = ORIGINAL / "independent_expected_outcomes.jsonl"
INPUTS = ORIGINAL / "frozen_fault_scenario_manifest.json"
REPORTS = ("summary", "t12_contract_decision", "t12_semantic_counterexamples", "versioned_change_manifest",
           "focused_test_results", "full_development_results", "historical_preservation")
NO_CALLS = dict(repair.NO_CALLS)


def emit(name, value):
    return j.atomic_freeze(OUT / (name + ".json"), j.canonical(value))


def load(name):
    return j.strict_json(j.read_bytes(OUT / (name + ".json")))


def authority():
    result = latest.authority()
    latest.sources_unchanged()
    result["latest_58_of_59_development"] = master.prior.root_check(latest.OUT, latest.MARKER, LATEST_SHA)
    summary = latest.load("summary")
    t.require([summary[k] for k in ("development_executed_count", "development_passed_count", "development_failed_count")] == [59, 58, 1],
              "HISTORICAL_DEVELOPMENT_ACCOUNTING_DRIFT")
    t.require(j.sha(j.read_bytes(ORACLE)) == ORIGINAL_ORACLE_SHA, "ORIGINAL_ORACLE_DRIFT")
    t.require(j.sha(j.read_bytes(INPUTS)) == ORIGINAL_INPUT_SHA, "ORIGINAL_INPUT_DRIFT")
    return result


def derive_oracle_v2(raw):
    """No SUT output is an input. Preserve every other original line byte-for-byte."""
    t.require(j.sha(raw) == ORIGINAL_ORACLE_SHA, "UNAUTHORIZED_ORACLE_INPUT")
    original_lines = raw.splitlines(keepends=True)
    revised_lines, changes = [], []
    for index, line in enumerate(original_lines):
        row = j.strict_json(line)
        if row["scenario_id"] == "T12":
            before = copy.deepcopy(row)
            t.require(row["expected"]["content_length_match"] == "UNAVAILABLE", "ORIGINAL_T12_EXPECTATION_DRIFT")
            needle = b'"content_length_match":"UNAVAILABLE"'
            t.require(line.count(needle) == 1, "NONUNIQUE_T12_EDIT_LOCATION")
            line = line.replace(needle, b'"content_length_match":"MISMATCH"', 1)
            revised = j.strict_json(line)
            before["expected"]["content_length_match"] = "MISMATCH"
            t.require(before == revised, "ORACLE_V2_NON_LENGTH_DIFFERENCE")
            changes.append({"scenario_id": "T12", "record_index": index,
                            "json_pointer": "/expected/content_length_match", "from": "UNAVAILABLE", "to": "MISMATCH"})
        revised_lines.append(line)
    t.require(len(original_lines) == 59 and len(changes) == 1, "ORACLE_V2_EXACTLY_ONE_CHANGE_REQUIRED")
    t.require(sum(a != b for a, b in zip(original_lines, revised_lines)) == 1, "ORACLE_V2_LINE_DRIFT")
    revised_raw = b"".join(revised_lines)
    records = [j.strict_json(line) for line in revised_lines]
    t.require(b"".join(j.canonical(row) for row in records) == revised_raw, "ORACLE_V2_RECONSTRUCTION_DRIFT")
    return {"version": "VersionedOracleV2_T12ObservedByteComparison", "records": records,
            "serialization": "concatenate canonical JSON records with one LF per record; original order",
            "jsonl_sha256": j.sha(revised_raw), "changes": changes,
            "other_58_records_byte_identical": True, "record_count": 59}


def prepare():
    t.require(not OUT.exists() and not OUT.is_symlink(), "NEW_DEVELOPMENT_DIRECTORY_REQUIRED")
    before = authority()
    findings = repair.previous.d.source_findings()
    OUT.mkdir()
    # This decision is frozen before the revised oracle or any new test results.
    emit("t12_contract_decision", {
        "mode": "OFFLINE_ENGINEERING_VALIDATION_CONTRACT_DEVELOPMENT_NOT_INDEPENDENT_RELEASE_VALIDATION",
        "selected_branch": "A", "decision_frozen_before_new_execution": True,
        "exact_conflict": {"fault_phase": "RESPONSE_BODY_READING", "exception_class": "builtins.RuntimeError",
            "trusted_wire_Content_Length": 50, "recoverable_observed_wire_bytes": 0, "normal_read_return": False,
            "original_oracle": "UNAVAILABLE", "frozen_22A_comparison": "MISMATCH"},
        "separate_questions": {
            "received_count": "bytes_read / actual_content_length counts preserved observed bytes; not an assertion of all bytes ever arriving on the wire",
            "complete_body": "requires normal read return, passing authoritative framing, and no comparable mismatch",
            "completed_body_consistency": "not established for T12; body remains BODY_COMPLETION_UNKNOWN",
            "existing_field": "content_length_match compares trusted same-representation declared length with observed preserved bytes, including interrupted reads"},
        "frozen_evidence": findings,
        "additional_contract_evidence": [h.ref(master.OUT / "response_body_interruption_semantics.json", "unknown_is_not_inferred_to_be_retryable_interruption"),
            h.ref(master.OUT / "transport_observability_contract_v1_draft.json", "observation_is_not_retry_authority"),
            h.ref(ORACLE, "original_literals_T05_T06_T07_already_require_interrupted_MISMATCH"),
            h.ref(repair.OUT / "length_representation_negative_tests.json", "previously_frozen_normal_empty_interrupted_and_representation_counterexamples")],
        "proof": [
            "Frozen BodyCompletionResultV2 requires actual_content_length == bytes_read, regardless of read completion.",
            "Frozen length_available requires trusted expected count and identical known byte representations, not normal read return.",
            "Frozen assess_body_completion computes length observation independently, then gives interruption/UNKNOWN precedence over mismatch for failure classification.",
            "Original independent T05/T06/T07 literals independently require MISMATCH for interrupted reads; T12 alone inherits transport_spec's UNAVAILABLE default.",
            "The original fixture explicitly supplies Content-Length: 50; its RuntimeError supplies no recoverable partial bytes. Neither a normal empty EOF nor absence of all wire traffic is inferred.",
            "Master completion rule and frozen 22A admission invariants separately prohibit partial/unknown parser access; comparison grants no completion or retry authority."],
        "why_not_B": "A completed-response-only interpretation would change the frozen observed-count field and established interrupted T05/T06/T07 semantics. No such prerequisite exists in frozen 22A.",
        "why_not_C": "Field invariants, comparison prerequisites, semantic precedence, and independent interrupted oracle literals resolve the authority question consistently.",
        "safety_preserved": {"T12_body_incomplete": True, "T12_UNKNOWN_RUNTIME_FAILURE": True,
            "T12_parser_quarantined": True, "T12_retry_authorized": False,
            "no_completion_inferred_from_MATCH": True, "no_retry_inferred_from_MISMATCH": True},
        "scientific_reproducibility": "Same original input identities/order and explicit observed-byte meaning; never manufacture completed bytes or scientific validity.",
        "branch_selected_for_59_of_59": False, "historical_assets_modified": False, **NO_CALLS})
    v2 = derive_oracle_v2(j.read_bytes(ORACLE))
    emit("versioned_change_manifest", {
        "change_scope": "VALIDATION_ORACLE_ONLY", "oracle_v2": v2,
        "oracle_location": "versioned_change_manifest.json#/oracle_v2/records",
        "original_oracle": h.ref(ORACLE, "immutable_original_oracle"),
        "original_scenario_inputs": h.ref(INPUTS, "immutable_all_59_original_inputs_including_original_embedded_expected_literals"),
        "decision": h.ref(OUT / "t12_contract_decision.json", "pre_execution_independent_contract_decision"),
        "runtime_version": "byte-frozen length-bound V1 repair; unchanged frozen 22A length/completion semantics",
        "runtime_root_sha256": latest.REPAIR_SHA,
        "runtime_source_bindings": repair.load("source_manifest")["sources"],
        "development_driver": h.ref(Path(__file__), "new_execution_reporting_and_validation_oracle_derivation_only"),
        "historical_preservation_before": before,
        "original_oracle_modified": False, "historical_runtime_modified": False,
        "versioned_oracle_created": True, "versioned_runtime_semantics_created": False,
        "scientific_policy_changed": False, "retry_policy_changed": False, "journal_integrity_weakened": False,
        "original_58_of_59_not_relabelled": True, "future_gate_label": "59/59 under Versioned Oracle V2",
        "independent_release_gate_passed": False, **NO_CALLS})
    return {"prepared": True, "decision": "A", "oracle_v2_sha256": v2["jsonl_sha256"]}


def unchanged():
    latest.sources_unchanged()
    change = load("versioned_change_manifest")
    binding = change["development_driver"]
    t.require(j.sha(j.read_bytes(ROOT / binding["artifact_path"])) == binding["sha256"], "DEVELOPMENT_DRIVER_DRIFT")
    t.require(change["oracle_v2"] == derive_oracle_v2(j.read_bytes(ORACLE)), "VERSIONED_ORACLE_DRIFT")
    t.require(j.sha(j.read_bytes(INPUTS)) == ORIGINAL_INPUT_SHA, "ORIGINAL_INPUT_DRIFT")


def execute_scenario(key, directory):
    unchanged()
    directory.parent.mkdir(parents=True, exist_ok=True)
    command = [sys.executable, "-m", repair.__name__, "scenario", "--key", key, "--output", str(directory)]
    process = subprocess.run(command, cwd=ROOT, capture_output=True, text=True)
    try:
        row = j.strict_json(process.stdout.encode())
        t.require(process.returncode == 0 and row.get("scenario_id") == key, "SCENARIO_CHILD_FAILED")
    except (ValueError, TypeError):
        row = {"scenario_id": key, "actual": {}, "execution_error": {"exit_code": process.returncode,
                "stdout": process.stdout, "stderr": process.stderr}}
    manifest, original = repair.previous.d.release.prior.frozen_inputs()
    revised = {r["scenario_id"]: r["expected"] for r in load("versioned_change_manifest")["oracle_v2"]["records"]}
    error = row.get("execution_error") or row.get("durable_terminal_error")
    differences = {"original": h.compare(original[key], row.get("actual") or {}),
                   "v2": h.compare(revised[key], row.get("actual") or {})}
    compact = {"scenario_id": key, "category": next(s["category"] for s in manifest["scenarios"] if s["scenario_id"] == key),
        "actual": row.get("actual"), "execution_error": error, "subprocess_exit_code": process.returncode,
        "original_oracle_mismatches": differences["original"], "versioned_oracle_mismatches": differences["v2"],
        "original_oracle_passed": not error and not differences["original"],
        "versioned_oracle_passed": not error and not differences["v2"],
        "fresh_reader_read_only": row.get("fresh_reader_read_only"), "raw_hash_verified": row.get("raw_hash_verified"),
        "journal_entry_hashes": row.get("journal_entry_hashes"),
        "execution_stdout_sha256": j.sha(process.stdout.encode()), "stderr": process.stderr,
        "reproduction_command": command,
        "reproduction_note": "use a NEW output directory; original scenario input only, no revised expectations enter the runtime",
        "synthetic_success_artifact_retention": "temporary; normalized actual observations and journal hashes retained in this report"}
    if error or differences["v2"]:
        compact["failure_detail"] = row
    return compact, row


def body_counterexample(key, directory, *, size, expected, normal, representation=t.ByteRepresentation.WIRE):
    raw = io.BytesIO(b"x" * size).read()
    directory.mkdir(parents=True)
    # C/D/K are explicit known semantic interruption units, not mappings from
    # an exception name. I separately exercises the actual unmapped error.
    completion = t.assess_body_completion(raw, read_returned_normally=normal,
        expected_content_length=expected, expected_length_trustworthy=expected is not None,
        expected_length_representation=t.ByteRepresentation.WIRE, byte_representation=representation,
        interruption_class=t.SemanticFailure.RESPONSE_BODY_TRANSPORT_INTERRUPTION if not normal else None, timestamp=h.NOW)
    artifact = t.RawArtifactStoreV1(directory / "raw").freeze_bytes("response.bin", raw)
    context = t.AttemptContextV1("counterexample:" + key, j.sha(key.encode()), 1)
    response = t.FrozenTransportResponseV2(context, completion, artifact, True)
    invocations, rejection = [], None
    try:
        t.guarded_parse(response, lambda value: invocations.append(len(value)))
    except t.TransportContractError as exc:
        rejection = str(exc)
    retry = t.semantic_retry_decision(completion.semantic_failure, request_replay_safe=True, attempt_ordinal=1)
    unsafe = t.semantic_retry_decision(completion.semantic_failure, request_replay_safe=False, attempt_ordinal=1)
    exhausted = t.semantic_retry_decision(completion.semantic_failure, request_replay_safe=True, attempt_ordinal=4)
    return {"counterexample_id": key, "evidence_scope": "explicit local body semantic/guard unit; no scientific parser",
        "read_returned_normally": normal, "expected_length": expected, "observed_preserved_bytes": size,
        "actual_representation": representation.value, "expected_representation": "wire",
        "content_length_match": completion.content_length_match, "body_state": completion.body_completion_state.value,
        "semantic_failure": completion.semantic_failure.value, "authoritative": response.authoritative,
        "complete_body_sha256": completion.body_sha256, "parser_invocations": len(invocations), "parser_rejection": rejection,
        "retry_authorized_replay_safe_attempt_1": retry.retry_authorized,
        "retry_authorized_replay_unsafe": unsafe.retry_authorized, "retry_authorized_exhausted_budget": exhausted.retry_authorized}


def counterexamples(directory, focused):
    # Literal expectations decided from frozen contracts, not actual outputs.
    specs = {
        "A": (50, 50, True, t.ByteRepresentation.WIRE, "MATCH", "BODY_COMPLETE", "NO_TECHNICAL_FAILURE", 1, False),
        "B": (0, 50, True, t.ByteRepresentation.WIRE, "MISMATCH", "BODY_INTERRUPTED", "RESPONSE_BODY_LENGTH_MISMATCH", 0, True),
        "C": (0, 50, False, t.ByteRepresentation.WIRE, "MISMATCH", "BODY_INTERRUPTED", "RESPONSE_BODY_TRANSPORT_INTERRUPTION", 0, True),
        "D": (20, 50, False, t.ByteRepresentation.WIRE, "MISMATCH", "BODY_INTERRUPTED", "RESPONSE_BODY_TRANSPORT_INTERRUPTION", 0, True),
        "E": (50, None, True, t.ByteRepresentation.WIRE, "UNAVAILABLE", "BODY_COMPLETE", "NO_TECHNICAL_FAILURE", 1, False),
        "F": (100, 50, True, t.ByteRepresentation.DECODED, "UNAVAILABLE", "BODY_COMPLETE", "NO_TECHNICAL_FAILURE", 1, False),
        "K": (50, 50, False, t.ByteRepresentation.WIRE, "MATCH", "BODY_INTERRUPTED", "RESPONSE_BODY_TRANSPORT_INTERRUPTION", 0, True)}
    rows = []
    for key, (size, expected, normal, rep, match, state, semantic, parsers, retry) in specs.items():
        row = body_counterexample(key, directory / key, size=size, expected=expected, normal=normal, representation=rep)
        wanted = {"content_length_match": match, "body_state": state, "semantic_failure": semantic,
                  "parser_invocations": parsers, "retry_authorized_replay_safe_attempt_1": retry,
                  "retry_authorized_replay_unsafe": False, "retry_authorized_exhausted_budget": False}
        row.update(expected=wanted, mismatches=h.compare(wanted, row))
        row["passed"] = not row["mismatches"] and (normal or row["complete_body_sha256"] is None)
        rows.append(row)
    wire = repair.lf.execute("L06", directory / "G")
    rows.append({"counterexample_id": "G", "description": "decoded acquired bytes plus independently frozen trusted wire actual count",
        "decoded_observed_bytes": wire["acquired_bytes"], "declared_wire_length": wire["trusted_expected_length_preserved"],
        "decoded_comparison": wire["content_length_match"], "wire_comparison": wire["actual_exact_outcome"],
        "journal_committed": wire["journal_committed"], "passed": wire["passed"] and wire["content_length_match"] == "UNAVAILABLE"
            and wire["actual_exact_outcome"] == "MATCH", "expected": {"decoded_comparison": "UNAVAILABLE", "wire_comparison": "MATCH"}})
    malformed, _ = execute_scenario("T10", directory / "H")
    rows.append({"counterexample_id": "H", "description": "malformed XML after complete transport; validity failure is nonretryable",
                 "execution": malformed, "passed": malformed["versioned_oracle_passed"]})
    trace = repair.previous.d.actual_read_trace()
    unknown = focused["T12"]["actual"]
    rows.append({"counterexample_id": "I", "description": "actual frozen unmapped RuntimeError during BODY_READING",
        "actual_bound_read_trace": trace, "full_path_actual": unknown,
        "passed": trace["content_length_match"] == "MISMATCH" and trace["read_returned_normally"] is False
            and trace["recoverable_bytes"] == 0 and unknown["semantic_failure_class"] == "UNKNOWN_RUNTIME_FAILURE"
            and not unknown["retry_authorized"] and not unknown["body_complete"]
            and not any(unknown["parser_invocation_counts"].values()) and unknown["next_attempt_ordinal"] is None})
    forged = repair.lf.execute("L10", directory / "J")
    rows.append({"counterexample_id": "J", "description": "attempt to mark exception-terminated partial completion authoritative",
        "expected_rejection": "UNPROVEN_BODY_COMPLETION", "actual_rejection": forged["actual_first_rejection"],
        "parser_invocations": forged["parser_invocations"], "journal_terminal_count": forged["journal_terminal_count"],
        "passed": forged["passed"] and forged["journal_terminal_count"] == 0})
    rows.sort(key=lambda row: row["counterexample_id"])
    return {"required_counterexamples": "A-J", "additional_counterexample": "K: interrupted after observing exactly 50 bytes; MATCH still cannot prove completion",
        "counterexamples": rows, "counterexample_count": len(rows), "passed_count": sum(row["passed"] for row in rows),
        "all_passed": all(row["passed"] for row in rows), "partial_parser_admissions": 0,
        "scientific_parsers_or_extraction_run": False, "retry_mapping_and_budget_unchanged": True}


def regression_suite(directory):
    groups = {"length_representation": [repair.TEST],
        "22A": [ROOT / "tests/test_search_plan_v24_alpha322a_transport_observability_offline.py"],
        "22B_retry_mapping": [ROOT / "tests/test_search_plan_v24_alpha322b_exception_mapping_offline.py"],
        "22C_journal_resume": [ROOT / "tests/test_search_plan_v24_alpha322c_attempt_journal_resume_offline.py"],
        "R2": [repair.previous.d.release.r2.CONSTRUCTION_TEST, repair.previous.d.release.r2.INTEGRITY_TEST,
               repair.previous.d.release.r2.ISOLATION_TEST], "T11": repair.previous.d.release.development.TESTS}
    results = {}
    directory.mkdir()
    for key, paths in groups.items():
        value = repair.run_pytest(key, paths, directory)
        results[key] = {k: v for k, v in value.items() if k not in {"log", "junit"}}
        results[key]["test_output"] = j.read_bytes(ROOT / value["log"]["artifact_path"]).decode()
        results[key]["junit_xml"] = j.read_bytes(ROOT / value["junit"]["artifact_path"]).decode() if value["junit"] else None
    positive = repair.r0.positive(directory / "R0_positive")
    negatives = [repair.r0.negative(directory / row["fixture_id"], row)
                 for row in repair.r0.source_spec("repair_negative_fixture_specification")["fixtures"]]
    identities = [repair.ri.negative(directory / row["fixture_id"], row) for row in
                  j.strict_json(j.read_bytes(repair.ri.R11 / "r2_runtime_identity_negative_fixture_spec.json"))["fixtures"]]
    recoveries = repair.r0.recovery(directory / "recovery")
    validators = [repair.vf.execute(key, directory / ("T11_" + key)) for key in repair.vf.SPEC]
    fixtures = [positive] + negatives + identities + recoveries + validators
    fixture_summary = [{"fixture_id": row.get("fixture_id", "R0_positive"), "passed": row["passed"],
                        "full_observation_sha256": j.sha(j.canonical(row))} for row in fixtures]
    return {"pytest_groups": results, "pytest_tests": sum(row["tests"] for row in results.values()),
        "pytest_failures": sum(row["failures"] + row["errors"] for row in results.values()),
        "explicit_length_bound_runtime_fixtures": fixture_summary, "explicit_fixture_count": len(fixtures),
        "explicit_fixture_passed_count": sum(row["passed"] for row in fixtures),
        "all_passed": all(row["passed"] for row in results.values()) and all(row["passed"] for row in fixtures),
        "full_repository_suite_claimed": False, "fresh_process_offline_guard": True}


def execute():
    t.require(not (OUT / MARKER).exists(), "FROZEN_RUN_IMMUTABLE")
    unchanged()
    manifest, original = repair.previous.d.release.prior.frozen_inputs()
    with tempfile.TemporaryDirectory(prefix="alpha322-t12-contract-development-") as temp:
        scratch = Path(temp)
        focused = {}
        for key in ("T12", "T05", "T11", "T17", "T18"):
            focused[key], _ = execute_scenario(key, scratch / "focus" / key)
            print("focused " + key + ": " + str(focused[key]["versioned_oracle_passed"]), flush=True)
        counters = counterexamples(scratch / "counterexamples", focused)
        emit("t12_semantic_counterexamples", counters)
        regressions = regression_suite(scratch / "regressions")
        focus_passed = all(row["versioned_oracle_passed"] for row in focused.values())
        emit("focused_test_results", {"scenarios": focused, "counterexamples_passed": counters["all_passed"],
            "regressions": regressions, "all_selected_contract_checks_passed": focus_passed and counters["all_passed"] and regressions["all_passed"],
            "T12_original_oracle_passed": focused["T12"]["original_oracle_passed"], "mode": "DEVELOPMENT_ONLY"})
        t.require(focus_passed and counters["all_passed"] and regressions["all_passed"], "FOCUSED_DEVELOPMENT_BARRIER_FAILED")
        # V2 expected outcomes are already frozen; each original input executes once.
        rows = []
        for key in manifest["order"]:
            destination = OUT / "failure_evidence" / "T12" if key == "T12" else scratch / "matrix" / key
            if key == "T12":
                destination.parent.mkdir()
            row, full = execute_scenario(key, destination)
            if key == "T12":
                evidence = destination / "original_oracle_failure_trace.json"
                j.atomic_freeze(evidence, j.canonical(full))
                row["failure_evidence"] = h.ref(evidence, "preserved_original_oracle_T12_failure_not_waived")
                row["synthetic_success_artifact_retention"] = "not applicable; original-oracle failure raw/journal/trace preserved"
            elif row["execution_error"] or not row["versioned_oracle_passed"]:
                # Unexpected failures must retain their exact synthetic bytes, too.
                import shutil
                evidence = OUT / "failure_evidence" / key
                evidence.parent.mkdir(exist_ok=True)
                shutil.copytree(destination, evidence)
                row["unexpected_failure_artifact_copy"] = str(evidence.relative_to(ROOT))
            rows.append(row)
            print("development " + key + ": original=" + str(row["original_oracle_passed"])
                  + " V2=" + str(row["versioned_oracle_passed"]), flush=True)
        emit("full_development_results", {"mode": "DEVELOPMENT_NOT_INDEPENDENT_RELEASE_VALIDATION",
            "original_input_manifest": h.ref(INPUTS, "all_59_original_scenario_inputs"),
            "oracle_v2": h.ref(OUT / "versioned_change_manifest.json", "embedded_pre_execution_V2_oracle"),
            "same_actual_execution_compared_to_both_oracles": True, "matrix_scenario_reruns": 0,
            "scenario_count": len(rows), "executed_count": len(rows),
            "original_oracle_passed_count": sum(row["original_oracle_passed"] for row in rows),
            "original_oracle_failed_count": sum(not row["original_oracle_passed"] for row in rows),
            "versioned_oracle_passed_count": sum(row["versioned_oracle_passed"] for row in rows),
            "versioned_oracle_failed_count": sum(not row["versioned_oracle_passed"] for row in rows),
            "original_order_preserved": [row["scenario_id"] for row in rows] == manifest["order"],
            "runtime_received_revised_oracle": False, "scenarios": rows, "independent_release_gate_passed": False})
    unchanged()
    return {"executed_count": len(rows), "V2_passed": sum(row["versioned_oracle_passed"] for row in rows)}


def freeze():
    t.require(not (OUT / MARKER).exists(), "FROZEN_RUN_IMMUTABLE")
    unchanged()
    change = load("versioned_change_manifest")
    before, after = change["historical_preservation_before"], authority()
    t.require(before == after, "HISTORICAL_AUTHORITY_CHANGED")
    full, focus, counters = load("full_development_results"), load("focused_test_results"), load("t12_semantic_counterexamples")
    rows = full["scenarios"]
    all_passed = len(rows) == 59 and all(row["versioned_oracle_passed"] for row in rows) and focus["all_selected_contract_checks_passed"]
    original_differences = [{"scenario_id": row["scenario_id"], "mismatches": row["original_oracle_mismatches"]}
                            for row in rows if not row["original_oracle_passed"]]
    t.require(original_differences == [{"scenario_id": "T12", "mismatches": [
        {"field": "content_length_match", "expected": "UNAVAILABLE", "actual": "MISMATCH"}]}], "UNEXPECTED_ORIGINAL_COMPATIBILITY_DIFFERENCE")
    t12 = next(row for row in rows if row["scenario_id"] == "T12")
    t.require(t12["actual"]["semantic_failure_class"] == "UNKNOWN_RUNTIME_FAILURE"
              and t12["actual"]["body_complete"] is False and not t12["actual"]["retry_authorized"]
              and not any(t12["actual"]["parser_invocation_counts"].values()), "T12_SAFETY_DRIFT")
    nonwiring = repair.nonwiring()
    t.require(nonwiring["passed"], "PRODUCTION_WIRING_FORBIDDEN")
    emit("historical_preservation", {"before": before, "after": after, "verified_equal": True,
        "original_oracle_sha256": ORIGINAL_ORACLE_SHA, "original_inputs_sha256": ORIGINAL_INPUT_SHA,
        "latest_historical_result_unchanged": {"root_sha256": LATEST_SHA, "executed": 59, "passed": 58, "failed": 1},
        "original_22D_root_unchanged": "e265bb83e8b169fa18b1adb2e0b9ca39e1c0d85908916fb8f365028371bdbadc",
        "alpha3_21_closure_unchanged": "3e066b012a0b422c1b1c97f68364bd9bd8373ee78c53665322f665c61d84a788",
        "all_frozen_runtime_bindings_byte_identical": True, "historical_assets_modified": False,
        "original_oracle_modified": False, "historical_runtime_modified": False, "nonwiring": nonwiring})
    summary = {"t12_contract_decision": "A", "t12_contract_resolution_completed": bool(all_passed),
        "status": "completed" if all_passed else "development_failed", "mode": "DEVELOPMENT_NOT_INDEPENDENT_RELEASE_VALIDATION",
        "original_oracle_modified": False, "historical_runtime_modified": False,
        "versioned_oracle_created": True, "versioned_runtime_semantics_created": False,
        "t12_original_oracle_passed": False, "t12_versioned_contract_passed": t12["versioned_oracle_passed"],
        "development_scenario_count": 59, "development_executed_count": len(rows),
        "development_passed_count": full["versioned_oracle_passed_count"], "development_failed_count": full["versioned_oracle_failed_count"],
        "original_oracle_compatibility": {"passed": full["original_oracle_passed_count"], "failed": full["original_oracle_failed_count"],
                                          "differences": original_differences, "gate_passed": False},
        "versioned_oracle_compatibility": {"passed": full["versioned_oracle_passed_count"], "failed": full["versioned_oracle_failed_count"],
                                           "label": "59/59 under Versioned Oracle V2" if all_passed else "V2 development failure"},
        "oracle_v2_jsonl_sha256": change["oracle_v2"]["jsonl_sha256"], "runtime_root_sha256": latest.REPAIR_SHA,
        "counterexamples_passed_count": counters["passed_count"], "counterexample_count": counters["counterexample_count"],
        "pytest_tests": focus["regressions"]["pytest_tests"], "pytest_failures": focus["regressions"]["pytest_failures"],
        "explicit_runtime_fixture_count": focus["regressions"]["explicit_fixture_count"],
        "remaining_runtime_defects": sum(bool(row["execution_error"] or row["versioned_oracle_mismatches"]) for row in rows),
        "remaining_contract_conflicts": 0, "original_oracle_contract_differences_preserved": 1,
        "independent_release_gate_passed": False, "scientific_policy_changed": False,
        "retry_policy_changed": False, "journal_integrity_weakened": False, "historical_assets_modified": False,
        "next_stage_recommendation": "NEW_INDEPENDENT_ALPHA3_22_RELEASE_VALIDATION_UNDER_VERSIONED_ORACLE_V2" if all_passed else "AUDIT_DEVELOPMENT_FAILURE_OFFLINE",
        "next_release_requirements": ["new run directory", "explicit frozen length-bound V1 runtime root and all source bindings",
            "explicit Oracle V2 records and SHA-256", "all original 59 full scenario definitions and independent expected outcomes",
            "all original plus R2, T11, representation and A-J repair regressions", "not a release pass until independently executed",
            "any future result must say 59/59 under Versioned Oracle V2, never under the original oracle"], **NO_CALLS}
    emit("summary", summary)
    t.require({path.name for path in OUT.glob("*.json")} == {name + ".json" for name in REPORTS}, "REPORT_SURFACE_DRIFT")
    unchanged()
    t.require(before == authority(), "HISTORICAL_AUTHORITY_DRIFT_AT_SEAL")
    root = master.root_hash(OUT, MARKER)
    j.atomic_freeze(OUT / MARKER, (root + "\n").encode())
    j.sync_directory(OUT)
    t.require(master.root_hash(OUT, MARKER) == root, "POST_FREEZE_ROOT_MISMATCH")
    return {**summary, "development_root_sha256": root, "workspace": str(OUT)}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("operation", choices=("prepare", "execute", "freeze"))
    args = parser.parse_args()
    with master.prior.offline_guard():
        print(json.dumps(globals()[args.operation](), sort_keys=True))
