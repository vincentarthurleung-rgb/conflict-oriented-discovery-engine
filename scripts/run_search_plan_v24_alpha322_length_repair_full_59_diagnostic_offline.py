"""One authorized development matrix over the byte-frozen length repair.

No runtime changes, new oracle, release qualification or historical writes.
All original scenarios execute in isolated processes and directories once.
"""

import argparse
import json
import subprocess
import sys
from pathlib import Path

from scripts import run_search_plan_v24_alpha322_body_length_repair_offline as repair

j, t, h, ROOT = repair.j, repair.t, repair.h, repair.ROOT
OUT = ROOT / "runs/20261010_search_plan_v24_dev_alpha3_22_body_length_repair_full_59_development_diagnostics_offline"
MARKER = "search_plan_v24_dev_alpha3_22_length_repair_full_59_development_sha256"
REPAIR_SHA = "bb834355a9dbb3e560f3c3ca88939696923cbc226f60179f18ee42e40a8330e5"
NO_CALLS = dict(repair.NO_CALLS)
COPIES = ("body_length_contract_binding", "t12_t17_t18_focused_results",
          "length_representation_negative_tests", "regression_results")


def emit(name, value):
    return j.atomic_freeze(OUT / (name + ".json"), j.canonical(value))


def load(name):
    return j.strict_json(j.read_bytes(OUT / (name + ".json")))


def authority():
    value = repair.authority()
    repair.sources_unchanged()
    value["frozen_body_length_repair"] = repair.previous.d.release.master.prior.root_check(repair.OUT, repair.MARKER, REPAIR_SHA)
    value["frozen_repair_source_manifest"] = h.ref(repair.OUT / "source_manifest.json", "unchanged_14_source_repair_bindings")
    prior = repair.load("summary")
    t.require([prior[key] for key in ("development_executed_count", "development_passed_count", "development_failed_count",
                                     "development_not_executed_count")] == [0, 0, 0, 59], "HISTORICAL_FOCUSED_ONLY_ACCOUNTING_DRIFT")
    focus = repair.load("t12_t17_t18_focused_results")["scenarios"]
    t.require(not focus["T12"]["passed"] and focus["T17"]["passed"] and focus["T18"]["passed"], "FOCUSED_AUTHORITY_DRIFT")
    return value


def sources_unchanged():
    repair.sources_unchanged()
    for row in load("source_manifest")["sources"]:
        raw = j.read_bytes(ROOT / row["artifact_path"])
        t.require(j.sha(raw) == row["sha256"] and raw == j.read_bytes(OUT / "implementation" / Path(row["artifact_path"]).name),
                  "MATRIX_FROZEN_SOURCE_DRIFT")


