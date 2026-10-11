"""Preserve the stopped release preflight; never repair or restart its driver.

Only read-only forensics, non-executing engineering checks, and exclusive
failure-artifact freezes are performed. No scenario or regression is invoked.
"""

import json
import subprocess
import sys
from pathlib import Path

from scripts import run_search_plan_v24_alpha322_final_release_oracle_v2_offline as stopped

j, t, h, ROOT, OUT = stopped.j, stopped.t, stopped.h, stopped.ROOT, stopped.OUT
TRACE = '''Traceback (most recent call last):
  File "<stdin>", line 5, in <module>
  File "/home/vincent/project/conflict-oriented-discovery-engine/scripts/run_search_plan_v24_alpha322_final_release_oracle_v2_offline.py", line 92, in frozen_inputs
    t.require(scenario["expected"] == old["expected"], "ORIGINAL_EMBEDDED_EXPECTATION_DRIFT")
              ~~~~~~~~^^^^^^^^^^^^
KeyError: 'expected'
'''
INVARIANTS = (
    "partial_response_parser_quarantine", "UNKNOWN_automatic_retry_prohibition", "replay_safety",
    "four_attempt_budget", "attempt_ordinal_uniqueness", "write_ahead_durability_ordering",
    "journal_hash_chain_integrity", "successful_request_immutability", "terminal_noneligible_and_validity_failure_skipping",
    "OA_barrier_immutability", "JATS_activation_integrity", "same_request_attempt_evidence_binding",
    "runtime_identity_schema", "secret_redaction")


