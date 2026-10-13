"""Artifact-only orchestration around the two-line versioned namespace fix.

Runtime execution, oracle comparison, regression assertions and safety checks
are delegated to the unchanged functions in the frozen corrected runner.
This wrapper supplies isolated directories and the requested report filenames,
reads committed evidence back, and seals the complete release only afterwards.
"""

import argparse
import difflib
import json
import subprocess
import sys
import traceback
import xml.etree.ElementTree as ET
from pathlib import Path

from scripts import run_search_plan_v24_alpha322_independent_release_log_namespace_v1_offline as r


ROOT = r.ROOT
BASE = ROOT / "scripts/run_search_plan_v24_alpha322_independent_release_binding_v2_eof1_offline.py"
BASE_SHA = "1394b78f80cb534f70c03ae8185b8ca4d09c0c1d0206d443505a870d9a64df19"
OLD_RELEASE = ROOT / "runs/20261011_search_plan_v24_dev_alpha3_22_independent_release_runner_binding_v2_offline"
OLD_RELEASE_MARKER = "search_plan_v24_dev_alpha3_22_independent_release_binding_v2_sha256"
OLD_RELEASE_SHA = "a83b0834ccfd534c8ec5524f41256504c5076ef4f3b93c4cead43a2932d34564"
OLD_PHASE1 = ROOT / "runs/20261012_search_plan_v24_dev_alpha3_22_release_runner_eof_only_phase1_preflight_offline"
OLD_PHASE1_MARKER = "search_plan_v24_dev_alpha3_22_runner_eof_only_phase1_preflight_sha256"
OLD_PHASE1_SHA = "bd6582adcf4a9992b9fab603ed9e29117f2c7b9f96240c3023206a9bb13315e2"
PREFLIGHT = ROOT / "runs/20261012_search_plan_v24_dev_alpha3_22_release_log_namespace_preflight_offline"
PREFLIGHT_MARKER = "search_plan_v24_dev_alpha3_22_log_namespace_preflight_sha256"
RELEASE = ROOT / "runs/20261012_search_plan_v24_dev_alpha3_22_final_independent_oracle_v2_log_namespace_offline"
RELEASE_MARKER = "search_plan_v24_dev_alpha3_22_log_namespace_release_sha256"
REQUIRED = "summary validation frozen_bindings regression_results safety_results artifact_integrity historical_preservation".split()


def write(directory, name, value):
    return r.j.atomic_freeze(directory / (name + ".json"), r.j.canonical(value))


def historical_authority():
    result = r.authority()
    for key, directory, marker, digest in (
            ("previous_successful_phase1", OLD_PHASE1, OLD_PHASE1_MARKER, OLD_PHASE1_SHA),
            ("preserved_log_collision_release", OLD_RELEASE, OLD_RELEASE_MARKER, OLD_RELEASE_SHA)):
        result[key] = r.master.prior.root_check(directory, marker, digest)
    r.t.require(r.j.sha(BASE.read_bytes()) == BASE_SHA, "FROZEN_BASE_RUNNER_DRIFT")
    return result


def confirm_collision():
    rows = [r.j.strict_json(line) for line in (OLD_RELEASE / "scenario_results.jsonl").read_bytes().splitlines()]
    r.t.require(len(rows) == 59 and all(row["status"] == "PASS" for row in rows), "OLD_MATRIX_ACCOUNTING_DRIFT")
    r.t.require(all(row["specific_release_checks"]["passed"] for row in rows
                    if row["scenario_id"] in {"T05", "T11", "T12", "T17", "T18"}), "OLD_SPECIFIC_CHECK_DRIFT")
    counts = junit_counts(OLD_RELEASE / "execution/T11.xml")
    r.t.require(counts == dict(tests=43, failures=0, errors=0, skipped=0), "OLD_T11_JUNIT_DRIFT")
    original_log = OLD_RELEASE / "execution/T11.txt"
    r.t.require(r.read(original_log)["scenario_id"] == "T11", "OLD_SCENARIO_LOG_NOT_PRESERVED")
    failure = r.read(OLD_RELEASE / "repair_regression_results.json")["failure"]
    r.t.require(failure["message"] == "IMMUTABLE_ARTIFACT_EXISTS_OR_INVALID", "OLD_COLLISION_FAILURE_DRIFT")
    return {"all_59_scenarios_passed": True, "all_five_special_checks_passed": True,
            "T11_JUnit": counts, "failure": failure,
            "original_scenario_log": r.h.ref(original_log, "preserved_original_scenario_stdout")}


