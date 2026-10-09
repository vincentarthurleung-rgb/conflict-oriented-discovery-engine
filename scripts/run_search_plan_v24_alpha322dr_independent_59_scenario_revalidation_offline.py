#!/usr/bin/env python3
"""One-shot independent D-R release validation. Never edit or retry a failure."""

import ast
import copy
import json
import subprocess
import sys
import tempfile
import traceback
import xml.etree.ElementTree as ET
from pathlib import Path

from scripts import search_plan_v24_alpha322dr_r2_independent_harness as h
from scripts import run_search_plan_v24_alpha322r2_minimal_runtime_identity_fix_offline as r2

j, t, master = h.j, h.t, h.master
ROOT = h.ROOT
OUT = ROOT / "runs/20261009_search_plan_v24_dev_alpha3_22dr_independent_59_scenario_revalidation_offline"
MARKER = "search_plan_v24_dev_alpha3_22dr_sha256"
R2_SHA = "25b87ad7fb315cfec326bb31858fb1d0382ee2343cb2537dad216113907d4484"
MANIFEST_SHA = "aed33640b5a88badd5a785b41019158ca369b656f20a5a150713b2e8f8eba23b"
ORACLE_SHA = "b1d452438341fd2a01262f09a75649169dd726da119371b30388c4a464d6d817"
TEST = ROOT / "tests/test_search_plan_v24_alpha322dr_preflight_offline.py"
SOURCES = [Path(h.__file__), Path(__file__), TEST]
REQUIRED = """summary validation upstream_root_verification original_59_scenario_binding
independent_oracle_integrity r2_runtime_binding scenario_failure_evidence
repair_specific_fixture_results crash_resume_and_barrier_results safety_invariant_results
regression_results historical_preservation""".split()
PENDING = {"execution_status": "NOT_EXECUTED", "passed": False,
           "reason": "release stopped at first critical failure; no historical result substituted"}
NO_CALLS = {key: 0 for key in ("network_calls", "pubmed_calls", "pmc_calls", "provider_calls",
                             "deepseek_calls", "openai_calls", "llm_calls", "builder_calls", "quality_calls")}
NEXT_PASS = "EXECUTE_ALPHA3_22E_FOCUSED_HISTORICAL_REGRESSION_AND_SEEN_DATA_REPLAY_OFFLINE"
NEXT_FAIL = "MINIMAL_DEVELOPMENT_CORRECTION_OF_FIRST_FROZEN_ALPHA3_22DR_FAILURE"


def emit(stem, value):
    return j.atomic_freeze(OUT / (stem + ".json"), j.canonical(value))


def frozen_inputs():
    manifest_raw = j.read_bytes(h.ORIGINAL / "frozen_fault_scenario_manifest.json")
    oracle_raw = j.read_bytes(h.ORIGINAL / "independent_expected_outcomes.jsonl")
    t.require(j.sha(manifest_raw) == MANIFEST_SHA and j.sha(oracle_raw) == ORACLE_SHA, "ORIGINAL_FROZEN_INPUT_DRIFT")
    manifest = j.strict_json(manifest_raw)
    rows = [j.strict_json(raw) for raw in oracle_raw.splitlines()]
    order = [row["scenario_id"] for row in manifest["scenarios"]]
    t.require(len(order) == len(set(order)) == len(rows) == 59 and
              manifest["order"] == order == [row["scenario_id"] for row in rows], "ORIGINAL_ORDER_OR_COUNT_MISMATCH")
    master.d2.d1.d.checked_tree(manifest["source_bindings"])
    tree = ast.parse(Path(h.oracle.__file__).read_bytes())
    t.require(not any(isinstance(node, (ast.Import, ast.ImportFrom)) for node in ast.walk(tree)), "ORACLE_NOT_INDEPENDENT")
    return manifest, {row["scenario_id"]: row["expected"] for row in rows}


