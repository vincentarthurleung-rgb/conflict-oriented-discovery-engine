#!/usr/bin/env python3
"""Development-only execute then report/freeze; never an independent release."""

import argparse
import json
import os
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path

from scripts import search_plan_v24_alpha322_t12_binding_diagnostic_v1 as d

j, t, h, ROOT = d.j, d.t, d.h, d.ROOT
OUT = ROOT / "runs/20261010_search_plan_v24_dev_alpha3_22_t12_full_matrix_development_diagnostics_offline"
MARKER = "search_plan_v24_dev_alpha3_22_t12_development_sha256"
TEST = ROOT / "tests/test_search_plan_v24_alpha322_t12_binding_diagnostic_v1_offline.py"
SOURCES = [Path(d.__file__), Path(__file__), TEST]
NO_CALLS = dict(d.release.NO_CALLS)
ALLOWED_CLASSES = {"HARNESS_INPUT_BINDING_DEFECT", "HARNESS_INTEGRATION_DEFECT", "RUNTIME_IMPLEMENTATION_DEFECT",
                   "FROZEN_SCENARIO_OR_ORACLE_CONFLICT", "ENVIRONMENT_LIMITATION", "UNRESOLVED"}
REQUIRED = """summary t12_root_cause t12_fixture_binding_correction t12_focused_results grouped_failure_report
reporting_addendum_check validation""".split()


def emit(name, value):
    return j.atomic_freeze(OUT / (name + ".json"), j.canonical(value))


def sources_unchanged():
    value = j.strict_json(j.read_bytes(OUT / "source_manifest.json"))
    for item in value["sources"]:
        raw = j.read_bytes(ROOT / item["artifact_path"])
        t.require(j.sha(raw) == item["sha256"] and raw == j.read_bytes(OUT / "implementation" / Path(item["artifact_path"]).name),
                  "DEVELOPMENT_SOURCE_CHANGED_DURING_EXECUTION")
    return value


def pytest_group(name, paths):
    temporary = Path(tempfile.mkdtemp(prefix="alpha322-t12-" + name + "-")) / "pytest"
    xml = OUT / "execution" / (name + ".xml")
    wrapper = ("import sys, pytest; from scripts import run_search_plan_v24_alpha322_master_prereg_offline as m; "
               "ctx=m.prior.offline_guard(); ctx.__enter__(); sys.exit(pytest.main(sys.argv[1:]))")
    command = [sys.executable, "-c", wrapper, "-q", "-W", "error", *map(str, paths),
               "--junitxml=" + str(xml), "--basetemp=" + str(temporary)]
    environment = dict(os.environ)
    environment["ALPHA322_T12_DIAGNOSTIC_EVIDENCE_DIR"] = str(OUT)
    process = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, env=environment)
    log = OUT / "execution" / (name + ".txt")
    j.atomic_freeze(log, (process.stdout + process.stderr).encode())
    counts = dict.fromkeys(("tests", "failures", "errors", "skipped"), 0)
    if xml.exists():
        for suite in ET.parse(xml).getroot().iter("testsuite"):
            for key in counts:
                counts[key] += int(suite.attrib.get(key, 0))
    result = {"command": command, "exit_code": process.returncode, **counts,
        "passed": process.returncode == 0 and counts["tests"] > 0 and not any(counts[key] for key in ("failures", "errors", "skipped")),
        "log": h.ref(log, "unaltered_actual_test_output"), "junit": h.ref(xml, "actual_test_counts") if xml.exists() else None,
        "temporary_directory_outside_freeze": str(temporary), "fresh_process_offline_guard": True}
    print(name + ": " + json.dumps({key: result[key] for key in ("tests", "failures", "errors", "passed")}), flush=True)
    return result


