#!/usr/bin/env python3
"""Finish the evidence-only R1.1 audit with a narrowly corrected audit guard.

The initial sealed audit, collector and original tests remain byte-frozen.
No R1 fixture, capture, journal, transport, resume or scientific runner executes.
"""

import ast
import json
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

from scripts import run_search_plan_v24_alpha322r11_runtime_identity_failure_audit_offline as audit

ROOT, OUT, u, t = audit.ROOT, audit.OUT, audit.u, audit.t
ARCHIVE = ROOT / "runs/20261009_search_plan_v24_dev_alpha3_22r11_runtime_identity_failure_audit_offline_failed_audit_guard_01"
INITIAL_ROOT = "2928118c880bae358fccdcdfcaceda3d2c4549da41159a5a793eb1e279292105"
GUARD = ROOT / "tests/test_search_plan_v24_alpha322r11_runtime_identity_failure_audit_guard_v2_offline.py"


def root_check(directory, expected):
    return audit.r0.d.master.prior.root_check(directory, audit.ROOT_MARKER, expected)


def test_counts(path):
    counts = {"tests": 0, "failures": 0, "errors": 0, "skipped": 0}
    for suite in ET.parse(path).getroot().iter("testsuite"):
        for key in counts:
            counts[key] += int(suite.attrib.get(key, 0))
    return counts


def inspect_guard_amendment():
    original = ast.parse(u.read_bytes(audit.TEST))
    corrected = ast.parse(u.read_bytes(GUARD))
    name = "test_no_runtime_fixture_dispatch_or_capture_calls_in_audit_source"

    def scientific_and_schema_tests(tree):
        return [ast.dump(node, include_attributes=False) for node in tree.body
                if not (isinstance(node, ast.Expr) and isinstance(node.value, ast.Constant)
                        and isinstance(node.value.value, str))
                and not (isinstance(node, ast.FunctionDef) and node.name == name)]

    t.require(scientific_and_schema_tests(original) == scientific_and_schema_tests(corrected),
              "AUDIT_GUARD_AMENDMENT_ALTERED_EVIDENCE_OR_SCHEMA_TESTS")
    old_guard = next(node for node in original.body if isinstance(node, ast.FunctionDef) and node.name == name)
    new_guard = next(node for node in corrected.body if isinstance(node, ast.FunctionDef) and node.name == name)
    t.require(ast.dump(old_guard.body[1], include_attributes=False)
              == ast.dump(new_guard.body[1], include_attributes=False), "FORBIDDEN_RUNTIME_CALL_SET_CHANGED")
    source = u.read_bytes(Path(audit.__file__)).decode()
    tree = ast.parse(source)
    calls = [node.func for node in ast.walk(tree)
             if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)]
    run_calls = [call for call in calls if call.attr == "run"]
    t.require(run_calls and all(isinstance(call.value, ast.Name) and call.value.id == "subprocess"
                               for call in run_calls), "UNAUTHORIZED_AUDIT_RUNNER_CALL")
    return {"amendment_scope": "static audit guard only: distinguish audit subprocess.run from runtime runner.run",
            "evidence_schema_and_design_tests_unchanged": True, "forbidden_runtime_call_set_unchanged": True,
            "original_test_source": audit.ref(audit.TEST, "unchanged_original_overbroad_audit_guard"),
            "corrected_test_source": audit.ref(GUARD, "separately_versioned_audit_guard_V2"),
            "scientific_oracle_or_runtime_fixture_changes": False}