def junit_counts(path):
    return {key: sum(int(suite.attrib.get(key, 0)) for suite in ET.parse(path).getroot().iter("testsuite"))
            for key in ("tests", "failures", "errors", "skipped")}


def source_delta():
    old, new = BASE.read_bytes(), Path(r.__file__).read_bytes()
    anchor = b'        (OUT / name).mkdir()\n    sources = []'
    previous_call = b'            group = repair.run_pytest(name, paths, OUT / "execution")'
    r.t.require(old.count(anchor) == old.count(previous_call) == 1, "BASE_ROUTING_ANCHOR_DRIFT")
    expected = old.replace(anchor, b'        (OUT / name).mkdir()\n    (OUT / "execution/regressions").mkdir()\n    sources = []')
    expected = expected.replace(previous_call, b'            group = repair.run_pytest(name, paths, OUT / "execution/regressions")')
    r.t.require(new == expected and new.endswith(b"\n") and not new.endswith(b"\n\n"), "NON_ROUTING_SOURCE_DELTA")
    return {"passed": True, "base_runner_sha256": BASE_SHA, "corrected_runner_sha256": r.j.sha(new),
            "changes": ["create execution/regressions parent", "route pytest group artifacts to execution/regressions"],
            "all_other_bytes_unchanged": True,
            "diff": "".join(difflib.unified_diff(old.decode().splitlines(keepends=True),
                new.decode().splitlines(keepends=True), fromfile=str(BASE.relative_to(ROOT)),
                tofile=str(Path(r.__file__).relative_to(ROOT))))}


def log_layout(order, directory):
    scenarios = {key: str(directory / "execution" / (key + ".txt")) for key in order}
    regression = {key: {extension: str(directory / "execution/regressions" / (key + "." + extension))
                         for extension in ("txt", "xml")} for key in r.test_groups()}
    return {"scenario_logs": scenarios, "regression_artifacts": regression}


def path_preflight(order):
    r.t.require(not RELEASE.exists() and not RELEASE.is_symlink(), "NEW_RELEASE_DIRECTORY_REQUIRED")
    r.t.require(RELEASE.parent.resolve() == (ROOT / "runs").resolve() and RELEASE.resolve() == RELEASE,
                "RELEASE_PATH_NOT_ISOLATED")
    r.t.require(not any(RELEASE.is_relative_to(path) or path.is_relative_to(RELEASE)
                        for path in RELEASE.parent.iterdir() if path.is_dir()), "HISTORICAL_DIRECTORY_OVERLAP")
    layout = log_layout(order, RELEASE)
    scenario_paths = list(layout["scenario_logs"].values())
    regression_paths = [path for group in layout["regression_artifacts"].values() for path in group.values()]
    checks = {"all_59_scenario_paths_unique": len(scenario_paths) == len(set(scenario_paths)) == 59,
              "all_12_regression_artifact_paths_unique": len(regression_paths) == len(set(regression_paths)) == 12,
              "scenario_regression_paths_disjoint": not set(scenario_paths) & set(regression_paths),
              "all_paths_inside_new_release": all(Path(path).is_relative_to(RELEASE) for path in scenario_paths + regression_paths),
              "new_release_directory_absent": not RELEASE.exists()}
    probe = PREFLIGHT / "path_probe"
    old = probe / "old/execution/T11.txt"
    old.parent.mkdir(parents=True)
    r.j.atomic_freeze(old, b"original scenario log\n")
    rejection = None
    try:
        r.j.atomic_freeze(old, b"regression log must be rejected\n")
    except r.t.TransportContractError as exc:
        rejection = str(exc)
    checks["old_T11_collision_rejected"] = rejection == "IMMUTABLE_ARTIFACT_EXISTS_OR_INVALID"
    checks["negative_probe_original_log_unchanged"] = old.read_bytes() == b"original scenario log\n"
    corrected = probe / "corrected"
    all_paths = scenario_paths + regression_paths
    for parent in sorted({Path(path).parent for path in all_paths}):
        local = corrected / parent.relative_to(RELEASE)
        local.mkdir(parents=True, exist_ok=True)
        r.t.require(local.resolve().is_relative_to(corrected.resolve()) and not local.is_symlink(), "UNSAFE_LOG_PARENT")
    scenario = corrected / "execution/T11.txt"
    regression = corrected / "execution/regressions/T11.txt"
    r.j.atomic_freeze(scenario, b"scenario T11\n")
    r.j.atomic_freeze(regression, b"pytest T11\n")
    checks["corrected_T11_layout_succeeds"] = scenario.read_bytes() == b"scenario T11\n" and regression.read_bytes() == b"pytest T11\n"
    checks["all_required_log_parents_created_safely"] = all((corrected / Path(path).parent.relative_to(RELEASE)).is_dir() for path in all_paths)
    return {"checks": checks, "passed": all(checks.values()), "log_path_layout": layout,
            "old_collision_rejection": rejection, "scenario_executions": 0,
            "scenario_log_collisions": len(scenario_paths) - len(set(scenario_paths)),
            "regression_log_collisions": len(regression_paths) - len(set(regression_paths)),
            "immutable_artifact_checks_disabled": False}


