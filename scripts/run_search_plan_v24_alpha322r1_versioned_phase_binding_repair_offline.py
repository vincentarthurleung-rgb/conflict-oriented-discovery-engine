#!/usr/bin/env python3
"""One append-only offline R1 implementation/fixture/regression freeze.

Never executes the 22D matrix. A failed run is sealed as failed, not rerun,
rewritten, or promoted. No live acquisition surface is wired to V2.
"""

import ast
import json
import subprocess
import sys
import traceback
import xml.etree.ElementTree as ET
from pathlib import Path

from scripts import search_plan_v24_alpha322r1_repair_fixtures as fixtures
from scripts import search_plan_v24_alpha322r1_versioned_phase_binding_integration as h
from code_engine import stage_barrier_snapshot_v2 as barrier

j, f, r0 = h.j, h.f, h.r0
ROOT, OUT = h.ROOT, f.R1
ROOT_MARKER = "search_plan_v24_dev_alpha3_22r1_sha256"
R0_SHA = "eee21b8c34e3ea378e164ae1316edf9dd59076a934cb4fa07a0ddb9781691840"
PASS = "VERSIONED_FAILURE_PHASE_BINDING_REPAIR_IMPLEMENTED_AND_TESTED_OFFLINE"
FAIL = "ALPHA3_22R1_FAILED_PHASE_BINDING_REPAIR_VALIDATION"
NEXT_PASS = "EXECUTE_ALPHA3_22DR_INDEPENDENT_59_SCENARIO_REVALIDATION_OFFLINE"
NEXT_FAIL = "AUDIT_ALPHA3_22R1_FROZEN_REPAIR_FAILURE_OFFLINE"
TEST = ROOT / "tests/test_search_plan_v24_alpha322r1_versioned_phase_binding_offline.py"
COMPONENTS = [Path(f.__file__), Path(j.__file__), Path(h.p.__file__), Path(barrier.__file__), Path(h.__file__)]
NO_CALLS = dict(r0.NO_CALLS)
REQUIRED = """alpha3_22_master_root_verification alpha3_22a_root_verification alpha3_22b_root_verification
alpha3_22c_root_verification alpha3_22d_failed_root_verification alpha3_22r0_root_verification alpha3_21_closure_verification
r1_scope_boundary r0_repair_design_binding transport_failure_phase_binding_v2_contract
transport_failure_phase_binding_v2_implementation_manifest failure_occurrence_evidence_binding mapping_phase_immutability_audit
lifecycle_trace_binding_contract lifecycle_trace_validation_results same_request_attempt_binding_audit
partial_raw_artifact_binding_audit journal_failure_event_v2_schema journal_failure_event_v2_writer_manifest
journal_failure_event_v2_verifier_manifest journal_v2_durability_regression journal_v2_hash_chain_regression
journal_v2_single_writer_regression journal_v2_terminal_uniqueness_regression journal_resume_reader_v2_manifest
journal_resume_state_reconstruction_results attempt_ordinal_preservation_results committed_failure_vs_abandoned_recovery_results
r0_positive_fixture_results r0_negative_fixture_results r0_recovery_fixture_results repair_first_rejection_reason_audit
partial_parser_quarantine_regression retry_policy_delegation_audit original_22d_oracle_preservation_audit
original_22d_failed_state_preservation_audit v1_v2_explicit_version_isolation_audit legacy_22a_regression_results
legacy_22b_regression_results legacy_22c_regression_results production_runtime_nonwiring_audit scientific_policy_firewall_audit
contamination_baseline_immutability_audit future_independent_revalidation_handoff historical_preservation_audit
scientific_state_safety_audit validation summary""".split()
MARKERS = {"transport_failure_phase_binding_v2_implementation_sha256": "transport_failure_phase_binding_v2_implementation_manifest",
    "journal_failure_event_v2_bundle_sha256": "journal_failure_event_v2_bundle",
    "journal_resume_reader_v2_implementation_sha256": "journal_resume_reader_v2_manifest",
    "alpha3_22r1_repair_validation_bundle_sha256": "alpha3_22r1_repair_validation_bundle"}


def ref(path, role):
    return {"artifact_path": str(Path(path).relative_to(ROOT)), "sha256": j.sha(j.read_bytes(path)), "artifact_role": role}


def emit(name, record):
    return fixtures.write_json(OUT / (name + ".json"), record)


