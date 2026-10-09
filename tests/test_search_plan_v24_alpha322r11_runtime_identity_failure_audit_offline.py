"""Static/serialized-evidence/schema checks only; never R1 runtime fixtures."""

import ast
import copy
from pathlib import Path

import pytest

from scripts import run_search_plan_v24_alpha322r11_runtime_identity_failure_audit_offline as audit


@pytest.fixture(autouse=True)
def offline():
    with audit.r0.d.master.prior.offline_guard():
        yield


@pytest.fixture(scope="module")
def documents():
    return audit.prepare_documents()


@pytest.fixture
def signal(documents):
    reference = documents["r1_actual_serialized_event_inspection"]["cases"][0]["exception_payload"]
    return audit.load(audit.ROOT / reference["artifact_path"])


def test_frozen_roots_and_failed_R1_counts_preserved(documents):
    authority = documents["upstream_root_verification"]
    assert all(authority[key]["verified"] for key in ("master", "alpha322a", "alpha322b", "alpha322c", "alpha322d", "alpha322r0", "alpha322r1", "closure"))
    saved = documents["r1_failed_snapshot_verification"]
    assert saved["status"] == "failed" and saved["classification"] == audit.prior.FAIL
    assert saved["negative_pass_count"] == 19 and saved["negative_fail_count"] == 3
    assert not saved["original_positive_passed"] and not saved["rec01_passed"] and not saved["rec02_executed"]


def test_exact_exception_schema_authority_and_four_fields(documents):
    record = documents["r1_runtime_identity_schema_authority"]
    assert record["schema_version"] == "TransportExceptionProvenanceV1"
    assert record["schema"]["sha256"] == "47b881c7e6432aec67e7ba37779be94d6f0e7a159d432f364153484132799076"
    assert record["schema_id"] == "urn:alpha3_22:TransportExceptionProvenanceV1"
    fields = documents["r1_runtime_identity_required_field_inventory"]
    assert set(fields["required_fields"]) == {"python_version", "client_module", "client_version", "client_code_sha256"}
    assert not fields["optional_fields"] and fields["nullable_required_fields"] == ["client_version"]
    assert fields["additional_properties"] is False


@pytest.mark.parametrize("case_id", ["R0_P01", "N14", "N17", "N21", "REC01"])
def test_actual_signal_has_parent_missing_python_and_no_failure_terminal(documents, case_id):
    case = next(row for row in documents["r1_actual_serialized_event_inspection"]["cases"] if row["case_id"] == case_id)
    assert case["runtime_identity_parent_present"] and not case["python_version_present"]
    assert case["missing_runtime_identity_fields"] == ["python_version"]
    assert case["signal_hash_matches_both_envelopes"] and not case["failure_terminal_durable"]
    assert case["durable_event_count"] == (14 if case_id == "REC01" else 6)
    assert not case["whole_rejected_terminal_candidate_bytes_preserved"]


def test_actual_required_child_rejection_uses_container_path(signal, documents):
    assert audit.schema_probe(signal) == "SCHEMA_REQUIRED:$.runtime_identity"
    explanation = documents["r1_schema_rejection_path_audit"]
    assert explanation["parent_present"] and explanation["missing_child_by_required_set_difference"] == ["python_version"]
    assert explanation["actual_first_path"] == "$.runtime_identity"
    assert explanation["actual_first_path"] != "$.runtime_identity.python_version"


def test_schema_only_absent_parent_reports_root_container_not_identity_child(signal):
    specimen = copy.deepcopy(signal)
    specimen.pop("runtime_identity")
    assert audit.schema_probe(specimen) == "SCHEMA_REQUIRED:$"


@pytest.mark.parametrize("value", [None, 13, True, [], {}])
def test_schema_only_unsupported_python_type_reports_exact_leaf(signal, value):
    specimen = copy.deepcopy(signal)
    specimen["runtime_identity"]["python_version"] = value
    assert audit.schema_probe(specimen) == "SCHEMA_TYPE:$.runtime_identity.python_version"


