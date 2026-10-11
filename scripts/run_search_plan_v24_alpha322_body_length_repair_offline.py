"""Offline development repair accounting; never an independent release gate."""

import argparse
import ast
import json
import subprocess
import sys
from pathlib import Path

from scripts import run_search_plan_v24_alpha322_t12_full_development_diagnostic_offline as previous
from scripts import search_plan_v24_alpha322_length_bound_harness_v1 as h
from scripts import search_plan_v24_alpha322_length_bound_r2_fixtures_v1 as r0
from scripts import search_plan_v24_alpha322_length_bound_ri_fixtures_v1 as ri
from scripts import search_plan_v24_alpha322_length_bound_t11_fixtures_v1 as vf
from scripts import search_plan_v24_alpha322_length_representation_fixtures_v1 as lf

j, t, ROOT = h.j, h.t, h.ROOT
OUT = ROOT / "runs/20261010_search_plan_v24_dev_alpha3_22_body_length_representation_journal_repair_offline"
MARKER = "search_plan_v24_dev_alpha3_22_body_length_repair_sha256"
DIAGNOSTIC_SHA = "fc809fd311fbe4861c5baf189dcb3de277cfa824a3f3c6695b5480cbd97f234d"
TEST = ROOT / "tests/test_search_plan_v24_alpha322_length_representation_repair_offline.py"
COMPONENTS = [ROOT / ("src/code_engine/" + name + ".py") for name in (
    "body_length_verification_v1", "append_only_attempt_journal_v2_length_bound_v1",
    "deterministic_resume_planner_v2_length_bound_v1", "stage_barrier_snapshot_v2_length_bound_v1",
    "validator_outcome_adapter_length_bound_v1")]
SOURCES = COMPONENTS + [Path(module.__file__) for module in (h, r0, ri, vf, lf, vf.h, r0.h)] + [Path(__file__), TEST]
NO_CALLS = dict(previous.NO_CALLS)
REQUIRED = "summary validation source_manifest body_length_contract_binding t12_t17_t18_focused_results length_representation_negative_tests regression_results historical_preservation".split()


def emit(name, value, directory=OUT):
    return j.atomic_freeze(directory / (name + ".json"), j.canonical(value))


def load(name):
    return j.strict_json(j.read_bytes(OUT / (name + ".json")))


def authority():
    release = previous.d.release
    result = release.development.authority()
    for name, directory, marker, digest in (
            ("latest_T11",release.development.OUT,release.development.MARKER,release.DEVELOPMENT_SHA),
            ("failed_DR2",release.OUT,release.MARKER,previous.d.RELEASE_SHA)):
        result[name] = release.master.prior.root_check(directory,marker,digest)
    for directory, records in (
            (release.development.OUT,j.strict_json(j.read_bytes(release.development.OUT / "source_manifest.json"))["sources"]),
            (release.OUT,j.strict_json(j.read_bytes(release.OUT / "runtime_component_binding.json"))["new_validation_sources"])):
        for source in records:
            raw = j.read_bytes(ROOT / source["artifact_path"])
            t.require(j.sha(raw) == source["sha256"] and raw == j.read_bytes(directory / "implementation" / Path(source["artifact_path"]).name),"FROZEN_SOURCE_DRIFT")
    t.require(j.sha(j.read_bytes(previous.d.ADDENDUM)) == previous.d.ADDENDUM_SHA,"REPORTING_ADDENDUM_DRIFT")
    result["unchanged_reporting_addendum"] = h.ref(previous.d.ADDENDUM,"unchanged_historical_reporting_addendum")
    previous.sources_unchanged()
    result["latest_development_diagnostic"] = previous.d.release.master.prior.root_check(previous.OUT, previous.MARKER, DIAGNOSTIC_SHA)
    result["nonwiring"] = nonwiring()
    t.require(result["nonwiring"]["passed"],"PRODUCTION_WIRING_FORBIDDEN")
    return result


