#!/usr/bin/env python3
"""Bounded R2 engineering execution/freeze. No scientific or 22D-R run."""

import ast
import json
import os
import subprocess
import sys
import traceback
import xml.etree.ElementTree as ET
from pathlib import Path

from code_engine import stage_barrier_snapshot_v2_r2 as barrier
from scripts import run_search_plan_v24_alpha322r11_runtime_identity_failure_audit_offline as audit
from scripts import search_plan_v24_alpha322r2_runtime_identity_fixtures as ri

h, fixtures, j, f = ri.h, ri.fixtures, ri.j, ri.fixtures.f
ROOT, OUT = h.ROOT, f.R2
TEMP = ROOT / "runs/20261009_search_plan_v24_dev_alpha3_22r2_test_temporaries_offline_iteration02"
ROOT_MARKER = "search_plan_v24_dev_alpha3_22r2_sha256"
PREVIOUS = ROOT / "runs/20261009_search_plan_v24_dev_alpha3_22r2_minimal_versioned_runtime_identity_fix_offline"
PREVIOUS_SHA = "fda6b7dfd3c54c696f0800a615a4c4dca6f857b1f7ea3078a166addbdd758c66"
R11_SHA = "e9e90e0ea4d88a758645628c3298edca0d4e3e938092aafa40a2318f9925a711"
NEXT = "EXECUTE_ALPHA3_22DR_INDEPENDENT_59_SCENARIO_REVALIDATION_OFFLINE"
NEXT_FAIL = "RESOLVE_SMALLEST_ALPHA3_22R2_IMPLEMENTATION_BLOCKER_OFFLINE"
NO_CALLS = dict(audit.NO_CALLS)
COMPONENTS = [Path(module.__file__) for module in (ri.identity, f, j, h.p, barrier, h)]
CONSTRUCTION_TEST = ROOT / "tests/test_search_plan_v24_alpha322r2_runtime_identity_construction_offline.py"
INTEGRITY_TEST = ROOT / "tests/test_search_plan_v24_alpha322r2_versioned_runtime_identity_offline.py"
ISOLATION_TEST = ROOT / "tests/test_search_plan_v24_alpha322r2_isolation_and_binding_offline.py"
SUPPORT = [Path(fixtures.__file__), Path(ri.__file__), Path(__file__), CONSTRUCTION_TEST, INTEGRITY_TEST, ISOLATION_TEST]
REQUIRED = """summary validation r2_source_implementation_manifest r2_runtime_identity_schema_validation
r2_original_r0_fixture_results r2_ri01_ri06_results r2_recovery_results r2_regression_results
r2_historical_preservation_audit r2_independent_22dr_handoff""".split()


def ref(path, role):
    return audit.ref(path, role)


def emit(stem, value):
    return j.atomic_freeze(OUT / (stem + ".json"), j.canonical(value))


def authority():
    result = audit.verify_authority()
    result["alpha322r11"] = audit.r0.d.master.prior.root_check(audit.OUT, audit.ROOT_MARKER, R11_SHA)
    design = audit.OUT / "r2_minimal_versioned_repair_design.json"
    j.require(j.sha(j.read_bytes(design)) == f.R11_DESIGN_SHA, "FROZEN_R2_DESIGN_MISMATCH")
    result["R11_repair_design"] = ref(design, "unchanged_frozen_R2_design")
    result["R11_identity_negative_specs"] = ref(ri.R11 / "r2_runtime_identity_negative_fixture_spec.json", "unchanged_frozen_RI01_RI06_oracles")
    return result


