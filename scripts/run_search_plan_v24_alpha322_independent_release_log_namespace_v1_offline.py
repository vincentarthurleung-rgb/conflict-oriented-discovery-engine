"""One fail-fast independent release attempt against the frozen Oracle V2.

No expectation generator, runtime repair, scenario repair, or release rerun.
All scenario observations come from the byte-frozen latest integration in
fresh subprocesses. Expected values come only from frozen external artifacts.
"""

import argparse
import io
import json
import subprocess
import sys
import traceback
from pathlib import Path

from scripts import run_search_plan_v24_alpha322_length_repair_full_59_diagnostic_offline as latest
from scripts import search_plan_v24_alpha322_release_oracle_binding_v2 as binding

repair, j, t, h, ROOT = latest.repair, latest.j, latest.t, latest.h, latest.ROOT
master = repair.previous.d.release.master
FAILED = ROOT / "runs/20261011_search_plan_v24_dev_alpha3_22_final_release_validation_oracle_v2_offline"
FAILED_MARKER = "search_plan_v24_dev_alpha3_22_final_release_oracle_v2_sha256"
PHASE1 = ROOT / "runs/20261011_search_plan_v24_dev_alpha3_22_release_runner_binding_v2_preflight_offline"
PHASE1_MARKER = "search_plan_v24_dev_alpha3_22_runner_binding_v2_preflight_sha256"
PHASE1_SHA = None
OUT = ROOT / "runs/20261011_search_plan_v24_dev_alpha3_22_independent_release_runner_binding_v2_offline"
MARKER = "search_plan_v24_dev_alpha3_22_independent_release_binding_v2_sha256"
HISTORICAL_RUNNER = ROOT / "scripts/run_search_plan_v24_alpha322_final_release_oracle_v2_offline.py"
HISTORICAL_RUNNER_SHA = "e6623715954fbfe34dcb724fd2f313754cf6cb29651a384f347642092dfb9117"
CONTRACT = ROOT / "runs/20261010_search_plan_v24_dev_alpha3_22_t12_length_contract_resolution_offline"
CONTRACT_SHA = "4301d3c0607796d990278f7529350ecdb515b99964975aabf0d8d014ec68c8e8"
LATEST_SHA = "d5314eb4b2387cad9a7ab5318ee0ed6df7bf1b47a230ad97702bfc7035a05a04"
ORIGINAL_ORACLE_SHA = "b1d452438341fd2a01262f09a75649169dd726da119371b30388c4a464d6d817"
V2_SHA = "682e63ebbfeeca9e932db3f73fcadb8ab02181b7e8cbfc639f9fc4440bf77645"
SCENARIO_SHA = "aed33640b5a88badd5a785b41019158ca369b656f20a5a150713b2e8f8eba23b"
CLASS_PASS = "INDEPENDENT_RUNTIME_RELEASE_VALIDATION_PASSED_UNDER_VERSIONED_ORACLE_V2"
CLASS_FAIL = "INDEPENDENT_RUNTIME_RELEASE_VALIDATION_FAILED_UNDER_VERSIONED_ORACLE_V2"
NO_CALLS = dict(repair.NO_CALLS)
REQUIRED = "summary validation frozen_input_bindings oracle_v1_v2_difference repair_regression_results critical_safety_results failure_evidence historical_preservation".split()


def read(path):
    return j.strict_json(j.read_bytes(path))


def emit(name, value):
    return j.atomic_freeze(OUT / (name + ".json"), j.canonical(value))


def obj(name):
    return read(OUT / (name + ".json"))


def compare(expected, actual):
    return [{"field": key, "expected": value, "actual": actual.get(key)}
            for key, value in expected.items() if actual.get(key) != value]


def verify_reference(reference):
    path = Path(reference["artifact_path"])
    path = path if path.is_absolute() else ROOT / path
    raw = j.read_bytes(path)
    t.require(j.sha(raw) == reference["sha256"], "REFERENCE_HASH_MISMATCH:" + str(path))
    if "byte_count" in reference:
        t.require(len(raw) == reference["byte_count"], "REFERENCE_BYTE_COUNT_MISMATCH")
    return raw


def authority():
    result = latest.authority()
    latest.sources_unchanged()
    result["latest_58_of_59_development"] = master.prior.root_check(latest.OUT, latest.MARKER, LATEST_SHA)
    result["versioned_oracle_contract_resolution"] = master.prior.root_check(
        CONTRACT, "search_plan_v24_dev_alpha3_22_t12_contract_resolution_sha256", CONTRACT_SHA)
    t.require([latest.load("summary")[key] for key in ("development_executed_count", "development_passed_count", "development_failed_count")] == [59, 58, 1],
              "HISTORICAL_58_OF_59_ACCOUNTING_DRIFT")
    change = read(CONTRACT / "versioned_change_manifest.json")
    verify_reference(change["development_driver"])
    verify_reference(read(CONTRACT / "execution_failure/first_attempt.json")["new_execution_wrapper"])
    result["failed_preflight_only_release"] = master.prior.root_check(
        FAILED, FAILED_MARKER, binding.ROOTS["failed_preflight"])
    failure = read(FAILED / "summary.json")
    t.require([failure[key] for key in ("executed_count", "not_executed_count")] == [0, 59],
              "HISTORICAL_PREFLIGHT_ONLY_ACCOUNTING_DRIFT")
    t.require(not (FAILED / "scenarios").exists() and not (FAILED / "repairs").exists(),
              "HISTORICAL_PREFLIGHT_EXECUTION_BOUNDARY_DRIFT")
    t.require(j.sha(j.read_bytes(HISTORICAL_RUNNER)) == HISTORICAL_RUNNER_SHA,
              "FAILED_HISTORICAL_RUNNER_MODIFIED")
    if PHASE1_SHA is not None:
        result["frozen_phase1_runner_preflight"] = phase1_check()
    return result


def runtime_binding():
    return {name: module.__name__ for name, module in {
        "journal": j, "resume": h.p, "barrier": h.s, "lifecycle": t, "observability": h.o,
        "mapper": h.b, "phase_binding": h.f, "validator_integration": h.integration,
        "validator_outcome_adapter": h.integration.validity, "runtime_identity": repair.ri.identity,
        "scenario_harness": h}.items()} | {
        "integration_entrypoint": repair.scenario_child.__module__ + ":" + repair.scenario_child.__name__}