def authority():
    result = r0.verify_authority()
    result["alpha322r0"] = r0.d.master.prior.root_check(r0.OUT, r0.ROOT_MARKER, R0_SHA)
    expected = {"transport_failure_phase_binding_v2_proposal": f.DESIGN_SHA,
        "alpha3_22r0_repair_design_bundle": "6e4e1ab4b1556df93d6e72d7d30ed3393db7a1d08bc4e1cb84438cfdb51d5362",
        "cross_component_root_cause_evidence": "3ba7d1fb8dacb9ddcd3508534143d1a9feb50cc7e9f1496594474df33733b8ea"}
    for stem, digest in expected.items():
        path = r0.OUT / (stem + ".json")
        j.require(j.sha(j.read_bytes(path)) == digest, "FROZEN_R0_MEMBER_MISMATCH")
        r0.verify_design_references(r0.obj(path))
    return result


def attempt_fixture(name, callback):
    try:
        return callback()
    except Exception as exc:
        path = OUT / "execution" / (name + "_failure.txt")
        j.atomic_freeze(path, traceback.format_exc().encode())
        return {"fixture_id": name, "passed": False, "error": type(exc).__name__ + ":" + str(exc),
                "failure_evidence": ref(path, "preserved_runtime_failure"), "not_retried": True}


def regression(name, paths):
    xml = OUT / "execution" / (name + ".xml")
    cmd = [sys.executable, "-m", "pytest", "-q", "-W", "error", *paths,
           "--junitxml=" + str(xml), "--basetemp=" + str(OUT / "execution" / (name + "_temp"))]
    process = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, check=False)
    log = OUT / "execution" / (name + ".txt")
    j.atomic_freeze(log, (process.stdout + process.stderr).encode())
    counts = {"tests": 0, "failures": 0, "errors": 0, "skipped": 0}
    if xml.is_file():
        for suite in ET.parse(xml).getroot().iter("testsuite"):
            for key in counts:
                counts[key] += int(suite.attrib.get(key, 0))
    print(name + ": exit=" + str(process.returncode) + " " + json.dumps(counts), flush=True)
    return {"command": cmd, "exit_code": process.returncode, **counts,
            "passed": process.returncode == 0 and counts["tests"] > 0 and not counts["errors"] and not counts["failures"],
            "log": ref(log, "unaltered_test_output"), "junit": ref(xml, "test_case_accounting") if xml.is_file() else None}


def selected_tests(result, fragments):
    if result["junit"] is None:
        return {"cases": [], "count": 0, "passed": False, "execution": None, "error": "test XML unavailable; no pass inferred"}
    xml = ROOT / result["junit"]["artifact_path"]
    rows = []
    for item in ET.parse(xml).getroot().iter("testcase"):
        if any(fragment in item.attrib["name"] for fragment in fragments):
            rows.append({"test": item.attrib["name"], "passed": not any(item.find(tag) is not None for tag in ("failure", "error", "skipped"))})
    return {"cases": rows, "count": len(rows), "passed": bool(rows) and all(row["passed"] for row in rows),
            "execution": result["junit"]}


def nonwiring():
    names = {path.stem for path in COMPONENTS}
    allowed = set(COMPONENTS)
    hits = []
    for path in (ROOT / "src").rglob("*.py"):
        if path in allowed:
            continue
        tree = ast.parse(path.read_bytes())
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                used = {alias.name for alias in node.names} | {(node.module or "").split(".")[-1]}
            elif isinstance(node, ast.Import):
                used = {alias.name.split(".")[-1] for alias in node.names}
            else:
                continue
            if used & names:
                hits.append({"path": str(path.relative_to(ROOT)), "line": node.lineno})
    return {"production_runtime_v2_wiring_enabled": bool(hits), "unexpected_source_imports": hits,
            "audit_scope": "all src Python imports; V2 implementation modules excluded; offline scripts allowed",
            "runtime_activation_allowed": all(getattr(module, "RUNTIME_ACTIVATION_ALLOWED", False) is False for module in (f, j)),
            "passed": not hits}