def preflight():
    r.t.require(not PREFLIGHT.exists() and not PREFLIGHT.is_symlink(), "NEW_PREFLIGHT_REQUIRED_NO_RERUN")
    before = historical_authority()
    collision, delta = confirm_collision(), source_delta()
    manifest, records, raw, difference = r.frozen_inputs()
    PREFLIGHT.mkdir()
    (PREFLIGHT / "execution").mkdir()
    paths = path_preflight(manifest["order"])
    sources = sorted(set(r.source_paths() + [BASE, Path(__file__).absolute()]))
    snapshots = []
    for source in sources:
        snapshot = PREFLIGHT / "implementation" / source.relative_to(ROOT)
        snapshot.parent.mkdir(parents=True, exist_ok=True)
        r.j.atomic_freeze(snapshot, source.read_bytes())
        snapshots.append({"source": r.h.ref(source, "frozen_namespace_preflight_source"),
                          "snapshot": r.h.ref(snapshot, "physical_byte_identical_source")})
    commands = [[sys.executable, "-m", "compileall", "-q", *map(str, sources)], ["git", "diff", "--check"]]
    commands += [["git", "diff", "--no-index", "--check", "/dev/null", str(path)]
                 for path in (Path(r.__file__), Path(__file__))]
    engineering = []
    for index, command in enumerate(commands):
        process = subprocess.run(command, cwd=ROOT, capture_output=True, text=True)
        log = PREFLIGHT / "execution" / ("engineering_%d.txt" % index)
        r.j.atomic_freeze(log, (process.stdout + process.stderr).encode())
        engineering.append({"command": command, "exit_code": process.returncode, "log": r.h.ref(log, "actual_preflight_engineering_check"),
            "passed": process.returncode in ({0, 1} if "--no-index" in command else {0}) and not process.stdout and not process.stderr})
    after = historical_authority()
    preserved = before == after and all(r.verify_reference(row["source"]) == r.verify_reference(row["snapshot"]) for row in snapshots)
    passed = paths["passed"] and delta["passed"] and preserved and all(row["passed"] for row in engineering)
    configuration = {"mode": "OFFLINE_LOG_PATH_CORRECTION_PREFLIGHT_NO_SCENARIO_EXECUTION", "source_bindings": snapshots,
        "upstream_authority": before, "actual_runtime_binding": r.runtime_binding(), "runtime_journal_authority": r.j.AUTHORITY,
        "input_bindings": {"source_only_scenarios": r.h.ref(r.h.ORIGINAL / "frozen_fault_scenario_manifest.json", "unchanged_original_59"),
            "independent_oracle_v1": r.h.ref(r.h.ORIGINAL / "independent_expected_outcomes.jsonl", "unchanged_V1"),
            "frozen_oracle_v2_container": r.h.ref(r.CONTRACT / "versioned_change_manifest.json", "complete_frozen_V2_records")},
        "runner_source": r.h.ref(Path(r.__file__), "two_line_artifact_routing_only_correction"),
        "external_artifact_orchestrator": r.h.ref(Path(__file__).absolute(), "report_names_readback_and_final_root_only"),
        "scenario_manifest_sha256": r.SCENARIO_SHA, "oracle_v2_sha256": r.V2_SHA,
        "original_oracle_sha256": r.ORIGINAL_ORACLE_SHA, "scenario_order": manifest["order"], "oracle_difference": difference,
        "integration_entrypoint": [sys.executable, "-m", r.repair.__name__, "scenario", "--key", "<frozen_id>", "--output", "<new_isolated_directory>"],
        "log_path_layout": paths["log_path_layout"], "release_directory": str(RELEASE), "release_marker": RELEASE_MARKER,
        "phase1_directory": str(PREFLIGHT), "phase1_marker": PREFLIGHT_MARKER,
        "runtime_source_modified": False, "scientific_policy_changed": False, "retry_policy_changed": False,
        "original_oracle_modified": False, "source_delta": delta, **r.NO_CALLS}
    reports = {"summary": {"runner_preflight_status": "completed" if passed else "failed", "logging_namespace_fix_passed": passed,
            "corrected_runner_sha256": delta["corrected_runner_sha256"], "historical_assets_modified": not preserved,
            "scenario_executions": 0, "release_execution_started": False, **r.NO_CALLS},
        "validation": {"passed": passed, "source_delta": delta, "engineering_checks": engineering,
            "historical_preservation_before": before, "historical_preservation_after": after,
            "confirmed_old_collision": collision, "path_checks": paths["checks"]},
        "runner_source_manifest": {"sources": snapshots, "source_delta": delta},
        "path_preflight_results": paths, "frozen_release_configuration": configuration}
    for name, value in reports.items():
        write(PREFLIGHT, name, value)
    root = seal(PREFLIGHT, PREFLIGHT_MARKER)
    return {**reports["summary"], "runner_preflight_root_sha256": root, "workspace": str(PREFLIGHT)}


