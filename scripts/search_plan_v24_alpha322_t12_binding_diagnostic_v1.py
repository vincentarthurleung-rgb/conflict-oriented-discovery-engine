"""Offline evidence-only T12 adapter; never changes frozen transport inputs."""

import ast
import http.client
import io
import json
import sys
import traceback
from pathlib import Path

from scripts import run_search_plan_v24_alpha322dr2_full_independent_revalidation_offline as release

h, j, t, ROOT = release.h, release.j, release.t, release.ROOT
RUNTIME_ACTIVATION_ALLOWED = False
CLASSIFICATION = "FROZEN_SCENARIO_OR_ORACLE_CONFLICT"
RELEASE_SHA = "210b537622dca9f47a8fba7763cf13be17ab27e3e7e5668a4728e909f9a9ed65"
ADDENDUM = ROOT / "runs/20261010_search_plan_v24_dev_alpha3_22dr2_reporting_addendum.json"
ADDENDUM_SHA = "18d88ae6a8b15403febf81ba50ce04a8dbbd56d941e299cbbe7af6bd1e30e937"


def authority():
    result = release.authority()
    result["failed_DR2"] = release.master.prior.root_check(release.OUT, release.MARKER, RELEASE_SHA)
    bindings = j.strict_json(j.read_bytes(release.OUT / "runtime_component_binding.json"))["new_validation_sources"]
    for source in bindings:
        raw = j.read_bytes(ROOT / source["artifact_path"])
        t.require(j.sha(raw) == source["sha256"] and raw == j.read_bytes(
            release.OUT / "implementation" / Path(source["artifact_path"]).name), "FROZEN_DR2_SOURCE_DRIFT")
    result["frozen_DR2_sources"] = bindings
    summary = j.strict_json(j.read_bytes(release.OUT / "summary.json"))
    t.require([summary[key] for key in ("executed_scenario_count", "passed_scenario_count", "failed_scenario_count",
                                       "not_executed_scenario_count", "first_failed_scenario")] == [12, 11, 1, 47, "T12"],
              "HISTORICAL_DR2_OUTCOME_DRIFT")
    t.require(j.sha(j.read_bytes(ADDENDUM)) == ADDENDUM_SHA, "REPORTING_ADDENDUM_DRIFT")
    result["reporting_addendum"] = h.ref(ADDENDUM, "unchanged_historical_reporting_addendum")
    return result


def source_findings():
    manifest, expected = release.prior.frozen_inputs()
    scenario = next(row for row in manifest["scenarios"] if row["scenario_id"] == "T12")
    original = ROOT / "scripts/run_search_plan_v24_alpha322d_independent_fault_injection_offline.py"
    tree = ast.parse(j.read_bytes(original))
    fault_class = next(node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == "BoundFaultFile")
    literals = [node.value for node in ast.walk(fault_class) if isinstance(node, ast.Constant) and isinstance(node.value, bytes)]
    headers = next(value for value in literals if value.startswith(b"HTTP/1.1"))
    t.require(headers == b"HTTP/1.1 200 OK\r\nContent-Length: 50\r\n\r\n<article>", "FROZEN_HEADER_SOURCE_DRIFT")
    oracle_tree = ast.parse(j.read_bytes(Path(h.oracle.__file__)))
    call = next(node for node in ast.walk(oracle_tree) if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                and node.func.id == "transport_spec" and node.args and isinstance(node.args[0], ast.Constant)
                and node.args[0].value == "T12")
    t.require(not any(keyword.arg == "length" for keyword in call.keywords), "T12_ORACLE_SOURCE_DRIFT")
    return {"original_definition": scenario, "original_expected": expected["T12"],
        "scenario_definition_explicit_headers": None,
        "scenario_does_not_require_absent_or_untrusted_length": True,
        "header_authority": "original frozen scenario manifest source_bindings -> BoundFaultFile.__init__",
        "actual_frozen_header_bytes": headers.split(b"\r\n\r\n")[0].decode("ascii"),
        "original_header_source": h.ref(original, "original_frozen_actual_external_fixture"),
        "oracle_source": h.ref(Path(h.oracle.__file__), "original_literal_oracle_default_length"),
        "master_body_contract": h.ref(release.master.OUT / "response_body_completion_semantics.json", "frozen_same_representation_length_rule"),
        "runtime_body_contract": h.ref(Path(t.__file__), "unchanged_frozen_22A_body_semantics"),
        "oracle_length_default_used": "UNAVAILABLE", "explicit_T12_length_override": False,
        "original_fault_type": "builtins.RuntimeError", "original_fault_phase": "RESPONSE_BODY_READING"}