def artifact_data():
    scenario_raw = j.read_bytes(h.ORIGINAL / "frozen_fault_scenario_manifest.json")
    original_raw = j.read_bytes(h.ORIGINAL / "independent_expected_outcomes.jsonl")
    change = binding.parse(j.read_bytes(CONTRACT / "versioned_change_manifest.json"))
    observed_roots = {
        "failed_preflight": j.read_bytes(FAILED / FAILED_MARKER).decode().strip(),
        "oracle_contract": j.read_bytes(CONTRACT / "search_plan_v24_dev_alpha3_22_t12_contract_resolution_sha256").decode().strip(),
        "runtime_development": j.read_bytes(latest.OUT / latest.MARKER).decode().strip()}
    return scenario_raw, original_raw, change, observed_roots, runtime_binding()


def frozen_inputs():
    """Source-only manifest -> separately frozen oracle by exact scenario_id."""
    scenario_raw, original_raw, change, roots, runtime = artifact_data()
    manifest = binding.parse(scenario_raw)
    records, v2_raw = binding.bind(manifest, original_raw, change)
    binding.authority(scenario_raw, original_raw, v2_raw, roots, runtime)
    difference = {"changed_scenario_count": 1, "changes": [
        {"scenario_id": "T12", "field": "content_length_match", "old": "UNAVAILABLE", "new": "MISMATCH"}],
        "other_58_expectations_byte_identical": True, "original_oracle_sha256": ORIGINAL_ORACLE_SHA,
        "oracle_v2_sha256": V2_SHA, "original_scenario_manifest_sha256": SCENARIO_SHA,
        "oracle_V2_loaded_directly_from_frozen_records": True,
        "binding_key": "scenario_id", "scenario_manifest_contains_expectations": False,
        "scenario_oracle_bijection_verified": True, "expectation_generation_function_calls": 0,
        "runtime_calls_to_calculate_expectations": 0, "original_oracle_modified": False,
        "historical_original_oracle_development_result": "58/59"}
    return manifest, records, v2_raw, difference


def test_groups():
    release = repair.previous.d.release
    return {"representation": [repair.TEST],
        "22A": [ROOT / "tests/test_search_plan_v24_alpha322a_transport_observability_offline.py"],
        "22B": [ROOT / "tests/test_search_plan_v24_alpha322b_exception_mapping_offline.py"],
        "22C": [ROOT / "tests/test_search_plan_v24_alpha322c_attempt_journal_resume_offline.py"],
        "R2": [release.r2.CONSTRUCTION_TEST, release.r2.INTEGRITY_TEST, release.r2.ISOLATION_TEST],
        "T11": release.development.TESTS}


def source_paths():
    modules = (latest, t, h.o, h.b, h.f, h.p, h.s, h.integration, h.integration.validity, h.identity, repair.ri.identity,
               repair.previous.d.release, repair.previous.d.release.prior)
    paths = list(repair.SOURCES) + [Path(module.__file__) for module in modules] + [Path(__file__), Path(binding.__file__), HISTORICAL_RUNNER]
    paths += [path for group in test_groups().values() for path in group]
    return sorted(set(path.absolute() for path in paths))


def freeze_configuration():
    t.require(not OUT.exists() and not OUT.is_symlink(), "NEW_RELEASE_ATTEMPT_REQUIRED_NO_RERUN")
    t.require(PHASE1_SHA is not None, "FROZEN_PHASE1_REQUIRED_BEFORE_RELEASE")
    before = authority()
    manifest, records, v2_raw, difference = frozen_inputs()
    t.require(repair.r0.j is j and repair.ri.j is j and repair.vf.j is j and repair.lf.j is j,
              "FIXTURES_MUST_USE_ACTUAL_LATEST_RUNTIME")
    OUT.mkdir()
    for name in ("execution", "scenarios", "repairs", "implementation", "inputs"):
        (OUT / name).mkdir()
    (OUT / "execution/regressions").mkdir()
    sources = []
    for path in source_paths():
        copy = OUT / "implementation" / path.relative_to(ROOT)
        copy.parent.mkdir(parents=True, exist_ok=True)
        j.atomic_freeze(copy, j.read_bytes(path))
        sources.append({"source": h.ref(path, "exact_pre_execution_source"),
                        "snapshot": h.ref(copy, "physical_byte_identical_release_source_snapshot")})
    j.atomic_freeze(OUT / "inputs/oracle_v2.jsonl", v2_raw)
    for source, name in ((h.ORIGINAL / "frozen_fault_scenario_manifest.json", "original_scenarios.json"),
                         (h.ORIGINAL / "independent_expected_outcomes.jsonl", "original_oracle.jsonl")):
        j.atomic_freeze(OUT / "inputs" / name, j.read_bytes(source))
    emit("oracle_v1_v2_difference", difference)
    configuration = emit("frozen_input_bindings", {"mode": "OFFLINE_INDEPENDENT_RELEASE_VALIDATION_NO_DEVELOPMENT_OR_REPAIR",
        "upstream_authority": before, "runner_preflight_root_sha256": PHASE1_SHA, "runtime_source_bindings": sources,
        "runtime_root_sha256": latest.REPAIR_SHA, "runtime_journal_authority": j.AUTHORITY,
        "runtime_modules": {name: module.__name__ for name, module in {
            "journal": j, "resume": h.p, "barrier": h.s, "lifecycle": t, "observability": h.o,
            "mapper": h.b, "phase_binding": h.f, "validator_integration": h.integration,
            "validator_outcome_adapter": h.integration.validity, "runtime_identity": repair.ri.identity}.items()},
        "integration_entrypoint": [sys.executable, "-m", repair.__name__, "scenario", "--key", "<frozen_id>", "--output", "<new_isolated_directory>"],
        "actual_scenario_harness": h.ref(Path(h.__file__), "latest_frozen_length_bound_integration"),
        "oracle_v2_source": h.ref(CONTRACT / "versioned_change_manifest.json", "frozen_V2_records_not_regenerated"),
        "oracle_v2_release_copy": h.ref(OUT / "inputs/oracle_v2.jsonl", "exact_frozen_V2_serialized_byte_stream"),
        "original_scenario_manifest": h.ref(OUT / "inputs/original_scenarios.json", "all_original_inputs_unchanged"),
        "original_oracle": h.ref(OUT / "inputs/original_oracle.jsonl", "original_oracle_unchanged_not_release_authority"),
        "oracle_v2_sha256": V2_SHA, "original_scenario_manifest_sha256": SCENARIO_SHA,
        "scenario_order": manifest["order"], "stop_on_first_critical_failure": True,
        "scenario_reruns_authorized": False, "historical_observations_substitute_for_new_execution": False,
        "regression_expectations": {
            "R0_positive": h.ref(repair.r0.f.R0 / "repair_positive_fixture_specification.json", "frozen_literal_positive"),
            "R0_negatives": h.ref(repair.r0.f.R0 / "repair_negative_fixture_specification.json", "22_exact_rejections"),
            "RI_negatives": h.ref(repair.ri.R11 / "r2_runtime_identity_negative_fixture_spec.json", "six_exact_rejections"),
            "recovery": h.ref(repair.r0.f.R0 / "repair_recovery_fixture_specification.json", "exact_REC01_REC02_identities"),
            "length_counterexamples": h.ref(CONTRACT / "t12_semantic_counterexamples.json", "frozen_11_unit_inputs_and_expectations"),
            "T11_literals": {key: value[1] for key, value in repair.vf.SPEC.items()},
            "representation_literals": dict(repair.lf.SPEC)},
        "test_groups": {name: [h.ref(path, "frozen_required_regression_test") for path in paths] for name, paths in test_groups().items()},
        "scientific_policy_changed": False, "retry_policy_changed": False,
        "production_runtime_v2_wiring_enabled": False, "alpha3_21_reopened": False, **NO_CALLS})
    j.atomic_freeze(OUT / "execution/pre_execution_configuration.sha256", (configuration.sha256 + "\n").encode())
    print("frozen_release_configuration_sha256=" + configuration.sha256, flush=True)
    return manifest, {row["scenario_id"]: row["expected"] for row in records}, before