def prepare():
    before = authority()
    t.require(not OUT.exists(), "NEW_DEVELOPMENT_DIRECTORY_REQUIRED")
    OUT.mkdir()
    (OUT / "execution").mkdir()
    emit("upstream_root_verification", before)
    emit("preparation_failures_preserved", {"failures":[
        {"operation":"initial prepare", "actual_rejection":"PRODUCTION_WIRING_FORBIDDEN",
         "cause":"historical nonwiring scanner has a closed allowlist and sees the newly authorized unwired versioned ports",
         "correction":"new scanner explicitly includes new ports; all historical hashes and sources still independently checked"},
        {"operation":"iteration before successful prepare", "actual_rejection":"FileNotFoundError",
         "cause":"new workspace had not been created after initial prepare rejection", "tests_executed":0}],
        "historical_scanners_modified":False,"runtime_or_scientific_policy_modified":False})
    emit("body_length_contract_binding", {
        "mode": "OFFLINE_DEVELOPMENT_NOT_INDEPENDENT_RELEASE_VALIDATION",
        "original_22A": h.ref(Path(t.__file__), "unchanged_frozen_body_completion_and_length_semantics"),
        "original_http_schema": h.ref(ROOT / "runs/20261008_search_plan_v24_dev_alpha3_22a_transport_state_observability_implementation_offline/http_response_provenance_v1_schema.json", "unchanged_frozen_schema"),
        "master_body_contract": h.ref(previous.d.release.master.OUT / "response_body_completion_semantics.json", "same_representation_authority"),
        "original_journal": h.ref(Path(previous.h.j.__file__), "historical_unconditional_raw_length_comparison"),
        "original_validator_adapter": h.ref(Path(previous.h.integration.validity.__file__), "same_comparison_on_validator_outcome_path"),
        "T12": {"read_returned_normally":False, "trusted_Content_Length":50, "recoverable_partial_bytes":0,
            "recovered_partial_bytes_are_not_completed_response_length":True,
            "actual_representation":"wire", "expected_representation":"wire",
            "frozen_22A_length_available_does_not_require_normal_return":True,
            "verified_22A_result":"MISMATCH", "original_oracle":"UNAVAILABLE",
            "classification":"FROZEN_SCENARIO_OR_ORACLE_CONFLICT", "no_rule_change_authorized":True,
            "header_preserved":True, "semantic_failure":"UNKNOWN_RUNTIME_FAILURE", "automatic_retry":False},
        "T17_T18": {"earliest_defect":"journal terminal verification, not frozen 22A completion",
            "replacement":"representation bound equality, request frozen before dispatch",
            "wire_count_not_reconstructed_from_transformed_count":True,
            "content_encoding_transfer_decoding_and_decompression_not_equated":True},
        "unchanged_checks":["request identity", "attempt ordinal", "raw hash and path", "body completion", "framing",
            "validator authority and result", "terminal uniqueness", "hash chain", "append/fsync ordering", "resume/retry policy"],
        "runtime_retry_policy_changed":False, "exception_mapping_table_changed":False, "scientific_policy_changed":False, **NO_CALLS})
    return {"workspace":str(OUT), "prepared":True}


def iteration():
    index = len(list((OUT / "execution").glob("development_iteration_*"))) + 1
    directory = OUT / "execution" / ("development_iteration_%02d" % index)
    directory.mkdir()
    sources = []
    for path in SOURCES:
        source = h.ref(path, "development_iteration_source")
        sources.append(source)
        j.atomic_freeze(directory / path.name, j.read_bytes(path))
    emit("source_manifest", {"sources":sources}, directory)
    result = run_pytest("focused", [TEST], directory)
    emit("execution_record", result, directory)
    return result