def actual_read_trace():
    """Observe the exact frozen HTTPResponse/file without changing its headers."""
    response = http.client.HTTPResponse(h.LocalFileHolder(h.BoundFaultFile(RuntimeError, "body")))
    returned, exception = None, None
    try:
        response.begin()
        headers = dict(response.getheaders())
        expected_length = response.length
        try:
            returned = response.read()
        except RuntimeError as exc:
            exception = exc
    finally:
        response.close()
    t.require(type(exception) is RuntimeError and returned is None, "ORIGINAL_UNKNOWN_READ_FAULT_NOT_OBSERVED")
    raw = exception.partial if hasattr(exception, "partial") else b""
    completion = t.assess_body_completion(raw, read_returned_normally=False,
        interruption_class=t.SemanticFailure.UNKNOWN_RUNTIME_FAILURE, expected_content_length=expected_length,
        expected_length_trustworthy=True, byte_representation=t.ByteRepresentation.WIRE,
        expected_length_representation=t.ByteRepresentation.WIRE, timestamp=h.NOW,
        interruption_reason="observed actual frozen RuntimeError before read return")
    return {"operation": "actual http.client.HTTPResponse.begin/read over unchanged frozen BoundFaultFile",
        "headers": headers, "expected_content_length": expected_length, "response_status": response.status,
        "headers_received_before_exception": True, "read_returned_normally": returned is not None,
        "read_return_value": None, "exception_class": type(exception).__module__ + "." + type(exception).__qualname__,
        "exception_before_body_completion": True, "exception_has_partial": hasattr(exception, "partial"),
        "recoverable_bytes": len(raw), "zero_bytes_mean_valid_eof": False,
        "zero_bytes_mean": "no recoverable bytes returned by the raised read operation; not proof that no wire bytes ever arrived",
        "byte_representation": completion.byte_representation.value,
        "expected_length_representation": completion.expected_length_representation.value,
        "decoded_or_decompressed_transform_applied": False, "length_comparison_applicable_under_frozen_22A": True,
        "content_length_match": completion.content_length_match,
        "semantic_failure": completion.semantic_failure.value, "body_state": completion.body_completion_state.value,
        "no_rule_makes_comparison_unavailable_merely_because_read_raised": True}


def normal_empty_counterexample(directory):
    directory.mkdir()
    raw = io.BytesIO(b"").read()  # actual normal configured local read, not claimed to be HTTPResponse.read
    completion = t.assess_body_completion(raw, read_returned_normally=True, expected_content_length=50,
        expected_length_trustworthy=True, byte_representation=t.ByteRepresentation.WIRE,
        expected_length_representation=t.ByteRepresentation.WIRE, timestamp=h.NOW)
    artifact = t.RawArtifactStoreV1(directory / "raw").freeze_bytes("response.bin", raw)
    response = t.FrozenTransportResponseV2(t.AttemptContextV1("normal-empty:OA:0", j.sha(b"normal-empty"), 1),
                                          completion, artifact, True)
    invoked = []
    rejection = None
    try:
        t.guarded_parse(response, lambda body: invoked.append(body))
    except t.TransportContractError as exc:
        rejection = str(exc)
    return {"configured_read": "local BytesIO.read; normal-return body-completion unit counterexample",
        "not_claimed_as_normal_bound_HTTPResponse_read": True, "read_returned_normally": True,
        "expected_content_length": 50, "actual_body_length": len(raw), "expected_length_trustworthy": True,
        "byte_representation": completion.byte_representation.value,
        "expected_length_representation": completion.expected_length_representation.value,
        "content_length_match": completion.content_length_match, "semantic_failure": completion.semantic_failure.value,
        "body_state": completion.body_completion_state.value, "parser_invocations": len(invoked),
        "parser_rejection": rejection, "raw_artifact": dict(artifact.__dict__),
        "passed": completion.content_length_match == "MISMATCH" and completion.semantic_failure == t.SemanticFailure.RESPONSE_BODY_LENGTH_MISMATCH
                  and completion.body_completion_state != t.BodyState.COMPLETE and not invoked
                  and rejection == "PARTIAL_OR_UNAUTHORITATIVE_RESPONSE_QUARANTINED"}


