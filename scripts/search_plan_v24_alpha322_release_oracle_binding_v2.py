"""Pure artifact binding and negative preflight; never imports or executes a SUT."""

import copy
import hashlib
import json


SCENARIO_SHA = "aed33640b5a88badd5a785b41019158ca369b656f20a5a150713b2e8f8eba23b"
ORIGINAL_SHA = "b1d452438341fd2a01262f09a75649169dd726da119371b30388c4a464d6d817"
V2_SHA = "682e63ebbfeeca9e932db3f73fcadb8ab02181b7e8cbfc639f9fc4440bf77645"
ROOTS = {
    "failed_preflight": "555e11d84e4b5e87e7bb874f3d7e3632c04c6a6ab71d96cd9162ee4e877cbb1a",
    "oracle_contract": "4301d3c0607796d990278f7529350ecdb515b99964975aabf0d8d014ec68c8e8",
    "runtime_development": "d5314eb4b2387cad9a7ab5318ee0ed6df7bf1b47a230ad97702bfc7035a05a04",
}
RUNTIME = {
    "journal": "code_engine.append_only_attempt_journal_v2_length_bound_v1",
    "resume": "code_engine.deterministic_resume_planner_v2_length_bound_v1",
    "barrier": "code_engine.stage_barrier_snapshot_v2_length_bound_v1",
    "lifecycle": "code_engine.transport_lifecycle_v2",
    "observability": "code_engine.transport_observability_v1",
    "mapper": "code_engine.transport_exception_mapping_v2",
    "phase_binding": "code_engine.transport_failure_phase_binding_v2_r2",
    "validator_integration": "scripts.search_plan_v24_alpha322_length_bound_t11_integration_v1",
    "validator_outcome_adapter": "code_engine.validator_outcome_adapter_length_bound_v1",
    "runtime_identity": "code_engine.runtime_identity_capture_r2",
    "scenario_harness": "scripts.search_plan_v24_alpha322_length_bound_harness_v1",
    "integration_entrypoint": "scripts.run_search_plan_v24_alpha322_body_length_repair_offline:scenario_child",
}
PATCH = [{"scenario_id": "T12", "record_index": 11,
          "json_pointer": "/expected/content_length_match", "from": "UNAVAILABLE", "to": "MISMATCH"}]


class BindingError(ValueError):
    """Fail-closed input contract rejection, without defaults or repairs."""


def require(condition, reason):
    if not condition:
        raise BindingError(reason)


def canonical(value):
    return (json.dumps(value, ensure_ascii=False, sort_keys=True,
                       separators=(",", ":"), allow_nan=False) + "\n").encode()


def parse(raw):
    def pairs(items):
        result = {}
        for key, value in items:
            require(key not in result, "DUPLICATE_JSON_KEY")
            result[key] = value
        return result
    def invalid_constant(value):
        raise BindingError("NONFINITE_JSON_CONSTANT:" + value)
    try:
        return json.loads(raw, object_pairs_hook=pairs, parse_constant=invalid_constant)
    except (ValueError, TypeError) as exc:
        if isinstance(exc, BindingError):
            raise
        raise BindingError("MALFORMED_JSON") from exc


def records(values, label):
    require(type(values) is list, "MALFORMED_" + label)
    for row in values:
        require(type(row) is dict and set(row) == {"scenario_id", "expected", "oracle_authority"}
                and type(row["scenario_id"]) is str and bool(row["scenario_id"])
                and type(row["expected"]) is dict and bool(row["expected"])
                and type(row["oracle_authority"]) is str and bool(row["oracle_authority"]),
                "MALFORMED_" + label)
    ids = [row["scenario_id"] for row in values]
    require(len(ids) == len(set(ids)), "DUPLICATE_" + label + "_ID")
    return ids


