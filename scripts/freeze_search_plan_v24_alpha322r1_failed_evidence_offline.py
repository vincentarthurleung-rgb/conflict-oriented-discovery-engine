"""Packaging-only seal of the failed R1 run; NO fixture/code repair or rerun.

Preserve pytest temporary trees (including intentional negative symlinks) in
an external append-only archive. The authoritative failed run contains only
physical artifacts, with the archive inventory transitively hash-bound.
"""

import os
import stat
from pathlib import Path

from scripts import run_search_plan_v24_alpha322r1_versioned_phase_binding_repair_offline as run

j, f, ROOT, OUT = run.j, run.f, run.ROOT, run.OUT
ARCHIVE = ROOT / "runs/20261009_search_plan_v24_dev_alpha3_22r1_preserved_test_temporaries_offline"
GROUPS = ("focused_v2", "legacy_22a", "legacy_22b", "legacy_22c", "frozen_r0", "historical_journal")
FINAL_CLASSIFICATION = "ALPHA3_22R1_FAILED_PHASE_BINDING_REPAIR_VALIDATION"


def inventory(directory):
    rows = []
    for path in sorted(directory.rglob("*")):
        # Path.rglob does not traverse symlink directories. Never follow a link.
        entry = {"path": str(path.relative_to(directory)), "mode": stat.S_IMODE(path.lstat().st_mode)}
        if path.is_symlink():
            entry.update(kind="symlink", preserved_link_text=os.readlink(path))
        elif path.is_file():
            raw = j.read_bytes(path)
            entry.update(kind="physical_file", sha256=j.sha(raw), byte_count=len(raw))
        elif path.is_dir():
            entry.update(kind="physical_directory")
        else:
            raise ValueError("UNEXPECTED_TEST_ARCHIVE_ENTRY")
        rows.append(entry)
    return rows