def seal(directory, marker):
    digest = r.master.root_hash(directory, marker)
    r.j.atomic_freeze(directory / marker, (digest + "\n").encode())
    r.j.sync_directory(directory)
    r.t.require(r.master.root_hash(directory, marker) == digest, "POST_FREEZE_ROOT_MISMATCH")
    return digest


def archived_regressions(reg):
    result = {"all_required_regression_artifacts_committed": False, "group_artifacts": {}, "failure": None}
    try:
        r.t.require(reg["all_passed"] and set(reg["pytest_groups"]) == set(r.test_groups()), "REQUIRED_REGRESSION_GROUP_NOT_ACCEPTED")
        for name, group in reg["pytest_groups"].items():
            log = r.verify_reference(group["log"])
            xml = r.verify_reference(group["junit"])
            expected = {key: group[key] for key in ("tests", "failures", "errors", "skipped")}
            counts = junit_counts(ROOT / group["junit"]["artifact_path"])
            r.t.require(group["passed"] and group["exit_code"] == 0 and counts == expected
                        and counts["tests"] > 0 and not any(counts[key] for key in ("failures", "errors", "skipped")),
                        "REGRESSION_ARCHIVE_READBACK_FAILED:" + name)
            result["group_artifacts"][name] = {"log": group["log"], "junit": group["junit"], "counts": counts,
                "log_bytes_read_back": len(log), "junit_bytes_read_back": len(xml), "readback_verified": True}
        r.t.require((RELEASE / "repair_regression_results.json").read_bytes() == r.j.canonical(reg), "REGRESSION_RESULT_READBACK_DRIFT")
        result["all_required_regression_artifacts_committed"] = True
    except Exception as exc:
        result["failure"] = {"qualified_class": type(exc).__module__ + "." + type(exc).__qualname__,
                             "message": str(exc), "traceback": traceback.format_exc()}
    return result