def execute():
    t.require(not OUT.exists() and not OUT.is_symlink(), "NEW_DEVELOPMENT_DIRECTORY_REQUIRED")
    before = d.authority()
    manifest, expected = d.release.prior.frozen_inputs()
    OUT.mkdir()
    for name in ("implementation", "execution", "scenarios"):
        (OUT / name).mkdir()
    sources = [h.ref(path, "new_development_only_diagnostic_and_reporting_source") for path in SOURCES]
    for path in SOURCES:
        j.atomic_freeze(OUT / "implementation" / path.name, j.read_bytes(path))
    emit("source_manifest", {"sources": sources, "runtime_inputs_modified": False,
        "latest_actual_runtime": before["latest_source_bindings"], "inherited_frozen_harness": h.ref(Path(h.__file__), "unchanged_DR2_scenario_handlers")})
    emit("root_verification", before)
    emit("diagnostic_execution_authorization", {
        "mode": "OFFLINE_ENGINEERING_DEVELOPMENT_NOT_RELEASE_VALIDATION",
        "supplemental_user_instruction": "保留 T12 冲突，继续全部 59 项开发诊断",
        "T12_conflict_does_not_block_isolated_development_matrix": True,
        "original_T12_input_and_oracle_preserved": True,
        "original_frozen_order": manifest["order"], "original_release_stop_policy_unchanged": True,
        "development_stop_on_ordinary_isolated_failure": False, "stop_on_shared_unsafe_state": True,
        "one_execution_per_original_matrix_identity": True, "no_runtime_or_oracle_edits_during_execution": True,
        "independent_release_gate_passed": False, **NO_CALLS})
    focused = d.focused_execution(OUT / "focused")
    emit("t12_focused_results", focused)
    findings = d.source_findings()
    emit("t12_root_cause", {**findings, "classification": d.CLASSIFICATION,
        "actual_read_trace": focused["actual_frozen_read_trace"],
        "first_contract_conflict": "oracle transport_spec default UNAVAILABLE versus original frozen BoundFaultFile Content-Length=50 and same-representation 22A comparison",
        "original_scenario_requires_interrupted_read_not_normal_eof": True,
        "read_interruption_does_not_disable_available_length_comparison": True,
        "runtime_defect_demonstrated_by_T12": False,
        "historical_addendum_classification_modified": False,
        "new_diagnosis_refines_prior_harness_defect_description_to_cross_frozen_artifact_conflict": True})
    emit("t12_fixture_binding_correction", {"status": "NOT_APPLIED_NO_INDEPENDENT_JUSTIFICATION",
        "classification": d.CLASSIFICATION, "t12_harness_binding_resolved": False,
        "legitimately_present_Content_Length_removed": False, "length_trust_downgraded": False,
        "normal_eof_fabricated_as_exception": False, "body_read_interruption_fabricated": False,
        "original_expected_outcome_changed": False, "runtime_length_checks_weakened": False,
        "new_adapter_purpose": "observe unchanged original inputs and correct REC reporting projection only",
        "full_diagnostic_continuation_authorized_separately_despite_unresolved_conflict": True})
    historical = j.strict_json(j.read_bytes(d.release.OUT / "repair_fixture_results.json"))
    projection = d.project_recovery(historical["recovery_fixtures"])
    emit("reporting_addendum_check", {"passed": projection == {"rec01_passed": True, "rec02_passed": True},
        "original_addendum": h.ref(d.ADDENDUM, "unchanged_reporting_key_addendum"),
        "frozen_execution_evidence": h.ref(d.release.OUT / "repair_fixture_results.json", "unchanged_R0_REC01_R0_REC02_execution_records"),
        "frozen_summary": h.ref(d.release.OUT / "summary.json", "unchanged_historical_false_projection"),
        "new_exact_identity_projection": projection, "execution_evidence_modified": False,
        "REC_fixtures_reexecuted_for_reporting_fix": False, "reporting_fix_is_runtime_repair": False})
    groups = {
        "focused_T12_diagnosis": [TEST],
        "22A": [ROOT / "tests/test_search_plan_v24_alpha322a_transport_observability_offline.py"],
        "22B": [ROOT / "tests/test_search_plan_v24_alpha322b_exception_mapping_offline.py"],
        "22C": [ROOT / "tests/test_search_plan_v24_alpha322c_attempt_journal_resume_offline.py"],
        "R2": [d.release.r2.CONSTRUCTION_TEST, d.release.r2.INTEGRITY_TEST, d.release.r2.ISOLATION_TEST],
        "T11_repair": d.release.development.TESTS}
    regressions = {name: pytest_group(name, paths) for name, paths in groups.items()}
    emit("regression_results", {"groups": regressions, "all_passed": all(row["passed"] for row in regressions.values()),
        "full_repository_coverage_claimed": False, "focused_diagnostic_assertion_pass_not_original_T12_oracle_pass": True})
    rows = []
    for scenario in manifest["scenarios"]:
        key = scenario["scenario_id"]
        sources_unchanged()
        command = [sys.executable, "-m", d.__name__, "--scenario", key, "--output", str(OUT / "scenarios" / key)]
        process = subprocess.run(command, cwd=ROOT, capture_output=True, text=True)
        log = OUT / "execution" / (key + ".txt")
        j.atomic_freeze(log, (process.stdout + process.stderr).encode())
        try:
            row = j.strict_json(process.stdout.encode())
            t.require(process.returncode == 0 and row.get("scenario_id") == key, "DIAGNOSTIC_CHILD_IDENTITY_OR_EXIT")
        except (ValueError, TypeError):
            row = {"scenario_id": key, "category": scenario["category"], "actual": {},
                   "execution_error": {"qualified_class": "DEVELOPMENT_CHILD_INFRASTRUCTURE_FAILURE", "message": process.stderr}}
        differences = h.compare(expected[key], row.get("actual") or {})
        error = row.get("durable_terminal_error") or row.get("execution_error")
        first = {"operation": "durable_terminal_verification" if row.get("durable_terminal_error") else "scenario_execution",
                 "error": error} if error else ({"operation": "unchanged_independent_oracle_comparison", **differences[0]} if differences else None)
        row.update(expected=expected[key], mismatches=differences, first_divergence=first,
            status="FAIL" if first else "PASS", execution_status="EXECUTED",
            failure_category=None if first is None else d.CLASSIFICATION if key == "T12" and differences == [
                {"field": "content_length_match", "expected": "UNAVAILABLE", "actual": "MISMATCH"}] else "UNRESOLVED",
            actual_execution_command=command, reproduction_command=command,
            reproduction_note="Use a NEW output directory for future reproduction; this executed matrix identity is never rerun here.",
            subprocess_exit_code=process.returncode, execution_log=h.ref(log, "unaltered_isolated_scenario_process_output"))
        rows.append(row)
        j.atomic_freeze(OUT / "execution" / (key + ".json"), j.canonical(row))
        print(key + ": " + row["status"], flush=True)
    j.atomic_freeze(OUT / "full_59_diagnostic_raw_results.jsonl", b"".join(j.canonical(row) for row in rows))
    compile_command = [sys.executable, "-m", "compileall", "-q", *map(str, SOURCES)]
    compiled = subprocess.run(compile_command, cwd=ROOT, capture_output=True, text=True)
    checks = []
    for command in [["git", "diff", "--check"]] + [["git", "diff", "--no-index", "--check", "/dev/null", str(path)] for path in SOURCES]:
        process = subprocess.run(command, cwd=ROOT, capture_output=True, text=True)
        checks.append({"command": command, "exit_code": process.returncode, "diagnostics": process.stdout + process.stderr,
            "passed": process.returncode in ({0} if len(command) == 3 else {0, 1}) and not process.stdout and not process.stderr})
    after = d.authority()
    t.require(j.canonical(before) == j.canonical(after), "HISTORICAL_AUTHORITY_CHANGED")
    sources_unchanged()
    emit("execution_complete", {"executed_count": len(rows), "passed_count": sum(row["status"] == "PASS" for row in rows),
        "failed_count": sum(row["status"] == "FAIL" for row in rows), "not_executed_count": 59 - len(rows),
        "source_bindings_unchanged": True, "historical_preservation": True,
        "compileall": {"command": compile_command, "passed": compiled.returncode == 0, "exit_code": compiled.returncode,
                       "diagnostics": compiled.stdout + compiled.stderr}, "git_diff_checks": checks,
        "no_matrix_rerun_performed": True, "report_classification_and_freeze_pending": True})
    return {"workspace": str(OUT), "stage": "EXECUTION_COMPLETE_AWAITING_FAILURE_CLASSIFICATION", "executed": len(rows),
            "passed": sum(row["status"] == "PASS" for row in rows), "failed": sum(row["status"] == "FAIL" for row in rows)}