def main():
    before = run.authority()
    j.require(not (OUT / run.ROOT_MARKER).exists() and not (OUT / "summary.json").exists(), "FAILURE_ALREADY_SEALED_NO_REWRITE")
    j.require(not ARCHIVE.exists(), "TEST_ARCHIVE_MUST_BE_NEW")
    for path in run.COMPONENTS + [Path(run.fixtures.__file__), Path(run.__file__), run.TEST]:
        j.require(j.read_bytes(path) == j.read_bytes(OUT / "implementation" / path.name), "IMPLEMENTATION_CHANGED_AFTER_FAILED_EXECUTION")
    j.require(f.implementation_identity() == j.sha(j.read_bytes(OUT / "runtime_v2_implementation_manifest.json")), "RUNTIME_IDENTITY_DRIFT")
    draft = j.strict_json(j.read_bytes(OUT / "summary_pending.json"))
    j.require(draft["status"] == "failed" and draft["r0_negative_fixture_pass_count"] == 19 and draft["r0_negative_fixture_fail_count"] == 3,
              "UNEXPECTED_FAILED_RESULT_DO_NOT_REINTERPRET")
    ARCHIVE.mkdir()
    archive_rows = []
    for group in GROUPS:
        source = OUT / "execution" / (group + "_temp")
        if not source.exists():
            archive_rows.append({"group": group, "temporary_directory_created": False})
            continue
        j.require(source.is_dir() and not source.is_symlink(), "INVALID_TEST_TEMP_DIRECTORY")
        source_rows = inventory(source)
        destination = ARCHIVE / source.name
        source.rename(destination)  # recoverable relocation, no deletion
        j.sync_directory(destination.parent)
        j.sync_directory(source.parent)
        target_rows = inventory(destination)
        j.require(source_rows == target_rows, "TEST_ARCHIVE_BYTES_OR_LINK_TEXT_CHANGED")
        archive_rows.append({"group": group, "temporary_directory_created": True,
            "original_location": str(source.relative_to(ROOT)), "preserved_location": str(destination.relative_to(ROOT)),
            "inventory_sha256": j.sha(j.canonical(source_rows)), "members": source_rows,
            "all_file_bytes_and_link_text_unchanged": True,
            "runtime_replay_after_relocation_not_authorized": True})
    archive_record = {"schema_version": "R1FailedRunTestTemporaryArchiveV1", "archives": archive_rows,
        "test_runs_not_reexecuted": True, "links_are_unfollowed_denial_fixture_evidence_only": True,
        "old_absolute_temp_paths_not_runtime_inputs": True, "no_material_deleted": True}
    run.fixtures.write_json(ARCHIVE / "test_archive_manifest.json", archive_record)
    archive_ref = run.ref(ARCHIVE / "test_archive_manifest.json", "preserved_negative_symlink_test_evidence_inventory")
    # Original diagnostics/audits stay byte-unchanged, including the provisional
    # broad classification. Terminal summary explains the narrower failure.
    run.emit("terminal_failure_classification_audit", {
        "authoritative_terminal_classification": FINAL_CLASSIFICATION,
        "provisional_classification": draft["alpha3_22r1_classification"],
        "reason": "repair positive and recovery fail schema preflight; 3 negative first-rejection checks blocked; no weakened journal invariant demonstrated",
        "original_validation_and_summary_pending_preserved": True,
        "failure_first_reason": "SCHEMA_REQUIRED:$.runtime_identity",
        "missing_frozen_required_field": "python_version",
        "frozen_schema": run.ref(run.r0.A / "exception_provenance_v1_schema.json", "unchanged_runtime_identity_schema"),
        "no_source_or_schema_repair": True, "no_runtime_rerun": True,
        "production_nonwiring_audit_note": "runtime_activation_allowed in preliminary audit is a misnamed all-module-flags-false check; actual f and j activation flags remain false"})
    frozen_specs = run.fixtures.source_spec("repair_negative_fixture_specification")["fixtures"]
    actual_rows = j.strict_json(j.read_bytes(OUT / "r0_negative_fixture_results.json"))["fixtures"]
    first_rejections = []
    for spec, result in zip(frozen_specs, actual_rows, strict=True):
        first = result.get("actual_first_rejection_reason")
        if first is None and "error" in result:
            first = result["error"].partition(":")[2]
        first_rejections.append({"fixture_id": spec["fixture_id"],
            "expected_first_rejection_reason": spec["expected"]["proposed_reason_code"],
            "actual_first_rejection_reason": first, "passed": result["passed"],
            "rejected_before_intended_perturbation": spec["fixture_id"] in {"N14", "N17"},
            "retry_dispatches": 0, "parser_invocations": 0})
    run.emit("complete_negative_first_rejection_failure_audit", {"fixture_count": 22,
        "fixtures": first_rejections, "pass_count": 19, "fail_count": 3, "failed_fixtures_not_rerun": True})
    run.emit("failed_run_packaging_preservation_audit", {
        "packaging_failure": "SYMLINK_FORBIDDEN while enumerating deliberate symlink-denial pytest artifacts",
        "test_archive": archive_ref, "temporary_directories_relocated_not_deleted": True,
        "primary_positive_negative_recovery_artifacts_not_moved_or_edited": True,
        "all_existing_output_file_contents_unchanged": True, "implementation_contents_unchanged": True,
        "packaging_only_no_additional_fixture_execution": True, "symlinks_in_authoritative_failed_run": False,
        "original_freezer_exit_code": 1, "complete_test_count": 512, "test_pass_count": 511, "test_fail_count": 1,
        "recovery_execution_note": "REC01 stops at committed failure schema validation; REC02 is not reached and not inferred as passed"})
    run.emit("r1_failed_runtime_freeze_handoff", {"ready_for_22DR": False, "next_stage": run.NEXT_FAIL,
        "no_automatic_audit_or_repair_execution": True, "source_implementation_failed_validation": True,
        "zero_byte_and_nonempty_partial_guard_not_reached_after_failed_commit": True,
        "committed_failure_reconstruction_verified": False, "uncommitted_REC02_recovery_verified": False,
        "legacy_A_B_C_R0_passed": True, "upstream_frozen_hashes_unchanged": True, **run.NO_CALLS})
    j.atomic_freeze(OUT / "implementation" / Path(__file__).name, j.read_bytes(Path(__file__)))
    physical_files = sorted(path for path in OUT.rglob("*") if path.is_file())
    j.require(not any(path.is_symlink() for path in OUT.rglob("*")), "FAILED_CORPUS_SYMLINK_FORBIDDEN")
    run.emit("alpha3_22r1_repair_validation_bundle", {
        "schema_version": "Alpha322R1RepairValidationBundle", "status": "failed", "classification": FINAL_CLASSIFICATION,
        "r0_root_sha256": run.R0_SHA,
        "members": [run.ref(path, "preserved_failed_implementation_or_test_artifact") for path in physical_files],
        "test_temporary_archive": archive_ref,
        "source_bindings": [run.ref(path, "failed_implementation_source_not_repaired") for path in
                            run.COMPONENTS + [Path(run.fixtures.__file__), Path(run.__file__), run.TEST, Path(__file__)]],
        "independent_59_matrix_executed": False, "runtime_fixtures_reexecuted": False})
    hashes = {}
    for marker, stem in run.MARKERS.items():
        hashes[marker] = j.sha(j.read_bytes(OUT / (stem + ".json")))
        j.atomic_freeze(OUT / marker, (hashes[marker] + "\n").encode())
    run.emit("summary", {**draft, "alpha3_22r1_classification": FINAL_CLASSIFICATION,
        "classification_audit": run.ref(OUT / "terminal_failure_classification_audit.json", "append_only_terminal_failure_classification"),
        "test_temporary_archive": archive_ref, "runtime_validation_failed_closed": True, "failure_evidence_frozen": True,
        "r0_recovery_rec02_executed": False, "test_pass_count": 511, "test_fail_count": 1,
        "implementation_repair_after_failure": False, "fixture_reruns": 0, **hashes})
    j.require(all((OUT / (name + ".json")).is_file() for name in run.REQUIRED), "FAILED_CORPUS_REQUIRED_ARTIFACT_MISSING")
    j.require(j.canonical(run.authority()) == j.canonical(before), "UPSTREAM_CHANGED_DURING_FAILURE_FREEZE")
    root = run.r0.d.master.root_hash(OUT, run.ROOT_MARKER)
    j.atomic_freeze(OUT / run.ROOT_MARKER, (root + "\n").encode())
    j.sync_directory(OUT)
    j.require(run.r0.d.master.root_hash(OUT, run.ROOT_MARKER) == root, "FAILED_ROOT_POST_FREEZE_MISMATCH")
    return {"status": "failed", "classification": FINAL_CLASSIFICATION, run.ROOT_MARKER: root,
            "workspace": str(OUT), "required_artifact_count": len(run.REQUIRED), **hashes, **run.NO_CALLS}


if __name__ == "__main__":
    import json
    with run.r0.d.master.prior.offline_guard():
        print(json.dumps(main(), sort_keys=True))