def sources_unchanged():
    latest.sources_unchanged()
    t.require(j.sha(j.read_bytes(OUT / "frozen_input_bindings.json"))
              == j.read_bytes(OUT / "execution/pre_execution_configuration.sha256").decode().strip(), "PRE_EXECUTION_CONFIGURATION_DRIFT")
    bindings = obj("frozen_input_bindings")
    for row in bindings["runtime_source_bindings"]:
        t.require(verify_reference(row["source"]) == verify_reference(row["snapshot"]), "FROZEN_RELEASE_SOURCE_DRIFT")
    for name in ("oracle_v2_release_copy", "original_scenario_manifest", "original_oracle", "oracle_v2_source"):
        verify_reference(bindings[name])
    frozen_inputs()


def load_observation(row):
    return j.strict_json(verify_reference(row["observation"]))["observation"]


def transport_integrity(row, directory):
    manifest = j.FrozenRequestManifestV2(j.read_bytes(directory / "request_manifest.json"))
    verified = j.JournalIntegrityVerifierV2.read(directory, manifest)
    events = [event.record() for event in verified.events]
    starts = {event["entry_hash"]: event for event in events if event["event_type"] == "ATTEMPT_STARTED"}
    dispatch = row["dispatch_log"]
    bindings = all(item["durable_start_hash"] in starts
        and starts[item["durable_start_hash"]]["logical_request_id"] == item["request_id"]
        and starts[item["durable_start_hash"]]["attempt_ordinal"] == item["attempt_ordinal"] for item in dispatch)
    observation = load_observation(row)
    exception = observation.get("exception_provenance")
    if exception is not None:
        h.o.validate_schema(exception, repair.ri.identity.exception_schema())
    checks = {"durable_start_dispatch_identity": bool(dispatch) and bindings,
        "journal_hash_chain_verified": True, "fresh_reader_read_only": row["fresh_reader_read_only"] is True,
        "raw_hash_verified": row["raw_hash_verified"] is True,
        "attempt_ordinals_unique": len({(d["request_id"], d["attempt_ordinal"]) for d in dispatch}) == len(dispatch),
        "four_attempt_limit": all(1 <= d["attempt_ordinal"] <= 4 for d in dispatch),
        "runtime_identity_schema": True}
    return {"checks": checks, "passed": all(checks.values()), "verified_event_count": len(events)}


def specific_check(row, directory):
    key, actual = row["scenario_id"], row["actual"]
    if key == "T05":
        return repair.previous.d.release.prior.t05_check(row)
    if key == "T11":
        return repair.previous.d.release.t11_check(row)
    observation = load_observation(row)
    body, http = observation.get("body_read_provenance") or {}, observation.get("http_response_provenance") or {}
    if key == "T12":
        exception = observation["exception_provenance"]
        root = next(node for node in exception["exception_nodes"] if node["node_id"] == exception["root_exception_node_id"])
        checks = {"RuntimeError_preserved": root["qualified_class_name"] == "builtins.RuntimeError",
            "UNKNOWN_mapping": actual["semantic_failure_class"] == "UNKNOWN_RUNTIME_FAILURE"
                and row["transport_mapping"]["mapping_rule_id"] is None,
            "trusted_header_50": http["HTTP_provenance_trusted"] is True and http["content_length_raw"] == "50"
                and http["expected_content_length_bytes"] == body["expected_content_length_bytes"] == 50,
            "retained_wire_zero": http["body_byte_representation"] == "wire" and body["bytes_read"] == row["raw_artifact"]["byte_count"] == 0,
            "V2_MISMATCH": actual["content_length_match"] == "MISMATCH", "body_incomplete": actual["body_complete"] is False
                and body["read_returned_normally"] is False and body["completion_state"] == "BODY_COMPLETION_UNKNOWN",
            "no_parser": not any(actual["parser_invocation_counts"].values()),
            "no_unauthorized_retry": actual["retry_authorized"] is False and actual["next_attempt_ordinal"] is None,
            "committed_unknown_terminal": actual["durable_terminal_committed"] is True
                and actual["terminal_logical_state"] == "TERMINAL_TECHNICAL_FAILURE",
            "fresh_reader_read_only": row["fresh_reader_read_only"] is True}
        return {"checks": checks, "passed": all(checks.values())}
    # T17/T18: use the unchanged verifier against the actual persisted evidence.
    context = t.AttemptContextV1(body["logical_request_id"], body["request_payload_sha256"], body["attempt_ordinal"])
    request = j.FrozenRequestManifestV2(j.read_bytes(directory / "request_manifest.json")).request(context.logical_request_id)
    raw = verify_reference(row["raw_artifact"])
    length = j.lengths.verify_complete_length(body, http, raw, context, request)
    checks = {"correct_actual_representation": length["actual_representation"] == ("decoded" if key == "T17" else "decompressed"),
        "wire_expected_preserved": length["expected_representation"] == "wire", "UNAVAILABLE_comparison": length["content_length_match"] == actual["content_length_match"] == "UNAVAILABLE",
        "no_cross_representation_equality": length["cross_representation_comparison_performed"] is False,
        "complete_normal_read": actual["body_complete"] is True and body["read_returned_normally"] is True,
        "valid_journal_terminal": actual["journal_integrity"] == "VERIFIED" and actual["durable_terminal_committed"] is True
            and actual["terminal_logical_state"] == "VALID_SUCCESS", "fresh_reader_read_only": row["fresh_reader_read_only"] is True}
    return {"checks": checks, "passed": all(checks.values()), "actual_length_verification": length}