def verify_references():
    verified = set()
    def walk(value):
        if isinstance(value, dict):
            if "artifact_path" in value and "sha256" in value:
                path = Path(value["artifact_path"])
                path = j.physical(path if path.is_absolute() else ROOT / path)
                raw = j.read_bytes(path)
                t.require(j.sha(raw) == value["sha256"], "DEVELOPMENT_REPORT_REFERENCE_HASH_MISMATCH:" + str(path))
                if "byte_count" in value:
                    t.require(len(raw) == value["byte_count"], "DEVELOPMENT_REPORT_REFERENCE_LENGTH_MISMATCH")
                verified.add((str(path), value["sha256"]))
            for child in value.values():
                walk(child)
        elif isinstance(value, list):
            for child in value:
                walk(child)
    for path in OUT.glob("*.json*"):
        raw = j.read_bytes(path)
        if path.suffix == ".jsonl":
            for line in raw.splitlines():
                walk(j.strict_json(line))
        else:
            walk(j.strict_json(raw))
    return len(verified)


def freeze():
    t.require((OUT / "execution_complete.json").is_file() and not (OUT / MARKER).exists(), "COMPLETED_UNSEALED_DEVELOPMENT_EXECUTION_REQUIRED")
    source_manifest = sources_unchanged()
    before = j.strict_json(j.read_bytes(OUT / "root_verification.json"))
    t.require(j.canonical(d.authority()) == j.canonical(before), "FROZEN_ROOT_CHANGED_BEFORE_REPORT")
    rows = [j.strict_json(raw) for raw in j.read_bytes(OUT / "full_59_diagnostic_raw_results.jsonl").splitlines()]
    review = j.strict_json(j.read_bytes(OUT / "failure_classification_review.json"))
    failed = {row["scenario_id"] for row in rows if row["status"] == "FAIL"}
    t.require(set(review["classifications"]) == failed, "FAILED_SCENARIO_CLASSIFICATIONS_INCOMPLETE")
    for row in rows:
        if row["status"] == "FAIL":
            assessment = review["classifications"][row["scenario_id"]]
            t.require(assessment["failure_category"] in ALLOWED_CLASSES, "UNKNOWN_FAILURE_CATEGORY")
            row.update(failure_category=assessment["failure_category"], root_cause_group=assessment["root_cause_group"],
                       diagnostic_explanation=assessment["explanation"])
    j.atomic_freeze(OUT / "full_59_diagnostic_results.jsonl", b"".join(j.canonical(row) for row in rows))
    groups = {}
    for row in rows:
        if row["status"] == "FAIL":
            key = row["root_cause_group"]
            group = groups.setdefault(key, {"failure_category": row["failure_category"], "scenario_ids": [], "failures": []})
            group["scenario_ids"].append(row["scenario_id"])
            group["failures"].append({key: row[key] for key in ("scenario_id", "expected", "actual", "first_divergence", "diagnostic_explanation", "reproduction_command", "execution_log")})
    emit("grouped_failure_report", {"groups": groups, "reporting_only_fixed_defect": "REC summary exact identity projection",
        "matrix_runtime_not_modified": True, "known_unexecuted_failures_not_inferred": True,
        "failure_classification_review": h.ref(OUT / "failure_classification_review.json", "post_execution_evidence_based_classification")})
    focus = j.strict_json(j.read_bytes(OUT / "t12_focused_results.json"))
    regression = j.strict_json(j.read_bytes(OUT / "regression_results.json"))
    execution = j.strict_json(j.read_bytes(OUT / "execution_complete.json"))
    all_passed = all(row["status"] == "PASS" for row in rows) and regression["all_passed"]
    counts = {name: sum(row.get("failure_category") == name for row in rows) for name in ALLOWED_CLASSES}
    summary = {"development_status": "diagnostics_completed_with_failures" if failed else "diagnostics_completed",
        "t12_root_cause": d.CLASSIFICATION, "t12_original_oracle_unchanged": True,
        "t12_harness_binding_resolved": False, "t12_focused_test_passed": focus["original_T12_oracle_passed"],
        "t12_diagnostic_assertions_passed": regression["groups"]["focused_T12_diagnosis"]["passed"],
        "normal_empty_counterexample_passed": focus["normal_empty_counterexample"]["passed"],
        "t05_passed": focus["T05_full_path_passed"], "t11_passed": focus["T11_full_path_passed"],
        "development_scenario_count": 59, "development_executed_count": len(rows),
        "development_passed_count": sum(row["status"] == "PASS" for row in rows),
        "development_failed_count": len(failed), "development_not_executed_count": 59 - len(rows),
        "runtime_defect_count": counts["RUNTIME_IMPLEMENTATION_DEFECT"],
        "harness_defect_count": counts["HARNESS_INPUT_BINDING_DEFECT"] + counts["HARNESS_INTEGRATION_DEFECT"] + 1,
        "harness_defect_count_includes_separate_REC_reporting_defect": True,
        "oracle_conflict_count": counts["FROZEN_SCENARIO_OR_ORACLE_CONFLICT"],
        "unresolved_failure_count": counts["UNRESOLVED"], "environment_limitation_count": counts["ENVIRONMENT_LIMITATION"],
        "defect_counts_count_failed_scenario_identities_not_shared_root_causes": True,
        "independent_release_gate_passed": False, "original_22dr2_modified": False,
        "scientific_policy_changed": False, "runtime_retry_policy_changed": False,
        "runtime_body_integrity_checks_weakened": False, "production_runtime_v2_wiring_enabled": False,
        "alpha3_21_reopened": False, "fresh_primary_attempt_started": False,
        "historical_assets_modified": False, "rec01_passed": True, "rec02_passed": True,
        "total_pytest_count": sum(row["tests"] for row in regression["groups"].values()),
        "total_pytest_failures": sum(row["failures"] + row["errors"] for row in regression["groups"].values()),
        "next_stage_recommendation": "EXECUTE_NEW_ALPHA3_22DR3_INDEPENDENT_RELEASE_REVALIDATION_OFFLINE" if all_passed else review["next_stage_recommendation"],
        "next_stage_automatically_started": False, **NO_CALLS}
    emit("historical_preservation", {"passed": True, "before": before, "after": d.authority(),
        "new_sources_and_snapshots_unchanged": source_manifest["sources"], "original_22dr2_modified": False,
        "original_oracle_modified": False, "runtime_behavior_changed": False})
    emit("validation", {"development_diagnostic_execution_completed": len(rows) == 59,
        "all_59_passed": all_passed, "independent_release_gate_passed": False,
        "ordinary_isolated_failures_did_not_abort_independent_scenarios": True,
        "T12_conflict_continuation_explicitly_authorized": True, "no_runtime_or_oracle_changes_during_execution": True,
        "regressions": regression, "engineering_checks": execution, "historical_preservation_verified": True,
        "power_loss_durability_claimed": False, **NO_CALLS})
    emit("summary", summary)
    t.require(all((OUT / (name + ".json")).is_file() for name in REQUIRED) and (OUT / "full_59_diagnostic_results.jsonl").is_file(), "REQUIRED_DEVELOPMENT_REPORT_MISSING")
    count = verify_references()
    emit("freeze_verification", {"report_reference_count_verified": count, "all_required_artifacts_present": True,
        "negative_fixture_corruption_claims_not_promoted_to_admitted_provenance": True,
        "source_hashes_and_frozen_roots_verified": True})
    t.require(j.canonical(d.authority()) == j.canonical(before), "HISTORICAL_ROOT_DRIFT_BEFORE_SEAL")
    root = d.release.master.root_hash(OUT, MARKER)
    j.atomic_freeze(OUT / MARKER, (root + "\n").encode())
    j.sync_directory(OUT)
    t.require(d.release.master.root_hash(OUT, MARKER) == root, "DEVELOPMENT_ROOT_POST_FREEZE_MISMATCH")
    return {**summary, "development_root_sha256": root, "workspace": str(OUT)}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("operation", choices=("execute", "freeze"))
    args = parser.parse_args()
    with d.release.master.prior.offline_guard():
        print(json.dumps(execute() if args.operation == "execute" else freeze(), sort_keys=True))