def previous_development_attempt():
    verified = audit.r0.d.master.prior.root_check(PREVIOUS, ROOT_MARKER, PREVIOUS_SHA)
    manifest = j.strict_json(j.read_bytes(PREVIOUS / "r2_source_implementation_manifest.json"))
    snapshots = []
    for source in manifest["source_files"] + manifest["supporting_source_files"]:
        snapshot = PREVIOUS / "implementation" / Path(source["artifact_path"]).name
        j.require(j.sha(j.read_bytes(snapshot)) == source["sha256"], "PRIOR_R2_SOURCE_SNAPSHOT_DRIFT")
        snapshots.append({"original_development_source_path": source["artifact_path"],
                          "historical_version_authority": ref(snapshot, "unchanged_first_iteration_source_bytes")})
    return {"verified_root": verified, "summary": ref(PREVIOUS / "summary.json", "unchanged_failed_first_R2_iteration"),
        "failure_log": ref(PREVIOUS / "execution/R2_integrity_isolation.txt", "original_unraisable_HTTPResponse_cleanup_failure"),
        "source_versions": snapshots,
        "original_source_paths_are_historical_observations_resolved_by_these_physical_snapshots": True,
        "change_in_second_iteration": "explicit local in-memory HTTPResponse.close() in finally after unchanged occurrence capture",
        "failure_diagnostics_and_test_history_preserved": True, "frozen_oracles_changed": False,
        "warning_filters_or_schema_suppression_added": False}


def nonwiring():
    names = {path.stem for path in COMPONENTS}
    hits = []
    for path in (ROOT / "src").rglob("*.py"):
        if path in COMPONENTS:
            continue
        for node in ast.walk(ast.parse(path.read_bytes())):
            if isinstance(node, ast.ImportFrom):
                used = {alias.name for alias in node.names} | {(node.module or "").split(".")[-1]}
            elif isinstance(node, ast.Import):
                used = {alias.name.split(".")[-1] for alias in node.names}
            else:
                continue
            if used & names:
                hits.append({"artifact_path": str(path.relative_to(ROOT)), "line": node.lineno})
    return {"passed": not hits and all(module.RUNTIME_ACTIVATION_ALLOWED is False for module in (ri.identity, f, j)),
            "production_runtime_v2_wiring_enabled": bool(hits), "unexpected_imports": hits}


def pytest_group(name, paths):
    temporary = TEMP / name
    j.require(not temporary.exists() and not temporary.is_symlink(), "TEST_TEMPORARY_PATH_MUST_BE_NEW")
    xml = OUT / "execution" / (name + ".xml")
    command = [sys.executable, "-m", "pytest", "-q", "-W", "error", *[str(path) for path in paths],
               "--junitxml=" + str(xml), "--basetemp=" + str(temporary)]
    process = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, check=False)
    log = OUT / "execution" / (name + ".txt")
    j.atomic_freeze(log, (process.stdout + process.stderr).encode())
    counts = {"tests": 0, "failures": 0, "errors": 0, "skipped": 0}
    if xml.is_file():
        for suite in ET.parse(xml).getroot().iter("testsuite"):
            for key in counts:
                counts[key] += int(suite.attrib.get(key, 0))
    result = {"command": command, "exit_code": process.returncode, **counts,
        "passed": process.returncode == 0 and counts["tests"] > 0 and not any(counts[key] for key in ("failures", "errors", "skipped")),
        "log": ref(log, "unaltered_offline_test_output"), "junit": ref(xml, "actual_test_accounting") if xml.is_file() else None,
        "test_temporaries_preserved_outside_release_root": str(temporary.relative_to(ROOT))}
    print(name + ": " + json.dumps({key: result[key] for key in ("passed", "tests", "failures", "errors", "skipped")}), flush=True)
    return result


def temporary_inventory():
    entries = []
    for directory, folders, files in os.walk(TEMP, topdown=True, followlinks=False):
        folders.sort()
        for name in sorted(folders + files):
            path = Path(directory) / name
            entry = {"relative_path": str(path.relative_to(TEMP))}
            if path.is_symlink():
                entry.update(entry_type="symlink", link_target=os.readlink(path), target_not_followed=True)
            elif path.is_file():
                entry.update(entry_type="physical_file", sha256=j.sha(j.read_bytes(path)))
            else:
                entry.update(entry_type="directory")
            entries.append(entry)
    return {"temporary_root": str(TEMP.relative_to(ROOT)), "entries": entries,
            "symlink_targets_not_followed": True, "preserved_without_relocation_or_cleanup": True}