def bind(manifest, original_raw, change):
    """Bind independent literal outcomes to source-only IDs; no mutation."""
    require(type(manifest) is dict and type(manifest.get("scenarios")) is list
            and type(manifest.get("order")) is list, "MALFORMED_SCENARIO_MANIFEST")
    scenarios = manifest["scenarios"]
    require(all(type(row) is dict and type(row.get("scenario_id")) is str
                and "expected" not in row for row in scenarios), "MALFORMED_SOURCE_ONLY_SCENARIO")
    ids = [row["scenario_id"] for row in scenarios]
    require(len(ids) == len(set(ids)), "DUPLICATE_SCENARIO_ID")
    require(len(ids) == 59 and manifest["order"] == ids
            and manifest.get("stop_on_first_critical_failure") is True, "SCENARIO_COUNT_ORDER_OR_FAIL_FAST")
    lines = original_raw.splitlines(keepends=True)
    original = [parse(line) for line in lines]
    old_ids = records(original, "V1_ORACLE")
    require(old_ids == ids, "V1_ORACLE_BIJECTION_OR_ORDER")
    require(type(change) is dict and type(change.get("oracle_v2")) is dict, "MALFORMED_V2_ORACLE")
    v2 = change["oracle_v2"]
    require(set(v2) == {"version", "records", "serialization", "jsonl_sha256", "changes",
                        "other_58_records_byte_identical", "record_count"}, "UNSUPPORTED_V2_ORACLE_STRUCTURE")
    new_ids = records(v2["records"], "V2_ORACLE")
    require(not set(ids) - set(new_ids), "MISSING_V2_ORACLE_ENTRY")
    require(not set(new_ids) - set(ids), "EXTRA_V2_ORACLE_ENTRY")
    require(new_ids == ids and len(new_ids) == v2["record_count"] == 59, "V2_ORACLE_COUNT_OR_ORDER")
    require(v2["version"] == "VersionedOracleV2_T12ObservedByteComparison"
            and v2["serialization"] == "concatenate canonical JSON records with one LF per record; original order"
            and v2["other_58_records_byte_identical"] is True, "UNSUPPORTED_V2_ORACLE_CONTRACT")
    require(v2["changes"] == PATCH, "INCORRECT_V2_PATCH")
    changed = []
    for old, new, line in zip(original, v2["records"], lines):
        if canonical(new) != line:
            changed.append(new["scenario_id"])
    require(changed == ["T12"], "V2_DIFFERENCE_COUNT_OR_ID")
    old, new = original[11], v2["records"][11]
    require(old["scenario_id"] == new["scenario_id"] == "T12"
            and old["expected"].get("content_length_match") == "UNAVAILABLE"
            and new["expected"].get("content_length_match") == "MISMATCH", "V2_PATCH_VALUE_OR_POSITION")
    projection = copy.deepcopy(new)
    projection["expected"]["content_length_match"] = "UNAVAILABLE"
    require(canonical(projection) == lines[11], "V2_EXTRA_DIFFERENCE")
    raw = b"".join(canonical(row) for row in v2["records"])
    require(hashlib.sha256(raw).hexdigest() == v2["jsonl_sha256"] == V2_SHA, "WRONG_V2_ORACLE_HASH")
    return v2["records"], raw


def authority(scenario_raw, original_raw, v2_raw, observed_roots, runtime):
    require(hashlib.sha256(scenario_raw).hexdigest() == SCENARIO_SHA, "WRONG_SCENARIO_HASH")
    require(hashlib.sha256(original_raw).hexdigest() == ORIGINAL_SHA, "WRONG_V1_ORACLE_HASH")
    require(hashlib.sha256(v2_raw).hexdigest() == V2_SHA, "WRONG_V2_ORACLE_HASH")
    require(observed_roots == ROOTS, "WRONG_FROZEN_ROOT_HASH")
    require(runtime == RUNTIME, "WRONG_RUNTIME_INTEGRATION_VERSION")