def complete_audit():
    initial = root_check(OUT, INITIAL_ROOT)
    old_summary = audit.load(OUT / "summary.json")
    t.require(old_summary["status"] == "failed"
              and old_summary["audit_test_counts"] == {"tests": 29, "failures": 1, "errors": 0, "skipped": 0},
              "INITIAL_AUDIT_FAILURE_ACCOUNTING_CHANGED")
    failures = [case.attrib["name"] for case in ET.parse(OUT / "audit_tests.xml").getroot().iter("testcase")
                if case.find("failure") is not None]
    t.require(failures == ["test_no_runtime_fixture_dispatch_or_capture_calls_in_audit_source"],
              "INITIAL_AUDIT_FAILURE_NOT_ISOLATED_TO_GUARD")
    t.require(u.read_bytes(Path(audit.__file__)) == u.read_bytes(OUT / "audit_source.py")
              and u.read_bytes(audit.TEST) == u.read_bytes(OUT / "audit_tests.py"),
              "INITIAL_AUDIT_SOURCE_OR_TEST_REWRITTEN")
    amendment = inspect_guard_amendment()
    documents = audit.prepare_documents()
    before = documents["upstream_root_verification"]
    originals = {stem: u.read_bytes(OUT / (stem + ".json")) for stem in documents}
    t.require(all(originals[stem] == u.canonical(value) for stem, value in documents.items()),
              "FORENSIC_EVIDENCE_OR_R2_DESIGN_CHANGED_BETWEEN_AUDIT_GUARDS")
    t.require(not ARCHIVE.exists() and not ARCHIVE.is_symlink() and not OUT.is_symlink(),
              "INITIAL_AUDIT_ARCHIVE_MUST_BE_NEW_PHYSICAL_PATH")
    # Recoverable relocation of newly generated audit files only. Frozen R1,
    # upstream snapshots and the six archived R1 temporary trees are untouched.
    OUT.rename(ARCHIVE)
    u.sync_directory(ARCHIVE.parent)
    archived = root_check(ARCHIVE, INITIAL_ROOT)
    store = t.RawArtifactStoreV1(OUT)

    def emit(stem, value):
        return store.freeze_bytes(stem + ".json", u.canonical(value))

    for stem, value in documents.items():
        emit(stem, value)
    store.freeze_bytes("audit_source.py", u.read_bytes(Path(audit.__file__)))
    store.freeze_bytes("audit_guard_v2_tests.py", u.read_bytes(GUARD))
    store.freeze_bytes("audit_completion_source.py", u.read_bytes(Path(__file__)))
    preservation = {"initial_audit_root": INITIAL_ROOT, "initial_status": "failed",
        "initial_audit_counts": old_summary["audit_test_counts"], "initial_failure_test_names": failures,
        "failure_category": "OVERBROAD_STATIC_AUDIT_GUARD_FALSE_POSITIVE_ON_ALLOWED_SUBPROCESS_RUN",
        "initial_failure_never_relabelled_or_overwritten": True,
        "archived_root_verified": archived, "initial_pre_relocation_verification": initial,
        "initial_directory_relocated_byte_identically": True,
        "initial_embedded_member_reference_resolution": {
            "original_prefix": str(OUT.relative_to(ROOT)), "archived_prefix": str(ARCHIVE.relative_to(ROOT)),
            "rule": "resolve archived audit-owned member paths by this prefix mapping only; upstream and source refs retain original paths"},
        "initial_summary": audit.ref(ARCHIVE / "summary.json", "unchanged_initial_audit_failed_summary"),
        "initial_validation": audit.ref(ARCHIVE / "validation.json", "unchanged_initial_28_pass_1_guard_failure"),
        "initial_test_output": audit.ref(ARCHIVE / "audit_tests.txt", "original_guard_failure_log"),
        "initial_junit": audit.ref(ARCHIVE / "audit_tests.xml", "original_guard_failure_junit"),
        "initial_source_snapshot": audit.ref(ARCHIVE / "audit_source.py", "unchanged_initial_collector"),
        "initial_test_snapshot": audit.ref(ARCHIVE / "audit_tests.py", "unchanged_initial_audit_tests"),
        "all_forensic_and_design_documents_byte_identical": True, "amendment": amendment,
        "R1_runtime_or_fixture_reexecution": False, "R2_implementation": False}
    emit("initial_audit_guard_failure_preservation", preservation)
    sources = [audit.ref(Path(audit.__file__), "unchanged_forensic_collector"),
               audit.ref(audit.TEST, "unchanged_initial_guard_tests"),
               audit.ref(GUARD, "new_audit_guard_V2_tests"), audit.ref(Path(__file__), "new_audit_completion_freezer")]
    emit("audit_source_manifest", {"sources": sources, "R1_source_modification": False,
                                   "initial_guard_failure_preserved": True})
    command = [sys.executable, "-m", "pytest", "-q", "-W", "error", str(GUARD.relative_to(ROOT)),
               "--junitxml=" + str(OUT / "audit_guard_v2_tests.xml")]
    process = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, check=False)
    store.freeze_bytes("audit_guard_v2_tests.txt", (process.stdout + process.stderr).encode())
    print(process.stdout + process.stderr, flush=True)
    counts = test_counts(OUT / "audit_guard_v2_tests.xml")
    comp = subprocess.run([sys.executable, "-m", "compileall", "-q", str(Path(audit.__file__)),
                           str(Path(__file__)), str(GUARD)], cwd=ROOT, capture_output=True, text=True, check=False)
    checks = []
    commands = [["git", "diff", "--check"]] + [
        ["git", "diff", "--no-index", "--check", "/dev/null", str(path)]
        for path in (Path(audit.__file__), audit.TEST, Path(__file__), GUARD)]
    for args in commands:
        check = subprocess.run(args, cwd=ROOT, capture_output=True, text=True, check=False)
        checks.append({"command": args, "exit_code": check.returncode,
                       "diagnostics": check.stdout + check.stderr,
                       "passed": check.returncode in ({0} if len(args) == 3 else {0, 1})
                                 and not check.stdout and not check.stderr})
    after = audit.verify_authority()
    root_check(ARCHIVE, INITIAL_ROOT)
    source_unchanged = all(u.sha(u.read_bytes(ROOT / source["artifact_path"])) == source["sha256"]
                           for source in sources)
    unchanged = u.canonical(before) == u.canonical(after) and source_unchanged
    passed = process.returncode == 0 and counts == {"tests": 29, "failures": 0, "errors": 0, "skipped": 0} \
        and comp.returncode == 0 and all(check["passed"] for check in checks) and unchanged
    emit("historical_preservation_audit", {"frozen_roots_and_source_bindings_unchanged": unchanged,
        "before": audit.ref(OUT / "upstream_root_verification.json", "verified_before_audit"), "after": after,
        "R1_runtime_source_bytes_unchanged": True, "archived_temporaries_not_traversed_or_mutated": True,
        "initial_audit_failure_preserved": audit.ref(OUT / "initial_audit_guard_failure_preservation.json", "append_only_audit_failure"),
        "initial_audit_archive_root_reverified": INITIAL_ROOT, "historical_assets_modified": not unchanged})
    emit("validation", {"passed": passed, "audit_schema_tests_only": True, "audit_guard_version": 2,
        "command": command, "exit_code": process.returncode, **counts,
        "test_output": audit.ref(OUT / "audit_guard_v2_tests.txt", "actual_audit_schema_guard_V2_log"),
        "junit": audit.ref(OUT / "audit_guard_v2_tests.xml", "actual_audit_schema_guard_V2_junit"),
        "initial_guard_failure_preserved": True,
        "compileall": {"exit_code": comp.returncode, "stdout": comp.stdout, "stderr": comp.stderr},
        "whitespace_checks": checks, "R1_runtime_fixtures_executed": 0,
        "original_59_matrix_executed": False, "new_runtime_pass_claims": False,
        "isolated_schema_tests_do_not_validate_actual_runtime_capture": True,
        "all_repository_tests_executed": False, "historical_preservation_verified": unchanged, **audit.NO_CALLS})
    emit("r1_runtime_identity_root_cause_evidence", {"classification": audit.CLASSIFICATION, "detail": audit.DIAGNOSIS,
        "audit_members": [audit.ref(OUT / (stem + ".json"), "forensic_evidence_or_design") for stem in sorted(documents)],
        "source_manifest": audit.ref(OUT / "audit_source_manifest.json", "source_binding"),
        "validation": audit.ref(OUT / "validation.json", "audit_only_validation"),
        "historical_preservation": audit.ref(OUT / "historical_preservation_audit.json", "post_audit_immutability_proof"),
        "initial_guard_failure_preservation": audit.ref(OUT / "initial_audit_guard_failure_preservation.json", "sealed_failure_not_hidden"),
        "runtime_repair_not_implemented_or_rerun": True})
    hashes = {}
    for marker, stem in audit.MARKERS.items():
        hashes[marker] = u.sha(u.read_bytes(OUT / (stem + ".json")))
        store.freeze_bytes(marker, (hashes[marker] + "\n").encode())
    summary = {**old_summary, "status": "completed" if passed else "failed", "audit_test_counts": counts,
        "r2_versioned_repair_design_frozen": passed, "historical_assets_modified": not unchanged,
        "initial_audit_guard_failure_root": INITIAL_ROOT, "initial_audit_guard_failure_preserved": True,
        "initial_audit_guard_failure_counts": old_summary["audit_test_counts"], "audit_guard_version": 2, **hashes}
    emit("summary", summary)
    t.require(all((OUT / (stem + ".json")).is_file() for stem in audit.REQUIRED), "REQUIRED_R11_ARTIFACT_MISSING")
    t.require(all(u.read_bytes(OUT / (stem + ".json")) == originals[stem] for stem in documents),
              "FORENSIC_EVIDENCE_CHANGED_DURING_GUARD_COMPLETION")
    t.require(u.canonical(audit.verify_authority()) == u.canonical(before), "FROZEN_AUTHORITY_DRIFT_BEFORE_SEAL")
    root_check(ARCHIVE, INITIAL_ROOT)
    root = audit.r0.d.master.root_hash(OUT, audit.ROOT_MARKER)
    store.freeze_bytes(audit.ROOT_MARKER, (root + "\n").encode())
    u.sync_directory(OUT)
    root_check(OUT, root)
    return {**summary, audit.ROOT_MARKER: root, "workspace": str(OUT), "required_json_count": len(audit.REQUIRED)}


if __name__ == "__main__":
    with audit.r0.d.master.prior.offline_guard():
        print(json.dumps(complete_audit(), ensure_ascii=False, sort_keys=True))