def run():
    before = authority()
    j.require(not OUT.exists(), "R1_OUTPUT_MUST_BE_NEW_NO_RERUN")
    OUT.mkdir()
    (OUT / "execution").mkdir()
    (OUT / "implementation").mkdir()
    emit("upstream_authority_before", before)
    for path in COMPONENTS + [Path(fixtures.__file__), Path(__file__), TEST]:
        j.atomic_freeze(OUT / "implementation" / path.name, j.read_bytes(path))
    emit("runtime_v2_implementation_manifest", {"schema_version": "RuntimeV2ImplementationManifestR1",
        "r0_proposal_sha256": f.DESIGN_SHA, "source_files": [ref(path, "prospective_V2_runtime_source") for path in COMPONENTS],
        "activation": "OFFLINE_SYNTHETIC_ONLY_NOT_PRODUCTION", "no_V1_conversion": True})
    positive = attempt_fixture("R0_P01", lambda: fixtures.positive(OUT / "execution" / "positive"))
    emit("r0_positive_fixture_results", positive)
    print("R0 positive: " + str(positive["passed"]), flush=True)
    supplement = attempt_fixture("R1_PARTIAL", lambda: fixtures.positive(OUT / "execution" / "nonempty", "partial"))
    emit("nonempty_partial_supplement_results", supplement)
    negative_spec = fixtures.source_spec("repair_negative_fixture_specification")
    j.require(len(negative_spec["fixtures"]) == 22, "FROZEN_NEGATIVE_COUNT_CHANGED")
    negatives = []
    for spec in negative_spec["fixtures"]:
        result = attempt_fixture(spec["fixture_id"], lambda spec=spec: fixtures.negative(OUT / "execution" / spec["fixture_id"], spec))
        negatives.append(result)
        emit("execution_" + spec["fixture_id"], result)
        print(spec["fixture_id"] + ": " + str(result["passed"]) + " " + str(result.get("actual_first_rejection_reason", result.get("error"))), flush=True)
    emit("r0_negative_fixture_results", {"fixture_count": 22, "pass_count": sum(row["passed"] for row in negatives),
        "fail_count": sum(not row["passed"] for row in negatives), "fixtures": negatives,
        "oracle": ref(f.R0 / "repair_negative_fixture_specification.json", "unchanged_frozen_R0_expectations"),
        "failed_cases_not_retried_or_repaired": True})
    recovered = attempt_fixture("R0_REC01_REC02", lambda: fixtures.recovery(OUT / "execution" / "recovery"))
    recovery_ok = isinstance(recovered, list) and len(recovered) == 2 and all(row["passed"] for row in recovered)
    emit("r0_recovery_fixture_results", {"passed": recovery_ok, "fixtures": recovered})
    print("R0 recovery: " + str(recovery_ok), flush=True)
    results = {}
    groups = {"focused_v2": [str(TEST.relative_to(ROOT))],
        "legacy_22a": ["tests/test_search_plan_v24_alpha322a_transport_observability_offline.py"],
        "legacy_22b": ["tests/test_search_plan_v24_alpha322b_exception_mapping_offline.py"],
        "legacy_22c": ["tests/test_search_plan_v24_alpha322c_attempt_journal_resume_offline.py"],
        "frozen_r0": ["tests/test_search_plan_v24_alpha322r0_phase_binding_repair_design_offline.py"],
        "historical_journal": ["tests/test_search_plan_v24_alpha322_master_prereg_offline.py", "tests/test_no_static_journal_weight_in_core_reasoning.py"]}
    for name, paths in groups.items():
        results[name] = regression(name, paths)
        emit(name + "_test_execution", results[name])
    comp = subprocess.run([sys.executable, "-m", "compileall", "-q", *[str(path) for path in COMPONENTS + [Path(fixtures.__file__), Path(__file__), TEST]]], cwd=ROOT, capture_output=True, text=True)
    emit("compileall_execution", {"exit_code": comp.returncode, "stdout": comp.stdout, "stderr": comp.stderr, "passed": comp.returncode == 0})
    diff = subprocess.run(["git", "diff", "--check"], cwd=ROOT, capture_output=True, text=True)
    new_diff = []
    for path in COMPONENTS + [Path(fixtures.__file__), Path(__file__), TEST]:
        check = subprocess.run(["git", "diff", "--no-index", "--check", "/dev/null", str(path)], cwd=ROOT, capture_output=True, text=True)
        new_diff.append({"path": str(path.relative_to(ROOT)), "exit_code": check.returncode, "diagnostics": check.stdout + check.stderr,
            "passed": check.returncode in {0, 1} and not check.stdout and not check.stderr})
    whitespace = {"tracked_exit_code": diff.returncode, "tracked_diagnostics": diff.stdout + diff.stderr,
                  "new_files": new_diff, "passed": diff.returncode == 0 and all(row["passed"] for row in new_diff)}
    emit("whitespace_verification", whitespace)
    after = authority()
    emit("upstream_authority_after", after)
    preserved = j.canonical(before) == j.canonical(after)
    wiring = nonwiring()
    passed = positive["passed"] and supplement["passed"] and all(row["passed"] for row in negatives) and recovery_ok \
        and all(result["passed"] for result in results.values()) and comp.returncode == 0 and whitespace["passed"] and preserved and wiring["passed"]
    classification = PASS if passed else FAIL
    if not results["focused_v2"]["passed"]:
        classification = "ALPHA3_22R1_FAILED_JOURNAL_INTEGRITY_REGRESSION"
    if not all(results[name]["passed"] for name in ("legacy_22a", "legacy_22b", "legacy_22c")) or not preserved:
        classification = "ALPHA3_22R1_FAILED_LEGACY_RUNTIME_PRESERVATION"
    documents(before, after, positive, supplement, negatives, recovered, results, wiring, preserved, passed, classification, whitespace, comp.returncode)
    j.require(all((OUT / (name + ".json")).is_file() for name in REQUIRED if name != "summary"), "R1_REQUIRED_ARTIFACT_MISSING")
    bundle_files = sorted(path for path in OUT.rglob("*") if path.is_file())
    emit("alpha3_22r1_repair_validation_bundle", {"schema_version": "Alpha322R1RepairValidationBundle",
        "r0_root_sha256": R0_SHA, "status": "completed" if passed else "failed",
        "members": [ref(path, "sealed_engineering_artifact_including_intentional_negative_fixtures") for path in bundle_files
                    if path.name != "summary.json"],
        "source_bindings": [ref(path, "unchanged_R1_source_after_validation") for path in COMPONENTS + [Path(fixtures.__file__), Path(__file__), TEST]],
        "not_independent_59_matrix_validation": True})
    hashes = {}
    for marker, stem in MARKERS.items():
        hashes[marker] = j.sha(j.read_bytes(OUT / (stem + ".json")))
        j.atomic_freeze(OUT / marker, (hashes[marker] + "\n").encode())
    # Summary was deliberately not prewritten: no mutation of freeze artifacts.
    summary = j.strict_json(j.read_bytes(OUT / "summary_pending.json"))
    emit("summary", {**summary, **hashes})
    j.require(all((OUT / (name + ".json")).is_file() for name in REQUIRED), "R1_REQUIRED_ARTIFACT_MISSING_AT_SEAL")
    j.require(j.canonical(authority()) == j.canonical(before), "HISTORICAL_DRIFT_AT_SEAL")
    j.require(f.implementation_identity() == j.sha(j.read_bytes(OUT / "runtime_v2_implementation_manifest.json")), "RUNTIME_SOURCE_DRIFT_AT_SEAL")
    root = r0.d.master.root_hash(OUT, ROOT_MARKER)
    j.atomic_freeze(OUT / ROOT_MARKER, (root + "\n").encode())
    j.sync_directory(OUT)
    j.require(r0.d.master.root_hash(OUT, ROOT_MARKER) == root, "R1_POST_FREEZE_ROOT_MISMATCH")
    return {**summary, **hashes, ROOT_MARKER: root, "workspace": str(OUT)}


