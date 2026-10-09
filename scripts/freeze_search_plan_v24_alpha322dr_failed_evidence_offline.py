"""Packaging-only seal of the stopped D-R attempt. No scenario/fixture reruns.

All existing bytes remain unchanged. The release runner's unsuccessful
transitive historical-negative-reference check is preserved, not suppressed.
New release reference records are checked recursively; upstream corpora are
verified under their frozen roots, which intentionally include corrupt tests.
"""

import json
import subprocess
import sys
import traceback
from pathlib import Path

from scripts import run_search_plan_v24_alpha322dr_independent_59_scenario_revalidation_offline as run

OUT, ROOT, j, t, h = run.OUT, run.ROOT, run.j, run.t, run.h


def nested_release_references():
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
                verified.add((str(path.relative_to(ROOT)), value["sha256"]))
            for child in value.values():
                walk(child)
        elif isinstance(value, list):
            for child in value:
                walk(child)
    for path in sorted(OUT.rglob("*")):
        t.require(not path.is_symlink(), "FAILED_RELEASE_SYMLINK_FORBIDDEN")
        if path.suffix == ".json":
            walk(j.strict_json(j.read_bytes(path)))
        elif path.suffix == ".jsonl":
            for line in j.read_bytes(path).splitlines():
                walk(j.strict_json(line))
    return [{"artifact_path": path, "sha256": digest} for path, digest in sorted(verified)]