def execute():
    t.require(not OUT.exists() and not OUT.is_symlink(), "NEW_ISOLATED_DEVELOPMENT_DIRECTORY_REQUIRED")
    before = authority()
    manifest, oracle = repair.previous.d.release.prior.frozen_inputs()
    OUT.mkdir()
    for name in ("implementation", "execution", "scenarios"):
        (OUT / name).mkdir()
    sources = repair.load("source_manifest")["sources"] + [h.ref(Path(__file__), "new_execution_and_reporting_wrapper_only")]
    for row in sources:
        j.atomic_freeze(OUT / "implementation" / Path(row["artifact_path"]).name, j.read_bytes(ROOT / row["artifact_path"]))
    emit("source_manifest", {"sources": sources, "frozen_repair_root_sha256": REPAIR_SHA,
        "runtime_sources_changed": False, "new_source_scope": "isolated matrix execution and reporting only",
        "runtime_component_count": len(repair.COMPONENTS), "frozen_repair_source_count": 14})
    emit("root_verification", before)
    emit("matrix_execution_authorization", {
        "question": "若修复后 T17/T18 通过，但 T12 仍是冻结 oracle/22A 冲突，是否授权保留 T12 为 FAIL，继续在新的隔离目录执行全部 59 项开发诊断？",
        "user_answer": "保留 T12 冲突，继续全部 59 项开发诊断",
        "mode": "OFFLINE_DEVELOPMENT_NOT_INDEPENDENT_RELEASE_VALIDATION",
        "T12_conflict_does_not_block_new_isolated_matrix": True,
        "T12_input_or_oracle_change_authorized": False, "validation_contract_change_authorized": False,
        "original_order": manifest["order"], "one_execution_per_matrix_identity": True,
        "continue_ordinary_isolated_failures": True, "stop_affected_scope_on_unsafe_shared_state": True,
        "no_edits_during_matrix": True, "independent_release_gate_passed": False, **NO_CALLS})
    copies = []
    for name in COPIES:
        source, destination = repair.OUT / (name + ".json"), OUT / (name + ".json")
        j.atomic_freeze(destination, j.read_bytes(source))
        t.require(j.read_bytes(source) == j.read_bytes(destination), "FROZEN_REPAIR_EVIDENCE_COPY_MISMATCH")
        copies.append({"source": h.ref(source, "previously_frozen_focused_or_regression_evidence_not_reexecuted"),
                       "copy": h.ref(destination, "physical_byte_identical_copy"), "byte_identical": True})
    emit("reused_frozen_evidence", {"copies": copies, "fresh_full_matrix_results_not_substituted_from_history": True,
        "focused_and_pytest_regressions_reexecuted_in_this_continuation": False})
    rows = []
    unsafe_reason = None
    for scenario in manifest["scenarios"]:
        key = scenario["scenario_id"]
        if unsafe_reason is None:
            try:
                sources_unchanged()
            except t.TransportContractError as exc:
                unsafe_reason = str(exc)
        if unsafe_reason is not None:
            rows.append({"scenario_id": key, "category": scenario["category"], "expected": oracle[key],
                "actual": None, "status": "NOT_EXECUTED", "execution_status": "NOT_EXECUTED",
                "first_divergence": unsafe_reason, "failure_category": "ENVIRONMENT_LIMITATION",
                "reason": "unsafe shared source drift; no subsequent scenario dispatched"})
            continue
        command = [sys.executable, "-m", repair.__name__, "scenario", "--key", key,
                   "--output", str(OUT / "scenarios" / key)]
        process = subprocess.run(command, cwd=ROOT, capture_output=True, text=True)
        log = OUT / "execution" / (key + ".txt")
        j.atomic_freeze(log, (process.stdout + process.stderr).encode())
        try:
            row = j.strict_json(process.stdout.encode())
            t.require(process.returncode == 0 and type(row) is dict and row.get("scenario_id") == key,
                      "MATRIX_CHILD_INFRASTRUCTURE_FAILURE")
        except (ValueError, TypeError):
            row = {"scenario_id": key, "category": scenario["category"], "actual": {},
                   "execution_error": {"qualified_class": "MATRIX_CHILD_INFRASTRUCTURE_FAILURE",
                                       "message": process.stderr, "exit_code": process.returncode}}
        mismatches = h.compare(oracle[key], row.get("actual") or {})
        error = row.get("durable_terminal_error") or row.get("execution_error")
        failed = bool(error or mismatches)
        conflict = key == "T12" and not error and mismatches == [
            {"field": "content_length_match", "expected": "UNAVAILABLE", "actual": "MISMATCH"}]
        first = {"operation": "durable_terminal_verification" if row.get("durable_terminal_error") else "scenario_execution",
                 "error": error} if error else ({"operation": "unchanged_original_oracle_comparison", **mismatches[0]} if mismatches else None)
        row.update(expected=oracle[key], mismatches=mismatches, status="FAIL" if failed else "PASS",
            execution_status="EXECUTED", first_divergence=first,
            failure_category="FROZEN_SCENARIO_OR_ORACLE_CONFLICT" if conflict else "UNRESOLVED" if failed else None,
            root_cause_group="T12_FROZEN_LENGTH_EVIDENCE_ORACLE_CONFLICT" if conflict else None,
            actual_execution_command=command, reproduction_command=command,
            reproduction_note="Future reproductions require a NEW output directory; no scenario reruns occur in this matrix.",
            subprocess_exit_code=process.returncode, execution_log=h.ref(log, "unaltered_fresh_isolated_scenario_output"))
        rows.append(row)
        j.atomic_freeze(OUT / "execution" / (key + ".json"), j.canonical(row))
        print(key + ": " + row["status"], flush=True)
    j.atomic_freeze(OUT / "full_59_development_results.jsonl", b"".join(j.canonical(row) for row in rows))
    after = authority()
    sources_unchanged()
    t.require(j.canonical(before) == j.canonical(after), "UPSTREAM_AUTHORITY_CHANGED_DURING_MATRIX")
    emit("execution_complete", {"scenario_count": len(rows), "executed_count": sum(row["execution_status"] == "EXECUTED" for row in rows),
        "passed_count": sum(row["status"] == "PASS" for row in rows), "failed_count": sum(row["status"] == "FAIL" for row in rows),
        "not_executed_count": sum(row["status"] == "NOT_EXECUTED" for row in rows),
        "no_scenario_reruns": True, "sources_and_upstream_roots_unchanged": True,
        "ordinary_isolated_failures_did_not_abort_matrix": True, "unsafe_shared_state": unsafe_reason})
    return load("execution_complete")