def authority():
    result = r2.authority()
    result["alpha322r2"] = master.prior.root_check(r2.OUT, r2.ROOT_MARKER, R2_SHA)
    implementation = j.strict_json(j.read_bytes(r2.OUT / "r2_source_implementation_manifest.json"))
    for item in implementation["source_files"] + implementation["supporting_source_files"]:
        t.require(j.sha(j.read_bytes(ROOT / item["artifact_path"])) == item["sha256"], "R2_FROZEN_SOURCE_DRIFT")
    t.require(r2.nonwiring()["passed"], "PRODUCTION_WIRING_FORBIDDEN")
    frozen_inputs()
    result["successful_R2_source_manifest"] = h.ref(r2.OUT / "r2_source_implementation_manifest.json", "immutable_actual_R2_implementation")
    result["successful_R2_source_bindings"] = implementation["source_files"] + implementation["supporting_source_files"]
    return result


def pytest_group(name, paths, log_directory):
    # pytest's current-directory symlinks remain outside the physical freeze.
    temporary = Path(tempfile.mkdtemp(prefix="alpha322dr-" + name + "-"))
    xml = log_directory / (name + ".xml")
    command = [sys.executable, "-m", "pytest", "-q", "-W", "error", *map(str, paths),
               "--junitxml=" + str(xml), "--basetemp=" + str(temporary / "pytest")]
    process = subprocess.run(command, cwd=ROOT, capture_output=True, text=True)
    log = log_directory / (name + ".txt")
    j.atomic_freeze(log, (process.stdout + process.stderr).encode())
    counts = {"tests": 0, "failures": 0, "errors": 0, "skipped": 0}
    if xml.is_file():
        for suite in ET.parse(xml).getroot().iter("testsuite"):
            for key in counts:
                counts[key] += int(suite.attrib.get(key, 0))
    return {"execution_status": "EXECUTED", "command": command, "exit_code": process.returncode, **counts,
            "passed": process.returncode == 0 and counts["tests"] > 0 and not any(counts[key] for key in ("failures", "errors", "skipped")),
            "log": h.ref(log, "unaltered_test_output"), "junit": h.ref(xml, "actual_test_accounting") if xml.exists() else None,
            "test_temporary_directory": str(temporary), "temporary_directory_outside_release_root": True}


def journal_evidence(directory):
    files = []
    for path in sorted(directory.rglob("*")) if directory.exists() else []:
        t.require(not path.is_symlink(), "SCENARIO_EVIDENCE_SYMLINK_FORBIDDEN")
        if path.is_file():
            files.append(h.ref(path, "physical_single_execution_scenario_evidence"))
    return files


def t05_check(row):
    if row is None:
        return dict(PENDING)
    binding = row.get("failure_phase_binding") or {}
    actual = row.get("actual", {})
    checks = {"original_fault_passed": row["status"] == "PASS",
              "occurrence_phase": binding.get("occurrence_evidence", {}).get("failure_occurrence_phase") == "RESPONSE_BODY_READING",
              "mapping_phase": binding.get("mapping_evidence", {}).get("mapping_evidence_phase") == "RESPONSE_BODY_READING",
              "persistence_phase": binding.get("terminal_persistence_phase") == "RAW_RESPONSE_FROZEN",
              "partial_quarantined": actual.get("raw_artifact_trust") == "NONAUTHORITATIVE_PARTIAL",
              "fresh_R2_reader_state": actual.get("terminal_logical_state") == "RETRYABLE_FAILURE_WITH_BUDGET",
              "next_ordinal_two": actual.get("next_attempt_ordinal") == 2,
              "zero_consumers": bool(actual.get("parser_invocation_counts")) and not any(actual["parser_invocation_counts"].values()),
              "durable_terminal": actual.get("durable_terminal_committed") is True,
              "no_schema_or_mapping_binding_rejection": row.get("durable_terminal_error") is None}
    return {"execution_status": "EXECUTED", "passed": all(checks.values()), "checks": checks,
            "binding": binding, "fresh_process_resume_plan": row.get("fresh_process_resume_plan"),
            "journal": row.get("journal")}