def test_schema_only_version_mismatch_isolates_expected_const(signal):
    specimen = copy.deepcopy(signal)
    # Explicit synthetic shape specimen ONLY. No runtime capture, no journal,
    # no repaired behavior is exercised or inferred from this value.
    specimen["runtime_identity"]["python_version"] = "synthetic:audit-shape-version"
    specimen["schema_version"] = "WrongSchemaVersion"
    assert audit.schema_probe(specimen) == "SCHEMA_CONST:$.schema_version"


def test_schema_only_extra_runtime_fields_forbidden(signal):
    specimen = copy.deepcopy(signal)
    specimen["runtime_identity"]["python_version"] = "synthetic:audit-shape-version"
    specimen["runtime_identity"]["run_id"] = "synthetic:audit"
    assert audit.schema_probe(specimen) == "SCHEMA_ADDITIONAL_PROPERTIES:$.runtime_identity"


def test_existing_codec_preserves_supplied_parent_and_all_three_keys(signal):
    raw = audit.o.canonical_bytes(signal)
    decoded = audit.u.strict_json(raw)
    assert decoded["runtime_identity"] == signal["runtime_identity"]
    assert set(decoded["runtime_identity"]) == {"client_module", "client_version", "client_code_sha256"}
    clean, _ = audit.o.SecretRedactorV1().tree(signal)
    assert clean["runtime_identity"] == signal["runtime_identity"]


def runtime_literal(path, name, function=None):
    tree = ast.parse(Path(path).read_bytes())
    nodes = tree.body if function is None else next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == function).body
    matches = [node.value for node in nodes if isinstance(node, ast.Assign)
               and any(isinstance(target, ast.Name) and target.id == name for target in node.targets)]
    assert len(matches) == 1 and isinstance(matches[0], ast.Dict)
    return {key.value for key in matches[0].keys}


def test_component_and_integration_independently_build_incomplete_overrides():
    keys = {"client_module", "client_version", "client_code_sha256"}
    assert runtime_literal(audit.prior.f.__file__, "runtime", "capture_failure") == keys
    assert runtime_literal(audit.prior.h.__file__, "RUNTIME") == keys


def test_existing_python_authority_is_actual_platform_convention(documents):
    source = documents["r1_python_version_authority_audit"]["source"]
    assert '"python_version": platform.python_version()' in source["assertion"]
    authority = documents["r1_python_version_authority_audit"]
    assert not authority["hardcoded_version_permitted_in_runtime_adapter"]
    assert not authority["exception_message_inference_permitted"]
    assert not authority["unknown_empty_arbitrary_defaults_permitted"]


def test_defect_mode_B_only_and_no_false_harness_only_attribution(documents):
    modes = documents["r1_runtime_identity_field_loss_analysis"]["defect_modes"]
    assert modes["B_REQUIRED_CHILD_OMITTED"]["supported"]
    assert not modes["A_PARENT_NEVER_CONSTRUCTED"]["supported"]
    assert not modes["C_VALID_IDENTITY_DROPPED_DURING_SERIALIZATION"]["supported"]
    assert not modes["D_SCHEMA_VERSION_OR_FIELD_PATH_MISMATCH"]["supported"]
    owners = documents["r1_harness_vs_component_defect_audit"]
    assert owners["component_capture_defect"] and owners["harness_integration_defect"]
    assert not owners["sole_test_fixture_defect"] and not owners["standalone_fixture_wrapper_constructs_runtime_identity"]


@pytest.mark.parametrize("case", ["n14", "n17", "n21"])
def test_wrong_first_rejection_stays_failed_and_masked(documents, case):
    row = documents["r1_negative_" + case + "_first_rejection_audit"]
    assert row["actual_first_rejection_reason"] == audit.ERROR
    assert row["expected_first_rejection_reason"] != audit.ERROR
    assert not row["passed"] and not row["intended_first_rejection_reached"]
    assert row["runtime_identity_masked_intended_check"]


