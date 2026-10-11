#!/usr/bin/env python3
"""One immutable offline release attempt; no runtime repair or scenario rerun."""

import json
import subprocess
import sys
import tempfile
import traceback
import xml.etree.ElementTree as ET
from pathlib import Path

from scripts import search_plan_v24_alpha322dr2_independent_harness as h
from scripts import run_search_plan_v24_alpha322dr_independent_59_scenario_revalidation_offline as prior
from scripts import run_search_plan_v24_alpha322_t11_validator_outcome_repair_offline as development

j, t, master, ROOT = h.j, h.t, h.master, h.ROOT
r2, fixtures = development.r2, development.fixtures
OUT = ROOT / "runs/20261010_search_plan_v24_dev_alpha3_22dr2_full_independent_revalidation_offline"
MARKER = "search_plan_v24_dev_alpha3_22dr2_sha256"
DEVELOPMENT_SHA = "98440ec9b7ccdb7a62628d461dd700470876038d5a4d0d6553bca9680acd1731"
TEST = ROOT / "tests/test_search_plan_v24_alpha322dr2_preflight_offline.py"
SOURCES = [Path(h.__file__), Path(__file__), TEST]
REQUIRED = """summary validation root_verification frozen_oracle_binding runtime_component_binding
failure_evidence repair_fixture_results crash_recovery_results safety_invariants regression_results historical_preservation""".split()
NO_CALLS = dict(prior.NO_CALLS)
NEXT_PASS = prior.NEXT_PASS
NEXT_FAIL = "FOCUSED_DEVELOPMENT_REPAIR_OF_OBSERVED_FIRST_DIVERGENCE_OFFLINE"
PENDING = {"execution_status": "NOT_EXECUTED", "passed": False,
           "reason": "first critical failure; historical results are not substituted"}


def emit(name, value):
    return j.atomic_freeze(OUT / (name + ".json"), j.canonical(value))


def authority():
    value = development.authority()
    value["latest_T11"] = master.prior.root_check(development.OUT, development.MARKER, DEVELOPMENT_SHA)
    sources = j.strict_json(j.read_bytes(development.OUT / "source_manifest.json"))["sources"]
    for source in sources:
        raw = j.read_bytes(ROOT / source["artifact_path"])
        t.require(j.sha(raw) == source["sha256"] and raw == j.read_bytes(
            development.OUT / "implementation" / Path(source["artifact_path"]).name), "LATEST_FROZEN_SOURCE_DRIFT")
    t.require(development.nonwiring()["passed"], "PRODUCTION_WIRING_FORBIDDEN")
    value["latest_source_bindings"] = sources
    value["production_nonwiring"] = development.nonwiring()
    return value


def pytest_group(name, paths):
    temporary = Path(tempfile.mkdtemp(prefix="alpha322dr2-" + name + "-")) / "pytest"
    xml = OUT / "execution" / (name + ".xml")
    # Every test process also has the existing offline guard, independently.
    wrapper = ("import sys, pytest; from scripts import run_search_plan_v24_alpha322_master_prereg_offline as m; "
               "ctx=m.prior.offline_guard(); ctx.__enter__(); sys.exit(pytest.main(sys.argv[1:]))")
    command = [sys.executable, "-c", wrapper, "-q", "-W", "error", *map(str, paths),
               "--junitxml=" + str(xml), "--basetemp=" + str(temporary)]
    process = subprocess.run(command, cwd=ROOT, capture_output=True, text=True)
    log = OUT / "execution" / (name + ".txt")
    j.atomic_freeze(log, (process.stdout + process.stderr).encode())
    counts = dict.fromkeys(("tests", "failures", "errors", "skipped"), 0)
    if xml.exists():
        for suite in ET.parse(xml).getroot().iter("testsuite"):
            for key in counts:
                counts[key] += int(suite.attrib.get(key, 0))
    result = {"execution_status": "EXECUTED", "command": command, "exit_code": process.returncode, **counts,
        "passed": process.returncode == 0 and counts["tests"] > 0 and not any(counts[key] for key in ("failures", "errors", "skipped")),
        "log": h.ref(log, "unaltered_actual_test_output"),
        "junit": h.ref(xml, "actual_test_accounting") if xml.exists() else None,
        "temporary_directory": str(temporary), "temporary_directory_outside_release_root": True,
        "fresh_process_offline_guard": True}
    print(name + ": " + json.dumps({key: result[key] for key in ("tests", "failures", "errors", "passed")}), flush=True)
    return result


