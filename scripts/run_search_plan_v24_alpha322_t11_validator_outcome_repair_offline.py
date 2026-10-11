#!/usr/bin/env python3
"""Bounded development verification/freeze; never run the 59-scenario matrix."""

import ast
import json
import subprocess
import sys
import tempfile
import traceback
import xml.etree.ElementTree as ET
from pathlib import Path

from scripts import search_plan_v24_alpha322_t11_validator_outcome_fixtures_v1 as fixtures
from scripts import run_search_plan_v24_alpha322r2_minimal_runtime_identity_fix_offline as r2

h, j, t = fixtures.h, fixtures.j, fixtures.t
ROOT = h.ROOT
OUT = ROOT / "runs/20261010_search_plan_v24_dev_alpha3_22_t11_validator_outcome_integration_repair_offline"
MARKER = "search_plan_v24_dev_alpha3_22_t11_repair_sha256"
NEXT = "EXECUTE_NEW_ALPHA3_22DR2_INDEPENDENT_59_SCENARIO_REVALIDATION_OFFLINE"
NO_CALLS = dict(h.dr.NO_CALLS)
COMPONENTS = [Path(module.__file__) for module in (h.validity, j, h.p)] + [ROOT / "src/code_engine/stage_barrier_snapshot_v2_validator_outcome_v1.py"]
TESTS = [ROOT / "tests/test_search_plan_v24_alpha322_t11_validator_outcome_v1_offline.py",
         ROOT / "tests/test_search_plan_v24_alpha322_t11_validator_outcome_integrity_offline.py"]
SOURCES = COMPONENTS + [Path(h.__file__), Path(fixtures.__file__), Path(__file__)] + TESTS
REQUIRED = """summary validation source_manifest t11_repair_test_results validator_outcome_negative_tests
r2_regression_results historical_preservation independent_revalidation_handoff""".split()


def ref(path, role):
    path = j.physical(Path(path))
    return {"artifact_path": str(path.relative_to(ROOT)), "sha256": j.sha(j.read_bytes(path)), "artifact_role": role}


def emit(name, value):
    return j.atomic_freeze(OUT / (name + ".json"), j.canonical(value))


def authority():
    before = r2.authority()
    before["successful_R2"] = h.dr.master.prior.root_check(r2.OUT, r2.ROOT_MARKER, h.dr.R2_SHA)
    before["failed_D_R"] = h.dr.master.prior.root_check(h.dr.OUT, h.dr.MARKER,
        "ce0b26478f00be29dc32e8dfccb64add7274d010fc7ae43e99e89ed2738d0560")
    h.dr.frozen_inputs()
    manifest = j.strict_json(j.read_bytes(r2.OUT / "r2_source_implementation_manifest.json"))
    for source in manifest["source_files"] + manifest["supporting_source_files"]:
        t.require(j.sha(j.read_bytes(ROOT / source["artifact_path"])) == source["sha256"], "FROZEN_R2_SOURCE_DRIFT")
    return before


def nonwiring():
    names = {path.stem for path in COMPONENTS} | {path.stem for path in r2.COMPONENTS}
    allowed = set(COMPONENTS + r2.COMPONENTS)
    hits = []
    for path in (ROOT / "src").rglob("*.py"):
        if path in allowed:
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
    return {"passed": not hits and all(module.RUNTIME_ACTIVATION_ALLOWED is False for module in (h, h.validity, j)),
            "production_runtime_v2_wiring_enabled": bool(hits), "unexpected_imports": hits,
            "explicit_unwired_development_modules": [str(path.relative_to(ROOT)) for path in COMPONENTS]}


def pytest_group(name, paths):
    temporary = Path(tempfile.mkdtemp(prefix="alpha322-t11-" + name + "-")) / "pytest"
    xml = OUT / "execution" / (name + ".xml")
    command = [sys.executable, "-m", "pytest", "-q", "-W", "error", *map(str, paths),
               "--junitxml=" + str(xml), "--basetemp=" + str(temporary)]
    process = subprocess.run(command, cwd=ROOT, capture_output=True, text=True)
    log = OUT / "execution" / (name + ".txt")
    j.atomic_freeze(log, (process.stdout + process.stderr).encode())
    counts = {"tests": 0, "failures": 0, "errors": 0, "skipped": 0}
    if xml.exists():
        for suite in ET.parse(xml).getroot().iter("testsuite"):
            for key in counts:
                counts[key] += int(suite.attrib.get(key, 0))
    result = {"command": command, "exit_code": process.returncode, **counts,
        "passed": process.returncode == 0 and counts["tests"] > 0 and not any(counts[key] for key in ("failures", "errors", "skipped")),
        "log": ref(log, "unaltered_test_output"), "junit": ref(xml, "actual_test_accounting") if xml.exists() else None,
        "test_temporary_directory": str(temporary), "temporary_directory_outside_frozen_root": True}
    print(name + ": " + json.dumps({key: result[key] for key in ("passed", "tests", "failures", "errors", "skipped")}), flush=True)
    return result