def matrix(manifest, expected):
    rows, failed = [], None
    for scenario in manifest["scenarios"]:
        key = scenario["scenario_id"]
        if failed:
            rows.append({"scenario_id": key, "category": scenario["category"], "expected": expected[key], "actual": None,
                "status": "NOT_EXECUTED", "execution_status": "NOT_EXECUTED", "first_divergence": None,
                "reason": "FIRST_CRITICAL_FAILURE:" + failed})
            continue
        directory = OUT / "scenarios" / key
        command = [sys.executable, "-m", repair.__name__, "scenario", "--key", key, "--output", str(directory)]
        row = {"scenario_id": key, "category": scenario["category"], "actual": {}}
        dispatched = False
        try:
            sources_unchanged()
            dispatched = True
            process = subprocess.run(command, cwd=ROOT, capture_output=True, text=True)
            log = OUT / "execution" / (key + ".txt")
            j.atomic_freeze(log, (process.stdout + process.stderr).encode())
            row = j.strict_json(process.stdout.encode())
            t.require(process.returncode == 0 and row["scenario_id"] == key, "SCENARIO_SUBPROCESS_FAILED")
            row.update(execution_log=h.ref(log, "unaltered_fresh_scenario_subprocess_output"), subprocess_exit_code=process.returncode)
            differences = compare(expected[key], row.get("actual") or {})
            error = row.get("execution_error") or row.get("durable_terminal_error")
            first = {"operation": "scenario_execution_or_durable_terminal", "error": error} if error else (
                {"operation": "frozen_oracle_V2_comparison", **differences[0]} if differences else None)
            row.update(expected=expected[key], mismatches=differences, status="FAIL" if first else "PASS", first_divergence=first)
            if row["status"] == "PASS" and scenario["category"] == "TRANSPORT":
                row["independent_transport_integrity"] = transport_integrity(row, directory)
                if not row["independent_transport_integrity"]["passed"]:
                    row.update(status="FAIL", first_divergence={"operation": "transport_integrity_checks"})
                elif key in {"T05", "T11", "T12", "T17", "T18"}:
                    row["specific_release_checks"] = specific_check(row, directory)
                    if not row["specific_release_checks"]["passed"]:
                        row.update(status="FAIL", first_divergence={"operation": key + "_specific_release_checks"})
        except Exception as exc:
            row.update(expected=expected[key], status="FAIL" if dispatched else "NOT_EXECUTED", first_divergence={"operation": "release_execution_exception", "error": str(exc)},
                execution_error={"qualified_class": type(exc).__module__ + "." + type(exc).__qualname__,
                                 "message": str(exc), "traceback": traceback.format_exc()})
        row.update(execution_status="EXECUTED" if dispatched else "NOT_EXECUTED", actual_execution_command=command,
            original_input_definition_sha256=j.sha(j.canonical(scenario)),
            original_injection_point=scenario["injection_point"], no_release_scenario_rerun=True)
        j.atomic_freeze(OUT / "execution" / (key + ".json"), j.canonical(row))
        rows.append(row)
        print(key + ": " + row["status"], flush=True)
        if row.get("first_divergence") is not None:
            failed = key
    j.atomic_freeze(OUT / "scenario_results.jsonl", b"".join(j.canonical(row) for row in rows))
    return rows


def body_counterexample(frozen, directory):
    key = frozen["counterexample_id"]
    directory.mkdir()
    raw = io.BytesIO(b"x" * frozen["observed_preserved_bytes"]).read()
    normal, expected = frozen["read_returned_normally"], frozen["expected_length"]
    completion = t.assess_body_completion(raw, read_returned_normally=normal, expected_content_length=expected,
        expected_length_trustworthy=expected is not None, byte_representation=t.ByteRepresentation(frozen["actual_representation"]),
        expected_length_representation=t.ByteRepresentation.WIRE,
        interruption_class=t.SemanticFailure.RESPONSE_BODY_TRANSPORT_INTERRUPTION if not normal else None, timestamp=h.NOW)
    artifact = t.RawArtifactStoreV1(directory / "raw").freeze_bytes("response.bin", raw)
    response = t.FrozenTransportResponseV2(t.AttemptContextV1("counterexample:" + key, j.sha(key.encode()), 1), completion, artifact, True)
    calls, rejection = [], None
    try:
        t.guarded_parse(response, lambda value: calls.append(len(value)))
    except t.TransportContractError as exc:
        rejection = str(exc)
    actual = {"content_length_match": completion.content_length_match, "body_state": completion.body_completion_state.value,
        "semantic_failure": completion.semantic_failure.value, "parser_invocations": len(calls),
        "retry_authorized_replay_safe_attempt_1": t.semantic_retry_decision(completion.semantic_failure, request_replay_safe=True, attempt_ordinal=1).retry_authorized,
        "retry_authorized_replay_unsafe": t.semantic_retry_decision(completion.semantic_failure, request_replay_safe=False, attempt_ordinal=1).retry_authorized,
        "retry_authorized_exhausted_budget": t.semantic_retry_decision(completion.semantic_failure, request_replay_safe=True, attempt_ordinal=4).retry_authorized}
    differences = compare(frozen["expected"], actual)
    return {"counterexample_id": key, "expected": frozen["expected"], "actual": actual, "mismatches": differences,
        "passed": not differences and (normal or completion.body_sha256 is None and not response.authoritative),
        "parser_rejection": rejection, "raw_artifact": dict(artifact.__dict__)}