def execute_repairs():
    base = OUT / "repairs"
    base.mkdir()
    result = {"positive": dict(PENDING), "negative_fixtures": [], "identity_fixtures": [],
              "recovery_fixtures": [], "validator_fixtures": [], "all_passed": False}
    result["positive"] = r2.fixtures.positive(base / "P01")
    if not result["positive"]["passed"]:
        return result
    for spec in r2.fixtures.source_spec("repair_negative_fixture_specification")["fixtures"]:
        row = r2.fixtures.negative(base / spec["fixture_id"], spec)
        result["negative_fixtures"].append(row)
        if not row["passed"] or row["actual_first_rejection_reason"] != row["expected_first_rejection_reason"]:
            return result
    specs = j.strict_json(j.read_bytes(r2.ri.R11 / "r2_runtime_identity_negative_fixture_spec.json"))["fixtures"]
    for spec in specs:
        row = r2.ri.negative(base / spec["fixture_id"], spec)
        result["identity_fixtures"].append(row)
        if not row["passed"]:
            return result
    result["recovery_fixtures"] = r2.fixtures.recovery(base / "recovery")
    if not all(row["passed"] for row in result["recovery_fixtures"]):
        return result
    for key in fixtures.SPEC:
        row = fixtures.execute(key, base / ("validator_" + key))
        result["validator_fixtures"].append(row)
        if not row["passed"]:
            return result
    result["all_passed"] = True
    return result


def t11_check(row):
    if row is None or row["status"] == "NOT_EXECUTED":
        return dict(PENDING)
    actual, outcome, terminal = row.get("actual") or {}, row.get("validator_outcome") or {}, row.get("terminal_payload") or {}
    observation = terminal.get("mapped_observation", {}).get("observation", {})
    checks = {
        "original_oracle_passed": row["status"] == "PASS", "complete_body": actual.get("body_complete") is True,
        "literal_false_projection": row.get("actual_validator_result", {}).get("source_identity_allows_progression") is False,
        "actual_false_preserved": outcome.get("accepted") is False and outcome.get("transport_body_state") == "BODY_COMPLETE",
        "A_validity_semantic": actual.get("semantic_failure_class") == "COMPLETE_BODY_RESPONSE_VALIDITY_FAILURE",
        "B_transport_mapping_unchanged": row.get("transport_mapping", {}).get("semantic_failure_class") == "NO_TECHNICAL_FAILURE",
        "committed_validity_failure": actual.get("durable_terminal_committed") is True and terminal.get("outcome") == "TERMINAL_RESPONSE_VALIDITY_FAILURE",
        "no_fabricated_parser_exception": observation.get("exception_provenance") is None and terminal.get("failure_phase_binding") is None,
        "no_scientific_eligibility": terminal.get("eligibility") is None and outcome.get("scientific_eligibility_established") is False,
        "no_retry": actual.get("retry_authorized") is False,
        "fresh_reader_terminal": actual.get("terminal_logical_state") == "TERMINAL_RESPONSE_VALIDITY_FAILURE",
        "next_ordinal_null": actual.get("next_attempt_ordinal") is None,
        "refetch_false": row.get("refetch_rejection") == "NOT_FIRST_AUTHORIZED_UNRESOLVED_REQUEST" and actual.get("resume_executable_ids") == [],
        "fresh_reader_read_only": row.get("fresh_reader_read_only") is True}
    return {"execution_status": "EXECUTED", "passed": all(checks.values()), "checks": checks,
            "fresh_process_plan": row.get("fresh_process_resume_plan"), "terminal_payload": terminal,
            "actual_validator_result": row.get("actual_validator_result"), "preserved_outcome": outcome}


def evidence_inventory(directory):
    result = []
    if directory.exists():
        for path in sorted(directory.rglob("*")):
            t.require(not path.is_symlink(), "EVIDENCE_SYMLINK_FORBIDDEN")
            if path.is_file():
                result.append(h.ref(path, "actual_single_execution_evidence"))
    return result