def verify_references():
    verified = set()
    def walk(value):
        if isinstance(value, dict):
            if "artifact_path" in value and "sha256" in value:
                path = Path(value["artifact_path"])
                path = path if path.is_absolute() else ROOT / path
                raw = j.read_bytes(path)
                t.require(j.sha(raw) == value["sha256"], "REPORT_REFERENCE_HASH_MISMATCH:" + str(path))
                if "byte_count" in value:
                    t.require(len(raw) == value["byte_count"], "REPORT_REFERENCE_LENGTH_MISMATCH")
                verified.add((str(path), value["sha256"]))
            for child in value.values():
                walk(child)
        elif isinstance(value, list):
            for child in value:
                walk(child)
    for path in OUT.glob("*.json*"):
        raw = j.read_bytes(path)
        if path.suffix == ".jsonl":
            for line in raw.splitlines():
                walk(j.strict_json(line))
        else:
            walk(j.strict_json(raw))
    return len(verified)


def freeze():
    t.require((OUT / "execution_complete.json").is_file() and not (OUT / MARKER).exists(), "COMPLETED_UNSEALED_MATRIX_REQUIRED")
    sources_unchanged()
    before = load("root_verification")
    t.require(j.canonical(before) == j.canonical(authority()), "UPSTREAM_AUTHORITY_DRIFT_BEFORE_SEAL")
    manifest, oracle = repair.previous.d.release.prior.frozen_inputs()
    rows = [j.strict_json(line) for line in j.read_bytes(OUT / "full_59_development_results.jsonl").splitlines()]
    t.require([row["scenario_id"] for row in rows] == manifest["order"]
              and all(row["expected"] == oracle[row["scenario_id"]] for row in rows), "ORIGINAL_59_ORACLE_OR_ORDER_DRIFT")
    groups = {}
    for row in rows:
        if row["status"] == "FAIL":
            group = groups.setdefault(row.get("root_cause_group") or row["failure_category"],
                                      {"failure_category": row["failure_category"], "failures": []})
            group["failures"].append({key: row[key] for key in ("scenario_id", "expected", "actual", "first_divergence", "reproduction_command", "execution_log")})
    emit("grouped_failure_report", {"groups": groups, "matrix_runtime_or_oracle_changed": False,
        "T12_preserved_as_FAIL_not_waived_to_PASS": True, "no_new_runtime_defects_inferred_from_unexecuted_cases": True})
    checks = []
    for command in ([sys.executable, "-m", "compileall", "-q", str(Path(__file__))], ["git", "diff", "--check"],
                    ["git", "diff", "--no-index", "--check", "/dev/null", str(Path(__file__))]):
        process = subprocess.run(command, cwd=ROOT, capture_output=True, text=True)
        checks.append({"command": command, "exit_code": process.returncode, "diagnostics": process.stdout + process.stderr,
            "passed": process.returncode in ({0, 1} if "--no-index" in command else {0}) and not process.stdout and not process.stderr})
    summary = dict(repair.load("summary"))
    summary.update(development_scenario_count=59,
        development_executed_count=sum(row["execution_status"] == "EXECUTED" for row in rows),
        development_passed_count=sum(row["status"] == "PASS" for row in rows),
        development_failed_count=sum(row["status"] == "FAIL" for row in rows),
        development_not_executed_count=sum(row["status"] == "NOT_EXECUTED" for row in rows),
        remaining_runtime_defect_count=sum(row["failure_category"] == "RUNTIME_IMPLEMENTATION_DEFECT" for row in rows),
        remaining_oracle_conflict_count=sum(row["failure_category"] == "FROZEN_SCENARIO_OR_ORACLE_CONFLICT" for row in rows),
        remaining_unresolved_failure_count=sum(row["failure_category"] == "UNRESOLVED" for row in rows),
        development_status="diagnostics_completed_with_failures" if groups else "diagnostics_completed",
        full_59_continuation_completed=all(row["execution_status"] == "EXECUTED" for row in rows),
        source_repair_root_sha256=REPAIR_SHA, frozen_repair_runtime_reused_unchanged=True,
        prior_focused_only_root_modified=False, prior_full_matrix_not_executed_records_modified=False,
        independent_release_gate_passed=False)
    emit("summary", summary)
    emit("historical_preservation", {"before": before, "after": authority(), "passed": True,
        "historical_assets_modified": False, "prior_focused_only_root_unchanged": True,
        "prior_focused_only_matrix_counts_unchanged": [0, 0, 0, 59], "original_DR2_counts_unchanged": [12, 11, 1, 47],
        "original_oracle_unchanged": True, "all_14_repair_sources_byte_identical": True})
    emit("validation", {"original_order_and_oracle_preserved": True,
        "fresh_execution_not_historical_substitution": True, "all_59_passed": all(row["status"] == "PASS" for row in rows),
        "independent_release_gate_passed": False, "engineering_checks": checks,
        "historical_preservation_verified": True, "no_runtime_or_oracle_edits_during_execution": True,
        "reused_regression_evidence": h.ref(OUT / "regression_results.json", "byte_identical_previous_frozen_regressions_not_new_calls"),
        "source_drift_checks_per_scenario": True, "power_loss_durability_claimed": False, **NO_CALLS})
    count = verify_references()
    emit("freeze_verification", {"report_reference_count_verified": count, "source_and_historical_roots_verified": True,
        "negative_fixture_corruption_claims_not_promoted_to_admitted_provenance": True})
    sources_unchanged()
    t.require(j.canonical(before) == j.canonical(authority()), "UPSTREAM_ROOT_DRIFT_AT_SEAL")
    root = repair.previous.d.release.master.root_hash(OUT, MARKER)
    j.atomic_freeze(OUT / MARKER, (root + "\n").encode())
    j.sync_directory(OUT)
    t.require(repair.previous.d.release.master.root_hash(OUT, MARKER) == root, "POST_FREEZE_ROOT_MISMATCH")
    return {**summary, "development_root_sha256": root, "workspace": str(OUT)}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("operation", choices=("execute", "freeze"))
    args = parser.parse_args()
    with repair.previous.d.release.master.prior.offline_guard():
        print(json.dumps(globals()[args.operation](), sort_keys=True))