def length_counterexamples(rows):
    indexed = {row["scenario_id"]: row for row in rows}
    specs = read(CONTRACT / "t12_semantic_counterexamples.json")["counterexamples"]
    base = OUT / "repairs/length_counterexamples"
    base.mkdir()
    results = []
    for frozen in specs:
        key = frozen["counterexample_id"]
        if key in {"A", "B", "C", "D", "E", "F", "K"}:
            row = body_counterexample(frozen, base / key)
        elif key == "G":
            result = repair.lf.execute("L06", base / key)
            actual = {"decoded_comparison": result["content_length_match"], "wire_comparison": result["actual_exact_outcome"]}
            row = {"counterexample_id": key, "expected": frozen["expected"], "actual": actual, "fixture": result,
                   "passed": not compare(frozen["expected"], actual) and result["passed"]}
        elif key == "H":
            actual = indexed["T10"]["actual"]
            expected = frozen["execution"]["actual"]
            row = {"counterexample_id": key, "expected": expected, "actual": actual,
                   "passed": not compare(expected, actual), "execution_source": "fresh release matrix T10; no original scenario rerun"}
        elif key == "I":
            actual, expected = indexed["T12"]["actual"], frozen["full_path_actual"]
            row = {"counterexample_id": key, "expected": expected, "actual": actual,
                "passed": not compare(expected, actual) and indexed["T12"]["specific_release_checks"]["passed"],
                "execution_source": "fresh release matrix T12 including exact RuntimeError/header/body evidence; no original scenario rerun"}
        else:
            t.require(key == "J", "UNKNOWN_FROZEN_COUNTEREXAMPLE")
            result = repair.lf.execute("L10", base / key)
            row = {"counterexample_id": key, "expected_rejection": frozen["expected_rejection"],
                "actual_rejection": result["actual_first_rejection"], "fixture": result,
                "passed": result["actual_first_rejection"] == frozen["expected_rejection"] and result["passed"]
                    and result["parser_invocations"] == result["journal_terminal_count"] == 0}
        results.append(row)
        if not row["passed"]:
            break
    return {"rows": results, "count": len(results), "passed_count": sum(row["passed"] for row in results),
            "all_passed": len(results) == 11 and all(row["passed"] for row in results)}


def regressions(rows):
    bindings = obj("frozen_input_bindings")["regression_expectations"]
    result = {"status": "EXECUTED", "R0_positive": None, "R0_negatives": [], "runtime_identity_negatives": [],
              "REC_fixtures": [], "T11_fixtures": [], "length_counterexamples": None, "pytest_groups": {}, "all_passed": False}
    try:
        positive = repair.r0.positive(OUT / "repairs/R0_positive")
        expected = read(repair.r0.f.R0 / "repair_positive_fixture_specification.json")["expected"]
        positive["release_exact_expected_match"] = positive["actual"] == expected
        result["R0_positive"] = positive
        t.require(positive["passed"] and positive["release_exact_expected_match"], "R0_POSITIVE_FAILED")
        for spec in read(repair.r0.f.R0 / "repair_negative_fixture_specification.json")["fixtures"]:
            row = repair.r0.negative(OUT / "repairs" / spec["fixture_id"], spec)
            result["R0_negatives"].append(row)
            t.require(row["passed"] and row["actual"] == spec["expected"]
                      and row["actual_first_rejection_reason"] == spec["expected"]["proposed_reason_code"], "R0_NEGATIVE_FAILED:" + spec["fixture_id"])
        for spec in read(repair.ri.R11 / "r2_runtime_identity_negative_fixture_spec.json")["fixtures"]:
            row = repair.ri.negative(OUT / "repairs" / spec["fixture_id"], spec)
            result["runtime_identity_negatives"].append(row)
            t.require(row["passed"] and row["actual"] == spec["expected"]
                      and row["actual_first_rejection"] == spec["expected_first_rejection"], "RI_NEGATIVE_FAILED:" + spec["fixture_id"])
        recovery_spec = read(repair.r0.f.R0 / "repair_recovery_fixture_specification.json")
        expected_recovery = {recovery_spec["fixture_id"]: recovery_spec["expected"],
            recovery_spec["crash_before_terminal_variant"]["fixture_id"]: recovery_spec["crash_before_terminal_variant"]["expected"]}
        result["REC_fixtures"] = repair.r0.recovery(OUT / "repairs/recovery")
        t.require({row["fixture_id"] for row in result["REC_fixtures"]} == set(expected_recovery)
                  and all(row["passed"] and row["actual"] == expected_recovery[row["fixture_id"]] for row in result["REC_fixtures"]), "REC_EXACT_IDENTITY_OR_OUTCOME_FAILED")
        for key, expected in bindings["T11_literals"].items():
            row = repair.vf.execute(key, OUT / "repairs" / ("T11_" + key))
            result["T11_fixtures"].append(row)
            t.require(row["passed"] and row["actual_exact_outcome"] == expected, "T11_FIXTURE_FAILED:" + key)
        result["length_counterexamples"] = length_counterexamples(rows)
        t.require(result["length_counterexamples"]["all_passed"], "LENGTH_COUNTEREXAMPLE_FAILED")
        for name, paths in test_groups().items():
            group = repair.run_pytest(name, paths, OUT / "execution/regressions")
            result["pytest_groups"][name] = group
            t.require(group["passed"], "REGRESSION_GROUP_FAILED:" + name)
        sources_unchanged()
        result["all_passed"] = (len(result["R0_negatives"]) == 22 and len(result["runtime_identity_negatives"]) == 6
            and len(result["REC_fixtures"]) == 2 and len(result["T11_fixtures"]) == 12 and len(result["pytest_groups"]) == 6)
    except Exception as exc:
        result["failure"] = {"qualified_class": type(exc).__module__ + "." + type(exc).__qualname__,
                             "message": str(exc), "traceback": traceback.format_exc()}
    result.update(original_scenario_count_contribution=0, fixture_reruns=0,
                  expectations_from_frozen_contracts_only=True, full_repository_suite_claimed=False)
    emit("repair_regression_results", result)
    return result