def failure_details(row, scenario):
    actual = row.get("actual") or {}
    error = row.get("durable_terminal_error") or row.get("execution_error") or {}
    return {"scenario_id": row["scenario_id"], "expected_behavior": row["expected"], "actual_behavior": actual,
        "first_divergent_operation": row["first_divergence"],
        "failure_class": "IMPLEMENTATION_DEFECT" if row.get("durable_terminal_error") else
                         "VALIDATION_HARNESS_OR_IMPLEMENTATION_REQUIRES_TRACE_REVIEW" if row.get("execution_error") else "OBSERVED_RUNTIME_CONTRACT_DIVERGENCE",
        "error": error, "frozen_scenario_definition": scenario,
        "journal_state": {"integrity": actual.get("journal_integrity"), "terminal": actual.get("terminal_logical_state"),
                          "durable_terminal_committed": actual.get("durable_terminal_committed"), "journal": row.get("journal")},
        "attempt_accounting": {key: actual.get(key) for key in ("attempts_consumed", "next_attempt_ordinal", "retry_authorized", "backoff_seconds", "dispatch_count")},
        "raw_artifact_trust_state": actual.get("raw_artifact_trust"), "raw_artifact": row.get("raw_artifact"),
        "fresh_process_recovery_state": row.get("fresh_process_resume_plan"),
        "reproducer_command": [sys.executable, "-m", h.__name__, "--recover", str(OUT / "scenarios" / row["scenario_id"])],
        "reproducer_scope": "read-only durable failure reconstruction; do not rerun original scenario inside this release attempt",
        "scenario_artifacts": row.get("evidence_files", [])}


def supplement(rows, manifest):
    import copy
    selected = {row["scenario_id"]: row for row in rows}
    changes = {
        "allow_partial_parser": ("T05", "parser_invocation_counts", dict.fromkeys(h.oracle.CONSUMERS, 1)),
        "reset_ordinal": ("T21", "next_attempt_ordinal", 1),
        "refresh_success": ("C06", "resume_executable_ids", ["C06:OA:0"]),
        "ignore_activation_mismatch": ("A03", "journal_integrity", "VERIFIED"),
        "retry_unknown": ("T12", "retry_authorized", True),
        "accept_corrupt_raw": ("C19", "raw_artifact_trust", "AUTHORITATIVE_COMPLETE")}
    mutations = []
    for key in manifest["mutation_ids"]:
        identifier, field, value = changes[key]
        actual = copy.deepcopy(selected[identifier]["actual"])
        actual[field] = value
        differences = h.compare(selected[identifier]["expected"], actual)
        mutations.append({"mutation_id": key, "scenario_id": identifier, "field": field,
                          "detected": any(item["field"] == field for item in differences), "differences": differences})
    directory = OUT / "scenarios/C20"
    before = j.sha(j.read_bytes(directory / "segment-0001.jsonl"))
    a, b = h.fresh_recovery(directory), h.fresh_recovery(directory)
    repeatable = a == b == selected["C20"]["fresh_process_resume_plan"] and before == j.sha(j.read_bytes(directory / "segment-0001.jsonl"))
    return {"execution_status": "EXECUTED", "passed": repeatable and all(item["detected"] for item in mutations),
            "repeatability_passed": repeatable, "mutations": mutations,
            "mutation_scope": "controlled observed-value mutations; comparison sensitivity, not a claim of runtime mutation testing"}


def verify_report_references():
    verified = set()
    def walk(value):
        if isinstance(value, dict):
            if "artifact_path" in value and "sha256" in value:
                path = Path(value["artifact_path"])
                path = j.physical(path if path.is_absolute() else ROOT / path)
                raw = j.read_bytes(path)
                t.require(j.sha(raw) == value["sha256"], "REPORT_REFERENCE_HASH_MISMATCH:" + str(path))
                if "byte_count" in value:
                    t.require(len(raw) == value["byte_count"], "REPORT_REFERENCE_LENGTH_MISMATCH")
                verified.add((str(path), value["sha256"]))
            for child in value.values():
                walk(child)
        elif isinstance(value, list):
            for child in value:
                walk(child)
    for path in OUT.glob("*.json"):
        walk(j.strict_json(j.read_bytes(path)))
    for raw in j.read_bytes(OUT / "scenario_results.jsonl").splitlines():
        walk(j.strict_json(raw))
    return len(verified)