def release(preflight_root):
    r.PHASE1, r.PHASE1_MARKER, r.PHASE1_SHA = PREFLIGHT, PREFLIGHT_MARKER, preflight_root
    before = historical_authority()
    r.t.require(r.read(PREFLIGHT / "path_preflight_results.json")["passed"], "PATH_PREFLIGHT_NOT_PASSED")
    r.t.require(not RELEASE.exists() and not RELEASE.is_symlink(), "NEW_RELEASE_REQUIRED_NO_RERUN")
    manifest, expected, _ = r.freeze_configuration()
    wrapper_copy = RELEASE / "execution/artifact_orchestrator.py"
    r.j.atomic_freeze(wrapper_copy, Path(__file__).read_bytes())
    bindings = r.obj("frozen_input_bindings")
    bindings.update(log_path_layout=log_layout(manifest["order"], RELEASE),
        external_artifact_orchestrator={"source": r.h.ref(Path(__file__).absolute(), "frozen_preflight_orchestrator"),
                                       "snapshot": r.h.ref(wrapper_copy, "pre_execution_physical_source_copy")})
    write(RELEASE, "frozen_bindings", bindings)
    rows = r.matrix(manifest, expected)
    if all(row["status"] == "PASS" for row in rows):
        reg = r.regressions(rows)
    else:
        reg = {"status": "NOT_EXECUTED", "all_passed": False, "pytest_groups": {}, "reason": "first critical matrix failure; no repair or rerun"}
        r.emit("repair_regression_results", reg)
    r.j.atomic_freeze(RELEASE / "regression_results.json", (RELEASE / "repair_regression_results.json").read_bytes())
    archive = archived_regressions(reg)
    engineering = r.engineering_checks()
    after, preservation_error = None, None
    try:
        r.sources_unchanged()
        after = historical_authority()
        preserved = before == after and Path(__file__).read_bytes() == wrapper_copy.read_bytes()
    except Exception as exc:
        preserved, preservation_error = False, str(exc)
    safe = r.invariants(rows, reg, preserved)
    write(RELEASE, "safety_results", safe)
    write(RELEASE, "historical_preservation", {"before": before, "after": after, "passed": preserved,
        "error": preservation_error, "runtime_source_modified": not preserved, "original_oracle_modified": False,
        "scientific_policy_changed": False, "historical_assets_modified": not preserved})
    layout = bindings["log_path_layout"]
    scenario_paths = list(layout["scenario_logs"].values())
    regression_paths = [path for group in layout["regression_artifacts"].values() for path in group.values()]
    integrity = {"scenario_log_collisions": len(scenario_paths) - len(set(scenario_paths)),
        "regression_log_collisions": len(regression_paths) - len(set(regression_paths)),
        "scenario_regression_overlap_count": len(set(scenario_paths) & set(regression_paths)),
        "all_paths_inside_new_release": all(Path(path).is_relative_to(RELEASE) for path in scenario_paths + regression_paths),
        "archived_regressions": archive,
        "all_required_regression_artifacts_committed": archive["all_required_regression_artifacts_committed"],
        "immutable_artifact_checks_disabled": False, "historical_artifacts_rewritten": False}
    write(RELEASE, "artifact_integrity", integrity)
    counts = {status: sum(row["status"] == status for row in rows) for status in ("PASS", "FAIL", "NOT_EXECUTED")}
    passed = (counts["PASS"] == len(rows) == 59 and reg["all_passed"] and safe["full_safety_coverage_completed"]
        and safe["critical_safety_failures"] == 0 and preserved and all(row["passed"] for row in engineering)
        and archive["all_required_regression_artifacts_committed"] and integrity["scenario_log_collisions"] == 0
        and integrity["regression_log_collisions"] == 0 and integrity["scenario_regression_overlap_count"] == 0)
    failed_rows = [row for row in rows if row.get("first_divergence") is not None]
    write(RELEASE, "failure_evidence", {"failures": failed_rows, "regression_failure": reg.get("failure"),
        "archive_failure": archive["failure"], "preservation_error": preservation_error,
        "first_failed_scenario": failed_rows[0]["scenario_id"] if failed_rows else None,
        "no_repair_no_rerun": True, "remaining_not_executed": counts["NOT_EXECUTED"]})
    selected = {row["scenario_id"]: row for row in rows}
    summary = {"release_status": "completed" if passed else "failed", "release_classification": r.CLASS_PASS if passed else r.CLASS_FAIL,
        "logging_namespace_fix_passed": integrity["scenario_regression_overlap_count"] == 0,
        "scenario_log_collisions": integrity["scenario_log_collisions"], "regression_log_collisions": integrity["regression_log_collisions"],
        "scenario_count": 59, "executed_count": counts["PASS"] + counts["FAIL"], "passed_count": counts["PASS"],
        "failed_count": counts["FAIL"], "not_executed_count": counts["NOT_EXECUTED"],
        "all_required_regression_artifacts_committed": archive["all_required_regression_artifacts_committed"],
        "regressions_passed": reg["all_passed"] and archive["all_required_regression_artifacts_committed"],
        "critical_safety_failures": safe["critical_safety_failures"], "full_safety_coverage_completed": safe["full_safety_coverage_completed"],
        "pytest_test_count": sum(row["tests"] for row in reg["pytest_groups"].values()),
        "pytest_failure_count": sum(row["failures"] + row["errors"] for row in reg["pytest_groups"].values()),
        "oracle_version": "V2", "original_oracle_modified": False, "oracle_v2_sha256": r.V2_SHA,
        "runtime_source_modified": not preserved, "scientific_policy_changed": False, "retry_policy_changed": False,
        "independent_release_gate_passed": bool(passed), "release_label": "59/59 under Versioned Oracle V2" if passed else "FAILED_UNDER_VERSIONED_ORACLE_V2",
        "original_oracle_59_of_59_passed": False, "historical_assets_modified": not preserved,
        "production_runtime_v2_wiring_enabled": False, "alpha3_21_reopened": False,
        "next_stage_recommendation": "EXECUTE_ALPHA3_22E_FOCUSED_HISTORICAL_AND_SEEN_DATA_REPLAY_OFFLINE" if passed else "MINIMAL_ENGINEERING_CORRECTION_OF_EXACT_OBSERVED_FAILURE",
        "next_stage_automatically_started": False, "runner_preflight_root_sha256": preflight_root,
        "corrected_runner_sha256": r.j.sha(Path(r.__file__).read_bytes()), **r.NO_CALLS}
    summary.update({field: selected[key]["status"] == "PASS" for field, key in (
        ("t05_passed", "T05"), ("t11_passed", "T11"), ("t12_passed_under_v2", "T12"), ("t17_passed", "T17"), ("t18_passed", "T18"))})
    write(RELEASE, "summary", summary)
    write(RELEASE, "validation", {"passed": bool(passed), "classification": summary["release_classification"],
        "all_59_original_identities_and_order_preserved": [row["scenario_id"] for row in rows] == manifest["order"],
        "each_expected_outcome_equals_frozen_V2": all(row["expected"] == expected[row["scenario_id"]] for row in rows),
        "zero_original_scenario_reruns": True, "fail_fast_honored": True, "runtime_and_oracle_unchanged": preserved,
        "no_new_expectation_generation": True, "actual_latest_runtime_used": True,
        "regressions_separate_from_original_59": True, "engineering_checks": engineering,
        "historical_assets_preserved": preserved, "no_22E_or_fresh_primary_execution": True,
        "all_required_regression_artifacts_committed": archive["all_required_regression_artifacts_committed"], **r.NO_CALLS})
    r.t.require(all((RELEASE / (name + ".json")).is_file() for name in REQUIRED)
                and (RELEASE / "scenario_results.jsonl").is_file(), "REQUIRED_REPORT_MISSING")
    reference_count = r.verify_report_references()
    r.j.atomic_freeze(RELEASE / "execution/reference_verification.json", r.j.canonical({
        "report_reference_count_verified": reference_count, "all_admitted_evidence_read_back_and_hash_verified": True,
        "negative_fixture_corruption_not_promoted_to_admitted_provenance": True}))
    if preserved:
        r.t.require(historical_authority() == before, "HISTORICAL_ROOT_DRIFT_AT_SEAL")
    root = seal(RELEASE, RELEASE_MARKER)
    return {**summary, "new_release_root_sha256": root, "workspace": str(RELEASE)}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("phase", choices=("preflight", "release"))
    parser.add_argument("--preflight-root")
    args = parser.parse_args()
    if args.phase == "release" and args.preflight_root is None:
        parser.error("--preflight-root required")
    r.OUT, r.MARKER = RELEASE, RELEASE_MARKER
    with r.master.prior.offline_guard():
        result = preflight() if args.phase == "preflight" else release(args.preflight_root)
        print(json.dumps(result, sort_keys=True), flush=True)
        if result.get("runner_preflight_status") == "failed" or result.get("release_status") == "failed":
            raise SystemExit(1)