def test_recovery_REC02_remains_not_executed_and_remaining_validity_unknown(documents):
    recovered = documents["r1_rec01_rec02_execution_reachability_audit"]
    assert not recovered["REC01"]["passed"] and not recovered["REC01"]["fresh_process_recovery_assertions_reached"]
    assert recovered["REC02"]["status"] == "NOT_EXECUTED" and not recovered["REC02"]["executed"]
    assert documents["r1_masked_downstream_validation_state"]["remaining_phase_binding_validity"] == "NOT_FULLY_EVALUATED"


def test_future_identity_specs_use_exact_frozen_error_paths_and_are_unexecuted(documents):
    spec = documents["r2_runtime_identity_negative_fixture_spec"]
    expected = {"RI01": "SCHEMA_REQUIRED:$", "RI02": audit.ERROR, "RI03": "SCHEMA_TYPE:$.runtime_identity.python_version",
        "RI04": "SCHEMA_CONST:$.schema_version", "RI05": "SCHEMA_REQUIRED:$", "RI06": "NESTED_PROVENANCE_CONTEXT"}
    assert spec["fixture_count"] == 6
    assert {row["fixture_id"]: row["expected_first_rejection"] for row in spec["fixtures"]} == expected
    assert all(row["execution_status"] == "SPECIFICATION_ONLY_NOT_EXECUTED" for row in spec["fixtures"])
    assert documents["r2_runtime_identity_positive_fixture_spec"]["execution_status"] == "SPECIFICATION_ONLY_NOT_EXECUTED"


def test_R0_original_expectations_unchanged_and_R2_does_not_bypass_binding(documents):
    refs = documents["r2_original_r0_fixture_preservation_audit"]["unchanged_original_specs"]
    assert len(refs) == 3
    for reference in refs:
        assert audit.u.sha(audit.u.read_bytes(audit.ROOT / reference["artifact_path"])) == reference["sha256"]
    spec = audit.load(audit.R0 / "repair_negative_fixture_specification.json")
    assert spec["fixture_count"] == 22 and len(spec["fixtures"]) == 22
    contract = documents["r2_runtime_identity_binding_contract"]
    assert contract["no_preflight_phase_binding_verified_true_without_verified_binding"]
    assert contract["original_semantic_phase_validation_order_preserved"]
    assert documents["r2_minimal_versioned_repair_design"]["narrow_dependency_fork_if_required"]["no_broad_journal_rewrite"]


def test_no_runtime_fixture_dispatch_or_capture_calls_in_audit_source():
    tree = ast.parse(Path(audit.__file__).read_bytes())
    forbidden = {"failed_attempt", "capture_failure", "bind_failure", "commit_terminal", "commit_failure", "start_attempt",
        "fresh_plan", "read_plan", "classify_abandoned", "positive", "negative", "recovery", "transport_scenario", "crash_setup", "crash_matrix"}
    calls = [node.func.attr for node in ast.walk(tree) if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)]
    assert not set(calls) & forbidden
    assert not any(isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == "run" for node in ast.walk(tree))


def test_archive_only_manifest_read_and_no_symlink_following(documents):
    record = documents["archived_test_temporaries_preservation_audit"]
    assert record["archived_group_count"] == 6 and record["archive_link_targets_not_followed"]
    assert record["archived_directory_entries_or_symlinks_not_traversed_in_R11"]


def test_science_contamination_and_independent_matrix_barriers_preserved(documents):
    counts = documents["contamination_baseline_immutability_audit"]["counts"]
    assert counts == {"future_seen_unique_pmid_count": 3560, "future_seen_unique_pmcid_count": 218,
        "future_seen_unique_doi_count": 252, "future_seen_candidate_identity_count": 271}
    safety = documents["scientific_state_safety_audit"]
    assert not safety["r1_source_modified"] and not safety["r1_frozen_tests_rerun"] and not safety["r2_correction_implemented"]
    assert not safety["alpha3_21_reopened"] and not safety["fresh_primary_attempt_started"]
    assert all(safety[name] == 0 for name in audit.NO_CALLS)
    prohibition = documents["independent_22dr_execution_prohibition"]
    assert not prohibition["independent_22dr_authorized"] and not prohibition["original_59_matrix_executed"]