def run_pytest(name, paths, directory):
    import tempfile
    import xml.etree.ElementTree as ET
    xml = directory / (name + ".xml")
    temporary = Path(tempfile.mkdtemp(prefix="alpha322-length-")) / "pytest"
    wrapper = ("import sys,pytest; from scripts import run_search_plan_v24_alpha322_master_prereg_offline as m; "
               "ctx=m.prior.offline_guard();ctx.__enter__();sys.exit(pytest.main(sys.argv[1:]))")
    command = [sys.executable, "-c", wrapper, "-q", "-W", "error", *map(str, paths),
               "--junitxml=" + str(xml), "--basetemp=" + str(temporary)]
    process = subprocess.run(command, cwd=ROOT, capture_output=True, text=True)
    log = directory / (name + ".txt")
    j.atomic_freeze(log, (process.stdout + process.stderr).encode())
    counts = dict.fromkeys(("tests", "failures", "errors", "skipped"), 0)
    if xml.exists():
        for suite in ET.parse(xml).getroot().iter("testsuite"):
            for key in counts:
                counts[key] += int(suite.attrib.get(key, 0))
    value = {"command":command, "exit_code":process.returncode, **counts,
        "passed":process.returncode == 0 and counts["tests"] > 0 and not any(counts[k] for k in ("failures","errors","skipped")),
        "log":h.ref(log,"unaltered_actual_test_output"), "junit":h.ref(xml,"actual_test_counts") if xml.exists() else None,
        "pytest_temporary_directory_outside_freeze":str(temporary), "fresh_process_offline_guard":True}
    print(name + ': ' + json.dumps({key:value[key] for key in ("tests","failures","errors","passed")}), flush=True)
    return value


def sources_unchanged():
    value = load("source_manifest")
    for item in value["sources"]:
        raw = j.read_bytes(ROOT / item["artifact_path"])
        t.require(j.sha(raw) == item["sha256"] and raw == j.read_bytes(OUT / "implementation" / Path(item["artifact_path"]).name), "DEVELOPMENT_SOURCE_DRIFT")
    return value


def nonwiring():
    allowed = set(COMPONENTS + previous.d.release.development.COMPONENTS + previous.d.release.r2.COMPONENTS)
    names = {path.stem for path in allowed}
    unexpected = []
    for path in (ROOT / "src").rglob("*.py"):
        if path in allowed:
            continue
        for node in ast.walk(ast.parse(j.read_bytes(path))):
            used = {a.name.split(".")[-1] for a in node.names} if isinstance(node, ast.Import) else (
                {a.name for a in node.names} | {(node.module or "").split(".")[-1]} if isinstance(node, ast.ImportFrom) else set())
            if used & names:
                unexpected.append({"artifact_path":str(path.relative_to(ROOT)), "line":node.lineno})
    return {"passed":not unexpected, "unexpected_imports":unexpected, "production_runtime_v2_wiring_enabled":bool(unexpected)}