def execute_repairs():
    fixtures, ri = r2.fixtures, r2.ri
    result = {"positive": dict(PENDING), "negative_fixtures": [], "identity_fixtures": [],
              "recovery_fixtures": [], "all_passed": False}
    base = OUT / "repairs"
    base.mkdir()
    result["positive"] = fixtures.positive(base / "P01")
    if not result["positive"]["passed"]:
        return result
    for spec in fixtures.source_spec("repair_negative_fixture_specification")["fixtures"]:
        row = fixtures.negative(base / spec["fixture_id"], spec)
        result["negative_fixtures"].append(row)
        if not row["passed"] or row["actual_first_rejection_reason"] != row["expected_first_rejection_reason"]:
            return result
    specs = j.strict_json(j.read_bytes(ri.R11 / "r2_runtime_identity_negative_fixture_spec.json"))["fixtures"]
    for spec in specs:
        row = ri.negative(base / spec["fixture_id"], spec)
        result["identity_fixtures"].append(row)
        if not row["passed"]:
            return result
    result["recovery_fixtures"] = fixtures.recovery(base / "recovery")
    result["all_passed"] = all(row["passed"] for row in result["recovery_fixtures"])
    return result


def supplemental_checks(rows, manifest):
    """Controlled observation mutations, not runtime edits or original reruns."""
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
        original = selected[identifier]
        mutated = copy.deepcopy(original["actual"])
        mutated[field] = value
        mismatches = h.compare(original["expected"], mutated)
        mutations.append({"mutation_id": key, "source_scenario": identifier, "mutated_field": field,
                          "detected": any(row["field"] == field for row in mismatches), "mismatches": mismatches})
    directory = OUT / "scenarios/C20"
    before = j.sha(j.read_bytes(directory / "segment-0001.jsonl"))
    plan = h.fresh_recovery(directory)
    repeated = h.fresh_recovery(directory)
    return {"execution_status": "EXECUTED", "mutations": mutations, "mutation_count": len(mutations),
            "mutation_scope": "independent comparison sensitivity to controlled observation changes; no runtime mutation claim",
            "repeatability_passed": plan == repeated == selected["C20"]["fresh_process_resume_plan"] and
                                    before == j.sha(j.read_bytes(directory / "segment-0001.jsonl")),
            "passed": all(row["detected"] for row in mutations) and plan == repeated}


def observed_counters(rows):
    values = {key: 0 for key in ("partial_parser_invocations", "unauthorized_retries", "attempt_ordinal_reuse_count",
                               "successful_request_refresh_count", "barrier_or_activation_drift_count")}
    for row in rows:
        actual = row.get("actual") or {}
        counts = actual.get("parser_invocation_counts", {})
        if actual.get("raw_artifact_trust") == "NONAUTHORITATIVE_PARTIAL":
            values["partial_parser_invocations"] += sum(counts.values())
        if actual.get("semantic_failure_class") == "UNKNOWN_RUNTIME_FAILURE" and actual.get("retry_authorized"):
            values["unauthorized_retries"] += 1
        if row.get("request_replay_safe") is False and actual.get("retry_authorized"):
            values["unauthorized_retries"] += 1
        dispatch = row.get("dispatch_log", [])
        keys = [(item["request_id"], item["attempt_ordinal"]) for item in dispatch]
        values["attempt_ordinal_reuse_count"] += len(keys) - len(set(keys))
        if actual.get("terminal_logical_state") in {"VALID_SUCCESS", "VALID_NONELIGIBLE_RESPONSE"}:
            values["successful_request_refresh_count"] += len(actual.get("resume_executable_ids", []))
        values["barrier_or_activation_drift_count"] += actual.get("activation_drift_count", 0)
    return values