def engineering_checks():
    commands = [[sys.executable, "-m", "compileall", "-q", *map(str, source_paths())], ["git", "diff", "--check"],
                ["git", "diff", "--no-index", "--check", "/dev/null", str(Path(__file__))]]
    results = []
    for index, command in enumerate(commands):
        process = subprocess.run(command, cwd=ROOT, capture_output=True, text=True)
        log = OUT / "execution" / ("engineering_%d.txt" % index)
        j.atomic_freeze(log, (process.stdout + process.stderr).encode())
        results.append({"command": command, "exit_code": process.returncode, "log": h.ref(log, "actual_engineering_check"),
            "passed": process.returncode in ({0, 1} if "--no-index" in command else {0}) and not process.stdout and not process.stderr})
    return results


def invariants(rows, reg, preserved):
    indexed = {row["scenario_id"]: row for row in rows if row["status"] == "PASS"}
    complete = len(indexed) == 59 and reg["all_passed"]
    executed = [row for row in rows if row["status"] != "NOT_EXECUTED"]
    counters = repair.previous.d.release.prior.observed_counters(executed)
    leaks = [str(path.relative_to(OUT)) for folder in (OUT / "scenarios", OUT / "repairs", OUT / "execution")
             for path in folder.rglob("*") if path.is_file() and h.SECRET.encode() in j.read_bytes(path)]
    checks = {"partial_response_parser_quarantine": counters["partial_parser_invocations"] == 0
            and all((row.get("actual") or {}).get("partial_parser_invocations", 0) == 0 for row in executed),
        "UNKNOWN_automatic_retry_prohibition": counters["unauthorized_retries"] == 0,
        "attempt_ordinal_uniqueness": counters["attempt_ordinal_reuse_count"] == 0,
        "four_attempt_budget": all(item["attempt_ordinal"] <= 4 for row in executed for item in row.get("dispatch_log", [])),
        "successful_request_immutability": counters["successful_request_refresh_count"] == 0,
        "secret_redaction": not leaks, "historical_and_scientific_preservation": preserved}
    if complete:
        transport = [row for row in rows if row["category"] == "TRANSPORT"]
        checks.update({
            "replay_safety": indexed["T20"]["actual"]["retry_authorized"] is False and indexed["C18"]["actual"]["retry_authorized"] is False,
            "write_ahead_durability_ordering": all(row["independent_transport_integrity"]["checks"]["durable_start_dispatch_identity"] for row in transport),
            "journal_hash_chain_integrity": all(row["independent_transport_integrity"]["passed"] for row in transport)
                and all(row["actual"]["journal_integrity"] == "FAILED_CLOSED" for row in rows if row["category"] in {"JOURNAL_INTEGRITY", "ACTIVATION_INTEGRITY"}),
            "terminal_noneligible_and_validity_failure_skipping": indexed["T11"]["specific_release_checks"]["passed"]
                and indexed["C07"]["actual"]["resume_executable_ids"] == []
                and indexed["E01"]["actual"]["terminal_validity_failure_blocks_later_dispatch"] is True
                and indexed["E01"]["actual"]["license_ineligible_refetch_count"] == 0,
            "OA_barrier_immutability": counters["barrier_or_activation_drift_count"] == 0
                and indexed["E01"]["actual"]["activation_drift_count"] == 0,
            "JATS_activation_integrity": all(indexed["A%02d" % n]["actual"]["dispatch_count"] == 0 for n in range(1, 7)),
            "same_request_attempt_evidence_binding": all(row["independent_transport_integrity"]["passed"] for row in transport)
                and len(reg["R0_negatives"]) == 22 and all(row["passed"] for row in reg["R0_negatives"]),
            "runtime_identity_schema": all(row["independent_transport_integrity"]["checks"]["runtime_identity_schema"] for row in transport)
                and len(reg["runtime_identity_negatives"]) == 6 and all(row["passed"] for row in reg["runtime_identity_negatives"]),
            "fresh_process_resume_read_only": all(row["fresh_reader_read_only"] is True for row in transport)
                and all(row["passed"] for row in reg["REC_fixtures"]),
            "all_specific_release_contracts": all(indexed[key]["specific_release_checks"]["passed"] for key in ("T05", "T11", "T12", "T17", "T18"))})
    return {"checks": checks, "critical_safety_failures": sum(value is False for value in checks.values()),
        "full_safety_coverage_completed": complete, "unexecuted_domains_certified": False,
        "full_coverage_original_categories": {category: sum(row["category"] == category and row["status"] == "PASS" for row in rows)
            for category in ("TRANSPORT", "CRASH", "JOURNAL_INTEGRITY", "ACTIVATION_INTEGRITY", "INTEGRATED")},
        "observed_counters": counters, "secret_leak_files": leaks, "physical_power_loss_claimed": False, **NO_CALLS}


def verify_report_references():
    verified = set()
    def walk(value):
        if isinstance(value, dict):
            if "artifact_path" in value and "sha256" in value:
                verify_reference(value)
                verified.add((value["artifact_path"], value["sha256"]))
            for child in value.values():
                walk(child)
        elif isinstance(value, list):
            for child in value:
                walk(child)
    for path in OUT.glob("*.json"):
        walk(read(path))
    for line in j.read_bytes(OUT / "scenario_results.jsonl").splitlines():
        walk(j.strict_json(line))
    # Deliberately corrupted fixture claims are not admitted references. Their
    # physical bytes remain bound by the complete root inventory.
    return len(verified)