def run():
    t.require(not OUT.exists() and not OUT.is_symlink(), "NEW_RELEASE_DIRECTORY_REQUIRED_NO_RERUN")
    before = authority()
    manifest, expected = prior.frozen_inputs()
    t.require(manifest["stop_on_first_critical_failure"] is True, "FROZEN_STOP_POLICY_CHANGED")
    sources = [h.ref(path, "new_release_validation_only_source") for path in SOURCES]
    OUT.mkdir()
    for name in ("execution", "implementation", "scenarios"):
        (OUT / name).mkdir()
    for path in SOURCES:
        j.atomic_freeze(OUT / "implementation" / path.name, j.read_bytes(path))
    emit("root_verification", before)
    emit("frozen_oracle_binding", {"original_scenario_count": 59, "original_order": manifest["order"],
        "scenario_manifest": h.ref(h.ORIGINAL / "frozen_fault_scenario_manifest.json", "unchanged_original_definitions"),
        "oracle": h.ref(h.ORIGINAL / "independent_expected_outcomes.jsonl", "unchanged_independent_literal_oracle"),
        "oracle_source": h.ref(Path(h.oracle.__file__), "unchanged_import_free_oracle_source"),
        "oracle_SUT_imports": 0, "regenerated": False, "source_bindings": manifest["source_bindings"],
        "stop_on_first_critical_failure": True})
    emit("runtime_component_binding", {"latest_development_root": DEVELOPMENT_SHA,
        "latest_integration_entrypoint": h.integration.__name__, "latest_source_bindings": before["latest_source_bindings"],
        "actual_writer_and_verifier": h.j.__name__, "actual_resume_planner": h.p.__name__,
        "actual_barrier_module": h.s.__name__, "actual_runtime_identity_and_phase_binding": h.f.__name__,
        "actual_lifecycle": h.t.__name__, "actual_observability": h.o.__name__, "actual_exception_mapping": h.b.__name__,
        "R2_source_manifest": h.ref(r2.OUT / "r2_source_implementation_manifest.json", "unchanged_frozen_R2_base"),
        "new_validation_sources": sources, "V1_fallback": False, "failed_R1_integration": False,
        "production_nonwiring": development.nonwiring()})
    emit("execution_plan", {"release_attempt": 1, "source_bindings": sources,
        "execution_order": ["structural_static_preflight", "separate_R0_RI_REC_T11_fixtures", "separate_relevant_regressions", "original_59_in_frozen_order", "comparison_mutations_and_readonly_repeatability_if_matrix_passes"],
        "original_matrix_order": manifest["order"], "stop_on_first_critical_failure": True,
        "one_execution_per_original_scenario": True, "no_runtime_edits_after_start": True,
        "separate_fixtures_and_regressions_not_counted_as_original_59": True, **NO_CALLS})
    preflight = pytest_group("static_preflight", [TEST])
    repairs = {"positive": dict(PENDING), "negative_fixtures": [], "identity_fixtures": [],
               "recovery_fixtures": [], "validator_fixtures": [], "all_passed": False}
    regressions, auxiliary_failure = {}, None
    if preflight["passed"]:
        try:
            repairs = execute_repairs()
            if not repairs["all_passed"]:
                auxiliary_failure = "REPAIR_SPECIFIC_FIXTURE_FAILED"
        except Exception as exc:
            auxiliary_failure = "REPAIR_FIXTURE_EXECUTION_ERROR"
            repairs["execution_error"] = {"message": str(exc), "traceback": traceback.format_exc()}
    else:
        auxiliary_failure = "STATIC_PREFLIGHT_FAILED"
    if auxiliary_failure is None:
        groups = {
            "legacy_22A_transport": [ROOT / "tests/test_search_plan_v24_alpha322a_transport_observability_offline.py"],
            "22B": [ROOT / "tests/test_search_plan_v24_alpha322b_exception_mapping_offline.py"],
            "22C": [ROOT / "tests/test_search_plan_v24_alpha322c_attempt_journal_resume_offline.py"],
            "R2": [r2.CONSTRUCTION_TEST, r2.INTEGRITY_TEST, r2.ISOLATION_TEST],
            "T11_repair": development.TESTS,
            "R0_contract": [ROOT / "tests/test_search_plan_v24_alpha322r0_phase_binding_repair_design_offline.py"],
            "legacy_master_contracts": [ROOT / "tests/test_search_plan_v24_alpha322_master_prereg_offline.py",
                                        ROOT / "tests/test_no_static_journal_weight_in_core_reasoning.py"]}
        for name, paths in groups.items():
            regressions[name] = pytest_group(name, paths)
            if not regressions[name]["passed"]:
                auxiliary_failure = "REGRESSION_FAILED:" + name
                break
    rows, failure = [], None
    for scenario in manifest["scenarios"]:
        key = scenario["scenario_id"]
        if failure is not None or auxiliary_failure:
            rows.append({"scenario_id": key, "category": scenario["category"], "status": "NOT_EXECUTED",
                "execution_status": "NOT_EXECUTED", "expected": expected[key], "actual": None,
                "first_divergence": None, "reason": auxiliary_failure or "FIRST_CRITICAL_FAILURE:" + failure["scenario_id"]})
            continue
        handler = {"TRANSPORT": h.transport_scenario, "CRASH": h.crash_scenario,
                   "JOURNAL_INTEGRITY": h.integrity_scenario, "ACTIVATION_INTEGRITY": h.integrity_scenario,
                   "INTEGRATED": h.integrated_scenario}[scenario["category"]]
        directory = OUT / "scenarios" / key
        try:
            row = handler(scenario, directory)
            differences = h.compare(expected[key], row["actual"])
            error = row.get("durable_terminal_error")
            first = {"operation": "V2_journal_terminal_verification_and_commit", "error": error} if error else (
                {"operation": "independent_semantic_comparison", **differences[0]} if differences else None)
            row.update(expected=expected[key], mismatches=differences, first_divergence=first,
                       status="FAIL" if first else "PASS", execution_status="EXECUTED")
            if key == "T05" and not prior.t05_check(row)["passed"]:
                row.update(status="FAIL", first_divergence=first or {"operation": "T05_full_regression_contract"})
            if key == "T11" and not t11_check(row)["passed"]:
                row.update(status="FAIL", first_divergence=first or {"operation": "T11_full_regression_contract"})
        except Exception as exc:
            row = {"scenario_id": key, "category": scenario["category"], "status": "FAIL", "execution_status": "EXECUTED",
                "expected": expected[key], "actual": {}, "mismatches": [],
                "first_divergence": {"operation": "scenario_execution_exception", "error": str(exc)},
                "execution_error": {"qualified_class": type(exc).__module__ + "." + type(exc).__qualname__,
                                    "message": str(exc), "traceback": traceback.format_exc()}}
        row["evidence_files"] = evidence_inventory(directory)
        rows.append(row)
        j.atomic_freeze(OUT / "execution" / (key + ".json"), j.canonical(row))
        print(key + ": " + row["status"], flush=True)
        if row["status"] == "FAIL":
            failure = failure_details(row, scenario)
    supplemental = supplement(rows, manifest) if failure is None and auxiliary_failure is None else dict(PENDING)
    # Non-executing syntax / whitespace checks are safe after a stopped gate.
    compile_command = [sys.executable, "-m", "compileall", "-q", *map(str, SOURCES + development.SOURCES + r2.COMPONENTS)]
    compiled = subprocess.run(compile_command, cwd=ROOT, capture_output=True, text=True)
    whitespace = []
    for command in [["git", "diff", "--check"]] + [["git", "diff", "--no-index", "--check", "/dev/null", str(path)] for path in SOURCES]:
        process = subprocess.run(command, cwd=ROOT, capture_output=True, text=True)
        whitespace.append({"command": command, "exit_code": process.returncode, "diagnostics": process.stdout + process.stderr,
                           "passed": process.returncode in ({0} if len(command) == 3 else {0, 1}) and not process.stdout and not process.stderr})
    engineering = {"compileall": {"command": compile_command, "exit_code": compiled.returncode,
        "passed": compiled.returncode == 0, "diagnostics": compiled.stdout + compiled.stderr}, "git_diff_checks": whitespace}
    after = authority()
    preserved = j.canonical(before) == j.canonical(after) and all(j.sha(j.read_bytes(ROOT / source["artifact_path"])) == source["sha256"] for source in sources)
    executed_rows = [row for row in rows if row["status"] != "NOT_EXECUTED"]
    counters = prior.observed_counters(executed_rows)
    counters["invalid_barrier_acceptance_count"] = counters.pop("barrier_or_activation_drift_count")
    leaks = [str(path.relative_to(OUT)) for path in (OUT / "scenarios").rglob("*.json*") if h.SECRET.encode() in j.read_bytes(path)]
    invariants = {
        "no_partial_parser": counters["partial_parser_invocations"] == 0,
        "no_unknown_or_unsafe_automatic_retry": counters["unauthorized_retries"] == 0,
        "no_attempt_ordinal_reuse": counters["attempt_ordinal_reuse_count"] == 0,
        "no_fifth_attempt": all(item["attempt_ordinal"] <= 4 for row in executed_rows for item in row.get("dispatch_log", [])),
        "no_committed_success_refresh": counters["successful_request_refresh_count"] == 0,
        "no_invalid_barrier_admission_observed": counters["invalid_barrier_acceptance_count"] == 0,
        "no_secret_leak": not leaks, "no_scientific_policy_drift": preserved,
        "no_lost_validator_outcome_in_T11": t11_check(next((row for row in rows if row["scenario_id"] == "T11"), None))["passed"]}
    invariant_failures = sum(value is False for value in invariants.values())
    executed = len(executed_rows)
    passed_count = sum(row["status"] == "PASS" for row in rows)
    passed = executed == passed_count == 59 and repairs["all_passed"] and len(regressions) == 7 and all(row["passed"] for row in regressions.values()) and supplemental.get("passed", False) and invariant_failures == 0 and compiled.returncode == 0 and all(row["passed"] for row in whitespace) and preserved
    rec = {row["fixture_id"]: row for row in repairs["recovery_fixtures"]}
    summary = {"alpha3_22dr2_status": "completed" if passed else "failed",
        "alpha3_22dr2_classification": "ALPHA3_22DR2_INDEPENDENT_59_SCENARIO_REVALIDATION_PASSED" if passed else "ALPHA3_22DR2_INDEPENDENT_REVALIDATION_FAILED",
        "original_scenario_count": 59, "executed_scenario_count": executed, "passed_scenario_count": passed_count,
        "failed_scenario_count": executed - passed_count, "not_executed_scenario_count": 59 - executed,
        "first_failed_scenario": failure["scenario_id"] if failure else None, "auxiliary_failure": auxiliary_failure,
        "t05_passed": prior.t05_check(next((row for row in executed_rows if row["scenario_id"] == "T05"), None))["passed"],
        "t11_passed": t11_check(next((row for row in rows if row["scenario_id"] == "T11"), None))["passed"],
        "r0_positive_passed": repairs["positive"]["passed"],
        "r0_negative_pass_count": sum(row["passed"] for row in repairs["negative_fixtures"]),
        "runtime_identity_negative_pass_count": sum(row["passed"] for row in repairs["identity_fixtures"]),
        "t11_negative_pass_count": sum(row["passed"] for row in repairs["validator_fixtures"]),
        "rec01_passed": rec.get("REC01", {}).get("passed", False), "rec02_passed": rec.get("REC02", {}).get("passed", False),
        "critical_safety_invariant_failures": invariant_failures, "critical_release_failure_count": int(failure is not None) + int(auxiliary_failure is not None), **counters,
        "counter_scope": "observed executed prefix and separate fixtures only; unexecuted safety domains are not certified",
        "original_oracle_modified": False, "historical_assets_modified": not preserved,
        "production_runtime_v2_wiring_enabled": False, "alpha3_21_reopened": False, "fresh_primary_attempt_started": False,
        "scientific_policy_changed": False, "runtime_modified_during_validation": False, "gate_passed": passed,
        "regression_test_count": sum(row["tests"] for row in regressions.values()),
        "regression_failures": sum(row["failures"] + row["errors"] for row in regressions.values()),
        "next_stage_recommendation": NEXT_PASS if passed else NEXT_FAIL, "next_stage_automatically_started": False, **NO_CALLS}
    j.atomic_freeze(OUT / "scenario_results.jsonl", b"".join(j.canonical(row) for row in rows))
    emit("failure_evidence", {"first_failed_scenario": summary["first_failed_scenario"], "failures": [failure] if failure else [],
        "auxiliary_failure": auxiliary_failure, "no_patch_no_rerun": True,
        "later_original_scenarios_not_executed": summary["not_executed_scenario_count"]})
    emit("repair_fixture_results", {**repairs, "original_59_scenario_count_includes_these": False,
        "R0_positive_oracle": h.ref(h.f.R0 / "repair_positive_fixture_specification.json", "unchanged_positive_oracle"),
        "R0_negative_oracle": h.ref(h.f.R0 / "repair_negative_fixture_specification.json", "unchanged_exact_first_rejections"),
        "identity_oracle": before["R11_identity_negative_specs"], "T11_fixture_spec": {key: list(value) for key, value in fixtures.SPEC.items()},
        "fixture_execution_preceded_original_matrix": True})
    emit("crash_recovery_results", {"planned_original_crash_count": 20,
        "executed_original_crash_count": sum(row["category"] == "CRASH" for row in executed_rows),
        "original_crash_results": [row for row in rows if row["category"] == "CRASH"],
        "T05": prior.t05_check(next((row for row in executed_rows if row["scenario_id"] == "T05"), None)),
        "T11": t11_check(next((row for row in rows if row["scenario_id"] == "T11"), None)),
        "REC01_REC02": repairs["recovery_fixtures"],
        "fresh_reader_entrypoint": h.__name__ + " --recover", "physical_power_loss_durability_claimed": False})
    emit("safety_invariants", {"observed_checks": invariants, "critical_safety_invariant_failures": invariant_failures,
        "full_59_scenario_safety_certification": passed, "counter_scope": summary["counter_scope"], **counters,
        "unexecuted_domains_not_counted_as_pass": True, "secret_leak_files": leaks,
        "repeatability_and_mutation_sensitivity": supplemental, "production_nonwiring": development.nonwiring(), **NO_CALLS})
    emit("regression_results", {"groups": regressions, "structural_preflight": preflight,
        "regression_test_count": summary["regression_test_count"], "regression_failures": summary["regression_failures"],
        "engineering_checks": engineering, "regressions_preceded_original_matrix": True,
        "full_repository_suite_claimed": False, "original_matrix_scenarios_counted_from_pytest": 0})
    emit("historical_preservation", {"passed": preserved, "before": before, "after": after,
        "historical_assets_modified": not preserved, "original_oracle_modified": False,
        "new_source_bindings_unchanged_after_start": sources, "frozen_runtime_changed": False,
        "scientific_policy_changed": False, "production_runtime_v2_wiring_enabled": False})
    emit("validation", {"passed": passed, "classification": summary["alpha3_22dr2_classification"],
        "stop_on_first_critical_failure_honored": True, "original_order_preserved": True,
        "no_runtime_or_oracle_edits_after_start": True, "no_original_scenario_rerun": True,
        "all_required_regression_groups_executed": len(regressions) == 7,
        "historical_preservation_verified": preserved, "engineering_checks": engineering, **NO_CALLS})
    emit("summary", summary)
    t.require(all((OUT / (name + ".json")).is_file() for name in REQUIRED) and (OUT / "scenario_results.jsonl").is_file(), "REQUIRED_RELEASE_ARTIFACT_MISSING")
    count = verify_report_references()
    emit("freeze_verification", {"report_reference_count_verified": count, "all_required_artifacts_present": True,
        "intentional_negative_fixture_claims_not_promoted_to_provenance": True,
        "all_physical_fixture_bytes_covered_by_root": True, "source_and_oracle_bindings_verified": True})
    t.require(j.canonical(authority()) == j.canonical(before), "UPSTREAM_CHANGED_BEFORE_SEAL")
    root = master.root_hash(OUT, MARKER)
    j.atomic_freeze(OUT / MARKER, (root + "\n").encode())
    j.sync_directory(OUT)
    t.require(master.root_hash(OUT, MARKER) == root, "ROOT_POST_FREEZE_MISMATCH")
    return {**summary, MARKER: root, "workspace": str(OUT)}


if __name__ == "__main__":
    with master.prior.offline_guard():
        print(json.dumps(run(), sort_keys=True))