def verify_nested_references():
    """Verify physical references recursively; never repair a referenced file."""
    verified = set()
    def walk(value):
        if isinstance(value, dict):
            if "sha256" in value and "artifact_path" in value:
                path = Path(value["artifact_path"])
                path = j.physical(path if path.is_absolute() else ROOT / path)
                raw = j.read_bytes(path)
                t.require(j.sha(raw) == value["sha256"], "NESTED_ARTIFACT_HASH_MISMATCH:" + str(path))
                if "byte_count" in value:
                    t.require(len(raw) == value["byte_count"], "NESTED_ARTIFACT_LENGTH_MISMATCH")
                key = (str(path), value["sha256"])
                if key not in verified:
                    verified.add(key)
                    if path.suffix == ".json":
                        walk(j.strict_json(raw))
                    elif path.suffix == ".jsonl":
                        for line in raw.splitlines():
                            walk(j.strict_json(line))
            for child in value.values():
                walk(child)
        elif isinstance(value, list):
            for child in value:
                walk(child)
    for path in OUT.glob("*.json"):
        walk(j.strict_json(j.read_bytes(path)))
    for line in j.read_bytes(OUT / "scenario_results.jsonl").splitlines():
        walk(j.strict_json(line))
    return len(verified)


def run():
    t.require(not OUT.exists() and not OUT.is_symlink(), "D_R_OUTPUT_EXISTS_NO_RERUN_OR_OVERWRITE")
    before = authority()
    manifest, expected = frozen_inputs()
    sources = [h.ref(path, "new_independent_validation_only_source") for path in SOURCES]
    OUT.mkdir()
    (OUT / "execution").mkdir()
    (OUT / "implementation").mkdir()
    (OUT / "scenarios").mkdir()
    for path in SOURCES:
        j.atomic_freeze(OUT / "implementation" / path.name, j.read_bytes(path))
    preflight = pytest_group("structural_preflight", [TEST], OUT / "execution")
    t.require(preflight["passed"], "PREFLIGHT_FAILED_NO_RELEASE_SCENARIO_EXECUTED")
    emit("upstream_root_verification", before)
    emit("original_59_scenario_binding", {"scenario_count": 59, "original_order": manifest["order"],
        "scenario_manifest": h.ref(h.ORIGINAL / "frozen_fault_scenario_manifest.json", "unchanged_original_scenarios"),
        "frozen_source_bindings": manifest["source_bindings"], "regenerated": False, "stop_on_first_critical_failure": True})
    emit("independent_oracle_integrity", {"unchanged": True, "original_sha256": ORACLE_SHA,
        "expected_outcomes": h.ref(h.ORIGINAL / "independent_expected_outcomes.jsonl", "original_independent_expected_literals"),
        "source": h.ref(Path(h.oracle.__file__), "original_literal_no_imports_oracle"),
        "oracle_SUT_imports": 0, "expected_values_regenerated_from_SUT": False, "safety_normalization": False})
    emit("r2_runtime_binding", {"successful_implementation_root": R2_SHA,
        "implementation_manifest": before["successful_R2_source_manifest"],
        "actual_component_bindings": before["successful_R2_source_bindings"], "new_harness_sources": sources,
        "actual_journal_writer_module": h.j.__name__, "actual_resume_reader_module": h.p.__name__,
        "actual_failure_binding_module": h.f.__name__, "V1_fallback": False,
        "failed_R1_integration_executed": False, "production_nonwiring": r2.nonwiring()})
    emit("execution_started", {"order": manifest["order"], "original_scenario_manifest_sha256": MANIFEST_SHA,
        "independent_oracle_sha256": ORACLE_SHA, "source_bindings": sources,
        "preflight": preflight, "original_fault_scenarios_executed_in_preflight": 0,
        "one_execution_per_original_scenario": True, "patch_or_rerun_after_first_failure": False})
    rows, failure = [], None
    for scenario in manifest["scenarios"]:
        key = scenario["scenario_id"]
        if failure is not None:
            rows.append({"scenario_id": key, "category": scenario["category"], "status": "NOT_EXECUTED",
                         "expected": expected[key], "actual": None, "first_divergence": None,
                         "reason": "FIRST_CRITICAL_FAILURE:" + failure["scenario_id"]})
            continue
        directory = OUT / "scenarios" / key
        handler = {"TRANSPORT": h.transport_scenario, "CRASH": h.crash_scenario,
                   "JOURNAL_INTEGRITY": h.integrity_scenario, "ACTIVATION_INTEGRITY": h.integrity_scenario,
                   "INTEGRATED": h.integrated_scenario}[scenario["category"]]
        try:
            row = handler(scenario, directory)
            mismatches = h.compare(expected[key], row["actual"])
            if row.get("durable_terminal_error"):
                first = {"checkpoint": "durable_terminal_commit", "error": row["durable_terminal_error"]}
            else:
                first = {"checkpoint": "independent_semantic_comparison", **mismatches[0]} if mismatches else None
            row.update(expected=expected[key], mismatches=mismatches, first_divergence=first,
                       status="FAIL" if first else "PASS", execution_status="EXECUTED")
            if key == "T05" and row["status"] == "PASS" and not t05_check(row)["passed"]:
                row.update(status="FAIL", first_divergence={"checkpoint": "required_full_T05_R2_path", "checks": t05_check(row)})
        except Exception as exc:
            redactor = h.o.SecretRedactorV1((h.SECRET,))
            row = {"scenario_id": key, "category": scenario["category"], "execution_status": "EXECUTED", "status": "FAIL",
                   "expected": expected[key], "actual": None, "mismatches": [], "first_divergence": {
                       "checkpoint": "actual_runtime_or_harness_exception", "error_type": type(exc).__module__ + "." + type(exc).__qualname__,
                       "error": redactor.text(str(exc)), "traceback": redactor.text(traceback.format_exc())}}
        row["request_replay_safe"] = scenario["initial_conditions"].get("replay_safe", True)
        row["physical_evidence"] = journal_evidence(directory)
        rows.append(row)
        j.atomic_freeze(OUT / "execution" / (key + ".json"), j.canonical(row))
        print(key + " " + row["status"], flush=True)
        if row["status"] == "FAIL":
            failure = row
            print("STOP: " + json.dumps(row["first_divergence"], ensure_ascii=False), flush=True)
    # No post-failure scenario, repair fixture, mutation, or regression is run.
    repairs = {"positive": dict(PENDING), "negative_fixtures": [], "identity_fixtures": [],
               "recovery_fixtures": [], "all_passed": False, "execution_status": "NOT_EXECUTED"}
    regressions, supplement = {}, dict(PENDING)
    if failure is None:
        try:
            repairs = execute_repairs()
            if repairs["all_passed"]:
                supplement = supplemental_checks(rows, manifest)
                groups = {
                    "legacy_22A": ["test_search_plan_v24_alpha322a_transport_observability_offline.py"],
                    "legacy_22B": ["test_search_plan_v24_alpha322b_exception_mapping_offline.py"],
                    "legacy_22C": ["test_search_plan_v24_alpha322c_attempt_journal_resume_offline.py"],
                    "R2": [r2.CONSTRUCTION_TEST.name, r2.INTEGRITY_TEST.name, r2.ISOLATION_TEST.name],
                    "R0": ["test_search_plan_v24_alpha322r0_phase_binding_repair_design_offline.py"]}
                if supplement["passed"]:
                    for name, paths in groups.items():
                        regressions[name] = pytest_group(name, [ROOT / "tests" / path for path in paths], OUT / "execution")
                        if not regressions[name]["passed"]:
                            break
        except Exception as exc:
            repairs["execution_error"] = {"error": str(exc), "traceback": traceback.format_exc()}
    # Non-executing engineering checks remain permitted after a stopped gate.
    compile_command = [sys.executable, "-m", "compileall", "-q", *map(str, SOURCES)]
    compiled = subprocess.run(compile_command, cwd=ROOT, capture_output=True, text=True)
    whitespace = []
    for command in [["git", "diff", "--check"]] + [
            ["git", "diff", "--no-index", "--check", "/dev/null", str(path)] for path in SOURCES]:
        process = subprocess.run(command, cwd=ROOT, capture_output=True, text=True)
        whitespace.append({"command": command, "exit_code": process.returncode,
                           "diagnostics": process.stdout + process.stderr,
                           "passed": process.returncode in ({0} if len(command) == 3 else {0, 1}) and not process.stdout and not process.stderr})
    engineering = {"compileall": {"command": compile_command, "exit_code": compiled.returncode,
                                  "passed": compiled.returncode == 0, "diagnostics": compiled.stdout + compiled.stderr},
                   "git_diff_checks": whitespace}
    j.atomic_freeze(OUT / "scenario_results.jsonl", b"".join(j.canonical(row) for row in rows))
    emit("scenario_failure_evidence", {"first_failed_scenario": failure["scenario_id"] if failure else None,
        "failure": failure, "failure_evidence_preserved": failure is not None,
        "no_patch_no_rerun": True, "later_scenarios_not_executed": sum(row["status"] == "NOT_EXECUTED" for row in rows)})
    after = authority()
    preserved = j.canonical(before) == j.canonical(after) and all(
        j.sha(j.read_bytes(ROOT / item["artifact_path"])) == item["sha256"] for item in sources)
    leaks = [str(path.relative_to(OUT)) for path in (OUT / "scenarios").rglob("*.json*")
             if h.SECRET.encode() in j.read_bytes(path)]
    counters = observed_counters([row for row in rows if row["status"] != "NOT_EXECUTED"])
    executed = sum(row["status"] != "NOT_EXECUTED" for row in rows)
    passed_count = sum(row["status"] == "PASS" for row in rows)
    critical_failures = int(failure is not None) + sum(counters.values()) + len(leaks)
    gate = (executed == passed_count == 59 and repairs["all_passed"] and supplement.get("passed", False) and
        len(regressions) == 5 and all(row["passed"] for row in regressions.values()) and critical_failures == 0 and
        compiled.returncode == 0 and all(row["passed"] for row in whitespace) and preserved)
    recovery = {row["fixture_id"]: row for row in repairs["recovery_fixtures"]}
    summary = {"alpha3_22dr_status": "completed" if gate else "failed",
        "alpha3_22dr_classification": "ALPHA3_22DR_PASSED_INDEPENDENT_59_SCENARIO_REVALIDATION" if gate else "ALPHA3_22DR_FAILED_INDEPENDENT_59_SCENARIO_REVALIDATION",
        "upstream_roots_verified": preserved, "original_oracle_unchanged": True, "original_scenario_manifest_unchanged": True,
        "original_scenario_count": 59, "executed_scenario_count": executed, "passed_scenario_count": passed_count,
        "failed_scenario_count": executed - passed_count, "not_executed_scenario_count": 59 - executed,
        "first_failed_scenario": failure["scenario_id"] if failure else None,
        "t05_passed": t05_check(next((row for row in rows if row["scenario_id"] == "T05" and row["status"] != "NOT_EXECUTED"), None))["passed"],
        "r0_positive_passed": repairs["positive"]["passed"],
        "r0_negative_pass_count": sum(row["passed"] for row in repairs["negative_fixtures"]),
        "runtime_identity_negative_pass_count": sum(row["passed"] for row in repairs["identity_fixtures"]),
        "rec01_passed": recovery.get("REC01", {}).get("passed", False), "rec02_passed": recovery.get("REC02", {}).get("passed", False),
        "critical_safety_invariant_failures": critical_failures, **counters,
        "counter_scope": "observed executed prefix only; NOT_EXECUTED safety domains not certified",
        "legacy_runtime_modified": False, "scientific_policy_changed": False, "production_runtime_v2_wiring_enabled": False,
        "alpha3_21_reopened": False, "fresh_primary_attempt_started": False, **NO_CALLS,
        "historical_assets_modified": not preserved, "next_stage_recommendation": NEXT_PASS if gate else NEXT_FAIL,
        "gate_passed": gate, "original_release_attempt_count": 1, "no_power_loss_durability_claim": True}
    emit("repair_specific_fixture_results", {**repairs, "original_negative_count": 22, "identity_negative_count": 6,
        "R0_positive_oracle": h.ref(h.f.R0 / "repair_positive_fixture_specification.json", "original_positive_oracle"),
        "R0_negative_oracle": h.ref(h.f.R0 / "repair_negative_fixture_specification.json", "original_exact_first_reasons"),
        "identity_negative_oracle": before["R11_identity_negative_specs"],
        "historical_R2_fixture_passes_not_counted_as_this_release": True})
    emit("crash_resume_and_barrier_results", {"planned_crashes": 20,
        "executed_crashes": sum(row["category"] == "CRASH" and row["status"] != "NOT_EXECUTED" for row in rows),
        "T05_full_R2_path": t05_check(next((row for row in rows if row["scenario_id"] == "T05" and row["status"] != "NOT_EXECUTED"), None)),
        "recovery_fixtures": repairs["recovery_fixtures"], "real_fresh_process_reader_entrypoint": "scripts.search_plan_v24_alpha322dr_r2_independent_harness --recover",
        "barrier_matrix_status": "NOT_EXECUTED" if failure else "EXECUTED", "physical_power_loss_tested": False})
    emit("safety_invariant_results", {"passed": gate, "critical_failure": failure["scenario_id"] if failure else None,
        "critical_safety_invariant_failures": critical_failures, **counters,
        "counter_scope": summary["counter_scope"], "unexecuted_safety_domains_are_not_passes": True,
        "redaction": {"actual_executed_artifacts_scanned": True, "leak_files": leaks},
        "repeatability_and_mutation_sensitivity": supplement, "planned_mutation_ids": manifest["mutation_ids"],
        "runtime_or_oracle_repair": False, "production_nonwiring": r2.nonwiring(), **NO_CALLS})
    emit("regression_results", {"execution_status": "EXECUTED" if regressions else "NOT_EXECUTED",
        "reason": None if regressions else "first critical matrix failure stopped all further executable validation",
        "groups": regressions, "structural_preflight": preflight, "preflight_is_not_original_matrix_or_regression": True,
        "engineering_checks": engineering, "full_repository_suite_claimed": False})
    emit("historical_preservation", {"passed": preserved, "historical_assets_modified": not preserved,
        "before": before, "after": after, "frozen_runtime_sources_unchanged": True,
        "original_59_scenarios_unchanged": True, "original_independent_oracle_unchanged": True,
        "new_validation_source_bindings_unchanged_after_start": sources,
        "scientific_policy_changed": False, "alpha3_21_reopened": False})
    emit("validation", {"passed": gate, "classification": summary["alpha3_22dr_classification"],
        "stop_on_first_failure_honored": True, "preflight": preflight, "engineering_checks": engineering,
        "original_order_preserved": True, "repair_specific_fixtures_separate_from_original_59": True,
        "historical_preservation": preserved, "all_required_regressions_executed": len(regressions) == 5,
        "remaining_scenarios_not_miscounted_as_pass": True, "no_rerun_or_runtime_modification": True,
        "full_repository_suite_executed": False, **NO_CALLS})
    emit("summary", summary)
    t.require(all((OUT / (name + ".json")).is_file() for name in REQUIRED), "REQUIRED_D_R_OUTPUT_MISSING")
    nested_count = verify_nested_references()
    emit("freeze_verification", {"nested_physical_references_verified": nested_count,
        "all_required_artifacts_present": True, "source_bindings_verified": True,
        "original_manifest_sha256": MANIFEST_SHA, "original_oracle_sha256": ORACLE_SHA})
    t.require(j.canonical(authority()) == j.canonical(before), "UPSTREAM_DRIFT_BEFORE_D_R_SEAL")
    root = master.root_hash(OUT, MARKER)
    j.atomic_freeze(OUT / MARKER, (root + "\n").encode())
    t.require(master.root_hash(OUT, MARKER) == root, "D_R_ROOT_POST_FREEZE_MISMATCH")
    return {**summary, MARKER: root, "workspace": str(OUT)}


if __name__ == "__main__":
    with master.prior.offline_guard():
        print(json.dumps(run(), sort_keys=True))