def focused():
    t.require(j.canonical(authority()) == j.canonical(load("upstream_root_verification")), "UPSTREAM_ROOT_DRIFT")
    (OUT / "implementation").mkdir()
    for path in SOURCES:
        j.atomic_freeze(OUT / "implementation" / path.name, j.read_bytes(path))
    emit("source_manifest", {"sources":[h.ref(path,"new_unwired_versioned_length_bound_development_source") for path in SOURCES],
        "new_journal_authority":j.AUTHORITY, "functional_change":"one shared representation-bound verifier on both terminal paths",
        "mechanical_ports":"journal append/reducer, planner, stage snapshots, validator result and existing offline fixtures",
        "nonwiring":nonwiring(), "frozen_runtime_sources_modified":False})
    specs, expected = previous.d.release.prior.frozen_inputs()
    rows = {}
    for key in ("T12","T17","T18","T05","T11"):
        scenario = next(row for row in specs["scenarios"] if row["scenario_id"] == key)
        row = h.transport_scenario(scenario, OUT / "execution" / key)
        mismatches = h.compare(expected[key],row["actual"])
        row.update(expected=expected[key], mismatches=mismatches, passed=not mismatches and row["durable_terminal_error"] is None)
        rows[key] = row
        print(key + ': ' + ('PASS' if row["passed"] else 'FAIL'), flush=True)
    emit("t12_t17_t18_focused_results", {"scenarios":rows, "original_oracle_unchanged":True,
        "T12_conflict_preserved":not rows["T12"]["passed"], "no_header_trust_or_fault_changes":True})
    length_rows = [lf.execute(key, OUT / "execution" / key) for key in lf.SPEC]
    emit("length_representation_negative_tests", {"fixtures":length_rows, "passed_count":sum(row["passed"] for row in length_rows),
        "fixture_count":14, "L03_expected_comparison_bound_to_verified_22A_not_T12_oracle":True})
    positive = r0.positive(OUT / "execution/R0_positive")
    negatives = [r0.negative(OUT / "execution" / spec["fixture_id"], spec)
                 for spec in r0.source_spec("repair_negative_fixture_specification")["fixtures"]]
    identities = [ri.negative(OUT / "execution" / spec["fixture_id"], spec) for spec in
                  j.strict_json(j.read_bytes(ri.R11 / "r2_runtime_identity_negative_fixture_spec.json"))["fixtures"]]
    recoveries = r0.recovery(OUT / "execution/recovery")
    validators = [vf.execute(key, OUT / "execution" / ("validator_" + key)) for key in vf.SPEC]
    groups = {"focused_length":[TEST],
        "22A":[ROOT / "tests/test_search_plan_v24_alpha322a_transport_observability_offline.py"],
        "22B":[ROOT / "tests/test_search_plan_v24_alpha322b_exception_mapping_offline.py"],
        "22C":[ROOT / "tests/test_search_plan_v24_alpha322c_attempt_journal_resume_offline.py"],
        "R2":[previous.d.release.r2.CONSTRUCTION_TEST,previous.d.release.r2.INTEGRITY_TEST,previous.d.release.r2.ISOLATION_TEST],
        "T11":previous.d.release.development.TESTS}
    regressions = {key:run_pytest(key,paths,OUT / "execution") for key,paths in groups.items()}
    fixture_passed = positive["passed"] and len(negatives) == 22 and len(identities) == 6 and len(validators) == 12 and all(
        row["passed"] for row in negatives + identities + recoveries + validators)
    emit("regression_results", {"r0_positive":positive, "r0_negatives":negatives, "ri_negatives":identities,
        "REC_fixtures":recoveries, "T11_fixtures":validators, "fixture_regressions_passed":fixture_passed,
        "new_runtime_exercised_by_all_explicit_fixtures":True, "pytest_groups":regressions,
        "all_regressions_passed":fixture_passed and all(row["passed"] for row in regressions.values()),
        "full_repository_suite_claimed":False})
    sources_unchanged()
    return {"focused_passes":{key:row["passed"] for key,row in rows.items()}, "length_tests_passed":sum(row["passed"] for row in length_rows),
            "regressions_passed":fixture_passed and all(row["passed"] for row in regressions.values())}


def scenario_child(key, directory):
    scenario = next(row for row in h.frozen_scenarios() if row["scenario_id"] == key)
    handlers = {"TRANSPORT":h.transport_scenario,"CRASH":h.crash_scenario,"JOURNAL_INTEGRITY":h.integrity_scenario,
                "ACTIVATION_INTEGRITY":h.integrity_scenario,"INTEGRATED":h.integrated_scenario}
    try:
        return handlers[scenario["category"]](scenario,directory)
    except Exception as exc:
        import traceback
        return {"scenario_id":key,"category":scenario["category"],"actual":{},"execution_error":{
            "qualified_class":type(exc).__module__ + '.' + type(exc).__qualname__, "message":str(exc), "traceback":traceback.format_exc()}}