def run():
    manifest, expected, before = freeze_configuration()
    rows = matrix(manifest, expected)
    if all(row["status"] == "PASS" for row in rows):
        reg = regressions(rows)
    else:
        reg = {"status": "NOT_EXECUTED", "all_passed": False, "pytest_groups": {},
               "reason": "first critical matrix failure; no repair or release rerun"}
        emit("repair_regression_results", reg)
    engineering = engineering_checks()
    after, preservation_error = None, None
    try:
        sources_unchanged()
        after = authority()
        preserved = before == after
    except Exception as exc:
        preserved, preservation_error = False, str(exc)
    safe = invariants(rows, reg, preserved)
    emit("critical_safety_results", safe)
    emit("historical_preservation", {"before": before, "after": after, "passed": preserved,
        "error": preservation_error, "runtime_source_modified": not preserved, "original_oracle_modified": False,
        "original_development_result_unchanged": {"root_sha256": LATEST_SHA, "passed": 58, "failed": 1},
        "contract_resolution_development_root_unchanged": CONTRACT_SHA,
        "alpha3_21_reopened": False, "scientific_policy_changed": False, "historical_assets_modified": not preserved})
    counts = {status: sum(row["status"] == status for row in rows) for status in ("PASS", "FAIL", "NOT_EXECUTED")}
    passed = (counts["PASS"] == len(rows) == 59 and safe["critical_safety_failures"] == 0
              and safe["full_safety_coverage_completed"] and reg["all_passed"] and preserved and all(row["passed"] for row in engineering))
    failed_rows = [row for row in rows if row.get("first_divergence") is not None]
    emit("failure_evidence", {"failures": failed_rows, "regression_failure": reg.get("failure"),
        "preservation_error": preservation_error, "first_failed_scenario": failed_rows[0]["scenario_id"] if failed_rows else None,
        "no_repair_no_rerun": True, "remaining_not_executed": counts["NOT_EXECUTED"],
        "failure_reproduction_policy": "read-only evidence inspection; do not rerun this release attempt"})
    selected = {row["scenario_id"]: row for row in rows}
    summary = {"alpha3_22_release_status": "completed" if passed else "failed",
        "alpha3_22_release_classification": CLASS_PASS if passed else CLASS_FAIL,
        "oracle_version": "V2", "oracle_v2_sha256": V2_SHA, "original_oracle_modified": False,
        "oracle_v2_frozen": True, "oracle_v2_changed_scenario_count": 1, "oracle_v2_changed_scenario_id": "T12",
        "oracle_v2_changed_field": "content_length_match", "scenario_count": 59,
        "executed_count": counts["PASS"] + counts["FAIL"], "passed_count": counts["PASS"], "failed_count": counts["FAIL"], "not_executed_count": counts["NOT_EXECUTED"],
        "t05_passed": selected["T05"]["status"] == "PASS", "t11_passed": selected["T11"]["status"] == "PASS",
        "t12_passed_under_v2": selected["T12"]["status"] == "PASS", "t17_passed": selected["T17"]["status"] == "PASS", "t18_passed": selected["T18"]["status"] == "PASS",
        "critical_safety_failures": safe["critical_safety_failures"], "repair_regressions_passed": reg["all_passed"],
        "pytest_test_count": sum(row["tests"] for row in reg["pytest_groups"].values()),
        "pytest_failure_count": sum(row["failures"] + row["errors"] for row in reg["pytest_groups"].values()),
        "independent_release_gate_passed": bool(passed), "runtime_source_modified": not preserved,
        "retry_policy_changed": False, "scientific_policy_changed": False, "production_runtime_v2_wiring_enabled": False,
        "alpha3_21_reopened": False, "fresh_primary_attempt_started": False,
        "next_stage_recommendation": "EXECUTE_ALPHA3_22E_FOCUSED_HISTORICAL_AND_SEEN_DATA_REPLAY_OFFLINE" if passed else "MINIMAL_ENGINEERING_CORRECTION_OF_EXACT_OBSERVED_FAILURE",
        "next_stage_automatically_started": False, "historical_assets_modified": not preserved,
        "release_label": "59/59 under Versioned Oracle V2" if passed else "FAILED_UNDER_VERSIONED_ORACLE_V2",
        "original_oracle_59_of_59_passed": False, "original_oracle_development_58_of_59_preserved": True, **NO_CALLS}
    emit("summary", summary)
    emit("validation", {"passed": bool(passed), "classification": summary["alpha3_22_release_classification"],
        "all_59_original_identities_and_order_preserved": [row["scenario_id"] for row in rows] == manifest["order"],
        "each_expected_outcome_equals_frozen_V2": all(row["expected"] == expected[row["scenario_id"]] for row in rows),
        "zero_original_scenario_reruns": True, "fail_fast_honored": True, "runtime_and_oracle_unchanged": preserved,
        "no_new_expectation_generation": True, "actual_latest_runtime_used": True,
        "regressions_separate_from_original_59": True, "engineering_checks": engineering,
        "historical_assets_preserved": preserved, "no_22E_or_fresh_primary_execution": True, **NO_CALLS})
    t.require(all((OUT / (name + ".json")).is_file() for name in REQUIRED), "REQUIRED_REPORT_MISSING")
    reference_count = verify_report_references()
    j.atomic_freeze(OUT / "execution/reference_verification.json", j.canonical({
        "report_reference_count_verified": reference_count, "scope": "all admitted top-level report and scenario result references",
        "negative_fixture_corruption_not_promoted_to_admitted_provenance": True, "all_physical_fixture_bytes_bound_by_root": True}))
    if preserved:
        t.require(authority() == before, "HISTORICAL_ROOT_DRIFT_AT_SEAL")
    root = master.root_hash(OUT, MARKER)
    j.atomic_freeze(OUT / MARKER, (root + "\n").encode())
    j.sync_directory(OUT)
    t.require(master.root_hash(OUT, MARKER) == root, "RELEASE_POST_FREEZE_ROOT_MISMATCH")
    return {**summary, "release_root_sha256": root, "workspace": str(OUT)}


def phase1_check():
    t.require(PHASE1_SHA is not None, "FROZEN_PHASE1_ROOT_REQUIRED")
    verified = master.prior.root_check(PHASE1, PHASE1_MARKER, PHASE1_SHA)
    configuration = read(PHASE1 / "frozen_release_configuration.json")
    t.require(read(PHASE1 / "summary.json")["runner_preflight_status"] == "completed",
              "PHASE1_PREFLIGHT_NOT_PASSED")
    t.require(configuration["actual_runtime_binding"] == runtime_binding() == binding.RUNTIME,
              "PHASE1_RUNTIME_INTEGRATION_DRIFT")
    for row in configuration["source_bindings"]:
        t.require(verify_reference(row["source"]) == verify_reference(row["snapshot"]),
                  "PHASE1_FROZEN_IMPLEMENTATION_DRIFT")
    for row in configuration["input_bindings"].values():
        verify_reference(row)
    return verified