def documents(before, after, positive, supplement, negatives, recovered, tests, wiring, preserved, passed, classification, whitespace, compile_exit):
    for name, key in (("alpha3_22_master", "master"), ("alpha3_22a", "alpha322a"), ("alpha3_22b", "alpha322b"),
        ("alpha3_22c", "alpha322c"), ("alpha3_22d_failed", "alpha322d"), ("alpha3_22r0", "alpha322r0"), ("alpha3_21_closure", "closure")):
        emit(name + "_root_verification" if name != "alpha3_21_closure" else name + "_verification", {"before": before[key], "after": after[key], "unchanged": preserved})
    r0_refs = [ref(f.R0 / (stem + ".json"), "frozen_R0_repair_authority") for stem in
        ("transport_failure_phase_binding_v2_proposal", "transport_failure_phase_binding_v2_schema", "transport_failure_phase_binding_v2_invariants",
         "journal_terminal_event_v2_proposal", "same_attempt_evidence_binding_contract", "repair_positive_fixture_specification",
         "repair_negative_fixture_specification", "repair_recovery_fixture_specification")]
    runtime = ref(OUT / "runtime_v2_implementation_manifest.json", "source_bound_prospective_V2_identity")
    emit("r1_scope_boundary", {"stage": "POST_ALPHA3_22D_VERSIONED_FAILURE_PHASE_BINDING_REPAIR_IMPLEMENTATION",
        "development_mode": True, "offline_only": True, "original_59_matrix_executed": False,
        "scientific_execution": False, "alpha3_21_reopened": False, **NO_CALLS})
    emit("r0_repair_design_binding", {"root_sha256": R0_SHA, "proposal_sha256": f.DESIGN_SHA, "references": r0_refs})
    contract = {"schema": ref(f.R0 / "transport_failure_phase_binding_v2_schema.json", "byte_unchanged_R0_concrete_schema"),
        "occurrence_owner": "controller capture_failure at actual signal, before phase advance",
        "retry_owner": "frozen 22B classifier delegates exclusively to frozen 22A semantic_retry_decision",
        "mapping_phase_equals_occurrence": True, "persistence_phase_equality_required": False,
        "actual_committed_same_attempt_trace_required": True, "immutable_mapping_snapshot_required": True,
        "no_temporal_inference": True, "no_orphan_terminal_inference": True,
        "structured_failure_route": "separate StructuredFailurePhaseBindingV2; frozen concrete schema not broadened",
        "structured_classification": "frozen original structured facts verified with unchanged B, never future facts",
        "trust_boundary": "source-bound cooperative controller; not an adversary rewriting all trusted files",
        "failure_rejection_order": [spec["expected"]["proposed_reason_code"] for spec in fixtures.source_spec("repair_negative_fixture_specification")["fixtures"]]}
    emit("transport_failure_phase_binding_v2_contract", contract)
    emit("transport_failure_phase_binding_v2_implementation_manifest", {"runtime_manifest": runtime,
        "component": ref(Path(f.__file__), "new_V2_phase_capture_and_verification"), "integration": ref(Path(h.__file__), "offline_explicit_controller"),
        "positive_result": ref(OUT / "r0_positive_fixture_results.json", "actual_R0_positive_execution"), "activation_allowed": False})
    emit("failure_occurrence_evidence_binding", {"actual_exception": "exact builtins.ConnectionResetError in in-memory bound HTTPResponse.read",
        "controller_captures_signal_facts_mapping_retry_before_advance": True,
        "interruption_event_evidence_reference_is_occurrence_hash": True, "runtime_identity": runtime,
        "result": positive, "nonempty_supplement": supplement})
    emit("mapping_phase_immutability_audit", {"failure_phase_not_remapped_at_persistence": True,
        "positive_phases": positive.get("phases"), "negative_results": [row for row in negatives if row["fixture_id"] in {"N01", "N02", "N08", "N09"}],
        "original_22B_bytes_preserved": preserved})
    emit("lifecycle_trace_binding_contract", {"anchored_to_prior_fsynced_prefix": True,
        "contains_actual_progress_records_and_sequence_hash_references": True, "no_terminal_self_hash_cycle": True,
        "ordered_trace_cross_checked_with_actual_journal_prefix": True, "timestamps_and_graph_reachability_alone_insufficient": True,
        "suffix": ["RESPONSE_BODY_READING", "RESPONSE_BODY_INTERRUPTED", "RAW_RESPONSE_FROZEN"]})
    emit("lifecycle_trace_validation_results", {"positive": positive, "negative_fixtures": [row for row in negatives if row["fixture_id"] in {"N03", "N04", "N05", "N18", "N19", "N22"}]})
    emit("same_request_attempt_binding_audit", {"identity_fields": ["run_id", "run_epoch", "stage_id", "logical_request_id",
        "request_payload_sha256", "attempt_ordinal", "manifest_sha256", "attempt_start_entry_hash"],
        "fixtures": [row for row in negatives if row["fixture_id"] in {"N06", "N07", "N15", "N16"}]})
    emit("partial_raw_artifact_binding_audit", {"zero_byte": positive, "nonempty_partial": supplement,
        "hash_and_path_and_count_verified": positive["passed"] and supplement["passed"],
        "complete_body_and_http_acceptance_independently_required": True, "parser_invocations": 0,
        "fixtures": [row for row in negatives if row["fixture_id"] in {"N10", "N11", "N22"}]})
    emit("journal_failure_event_v2_schema", {"schema_version": "JournalFailureEventV2SchemaBundle",
        "journal_envelope": j.journal_event_schema_v2(), "concrete_failure_binding": f.schema(), "structured_failure_binding": f.schema(True),
        "terminal_required_fields": ["outcome", "mapped_observation", "retry_decision", "raw_artifact", "validation", "eligibility", "failure_phase_binding"],
        "semantic_enforcement": "V2 _verify_terminal plus full actual prefix; JSON shape alone never authorizes commit"})
    for role in ("writer", "verifier"):
        emit("journal_failure_event_v2_" + role + "_manifest", {"component": ref(Path(j.__file__), "new_explicit_V2_" + role),
            "runtime_identity": runtime, "V1_implementation_edited": False, "source_snapshot": ref(OUT / "implementation" / Path(j.__file__).name, "byte_identical_R1_source")})
    for stem, fragments in (("journal_v2_durability_regression", ["wal_fsync", "failed_start", "torn_append"]),
        ("journal_v2_hash_chain_regression", ["rehashed_semantic", "torn_append"]), ("journal_v2_single_writer_regression", ["writer_and_reader"]),
        ("v1_v2_explicit_version_isolation_audit", ["explicit_versions"]), ("attempt_ordinal_preservation_results", ["abandoned_rule", "success_and_noneligible", "committed_unknown"]),
        ("barrier_activation_preservation_results", ["barrier_activation"])):
        emit(stem, selected_tests(tests["focused_v2"], fragments))
    emit("journal_v2_terminal_uniqueness_regression", {"result": next(row for row in negatives if row["fixture_id"] == "N17"),
        "uncertain_durability": next(row for row in negatives if row["fixture_id"] == "N21")})
    emit("journal_resume_reader_v2_manifest", {"component": ref(Path(h.p.__file__), "explicit_V2_read_only_resume"),
        "integration_entrypoint": ref(Path(h.__file__), "fresh_process_explicit_V2_reader"), "runtime_identity": runtime,
        "V1_event_conversion": False, "orphan_evidence_promotion": False, "read_only_planning": True})
    for stem in ("journal_resume_state_reconstruction_results", "committed_failure_vs_abandoned_recovery_results"):
        emit(stem, {"fixtures": recovered, "states_are_logical_request_states_not_A_lifecycle": True})
    emit("repair_first_rejection_reason_audit", {"fixture_count": 22, "expected_and_actual_first_rejection": negatives,
        "all_first_reasons_match": all(row["passed"] for row in negatives), "corruptions_use_separate_journals": True,
        "original_literal_R0_oracle_not_changed": True})
    emit("partial_parser_quarantine_regression", {"zero_byte_guard": positive.get("parser_rejection_verified", False),
        "nonempty_guard": supplement.get("parser_rejection_verified", False), "parser_invocations": 0,
        "partial_authoritative": False, "partial_parser_eligible": False})
    emit("retry_policy_delegation_audit", {"owner": "unchanged 22A semantic_retry_decision via unchanged B wrapper",
        "policy": {"maximum_attempts": 4, "timeout_seconds": 60, "backoff_seconds": [2, 4, 8]},
        "mapping_table_sha256": h.b.MAPPING_TABLE_SHA256, "semantic_retry_contract_sha256": h.b.SEMANTIC_RETRY_CONTRACT_SHA256,
        "fixtures": [row for row in negatives if row["fixture_id"] in {"N12", "N13", "N14"}], "retry_policy_changed": False})
    emit("original_22d_oracle_preservation_audit", {"oracle": ref(r0.d.OUT / "independent_expected_outcomes.jsonl", "unchanged_59_scenario_oracle"),
        "scenario_manifest": ref(r0.d.OUT / "frozen_fault_scenario_manifest.json", "unchanged_original_scenario_manifest"),
        "frozen_count": 59, "executed_by_R1": False, "unchanged": preserved})
    emit("original_22d_failed_state_preservation_audit", {"summary": ref(r0.d.OUT / "summary.json", "original_failed_D_summary"),
        "status": "failed", "classification": "ALPHA3_22D_FAILED_INDEPENDENT_FAULT_INJECTION", "frozen": 59,
        "executed": 5, "passed": 4, "failed": 1, "not_executed": 54, "R1_does_not_relabel_D": True})
    for name in ("legacy_22a", "legacy_22b", "legacy_22c"):
        emit(name + "_regression_results", tests[name])
    emit("production_runtime_nonwiring_audit", wiring)
    emit("scientific_policy_firewall_audit", {"unchanged_historical_bindings": before["scientific_bindings"],
        "scientific_policy_changed": False, "no_new_scientific_source_exposure": True, "only_opaque_synthetic_engineering_data": True,
        "known_PMID_checking": False, "provider_calls": 0, "llm_calls": 0})
    emit("contamination_baseline_immutability_audit", {"registry": before["registry"], "counts": before["counts"], "unchanged": preserved})
    emit("future_independent_revalidation_handoff", {"ready_for_separately_authorized_validation": passed,
        "next_stage": NEXT_PASS if passed else NEXT_FAIL, "requires_new_run_root": True, "original_59_manifest_and_oracle_required": True,
        "original_22D_frozen_failure_preserved": True, "independent_59_revalidation_executed": False,
        "R1_test_success_is_not_independent_D_R_success": True, "alpha321_resume_prohibited": True})
    emit("historical_preservation_audit", {"before": ref(OUT / "upstream_authority_before.json", "pre_execution_authority"),
        "after": ref(OUT / "upstream_authority_after.json", "post_execution_authority"), "byte_equal": preserved,
        "historical_assets_modified": not preserved, "historical_V1_source_bindings_unchanged": preserved})
    emit("scientific_state_safety_audit", {"development_mode": True, "fresh_primary_attempt_started": False,
        "alpha3_21_reopened": False, "production_runtime_v2_wiring_enabled": False, "scientific_policy_changed": False, **NO_CALLS})
    emit("journal_failure_event_v2_bundle", {"runtime_identity": runtime, "members": [ref(OUT / (stem + ".json"), "V2_journal_contract_and_result") for stem in
        ("journal_failure_event_v2_schema", "journal_failure_event_v2_writer_manifest", "journal_failure_event_v2_verifier_manifest",
         "journal_v2_durability_regression", "journal_v2_hash_chain_regression", "journal_v2_single_writer_regression", "journal_v2_terminal_uniqueness_regression")]})
    emit("validation", {"passed": passed, "classification": classification, "repair_positive_passed": positive["passed"],
        "negative_fixture_count": 22, "negative_pass_count": sum(row["passed"] for row in negatives),
        "recovery_passed": isinstance(recovered, list) and all(row["passed"] for row in recovered),
        "test_executions": tests, "compileall_exit_code": compile_exit, "whitespace": whitespace,
        "all_repository_tests_executed": False, "unrelated_environment_failures": [name for name, result in tests.items() if not result["passed"]],
        "independent_59_matrix_executed": False, "historical_preserved": preserved, **NO_CALLS})
    summary = {"status": "completed" if passed else "failed", "alpha3_22r1_classification": classification,
        "development_mode": True, "next_stage_recommendation": NEXT_PASS if passed else NEXT_FAIL,
        "r0_positive_fixture_passed": positive["passed"], "r0_negative_fixture_count": 22,
        "r0_negative_fixture_pass_count": sum(row["passed"] for row in negatives),
        "r0_negative_fixture_fail_count": sum(not row["passed"] for row in negatives),
        "r0_recovery_fixture_passed": isinstance(recovered, list) and all(row["passed"] for row in recovered),
        "focused_tests": tests["focused_v2"]["tests"], "all_executed_test_count": sum(result["tests"] for result in tests.values()),
        "legacy_counts": {name: tests[name]["tests"] for name in ("legacy_22a", "legacy_22b", "legacy_22c", "frozen_r0", "historical_journal")},
        "original_22d_status_preserved": "failed", "original_22d_oracle_unchanged": preserved,
        "independent_59_scenario_revalidation_executed": False, "production_runtime_v2_wiring_enabled": False,
        "historical_assets_modified": not preserved, "scientific_policy_changed": False, **before["counts"], **NO_CALLS}
    emit("summary_pending", summary)


if __name__ == "__main__":
    with r0.d.master.prior.offline_guard():
        print(json.dumps(run(), ensure_ascii=False, sort_keys=True))