def preflight(scenario_raw, original_raw, change, observed_roots, runtime):
    """A-J use data-only perturbations, never runtime or scenario calls."""
    manifest = parse(scenario_raw)
    rows = []
    def case(key, expected_rejection, call):
        try:
            call()
            actual = None
        except BindingError as exc:
            actual = str(exc)
        rows.append({"test_id": key, "expected_rejection": expected_rejection,
                     "actual_rejection": actual, "passed": actual == expected_rejection})
    def mutated(mutator):
        m, c = copy.deepcopy(manifest), copy.deepcopy(change)
        mutator(m, c)
        return lambda: bind(m, original_raw, c)
    _, v2_raw = bind(manifest, original_raw, change)
    def valid():
        bound, raw = bind(manifest, original_raw, change)
        authority(scenario_raw, original_raw, raw, observed_roots, runtime)
        require(len({row["scenario_id"]: row["expected"] for row in bound}) == 59, "BINDING_NOT_BIJECTIVE")
    case("A_VALID_BINDING", None, valid)
    case("B_MISSING_ORACLE_ENTRY", "MISSING_V2_ORACLE_ENTRY",
         mutated(lambda m, c: c["oracle_v2"]["records"].pop()))
    case("C_EXTRA_ORACLE_ENTRY", "EXTRA_V2_ORACLE_ENTRY", mutated(
        lambda m, c: c["oracle_v2"]["records"].append(dict(c["oracle_v2"]["records"][0], scenario_id="EXTRA"))))
    case("D_DUPLICATE_SCENARIO_ID", "DUPLICATE_SCENARIO_ID", mutated(
        lambda m, c: m["scenarios"][1].update(scenario_id=m["scenarios"][0]["scenario_id"])))
    case("E_DUPLICATE_ORACLE_ID", "DUPLICATE_V2_ORACLE_ID", mutated(
        lambda m, c: c["oracle_v2"]["records"].append(copy.deepcopy(c["oracle_v2"]["records"][0]))))
    case("F_UNSUPPORTED_STRUCTURE", "UNSUPPORTED_V2_ORACLE_STRUCTURE", mutated(
        lambda m, c: c["oracle_v2"].update(unsupported_field=True)))
    case("F_MALFORMED_RECORDS", "MALFORMED_V2_ORACLE", mutated(
        lambda m, c: c["oracle_v2"].update(records={})))
    case("G_INCORRECT_PATCH_FIELD", "INCORRECT_V2_PATCH", mutated(
        lambda m, c: c["oracle_v2"]["changes"][0].update(json_pointer="/expected/body_complete")))
    case("H_MULTIPLE_DIFFERENCES", "V2_DIFFERENCE_COUNT_OR_ID", mutated(
        lambda m, c: c["oracle_v2"]["records"][0]["expected"].update(content_length_match="MISMATCH")))
    wrong_roots = dict(observed_roots, oracle_contract="0" * 64)
    case("I_WRONG_ROOT_HASH", "WRONG_FROZEN_ROOT_HASH", lambda:
         authority(scenario_raw, original_raw, v2_raw, wrong_roots, runtime))
    case("I_WRONG_ORACLE_HASH", "WRONG_V2_ORACLE_HASH", lambda:
         authority(scenario_raw, original_raw, v2_raw + b"\n", observed_roots, runtime))
    wrong_runtime = dict(runtime, journal="code_engine.append_only_attempt_journal_v2")
    case("J_WRONG_RUNTIME_VERSION", "WRONG_RUNTIME_INTEGRATION_VERSION", lambda:
         authority(scenario_raw, original_raw, v2_raw, observed_roots, wrong_runtime))
    return {"tests": rows, "test_count": len(rows), "all_passed": all(row["passed"] for row in rows),
            "required_categories": "ABCDEFGHIJ", "scenario_executions": 0, "runtime_executions": 0,
            "expectations_from_SUT": False, "data_perturbations_only": True}