def freeze_failure():
    t.require(not OUT.exists(), "NEW_FAILURE_FREEZE_REQUIRED_NO_RELEASE_RERUN")
    before = stopped.authority()
    entry = Path(stopped.__file__)
    entry_raw = j.read_bytes(entry)
    t.require(b'scenario["expected"] == old["expected"]' in entry_raw, "FAILED_DRIVER_MUST_REMAIN_UNMODIFIED")
    original_raw = j.read_bytes(h.ORIGINAL / "independent_expected_outcomes.jsonl")
    scenario_raw = j.read_bytes(h.ORIGINAL / "frozen_fault_scenario_manifest.json")
    contract_path = stopped.CONTRACT / "versioned_change_manifest.json"
    contract = stopped.read(contract_path)
    v2_records = contract["oracle_v2"]["records"]
    v2_raw = b"".join(j.canonical(row) for row in v2_records)
    manifest = j.strict_json(scenario_raw)
    original_records = [j.strict_json(line) for line in original_raw.splitlines()]
    t.require(j.sha(original_raw) == stopped.ORIGINAL_ORACLE_SHA and j.sha(scenario_raw) == stopped.SCENARIO_SHA
              and j.sha(v2_raw) == stopped.V2_SHA, "FORENSIC_FROZEN_INPUT_DRIFT")
    t.require(len(v2_records) == 59 and len({row["scenario_id"] for row in v2_records}) == 59
              and [row["scenario_id"] for row in v2_records] == manifest["order"], "FORENSIC_IDENTITY_DRIFT")
    changes = []
    unchanged_lines = 0
    for old, new, raw in zip(original_records, v2_records, original_raw.splitlines(keepends=True)):
        if j.canonical(new) == raw:
            unchanged_lines += 1
        else:
            projection = dict(new, expected=dict(new["expected"], content_length_match="UNAVAILABLE"))
            t.require(projection == old and new["scenario_id"] == "T12"
                      and new["expected"]["content_length_match"] == "MISMATCH", "FORENSIC_EXTRA_ORACLE_CHANGE")
            changes.append({"scenario_id": "T12", "field": "content_length_match", "old": "UNAVAILABLE", "new": "MISMATCH"})
    t.require(len(changes) == 1 and unchanged_lines == 58, "FORENSIC_ORACLE_DIFF_FAILED")
    t.require(all("expected" not in row for row in manifest["scenarios"]), "FORENSIC_SCENARIO_SHAPE_CHANGED")

    OUT.mkdir()
    for name in ("execution", "inputs", "implementation"):
        (OUT / name).mkdir()
    for path in (entry, Path(__file__)):
        j.atomic_freeze(OUT / "implementation" / path.name, j.read_bytes(path))
    j.atomic_freeze(OUT / "execution/preflight_failure.txt", TRACE.encode())
    j.atomic_freeze(OUT / "inputs/original_scenarios.json", scenario_raw)
    j.atomic_freeze(OUT / "inputs/original_oracle.jsonl", original_raw)
    j.atomic_freeze(OUT / "inputs/oracle_v2.jsonl", v2_raw)

    stopped.emit("oracle_v1_v2_difference", {
        "status": "READ_ONLY_FORENSIC_CHECK_AFTER_STOP_NOT_RELEASE_RETRY", "changes": changes,
        "changed_scenario_count": 1, "other_58_expectations_byte_identical": True,
        "original_oracle_sha256": stopped.ORIGINAL_ORACLE_SHA, "oracle_v2_sha256": stopped.V2_SHA,
        "oracle_v2_source": h.ref(contract_path, "unchanged_frozen_V2_records"),
        "expectation_generation_function_calls": 0, "runtime_calls_to_calculate_expectations": 0,
        "frozen_inputs_are_not_the_failure_cause": True})
    stopped.emit("frozen_input_bindings", {
        "mode": "FAILED_OFFLINE_INDEPENDENT_RELEASE_PREFLIGHT_NO_EXECUTION",
        "freeze_purpose": "POST_FAILURE_PROVENANCE_ONLY_NOT_EXECUTION_AUTHORIZATION",
        "pre_execution_release_configuration_completed": False,
        "upstream_authority": before, "runtime_root_sha256": stopped.latest.REPAIR_SHA,
        "runtime_source_bindings": stopped.repair.load("source_manifest")["sources"],
        "intended_integration_entrypoint": [sys.executable, "-m", stopped.repair.__name__, "scenario"],
        "integration_entrypoint_invocations": 0,
        "test_harness_source": h.ref(Path(h.__file__), "frozen_latest_runtime_harness_not_executed"),
        "failed_release_driver": h.ref(entry, "preserved_unmodified_failed_preflight_driver"),
        "failed_release_driver_snapshot": h.ref(OUT / "implementation" / entry.name, "byte_identical_failed_source"),
        "failure_freezer": h.ref(Path(__file__), "failure_reporting_only_no_execution_or_repair"),
        "oracle_v2_source": h.ref(contract_path, "frozen_external_literal_records"),
        "oracle_v2_copy": h.ref(OUT / "inputs/oracle_v2.jsonl", "exact_frozen_V2_byte_stream"),
        "original_scenario_manifest": h.ref(OUT / "inputs/original_scenarios.json", "unaltered_source_only_scenario_definitions"),
        "original_oracle": h.ref(OUT / "inputs/original_oracle.jsonl", "unaltered_original_expected_values"),
        "oracle_v2_sha256": stopped.V2_SHA, "original_scenario_manifest_sha256": stopped.SCENARIO_SHA,
        "scenario_order": manifest["order"], "runtime_journal_authority": j.AUTHORITY,
        "scientific_policy_changed": False, "retry_policy_changed": False, **stopped.NO_CALLS})
    expected = {row["scenario_id"]: row["expected"] for row in v2_records}
    rows = [{"scenario_id": scenario["scenario_id"], "category": scenario["category"],
             "original_injection_point": scenario["injection_point"], "expected": expected[scenario["scenario_id"]],
             "actual": None, "status": "NOT_EXECUTED", "execution_status": "NOT_EXECUTED",
             "first_divergence": None, "reason": "RELEASE_PREFLIGHT_DRIVER_SCHEMA_ASSUMPTION_FAILED_CLOSED"}
            for scenario in manifest["scenarios"]]
    j.atomic_freeze(OUT / "scenario_results.jsonl", b"".join(j.canonical(row) for row in rows))
    stopped.emit("repair_regression_results", {
        "status": "NOT_EXECUTED", "all_passed": False, "reason": "release preflight failed before any executable work",
        "R0_positive": "NOT_EXECUTED", "R0_negatives": {"planned": 22, "executed": 0, "passed": 0},
        "runtime_identity_negatives": {"planned": 6, "executed": 0, "passed": 0},
        "T11_fixtures": {"planned": 12, "executed": 0, "passed": 0},
        "REC01_REC02": {"planned": 2, "executed": 0, "passed": 0},
        "length_counterexamples": {"planned": 11, "executed": 0, "passed": 0},
        "pytest_groups": {}, "pytest_test_count": 0, "historical_results_substituted": False})
    stopped.emit("critical_safety_invariants", {
        "evaluation_state": "NOT_EVALUATED", "checks": {key: "NOT_EVALUATED" for key in INVARIANTS},
        "critical_safety_failures": 0, "critical_release_preflight_failures": 1,
        "zero_observed_safety_failures_is_not_certification": True,
        "full_safety_coverage_completed": False, "unexecuted_domains_certified": False, **stopped.NO_CALLS})
    engineering = []
    for index, command in enumerate((
            [sys.executable, "-m", "compileall", "-q", *map(str, stopped.source_paths()), str(Path(__file__))],
            ["git", "diff", "--check"],
            ["git", "diff", "--no-index", "--check", "/dev/null", str(Path(__file__))])):
        process = subprocess.run(command, cwd=ROOT, capture_output=True, text=True)
        log = OUT / "execution" / ("engineering_%d.txt" % index)
        j.atomic_freeze(log, (process.stdout + process.stderr).encode())
        engineering.append({"command": command, "exit_code": process.returncode, "log": h.ref(log, "nonexecuting_engineering_check_after_stop"),
            "passed": process.returncode in ({0, 1} if "--no-index" in command else {0}) and not process.stdout and not process.stderr})
    after = stopped.authority()
    t.require(before == after and j.read_bytes(entry) == entry_raw, "HISTORICAL_OR_FAILED_DRIVER_DRIFT")
    stopped.emit("historical_preservation", {
        "before": before, "after": after, "passed": True, "historical_assets_modified": False,
        "runtime_source_modified": False, "original_oracle_modified": False, "failed_validation_driver_modified": False,
        "original_development_result_unchanged": {"root_sha256": stopped.LATEST_SHA, "passed": 58, "failed": 1},
        "contract_resolution_root_unchanged": stopped.CONTRACT_SHA,
        "alpha3_21_reopened": False, "scientific_policy_changed": False})
    stopped.emit("failure_evidence", {
        "phase": "PRE_EXECUTION_RELEASE_PREFLIGHT", "failure_category": "NEW_VALIDATION_DRIVER_SCHEMA_ASSUMPTION",
        "exception_class": "builtins.KeyError", "message": "expected",
        "trace": h.ref(OUT / "execution/preflight_failure.txt", "verbatim_observed_preflight_trace"),
        "failed_source": h.ref(OUT / "implementation" / entry.name, "exact_failed_source_snapshot"),
        "failure_location": str(entry.relative_to(ROOT)) + ":92",
        "root_cause": "The frozen scenario manifest intentionally contains source-only definitions and no expected member. Original expected outcomes are in independent_expected_outcomes.jsonl. The new driver incorrectly indexed scenario['expected'].",
        "frozen_runtime_defect_established": False, "frozen_oracle_defect_established": False,
        "scenario_executions": 0, "regression_executions": 0, "release_retries": 0,
        "minimal_correction_recommendation": "In a separately authorized engineering step, correct only the new validation loader's manifest-shape assumption; retain independent frozen oracle verification. Preserve this failed attempt and require a different new release directory.",
        "correction_implemented": False, "no_repair_no_rerun": True,
        "read_only_forensics_not_a_release_retry": True})
    summary = {
        "alpha3_22_release_status": "failed", "alpha3_22_release_classification": stopped.CLASS_FAIL,
        "oracle_version": "V2", "original_oracle_modified": False, "oracle_v2_frozen": True,
        "oracle_v2_sha256": stopped.V2_SHA, "oracle_v2_changed_scenario_count": 1,
        "oracle_v2_changed_scenario_id": "T12", "oracle_v2_changed_field": "content_length_match",
        "scenario_count": 59, "executed_count": 0, "passed_count": 0, "failed_count": 0, "not_executed_count": 59,
        "critical_release_preflight_failures": 1, "failure_phase": "PRE_EXECUTION_RELEASE_PREFLIGHT",
        "t05_passed": False, "t11_passed": False, "t12_passed_under_v2": False, "t17_passed": False, "t18_passed": False,
        "critical_safety_failures": 0, "safety_evaluation_state": "NOT_EVALUATED", "repair_regressions_passed": False,
        "independent_release_gate_passed": False, "runtime_source_modified": False, "retry_policy_changed": False,
        "scientific_policy_changed": False, "production_runtime_v2_wiring_enabled": False,
        "alpha3_21_reopened": False, "fresh_primary_attempt_started": False,
        "next_stage_recommendation": "MINIMAL_ENGINEERING_CORRECTION_OF_RELEASE_PREFLIGHT_SCHEMA_ASSUMPTION",
        "next_stage_automatically_started": False, "historical_assets_modified": False,
        "original_oracle_development_58_of_59_preserved": True, "release_reruns": 0, **stopped.NO_CALLS}
    stopped.emit("summary", summary)
    stopped.emit("validation", {
        "passed": False, "classification": stopped.CLASS_FAIL, "reason": "new release preflight driver error",
        "stopped_before_execution": True, "zero_scenario_reruns": True, "zero_regression_execution": True,
        "frozen_input_forensics_passed": True, "pre_execution_release_configuration_completed": False,
        "engineering_checks": engineering, "historical_assets_preserved": True,
        "no_22E_or_fresh_primary_execution": True, **stopped.NO_CALLS})
    t.require(all((OUT / (name + ".json")).is_file() for name in stopped.REQUIRED), "FAILURE_REPORT_MISSING")
    count = stopped.verify_report_references()
    j.atomic_freeze(OUT / "execution/reference_verification.json", j.canonical({"report_reference_count_verified": count,
        "all_artifact_references_verified": True, "no_actual_runtime_observations_or_release_pass_claimed": True}))
    root = stopped.master.root_hash(OUT, stopped.MARKER)
    j.atomic_freeze(OUT / stopped.MARKER, (root + "\n").encode())
    j.sync_directory(OUT)
    t.require(stopped.master.root_hash(OUT, stopped.MARKER) == root, "FAILED_RELEASE_ROOT_MISMATCH")
    return {**summary, "release_root_sha256": root, "workspace": str(OUT)}


if __name__ == "__main__":
    with stopped.master.prior.offline_guard():
        print(json.dumps(freeze_failure(), sort_keys=True))