def main():
    t.require(not (OUT / run.MARKER).exists() and not (OUT / "freeze_verification.json").exists(), "FAILED_RELEASE_ALREADY_SEALED")
    existing = [h.ref(path, "original_stopped_attempt_bytes_preserved") for path in sorted(OUT.rglob("*")) if path.is_file()]
    summary = j.strict_json(j.read_bytes(OUT / "summary.json"))
    rows = [j.strict_json(line) for line in j.read_bytes(OUT / "scenario_results.jsonl").splitlines()]
    t.require(summary["alpha3_22dr_status"] == "failed" and summary["first_failed_scenario"] == "T11" and
              [row["status"] for row in rows] == ["PASS"] * 10 + ["FAIL"] + ["NOT_EXECUTED"] * 48,
              "STOPPED_RELEASE_RESULT_MUST_NOT_CHANGE")
    authority = run.authority()
    t.require(j.canonical(authority) == j.read_bytes(OUT / "upstream_root_verification.json"), "UPSTREAM_ROOT_CHANGED")
    started = j.strict_json(j.read_bytes(OUT / "execution_started.json"))
    for reference in started["source_bindings"]:
        t.require(j.sha(j.read_bytes(ROOT / reference["artifact_path"])) == reference["sha256"], "RELEASE_SOURCE_CHANGED_AFTER_START")
    for path in run.SOURCES:
        t.require(j.read_bytes(path) == j.read_bytes(OUT / "implementation" / path.name), "RELEASE_SNAPSHOT_CHANGED")
    # Recheck only the failed read-only packaging operation. This does not
    # execute any fault, reader, classifier, fixture or runtime state machine.
    try:
        run.verify_nested_references()
    except t.TransportContractError as exc:
        packaging_failure = {"original_runner_exit_code": 1, "error": str(exc), "traceback": traceback.format_exc(),
            "operation": "over-broad transitive expansion into historical intentionally corrupted negative fixtures",
            "runtime_release_failure_not_changed": True, "failed_read_only_hash_check_reconfirmed_only": True}
    else:
        raise AssertionError("ORIGINAL_PACKAGING_FAILURE_MUST_REMAIN_REPRODUCIBLE")
    t.require("alpha3_22r1_versioned_phase_binding_repair_offline/execution/N09/" in packaging_failure["error"],
              "UNEXPECTED_PACKAGING_FAILURE_PRESERVE_WITHOUT_SEAL")
    j.atomic_freeze(OUT / "execution/packaging_failure.txt", packaging_failure["traceback"].encode())
    j.atomic_freeze(OUT / "implementation" / Path(__file__).name, j.read_bytes(Path(__file__)))
    command = [sys.executable, "-m", "compileall", "-q", str(Path(__file__))]
    compiled = subprocess.run(command, cwd=ROOT, capture_output=True, text=True)
    checked = subprocess.run(["git", "diff", "--no-index", "--check", "/dev/null", str(Path(__file__))],
                             cwd=ROOT, capture_output=True, text=True)
    t.require(compiled.returncode == 0 and checked.returncode in {0, 1} and not checked.stdout and not checked.stderr,
              "PACKAGING_SOURCE_ENGINEERING_CHECK_FAILED")
    references = nested_release_references()
    run.emit("freeze_verification", {"release_status": "FAILED_PRESERVED_NO_RERUN", "new_scientific_or_runtime_stage": False,
        "packaging_failure": packaging_failure,
        "packaging_failure_log": h.ref(OUT / "execution/packaging_failure.txt", "unchanged_check_failure_traceback"),
        "packaging_only_source": h.ref(Path(__file__), "append_only_failed_run_seal_no_runtime_execution"),
        "all_required_13_artifacts_present": all((OUT / (name + ".json")).is_file() for name in run.REQUIRED)
            and (OUT / "scenario_results.jsonl").is_file(),
        "original_output_bytes_preserved": existing,
        "recursive_new_release_reference_check": {"passed": True, "reference_count": len(references),
            "references": references, "scope": "every nested artifact_path/sha256 record in every new D-R JSON and JSONL",
            "historical_corpora_verification": "authoritative frozen roots and source bindings, not admission of corrupted negative-fixture pointers",
            "transitive_historical_negative_artifact_admission_claimed": False},
        "first_defect": {
            "scenario_id": "T11", "first_terminal_error": "VALIDATOR_OUTCOME_CONFLICT",
            "classification": "VALIDATOR_RETURN_VALUE_TO_TERMINAL_INTEGRATION_GAP",
            "source": h.ref(Path(h.__file__), "executed_validation_adapter_bytes_not_modified"),
            "observed": "complete well-formed direct identity mismatch; three consumers invoked; terminal not committed; fresh reader sees abandoned ordinal 1 and schedules ordinal 2",
            "mechanism": "consumers returns valid=False without a parser exception; adapter ignores record_validation's returned COMPLETE_BODY_RESPONSE_VALIDITY_FAILURE and classifies None plus complete trusted HTTP as NO_TECHNICAL_FAILURE; journal rejects the resulting accepted=False noneligible-success proposal",
            "journal_fail_closed_check_worked": True,
            "frozen_B_diagnostic": "SCIENTIFIC_VALIDITY_NOT_IMPLIED",
            "not_another_T05_phase_binding_or_runtime_identity_failure": True,
            "minimal_next_development_correction": "propagate the already-frozen boolean validation rejection through the explicit structured validity classification/binding/terminal path; preserve original retry rules, oracle, source validator and journal rejection checks",
            "fabricated_parser_exception_or_error_text_mapping_allowed": False,
            "correction_executed_here": False},
        "new_fault_scenarios_executed": 0, "repair_fixtures_executed": 0, "regressions_executed": 0,
        "existing_release_sources_changed": False, "existing_runtime_sources_changed": False,
        "compileall": {"exit_code": compiled.returncode, "passed": True},
        "whitespace_check": {"exit_code": checked.returncode, "passed": True},
        "historical_roots_reverified": True, **run.NO_CALLS})
    # Check the newly added records too, without rewriting prior observations.
    nested_release_references()
    for reference in existing:
        t.require(j.sha(j.read_bytes(ROOT / reference["artifact_path"])) == reference["sha256"], "STOPPED_ATTEMPT_BYTES_CHANGED")
    t.require(j.canonical(run.authority()) == j.canonical(authority), "UPSTREAM_DRIFT_DURING_FAILURE_SEAL")
    root = run.master.root_hash(OUT, run.MARKER)
    j.atomic_freeze(OUT / run.MARKER, (root + "\n").encode())
    j.sync_directory(OUT)
    t.require(run.master.root_hash(OUT, run.MARKER) == root, "FAILED_RELEASE_ROOT_POST_FREEZE_MISMATCH")
    return {"status": "failed", "scenario_attempts": 11, "passed": 10, "failed": 1, "not_executed": 48,
            "first_failed_scenario": "T11", "recursive_release_references_verified": len(references),
            "all_existing_output_bytes_preserved": True, run.MARKER: root, "workspace": str(OUT), **run.NO_CALLS}


if __name__ == "__main__":
    with run.master.prior.offline_guard():
        print(json.dumps(main(), sort_keys=True))