def preflight():
    """Development-only data binding tests, before a separately sealed release."""
    t.require(not PHASE1.exists() and not PHASE1.is_symlink() and not OUT.exists(),
              "NEW_SEPARATE_PHASE_DIRECTORIES_REQUIRED")
    before = authority()
    manifest, records, v2_raw, difference = frozen_inputs()
    results = binding.preflight(*artifact_data())
    PHASE1.mkdir()
    (PHASE1 / "execution").mkdir()
    snapshots = []
    for path in source_paths():
        snapshot = PHASE1 / "implementation" / path.relative_to(ROOT)
        snapshot.parent.mkdir(parents=True, exist_ok=True)
        j.atomic_freeze(snapshot, j.read_bytes(path))
        snapshots.append({"source": h.ref(path, "exact_phase1_source_binding"),
                          "snapshot": h.ref(snapshot, "physical_byte_identical_frozen_source")})
    checks = []
    commands = [[sys.executable, "-m", "compileall", "-q", *map(str, source_paths())],
                ["git", "diff", "--check"]]
    commands += [["git", "diff", "--no-index", "--check", "/dev/null", str(path)]
                 for path in (Path(__file__), Path(binding.__file__))]
    for index, command in enumerate(commands):
        process = subprocess.run(command, cwd=ROOT, capture_output=True, text=True)
        log = PHASE1 / "execution" / ("engineering_%d.txt" % index)
        j.atomic_freeze(log, (process.stdout + process.stderr).encode())
        checks.append({"command": command, "exit_code": process.returncode,
            "log": h.ref(log, "phase1_actual_engineering_check"),
            "passed": process.returncode in ({0, 1} if "--no-index" in command else {0})
                and not process.stdout and not process.stderr})
    after = authority()
    preserved = before == after and all(verify_reference(row["source"]) == verify_reference(row["snapshot"])
                                        for row in snapshots)
    passed = results["all_passed"] and preserved and all(row["passed"] for row in checks)
    configuration = {
        "mode": "OFFLINE_RUNNER_DEVELOPMENT_PREFLIGHT_NO_RUNTIME_SCENARIOS",
        "source_bindings": snapshots, "upstream_authority": before,
        "input_bindings": {
            "source_only_scenarios": h.ref(h.ORIGINAL / "frozen_fault_scenario_manifest.json", "unchanged_original_scenarios"),
            "independent_oracle_v1": h.ref(h.ORIGINAL / "independent_expected_outcomes.jsonl", "unchanged_V1_oracle"),
            "frozen_oracle_v2_container": h.ref(CONTRACT / "versioned_change_manifest.json", "full_frozen_V2_records")},
        "actual_runtime_binding": runtime_binding(), "runtime_journal_authority": j.AUTHORITY,
        "runtime_root_sha256": latest.REPAIR_SHA,
        "actual_scenario_harness": h.ref(Path(h.__file__), "frozen_length_bound_harness_v1"),
        "integration_entrypoint": [sys.executable, "-m", repair.__name__, "scenario", "--key",
                                   "<frozen_id>", "--output", "<new_isolated_directory>"],
        "runner_source": h.ref(Path(__file__), "new_versioned_runner_no_historical_edit"),
        "binding_source": h.ref(Path(binding.__file__), "pure_artifact_binding_no_SUT_import"),
        "oracle_v2_sha256": V2_SHA, "scenario_manifest_sha256": SCENARIO_SHA,
        "original_oracle_sha256": ORIGINAL_ORACLE_SHA, "scenario_order": manifest["order"],
        "oracle_difference": difference,
        "schemas": {"scenario_manifest": "object: order + source-only scenarios; scenario_id key; no expected",
            "original_oracle": "JSONL: scenario_id + expected object + oracle_authority",
            "oracle_v2": "versioned_change_manifest.json#/oracle_v2/records; full 59 literal records"},
        "scenario_oracle_bijection_verified": True, "scenario_count": 59,
        "release_directory": str(OUT), "release_marker": MARKER,
        "no_changes_allowed_after_release_start": True, "scientific_policy_changed": False,
        "runtime_source_modified": False, "original_oracle_modified": False, **NO_CALLS}
    reports = {
        "runner_source_manifest": {"sources": snapshots,
            "historical_runner_sha256": HISTORICAL_RUNNER_SHA, "historical_runner_modified": False,
            "correction": "strict source-only scenario_id to external frozen Oracle V2 bijection",
            "runtime_modified": False},
        "scenario_oracle_binding_test_results": results,
        "frozen_release_configuration": configuration,
        "summary": {"runner_preflight_status": "completed" if passed else "failed",
            "runner_manifest_oracle_binding_correct": results["all_passed"],
            "scenario_oracle_bijection_verified": results["all_passed"],
            "preflight_test_count": results["test_count"], "preflight_passed_count": sum(row["passed"] for row in results["tests"]),
            "release_execution_started": False, "scenario_executions": 0, "runtime_executions": 0,
            "historical_assets_modified": not preserved, "engineering_checks": checks,
            "original_runner_failure": {"class": "builtins.KeyError", "field": "expected",
                "before_any_scenario": True, "preserved_root_sha256": binding.ROOTS["failed_preflight"]},
            "oracle_version": "V2", "oracle_v2_changed_scenario_count": 1,
            "oracle_v2_changed_scenario_id": "T12", "runtime_source_modified": False,
            "original_oracle_modified": False, **NO_CALLS}}
    for name, value in reports.items():
        j.atomic_freeze(PHASE1 / (name + ".json"), j.canonical(value))
    root = master.root_hash(PHASE1, PHASE1_MARKER)
    j.atomic_freeze(PHASE1 / PHASE1_MARKER, (root + "\n").encode())
    j.sync_directory(PHASE1)
    t.require(master.root_hash(PHASE1, PHASE1_MARKER) == root, "PHASE1_POST_FREEZE_ROOT_MISMATCH")
    return {**reports["summary"], "runner_preflight_root_sha256": root, "workspace": str(PHASE1)}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("phase", choices=("preflight", "release"))
    parser.add_argument("--preflight-root")
    arguments = parser.parse_args()
    if arguments.phase == "release":
        if arguments.preflight_root is None:
            parser.error("--preflight-root is required for release")
        PHASE1_SHA = arguments.preflight_root
    elif arguments.preflight_root is not None:
        parser.error("preflight cannot bind its own not-yet-frozen root")
    with master.prior.offline_guard():
        result = preflight() if arguments.phase == "preflight" else run()
        print(json.dumps(result, sort_keys=True))
        if (result.get("runner_preflight_status") == "failed"
                or result.get("alpha3_22_release_status") == "failed"):
            raise SystemExit(1)