def project_recovery(rows):
    """Only the new reporting projection changes; exact frozen IDs, no aliases."""
    t.require(type(rows) is list, "REC_REPORT_RECORD_LIST_REQUIRED")
    indexed = {}
    for row in rows:
        t.require(type(row) is dict and row.get("fixture_id") not in indexed, "REC_REPORT_DUPLICATE_ID")
        t.require(type(row.get("passed")) is bool, "REC_REPORT_BOOLEAN_REQUIRED")
        indexed[row["fixture_id"]] = row
    t.require(set(indexed) == {"R0_REC01", "R0_REC02"}, "REC_REPORT_EXACT_IDENTITIES_REQUIRED")
    return {"rec01_passed": indexed["R0_REC01"]["passed"], "rec02_passed": indexed["R0_REC02"]["passed"]}


def focused_execution(directory):
    directory.mkdir()
    manifest, expected = release.prior.frozen_inputs()
    rows = {}
    for key in ("T12", "T05", "T11"):
        scenario = next(row for row in manifest["scenarios"] if row["scenario_id"] == key)
        row = h.transport_scenario(scenario, directory / key)
        differences = h.compare(expected[key], row["actual"])
        row.update(expected=expected[key], mismatches=differences, status="FAIL" if differences or row.get("durable_terminal_error") else "PASS")
        rows[key] = row
    return {"focused_development_only": True, "full_matrix_execution": False,
        "T12": rows["T12"], "T05": rows["T05"], "T11": rows["T11"],
        "actual_frozen_read_trace": actual_read_trace(),
        "normal_empty_counterexample": normal_empty_counterexample(directory / "normal-empty"),
        "original_T12_oracle_passed": rows["T12"]["status"] == "PASS",
        "diagnosis_consistency_passed": rows["T12"]["mismatches"] == [
            {"field": "content_length_match", "expected": "UNAVAILABLE", "actual": "MISMATCH"}],
        "T05_full_path_passed": release.prior.t05_check(rows["T05"])["passed"],
        "T11_full_path_passed": release.t11_check(rows["T11"])["passed"]}


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--scenario", required=True)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    with release.master.prior.offline_guard():
        scenario = next(row for row in h.frozen_scenarios() if row["scenario_id"] == args.scenario)
        handlers = {"TRANSPORT": h.transport_scenario, "CRASH": h.crash_scenario,
                    "JOURNAL_INTEGRITY": h.integrity_scenario, "ACTIVATION_INTEGRITY": h.integrity_scenario,
                    "INTEGRATED": h.integrated_scenario}
        try:
            result = handlers[scenario["category"]](scenario, args.output)
        except Exception as exc:
            result = {"scenario_id": args.scenario, "category": scenario["category"], "actual": {},
                "execution_error": {"qualified_class": type(exc).__module__ + "." + type(exc).__qualname__,
                    "message": h.o.SecretRedactorV1((h.SECRET,)).text(str(exc)),
                    "traceback": h.o.SecretRedactorV1((h.SECRET,)).text(traceback.format_exc())}}
        print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