def verify_release_references():
    """Recursively verify release reference records, not adversarial test claims.

Intentionally corrupted fixture receipts remain negative-test inputs. Their
actual physical bytes are covered by the run root; they are not provenance.
"""
    verified = set()
    def walk(value):
        if isinstance(value, dict):
            if "artifact_path" in value and "sha256" in value:
                path = Path(value["artifact_path"])
                path = j.physical(path if path.is_absolute() else ROOT / path)
                raw = j.read_bytes(path)
                t.require(j.sha(raw) == value["sha256"], "RELEASE_REFERENCE_HASH_MISMATCH:" + str(path))
                if "byte_count" in value:
                    t.require(len(raw) == value["byte_count"], "RELEASE_REFERENCE_LENGTH_MISMATCH")
                verified.add((str(path), value["sha256"]))
            for child in value.values():
                walk(child)
        elif isinstance(value, list):
            for child in value:
                walk(child)
    for path in OUT.glob("*.json"):
        walk(j.strict_json(j.read_bytes(path)))
    for path in OUT.glob("execution/development_iteration*/execution_record.json"):
        walk(j.strict_json(j.read_bytes(path)))
    return len(verified)


def run():
    t.require(OUT.exists() and not (OUT / MARKER).exists() and not (OUT / "summary.json").exists(), "DEVELOPMENT_ALREADY_FROZEN_NO_OVERWRITE")
    before = authority()
    t.require(j.canonical(before) == j.read_bytes(OUT / "upstream_root_verification.json"), "BASELINE_AUTHORITY_CHANGED")
    wiring = nonwiring()
    t.require(wiring["passed"], "PRODUCTION_WIRING_FORBIDDEN")
    (OUT / "implementation").mkdir()
    sources = [ref(path, "unwired_versioned_validator_result_development_source") for path in SOURCES]
    for path in SOURCES:
        j.atomic_freeze(OUT / "implementation" / path.name, j.read_bytes(path))
    emit("source_manifest", {"schema_version": "T11ValidatorOutcomeIntegrationSourceManifestV1", "sources": sources,
        "frozen_base_implementation": ref(r2.OUT / "r2_source_implementation_manifest.json", "unchanged_R2_base"),
        "versioned_integration_entrypoint": h.__name__, "new_journal_authority": j.AUTHORITY,
        "scientific_validator_contract": h.validity.contract("jats_primary_identity_v2"),
        "boolean_contract": h.validity.contract("literal_boolean"), "no_original_source_overwrite": True,
        "functional_changes": ["preserve actual validator result", "propagate A validation semantic separately from unchanged B transport mapping",
                               "strict completed-body outcome verification and terminal construction"],
        "mechanical_forks_only": ["journal append/fsync/hash/reducer/duplicate rules", "resume/abandoned policy", "barrier/activation dependencies"],
        "production_nonwiring": wiring})
    focused = pytest_group("final_focused", TESTS)
    t.require(focused["passed"], "FOCUSED_DEVELOPMENT_TESTS_FAILED_DIAGNOSTICS_PRESERVED")
    t11_result = h.t11(OUT / "execution/T11_repaired")
    t05_result = h.t05(OUT / "execution/T05_regression")
    negatives = [fixtures.execute(key, OUT / "execution" / ("validator_" + key)) for key in fixtures.SPEC]
    repair_root = OUT / "execution/R2_fixtures"
    repair_root.mkdir()
    positive = r2.fixtures.positive(repair_root / "P01")
    specs = r2.fixtures.source_spec("repair_negative_fixture_specification")["fixtures"]
    r0_negative = [r2.fixtures.negative(repair_root / spec["fixture_id"], spec) for spec in specs]
    ri_specs = j.strict_json(j.read_bytes(r2.ri.R11 / "r2_runtime_identity_negative_fixture_spec.json"))["fixtures"]
    identity_negative = [r2.ri.negative(repair_root / spec["fixture_id"], spec) for spec in ri_specs]
    recovery = r2.fixtures.recovery(repair_root / "recovery")
    groups = {
        "legacy_22A": [ROOT / "tests/test_search_plan_v24_alpha322a_transport_observability_offline.py"],
        "legacy_22B": [ROOT / "tests/test_search_plan_v24_alpha322b_exception_mapping_offline.py"],
        "legacy_22C": [ROOT / "tests/test_search_plan_v24_alpha322c_attempt_journal_resume_offline.py"],
        "frozen_R2": [r2.CONSTRUCTION_TEST, r2.INTEGRITY_TEST, r2.ISOLATION_TEST],
        "frozen_R0": [ROOT / "tests/test_search_plan_v24_alpha322r0_phase_binding_repair_design_offline.py"],
        "historical_contracts": [ROOT / "tests/test_search_plan_v24_alpha322_master_prereg_offline.py",
                                 ROOT / "tests/test_no_static_journal_weight_in_core_reasoning.py"]}
    regressions = {name: pytest_group(name, paths) for name, paths in groups.items()}
    compiled = subprocess.run([sys.executable, "-m", "compileall", "-q", *map(str, SOURCES)], cwd=ROOT,
                              capture_output=True, text=True)
    whitespace = []
    for command in [["git", "diff", "--check"]] + [
            ["git", "diff", "--no-index", "--check", "/dev/null", str(path)] for path in SOURCES]:
        process = subprocess.run(command, cwd=ROOT, capture_output=True, text=True)
        whitespace.append({"command": command, "exit_code": process.returncode, "diagnostics": process.stdout + process.stderr,
            "passed": process.returncode in ({0} if len(command) == 3 else {0, 1}) and not process.stdout and not process.stderr})
    after = authority()
    preserved = j.canonical(before) == j.canonical(after) and all(
        j.sha(j.read_bytes(ROOT / source["artifact_path"])) == source["sha256"] for source in sources)
    r0_valid = len(r0_negative) == 22 and all(row["passed"] and row["actual_first_rejection_reason"] == row["expected_first_rejection_reason"] for row in r0_negative)
    ri_valid = len(identity_negative) == 6 and all(row["passed"] for row in identity_negative)
    passed = (focused["passed"] and t11_result["passed"] and t05_result["passed"] and all(row["passed"] for row in negatives)
              and positive["passed"] and r0_valid and ri_valid and all(row["passed"] for row in recovery)
              and all(row["passed"] for row in regressions.values()) and compiled.returncode == 0
              and all(row["passed"] for row in whitespace) and preserved and nonwiring()["passed"])
    history = []
    for path in sorted(OUT.glob("execution/development_iteration*/execution_record.json")):
        record = j.strict_json(j.read_bytes(path))
        xmls = list(path.parent.glob("*.xml"))
        counts = {key: 0 for key in ("tests", "failures", "errors", "skipped")}
        for xml in xmls:
            for suite in ET.parse(xml).getroot().iter("testsuite"):
                for key in counts:
                    counts[key] += int(suite.attrib.get(key, 0))
        history.append({"development_iteration": record["development_iteration"], "exit_code": record["exit_code"],
            **counts, "execution_record": ref(path, "preserved_intermediate_execution_and_source_version"),
            "test_logs": [ref(log, "preserved_intermediate_failure_or_success_log") for log in path.parent.glob("*.txt")]})
    summary = {"t11_repair_status": "completed" if passed else "failed", "t11_focused_test_passed": t11_result["passed"],
        "validator_false_validity_failure_propagated": t11_result["terminal_payload"]["validation"]["accepted"] is False
            and t11_result["actual"]["semantic_failure_class"] == "COMPLETE_BODY_RESPONSE_VALIDITY_FAILURE",
        "complete_body_preserved": t11_result["actual"]["body_complete"], "parser_exception_fabricated": False,
        "validity_failure_terminal_committed": t11_result["actual"]["durable_terminal_committed"],
        "committed_validity_failure_refetch_allowed": False,
        "uncommitted_attempt_remains_abandoned": negatives[-1]["actual_exact_outcome"] == "ABANDONED_ATTEMPT_UNKNOWN_TERMINATION",
        "t05_regression_passed": t05_result["passed"], "r0_positive_passed": positive["passed"],
        "r0_negative_pass_count": sum(row["passed"] for row in r0_negative),
        "runtime_identity_negative_pass_count": sum(row["passed"] for row in identity_negative),
        "rec01_passed": recovery[0]["passed"], "rec02_passed": recovery[1]["passed"],
        "validator_contract_fixture_pass_count": sum(row["passed"] for row in negatives),
        "retry_policy_changed": False, "exception_mapping_table_changed": False, "scientific_policy_changed": False,
        "journal_integrity_weakened": False, "original_22dr_modified": False, "original_oracle_modified": False,
        "production_runtime_v2_wiring_enabled": False, "historical_assets_modified": not preserved,
        "complete_59_scenario_release_matrix_executed": False, "next_stage_automatically_started": False,
        "next_stage_recommendation": NEXT if passed else "RESOLVE_SMALLEST_T11_DEVELOPMENT_IMPLEMENTATION_FAILURE_OFFLINE",
        "final_pytest_test_count": focused["tests"] + sum(row["tests"] for row in regressions.values()),
        "final_pytest_failure_count": focused["failures"] + sum(row["failures"] for row in regressions.values()),
        "meaningful_intermediate_failure_records_preserved": True, **NO_CALLS}
    emit("t11_repair_test_results", {**t11_result,
        "frozen_original_failure": ref(h.dr.OUT / "scenario_failure_evidence.json", "unchanged_D_R_first_failure"),
        "local_baseline_reproduction": ref(OUT / "execution/baseline_T11.json", "original_code_reproduced_only_in_new_development_directory"),
        "focused_tests": focused, "development_iterations": history})
    emit("validator_outcome_negative_tests", {"fixture_count": 12, "passed": all(row["passed"] for row in negatives),
        "fixtures": negatives, "prospective_exact_specification": {key: list(value) for key, value in fixtures.SPEC.items()},
        "focused_pytest": focused, "no_truthiness": True, "no_fabricated_parser_exception": True})
    emit("r2_regression_results", {"T05": t05_result, "R0_positive": positive, "R0_negatives": r0_negative,
        "runtime_identity_negatives": identity_negative, "REC01_REC02": recovery, "pytest_groups": regressions,
        "original_22_r0_first_rejections_preserved": r0_valid,
        "RI_specified_admission_stages_preserved": ri_valid,
        "no_59_scenario_release_execution": True, "power_loss_durability_claimed": False})
    emit("historical_preservation", {"passed": preserved, "before": before, "after": after,
        "original_22dr_modified": False, "original_oracle_modified": False,
        "historical_assets_modified": not preserved, "all_frozen_R2_sources_and_snapshots_preserved": True,
        "source_bindings_stable_during_final_execution": sources, "production_nonwiring": nonwiring(),
        "scientific_policy_changed": False, "retry_policy_changed": False, "journal_integrity_weakened": False})
    emit("independent_revalidation_handoff", {"development_passed": passed, "recommended_next_stage": summary["next_stage_recommendation"],
        "new_release_authorized_or_started_here": False, "completely_new_validation_directory_and_root_required": True,
        "original_59_oracle": ref(h.dr.h.ORIGINAL / "independent_expected_outcomes.jsonl", "unchanged_independent_oracle"),
        "original_scenario_manifest": ref(h.dr.h.ORIGINAL / "frozen_fault_scenario_manifest.json", "unchanged_59_original_scenarios"),
        "integration_entrypoint": ref(Path(h.__file__), "explicit_unwired_validity_result_adapter_and_fresh_reader"),
        "repaired_semantic_outcome_owner": "22A.record_validation and 22A.semantic_retry_decision; transport B mapping unchanged",
        "journal_route": "explicit validator_outcome envelope; original exception/transport route unchanged",
        "no_fabricated_exception_or_retry_override": True, "original_22dr_failure_must_remain_unchanged": True})
    emit("validation", {"passed": passed, "focused_pytest": focused, "regression_groups": regressions,
        "compileall": {"passed": compiled.returncode == 0, "exit_code": compiled.returncode, "diagnostics": compiled.stdout + compiled.stderr},
        "whitespace_checks": whitespace, "development_iteration_history": history,
        "original_independent_expectations_unchanged": True, "historical_preservation_verified": preserved,
        "full_repository_suite_claimed": False, "complete_59_matrix_executed": False, **NO_CALLS})
    emit("summary", summary)
    t.require(all((OUT / (name + ".json")).is_file() for name in REQUIRED), "REQUIRED_DEVELOPMENT_OUTPUT_MISSING")
    reference_count = verify_release_references()
    emit("freeze_verification", {"nested_release_references_verified": reference_count,
        "negative_fixture_claims_not_promoted_to_provenance": True, "all_required_artifacts_present": True,
        "source_and_original_upstream_hashes_verified": True, "development_only": True})
    verify_release_references()
    t.require(j.canonical(authority()) == j.canonical(before), "UPSTREAM_DRIFT_BEFORE_SEAL")
    root = h.dr.master.root_hash(OUT, MARKER)
    j.atomic_freeze(OUT / MARKER, (root + "\n").encode())
    j.sync_directory(OUT)
    t.require(h.dr.master.root_hash(OUT, MARKER) == root, "DEVELOPMENT_ROOT_POST_FREEZE_MISMATCH")
    return {**summary, "development_root_sha256": root, "workspace": str(OUT)}


if __name__ == "__main__":
    with h.dr.master.prior.offline_guard():
        print(json.dumps(run(), sort_keys=True))