def matrix(continue_t12_conflict=False):
    focus = load("t12_t17_t18_focused_results")["scenarios"]
    t.require(focus["T17"]["passed"] and focus["T18"]["passed"] and (focus["T12"]["passed"] or continue_t12_conflict),
              "FOCUSED_ADMISSION_BARRIER_UNSATISFIED")
    emit("matrix_execution_authorization", {"explicit_user_continuation_despite_T12_conflict":continue_t12_conflict,
        "T12_remains_FAIL":not focus["T12"]["passed"], "no_runtime_or_oracle_changes_during_matrix":True,
        "development_not_release":True, **NO_CALLS})
    manifest, oracle = previous.d.release.prior.frozen_inputs()
    rows = []
    for scenario in manifest["scenarios"]:
        sources_unchanged()
        key = scenario["scenario_id"]
        command = [sys.executable,"-m",__name__,"scenario","--key",key,"--output",str(OUT / "scenarios" / key)]
        process = subprocess.run(command,cwd=ROOT,capture_output=True,text=True)
        log = OUT / "execution" / ("matrix_" + key + ".txt")
        j.atomic_freeze(log,(process.stdout + process.stderr).encode())
        try:
            row = j.strict_json(process.stdout.encode())
            t.require(process.returncode == 0 and row["scenario_id"] == key,"DIAGNOSTIC_CHILD_INFRASTRUCTURE_FAILURE")
        except (ValueError,TypeError):
            row = {"scenario_id":key,"category":scenario["category"],"actual":{},"execution_error":process.stderr}
        mismatches = h.compare(oracle[key],row.get("actual") or {})
        error = row.get("durable_terminal_error") or row.get("execution_error")
        failed = bool(error or mismatches)
        conflict = key == "T12" and not error and mismatches == [{"field":"content_length_match","expected":"UNAVAILABLE","actual":"MISMATCH"}]
        row.update(expected=oracle[key],mismatches=mismatches,status="FAIL" if failed else "PASS",execution_status="EXECUTED",
            first_divergence=error or (mismatches[0] if mismatches else None),
            failure_category="FROZEN_SCENARIO_OR_ORACLE_CONFLICT" if conflict else "UNRESOLVED" if failed else None,
            reproduction_command=command, subprocess_exit_code=process.returncode,execution_log=h.ref(log,"unaltered_matrix_execution_output"))
        rows.append(row)
        print(key + ': ' + row["status"],flush=True)
    j.atomic_freeze(OUT / "full_59_development_results.jsonl",b''.join(j.canonical(row) for row in rows))
    sources_unchanged()
    return {"executed":len(rows),"passed":sum(row["status"] == "PASS" for row in rows)}