def run():
    before = authority()
    previous = previous_development_attempt()
    wiring = nonwiring()
    j.require(wiring["passed"], "PRODUCTION_WIRING_FORBIDDEN")
    j.require(not OUT.exists() and not TEMP.exists(), "R2_EXECUTION_PATHS_MUST_BE_NEW")
    OUT.mkdir()
    (OUT / "implementation").mkdir()
    (OUT / "execution").mkdir()
    TEMP.mkdir()
    sources = [ref(path, "versioned_R2_component_or_integration") for path in COMPONENTS]
    supporting = [ref(path, "R2_fixture_test_or_freezer") for path in SUPPORT]
    for path in COMPONENTS + SUPPORT:
        j.atomic_freeze(OUT / "implementation" / path.name, j.read_bytes(path))
    emit("r2_source_implementation_manifest", {"schema_version": "RuntimeV2ImplementationManifestR2",
        "r0_proposal_sha256": f.DESIGN_SHA, "r11_repair_design_sha256": f.R11_DESIGN_SHA,
        "source_files": sources, "supporting_source_files": supporting,
        "activation": "OFFLINE_SYNTHETIC_ONLY_NOT_PRODUCTION", "no_V1_conversion": True,
        "historical_R1_runtime_manifest": ref(audit.R1 / "runtime_v2_implementation_manifest.json", "unchanged_R1_implementation"),
        "functional_changes": ["complete trusted runtime identity construction", "same immutable capture reused by mapped exception"],
        "mechanical_changes": ["actual R2 source/implementation identity", "explicit R2 phase/journal/resume/barrier dependencies"],
        "offline_fixture_cleanup": "explicit local HTTPResponse close after failure capture; no scientific or transport policy change",
        "prior_development_attempt": previous,
        "production_nonwiring": wiring})
    emit("upstream_root_verification", before)
    timeline, blockers = [], []

    def execute(name, callback):
        try:
            result = callback()
            passed = all(row["passed"] for row in result) if isinstance(result, list) else result["passed"]
            timeline.append({"sequence": len(timeline) + 1, "stage": name, "passed": passed})
            if not passed:
                blockers.append({"stage": name, "result": result})
            print(name + ": " + str(passed), flush=True)
            return result
        except Exception as exc:
            path = OUT / "execution" / (name + "_failure.txt")
            j.atomic_freeze(path, traceback.format_exc().encode())
            result = {"passed": False, "error": type(exc).__name__ + ":" + str(exc), "failure_evidence": ref(path, "concrete_failure_traceback")}
            blockers.append({"stage": name, "result": result})
            timeline.append({"sequence": len(timeline) + 1, "stage": name, "passed": False, "failure_evidence": result["failure_evidence"]})
            print(name + ": " + result["error"], flush=True)
            return result

    construction = execute("A_identity_construction", ri.construction)
    construction_tests = execute("A_identity_construction_tests", lambda: pytest_group("identity_construction", [CONSTRUCTION_TEST]))
    identity_valid = construction["passed"] and construction_tests["passed"]
    ri_spec = j.strict_json(j.read_bytes(ri.R11 / "r2_runtime_identity_negative_fixture_spec.json"))
    j.require(ri_spec["fixture_count"] == 6 and [row["fixture_id"] for row in ri_spec["fixtures"]] == ["RI01", "RI02", "RI03", "RI04", "RI05", "RI06"], "FROZEN_RI_SPEC_CHANGED")
    identity_negatives = []
    if identity_valid:
        for spec in ri_spec["fixtures"]:
            result = execute("B_" + spec["fixture_id"], lambda spec=spec: ri.negative(OUT / "execution" / spec["fixture_id"], spec))
            identity_negatives.append(result)
    ri_valid = len(identity_negatives) == 6 and all(row["passed"] for row in identity_negatives)
    positive = {"passed": False, "execution_status": "NOT_EXECUTED_AFTER_PRIOR_STAGE_FAILURE"}
    if ri_valid:
        positive = execute("C_R0_P01", lambda: fixtures.positive(OUT / "execution" / "positive"))
        if positive["passed"]:
            required_phases = {"occurrence": "RESPONSE_BODY_READING", "mapping": "RESPONSE_BODY_READING", "persistence": "RAW_RESPONSE_FROZEN"}
            if positive["phases"] != required_phases:
                positive["passed"] = False
                blockers.append({"stage": "C_R0_P01_PHASES", "expected": required_phases, "actual": positive["phases"]})
    negative_spec = fixtures.source_spec("repair_negative_fixture_specification")
    j.require(len(negative_spec["fixtures"]) == 22, "FROZEN_R0_NEGATIVE_COUNT_CHANGED")
    negatives = []
    if positive["passed"]:
        for spec in negative_spec["fixtures"]:
            result = execute("D_" + spec["fixture_id"], lambda spec=spec: fixtures.negative(OUT / "execution" / spec["fixture_id"], spec))
            negatives.append(result)
    negative_valid = len(negatives) == 22 and all(row["passed"] for row in negatives)
    recovery = {"passed": False, "execution_status": "NOT_EXECUTED_AFTER_PRIOR_STAGE_FAILURE"}
    if negative_valid:
        recovery = execute("E_REC01_REC02", lambda: fixtures.recovery(OUT / "execution" / "recovery"))
    recovered = isinstance(recovery, list) and len(recovery) == 2 and all(row["passed"] for row in recovery)
    regressions = {}
    supplement = {"passed": False, "execution_status": "NOT_EXECUTED_AFTER_PRIOR_STAGE_FAILURE"}
    if recovered:
        supplement = execute("F_nonempty_partial_supplement", lambda: fixtures.positive(OUT / "execution" / "nonempty_partial", "partial"))
        groups = {"R2_integrity_isolation": [INTEGRITY_TEST, ISOLATION_TEST],
            "legacy_22A": [ROOT / "tests/test_search_plan_v24_alpha322a_transport_observability_offline.py"],
            "legacy_22B": [ROOT / "tests/test_search_plan_v24_alpha322b_exception_mapping_offline.py"],
            "legacy_22C": [ROOT / "tests/test_search_plan_v24_alpha322c_attempt_journal_resume_offline.py"],
            "frozen_R0": [ROOT / "tests/test_search_plan_v24_alpha322r0_phase_binding_repair_design_offline.py"],
            "historical_contracts": [ROOT / "tests/test_search_plan_v24_alpha322_master_prereg_offline.py",
                                     ROOT / "tests/test_no_static_journal_weight_in_core_reasoning.py"]}
        for name, paths in groups.items():
            regressions[name] = execute("F_" + name, lambda name=name, paths=paths: pytest_group(name, paths))
    comp = subprocess.run([sys.executable, "-m", "compileall", "-q", *[str(path) for path in COMPONENTS + SUPPORT]],
                          cwd=ROOT, capture_output=True, text=True, check=False)
    checks = []
    commands = [["git", "diff", "--check"]] + [["git", "diff", "--no-index", "--check", "/dev/null", str(path)] for path in COMPONENTS + SUPPORT]
    for command in commands:
        check = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, check=False)
        checks.append({"command": command, "exit_code": check.returncode, "diagnostics": check.stdout + check.stderr,
            "passed": check.returncode in ({0} if len(command) == 3 else {0, 1}) and not check.stdout and not check.stderr})
    after = authority()
    prior_after = audit.r0.d.master.prior.root_check(PREVIOUS, ROOT_MARKER, PREVIOUS_SHA)
    preserved = j.canonical(before) == j.canonical(after) and all(
        j.sha(j.read_bytes(ROOT / source["artifact_path"])) == source["sha256"] for source in sources + supporting)
    inventory = temporary_inventory()
    emit("test_temporary_preservation_manifest", inventory)
    emit("execution_history", {"stage_order": "A construction -> B RI01-RI06 -> C R0_P01 -> D N01-N22 -> E recovery -> F regressions",
        "stages": timeline, "meaningful_failures": blockers, "failures_not_silently_discarded": True,
        "prior_development_attempt": previous,
        "automatic_code_repair_or_rerun": False})
    emit("r2_runtime_identity_schema_validation", {"passed": identity_valid, "construction": construction,
        "construction_tests": construction_tests, "frozen_schema": ref(audit.A / "exception_provenance_v1_schema.json", "unchanged_22A_exception_schema"),
        "trusted_construction_only_no_verifier_repair": True})
    emit("r2_ri01_ri06_results", {"passed": ri_valid, "fixture_count": 6, "executed_count": len(identity_negatives),
        "pass_count": sum(row["passed"] for row in identity_negatives), "fixtures": identity_negatives,
        "frozen_oracle": before["R11_identity_negative_specs"]})
    emit("r2_original_r0_fixture_results", {"positive": positive, "negative_fixture_count": 22,
        "negative_executed_count": len(negatives), "negative_pass_count": sum(row["passed"] for row in negatives),
        "negative_fixtures": negatives, "expected_first_reasons_unchanged": True,
        "frozen_positive_oracle": ref(f.R0 / "repair_positive_fixture_specification.json", "original_R0_positive"),
        "frozen_negative_oracle": ref(f.R0 / "repair_negative_fixture_specification.json", "original_22_R0_negative_reasons")})
    emit("r2_recovery_results", {"passed": recovered, "fixtures": recovery,
        "frozen_oracle": ref(f.R0 / "repair_recovery_fixture_specification.json", "original_R0_REC01_REC02"),
        "terminal_not_inferred_from_orphan_artifacts": True})
    emit("r2_regression_results", {"groups": regressions, "nonempty_partial_supplement": supplement,
        "all_required_groups_executed": len(regressions) == 6,
        "passed": len(regressions) == 6 and all(row["passed"] for row in regressions.values()) and supplement["passed"],
        "original_22DR_matrix_executed": False})
    emit("r2_historical_preservation_audit", {"passed": preserved, "before": before, "after": after,
        "historical_R1_modified": False, "original_22d_oracle_modified": False,
        "archived_R1_temporaries_and_symlinks_untouched": True, "R1_archive_manifest_verified_only": before["test_archive_manifest"],
        "contamination_counts": before["counts"], "scientific_policy_changed": False,
        "prior_R2_development_attempt": previous, "prior_R2_failed_root_reverified_after_iteration": prior_after,
        "alpha3_21_reopened": False, "production_nonwiring": nonwiring()})
    regression_valid = len(regressions) == 6 and all(row["passed"] for row in regressions.values()) and supplement["passed"]
    passed = identity_valid and ri_valid and positive["passed"] and negative_valid and recovered and regression_valid \
        and comp.returncode == 0 and all(row["passed"] for row in checks) and preserved and nonwiring()["passed"]
    def reached(key):
        rows = [row for row in negatives if row.get("fixture_id") == key]
        return len(rows) == 1 and rows[0]["passed"] and rows[0]["actual_first_rejection_reason"] == rows[0]["expected_first_rejection_reason"]
    summary = {"status": "completed" if passed else "failed", "runtime_identity_schema_valid": identity_valid,
        "r0_positive_fixture_passed": positive["passed"], "r0_negative_fixture_count": 22,
        "r0_negative_fixture_pass_count": sum(row["passed"] for row in negatives),
        "runtime_identity_negative_fixture_count": 6, "runtime_identity_negative_fixture_pass_count": sum(row["passed"] for row in identity_negatives),
        "n14_expected_rejection_reached": reached("N14"), "n17_expected_rejection_reached": reached("N17"), "n21_expected_rejection_reached": reached("N21"),
        "rec01_passed": recovered and recovery[0]["passed"], "rec02_passed": recovered and recovery[1]["passed"],
        "journal_integrity_preserved": negative_valid and recovered and regressions.get("R2_integrity_isolation", {}).get("passed", False),
        "partial_response_parser_invocations": positive.get("actual", {}).get("parser_invocations", 0)
            + sum(row.get("actual", {}).get("parser_invocations", 0) for row in negatives + identity_negatives)
            + supplement.get("actual", {}).get("parser_invocations", 0),
        "retry_policy_changed": False, "exception_mapping_table_changed": False, "scientific_policy_changed": False,
        "historical_r1_modified": False, "original_22d_oracle_modified": False, "production_runtime_v2_wiring_enabled": False,
        "original_R1_status_preserved": "failed", "alpha3_21_reopened": False, "fresh_primary_attempt_started": False,
        "independent_22DR_executed": False, "next_fresh_primary_ready_claimed": False,
        "development_iteration_count": 2, "prior_failed_iteration_preserved": True,
        "next_stage_recommendation": NEXT if passed else NEXT_FAIL, "historical_assets_modified": not preserved,
        "smallest_unresolved_blocker": blockers[0] if blockers else None, **NO_CALLS}
    emit("r2_independent_22dr_handoff", {"R2_release_passed": passed, "next_stage": summary["next_stage_recommendation"],
        "execution_authorized_here": False, "original_59_scenarios_and_oracle_required": True,
        "original_oracle": ref(audit.r0.d.OUT / "independent_expected_outcomes.jsonl", "unchanged_22D_independent_oracle"),
        "R2_integration": ref(Path(h.__file__), "explicit_R2_offline_integration"),
        "new_independent_validation_root_required": True, "no_claim_22DR_passed_or_fresh_primary_ready": True})
    emit("validation", {"passed": passed, "development_only": True, "focused_scopes_only": True,
        "compileall": {"passed": comp.returncode == 0, "exit_code": comp.returncode, "diagnostics": comp.stdout + comp.stderr},
        "whitespace_checks": checks, "historical_preservation_verified": preserved,
        "executed_22DR": False, "full_repository_suite_executed": False,
        "construction_test_count": construction_tests["tests"],
        "regression_test_count": sum(row["tests"] for row in regressions.values()),
        "test_failure_count": construction_tests["failures"] + sum(row["failures"] for row in regressions.values()),
        "test_error_count": construction_tests["errors"] + sum(row["errors"] for row in regressions.values()),
        "test_skip_count": construction_tests["skipped"] + sum(row["skipped"] for row in regressions.values()),
        "meaningful_failure_history": ref(OUT / "execution_history.json", "all_stage_results_and_failure_diagnostics"), **NO_CALLS})
    emit("summary", summary)
    j.require(all((OUT / (stem + ".json")).is_file() for stem in REQUIRED), "REQUIRED_R2_OUTPUT_MISSING")
    j.require(j.canonical(authority()) == j.canonical(before), "UPSTREAM_DRIFT_BEFORE_R2_SEAL")
    audit.r0.d.master.prior.root_check(PREVIOUS, ROOT_MARKER, PREVIOUS_SHA)
    root = audit.r0.d.master.root_hash(OUT, ROOT_MARKER)
    j.atomic_freeze(OUT / ROOT_MARKER, (root + "\n").encode())
    j.sync_directory(OUT)
    j.require(audit.r0.d.master.root_hash(OUT, ROOT_MARKER) == root, "R2_ROOT_POST_FREEZE_MISMATCH")
    return {**summary, "alpha3_22r2_sha256": root, "workspace": str(OUT)}


if __name__ == "__main__":
    with audit.r0.d.master.prior.offline_guard():
        print(json.dumps(run(), sort_keys=True))