def freeze():
    sources_unchanged()
    before = load("upstream_root_verification")
    t.require(j.canonical(before) == j.canonical(authority()),"HISTORICAL_ROOT_DRIFT")
    focus = load("t12_t17_t18_focused_results")["scenarios"]
    negatives, reg = load("length_representation_negative_tests"), load("regression_results")
    matrix_path = OUT / "full_59_development_results.jsonl"
    if not matrix_path.exists():
        manifest, oracle = previous.d.release.prior.frozen_inputs()
        rows = [{"scenario_id":row["scenario_id"],"expected":oracle[row["scenario_id"]],"actual":None,"status":"NOT_EXECUTED",
                 "first_divergence":None,"failure_category":None,"reason":"T12 focused frozen conflict; no separate full-matrix continuation authority"} for row in manifest["scenarios"]]
        j.atomic_freeze(matrix_path,b''.join(j.canonical(row) for row in rows))
    rows = [j.strict_json(line) for line in j.read_bytes(matrix_path).splitlines()]
    checks = []
    commands = [[sys.executable,"-m","compileall","-q",*map(str,SOURCES)],["git","diff","--check"]] + [
        ["git","diff","--no-index","--check","/dev/null",str(path)] for path in SOURCES]
    for command in commands:
        process = subprocess.run(command,cwd=ROOT,capture_output=True,text=True)
        checks.append({"command":command,"exit_code":process.returncode,"diagnostics":process.stdout + process.stderr,
                       "passed":process.returncode in ({0,1} if "--no-index" in command else {0}) and not process.stdout and not process.stderr})
    summary = {"length_repair_status":"completed" if focus["T12"]["passed"] and focus["T17"]["passed"] and focus["T18"]["passed"] else "failed",
        "T17_T18_representation_repair_completed":focus["T17"]["passed"] and focus["T18"]["passed"],
        "t12_focused_passed":focus["T12"]["passed"],"t17_focused_passed":focus["T17"]["passed"],"t18_focused_passed":focus["T18"]["passed"],
        "t12_oracle_contract_conflict_resolved":focus["T12"]["passed"],"cross_representation_comparison_eliminated":True,
        "length_negative_test_pass_count":str(negatives["passed_count"]) + "/14",
        "t05_regression_passed":focus["T05"]["passed"],"t11_regression_passed":focus["T11"]["passed"],
        "development_scenario_count":59,"development_executed_count":sum(row["status"] != "NOT_EXECUTED" for row in rows),
        "development_passed_count":sum(row["status"] == "PASS" for row in rows),"development_failed_count":sum(row["status"] == "FAIL" for row in rows),
        "development_not_executed_count":sum(row["status"] == "NOT_EXECUTED" for row in rows),
        "remaining_runtime_defect_count":sum(row.get("failure_category") == "RUNTIME_IMPLEMENTATION_DEFECT" for row in rows),
        "remaining_unresolved_failure_count":sum(row.get("failure_category") == "UNRESOLVED" for row in rows),
        "remaining_oracle_conflict_count":1 if not focus["T12"]["passed"] else 0,
        "independent_release_gate_passed":False,"original_59_oracle_modified":False,"retry_policy_changed":False,
        "exception_mapping_table_changed":False,"scientific_policy_changed":False,"journal_integrity_weakened":False,
        "production_runtime_v2_wiring_enabled":False,"alpha3_21_reopened":False,"historical_assets_modified":False,
        "next_stage_recommendation":"EXPLICIT_VERSIONED_T12_VALIDATION_CONTRACT_DECISION_BEFORE_RELEASE_QUALIFICATION",
        "next_stage_automatically_started":False, **NO_CALLS}
    emit("historical_preservation", {"before":before,"after":authority(),"passed":True,"historical_assets_modified":False,
        "original_DR2_outcomes_unchanged":[12,11,1,47],"new_sources_unchanged":True})
    emit("validation", {"original_59_gate_passed":False,"focused_length_tests_passed":negatives["passed_count"] == 14,
        "regression_results_passed":reg["all_regressions_passed"],"engineering_checks":checks,"nonwiring":nonwiring(),
        "meaningful_development_iterations":[h.ref(path,"preserved_intermediate_source_and_test_result") for path in sorted((OUT / "execution").glob("development_iteration_*/execution_record.json"))],
        "T12_conflict_is_not_silently_overridden":True,"historical_preservation_verified":True, **NO_CALLS})
    emit("summary",summary)
    t.require(all((OUT / (name + '.json')).is_file() for name in REQUIRED),"REQUIRED_ARTIFACT_MISSING")
    root = previous.d.release.master.root_hash(OUT,MARKER)
    j.atomic_freeze(OUT / MARKER,(root + '\n').encode())
    t.require(previous.d.release.master.root_hash(OUT,MARKER) == root,"POST_FREEZE_ROOT_MISMATCH")
    return {**summary,"development_root_sha256":root,"workspace":str(OUT)}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("operation",choices=("prepare","iteration","focused","matrix","freeze","scenario"))
    parser.add_argument("--continue-t12-conflict",action="store_true")
    parser.add_argument("--key")
    parser.add_argument("--output",type=Path)
    args = parser.parse_args()
    with previous.d.release.master.prior.offline_guard():
        result = scenario_child(args.key,args.output) if args.operation == "scenario" else matrix(args.continue_t12_conflict) if args.operation == "matrix" else globals()[args.operation]()
        print(json.dumps(result,sort_keys=True))
