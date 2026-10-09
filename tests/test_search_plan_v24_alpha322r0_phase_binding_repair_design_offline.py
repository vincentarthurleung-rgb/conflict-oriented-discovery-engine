"""Read-only frozen-evidence and static design checks, NOT repair tests.

No original 22D scenarios or proposed R1 fixture SUTs are executed here.
The independent fixture expectations are only checked for completeness.
"""

import ast
import copy
from pathlib import Path

import pytest

from scripts import run_search_plan_v24_alpha322r0_phase_binding_repair_design_offline as r
from scripts import search_plan_v24_alpha322r0_repair_fixture_specifications as f


@pytest.fixture(scope="module")
def documents():
    return r.prepare_documents()[1]


@pytest.mark.parametrize("stem", r.REQUIRED)
def test_every_required_artifact_is_designed(stem, documents):
    if stem not in {"validation", "summary"}:
        assert stem in documents and documents[stem]
    else:
        assert stem in Path(r.__file__).read_text()


def test_upstream_and_existing_T05_reverified_read_only():
    with r.d.master.prior.offline_guard():
        authority = r.verify_authority()
        frozen = r.audit_t05()
    assert all(authority[key]["verified"] for key in ("master", "alpha322a", "alpha322b", "alpha322c", "alpha322d", "closure"))
    assert frozen["context"]["attempt_ordinal"] == 1
    assert len(frozen["journal"]) == 6
    assert frozen["actual"]["actual"]["durable_terminal_committed"] is False
    assert frozen["expected"]["expected"]["durable_terminal_committed"] is True


def test_original_expected_outcomes_remain_independent_and_preserved(documents):
    audit = documents["independent_expected_outcome_preservation_audit"]
    assert audit["original_scenario_count"] == 59
    assert audit["original_oracle_sha256"] == r.ORACLE_SHA
    assert not audit["original_oracle_edited"]
    original = r.obj(r.d.OUT / "summary.json")
    assert original["fault_scenario_executed_count"] == 5
    assert original["fault_scenario_not_executed_count"] == 54


def test_cause_and_compatibility_do_not_claim_old_V1_acceptance(documents):
    assert documents["cross_component_root_cause_classification"]["primary_cause"] == "JOURNAL_FAILURE_PHASE_AND_PERSISTENCE_PHASE_CONFLATION"
    matrix = documents["cross_component_contract_authority_matrix"]
    assert matrix["frozen_semantic_contracts_compatible"]
    assert matrix["historical_implementation_equality_is_defective"]
    assert matrix["existing_V1_accepts_proposed_record"] is False
    assert matrix["in_place_V1_contract_amendment_allowed"] is False


def test_first_divergence_is_validation_not_resume_or_original_state(documents):
    result = documents["t05_expected_actual_first_divergence"]
    assert result["incorrect_journal_validation"] is True
    assert result["incorrect_state_production"] is False
    assert result["incorrect_event_serialization"] is False
    assert result["incorrect_integration_call_sequence"] is False
    assert documents["t05_resume_reconstruction_audit"]["not_a_resume_policy_defect"] is True


def test_all_three_phase_meanings_are_explicit(documents):
    phases = documents["failure_occurrence_mapping_persistence_phase_analysis"]
    assert phases["failure_occurrence_phase"]["value"] == "RESPONSE_BODY_READING"
    assert phases["mapping_evidence_phase"]["value"] == "RESPONSE_BODY_READING"
    assert phases["persistence_phase"]["value"] == "RAW_RESPONSE_FROZEN"
    assert phases["timestamp_only_proof_allowed"] is False
    invariants = documents["transport_failure_phase_binding_v2_invariants"]
    assert invariants["concrete_occurrence_mapping_equality_required"]
    assert not invariants["persistence_occurrence_equality_required"]


def test_no_actual_occurrence_event_is_invented_in_frozen_D(documents):
    trace = documents["t05_causal_execution_trace"]
    assert trace["occurrence_has_separate_durable_event_in_original_22D"] is False
    assert trace["no_new_occurrence_identity_retrofitted_to_22D"] is True
    assert [row["causal_order"] for row in trace["steps"]] == list(range(1, 11))
    assert trace["timestamps_prove_order"] is False


def test_partial_raw_is_zero_length_but_not_complete_or_parseable(documents):
    audit = documents["t05_partial_raw_freeze_audit"]
    assert audit["byte_count"] == 0
    assert audit["raw_artifact_frozen"] is True
    assert audit["body_complete"] is audit["authoritative"] is audit["parser_eligible"] is False
    assert all(count == 0 for count in audit["all_six_consumer_invocation_counts"].values())
    assert audit["RAW_RESPONSE_FROZEN_implies_BODY_COMPLETE"] is False


def test_schema_is_strict_and_does_not_claim_semantic_validation(documents):
    schema = documents["transport_failure_phase_binding_v2_schema"]
    def check(node):
        if type(node) is dict:
            if node.get("type") == "object":
                assert node["additionalProperties"] is False
                assert set(node["properties"]) == set(node["required"])
            for value in node.values():
                check(value)
        elif type(node) is list:
            for value in node:
                check(value)
    check(schema)
    assert schema["properties"]["schema_version"]["const"] == "TransportFailurePhaseBindingV2"
    assert "CONCRETE_EXCEPTION_OCCURRENCE" == schema["properties"]["binding_scope"]["const"]
    assert documents["transport_failure_phase_binding_v2_invariants"]["semantic_validation_implemented"] is False


def test_declarative_schema_is_not_misclassified_as_artifact_reference():
    schema = r.proposal_schema()
    r.verify_design_references(schema)
    changed = copy.deepcopy(schema)
    changed["additionalProperties"] = True
    with pytest.raises(ValueError, match="SCHEMA_OBJECT_CONTRACT_DRIFT"):
        r.verify_design_references(changed)


def test_actual_source_references_still_checked_without_weakening():
    r.verify_design_references(r.ref(Path(f.__file__)))
    with pytest.raises(ValueError):
        r.verify_design_references({"$schema": "anything", "$id": "other"})


def test_proposal_preserves_mapping_and_requires_trace_and_retry_authority(documents):
    proposal = documents["transport_failure_phase_binding_v2_proposal"]
    assert proposal["implementation_state"] == "NOT_IMPLEMENTED"
    assert proposal["no_new_retry_function"]
    assert "structured_body_completion" in proposal["non_exception_paths"]
    assert "unmapped_concrete_exception" in proposal["non_exception_paths"]
    validation = documents["journal_phase_transition_validation_proposal"]
    assert len(validation["ordered_validation_steps"]) == 11
    assert not validation["acceptance_from_enum_strings_only"]


def test_resume_requires_new_explicit_type_binding_not_a_policy_change(documents):
    surfaces = documents["minimal_implementation_change_surface"]["new_versioned_surfaces"]
    assert len(surfaces) == 4
    resume = next(surface for surface in surfaces if "resume_planner_v2" in surface["proposed_module_path"])
    assert "exact VerifiedJournalV1" in resume["why_required"]
    assert all(surface["existing_modules_changed"] is False for surface in surfaces)
    retry = documents["retry_authority_nonchange_audit"]
    assert retry["maximum_attempts"] == 4 and retry["timeout_seconds"] == 60
    assert retry["backoff_seconds"] == [2, 4, 8]
    assert not retry["second_retry_function_proposed"]


@pytest.mark.parametrize("fixture", f.negatives(), ids=lambda fixture: fixture["fixture_id"])
def test_negative_fixture_is_independently_specified_not_executed(fixture):
    assert fixture["execution_status"] == "SPECIFICATION_ONLY_NOT_EXECUTED"
    assert fixture["expected"]["failure"] == "FAIL_CLOSED"
    assert fixture["expected"]["accept_invalid_record"] is False
    assert fixture["expected"]["retry_dispatches"] == fixture["expected"]["parser_invocations"] == 0
    assert fixture["independent_perturbation"]


def test_fixtures_are_literal_without_SUT_imports():
    tree = ast.parse(Path(f.__file__).read_text())
    assert not any(isinstance(node, (ast.Import, ast.ImportFrom)) for node in ast.walk(tree))
    assert {f"N{index:02d}" for index in range(1, 15)} <= {row["fixture_id"] for row in f.negatives()}
    expected = f.positive()["expected"]
    assert expected["terminal_logical_state"] == "RETRYABLE_FAILURE_WITH_BUDGET"
    assert expected["next_attempt_ordinal"] == 2 and expected["backoff_seconds"] == 2
    assert f.positive()["failure_occurrence_phase"] == f.positive()["mapping_evidence_phase"] == "RESPONSE_BODY_READING"
    assert f.positive()["persistence_phase"] == "RAW_RESPONSE_FROZEN"


def test_recovery_expectations_do_not_come_from_resume_SUT():
    recovery = f.recovery()
    assert recovery["expected"]["failure_is_abandoned"] is False
    assert recovery["expected"]["success_skipped"] is True
    assert recovery["expected"]["executable_request_ids"] == ["repair:OA:0", "repair:OA:later"]
    assert recovery["crash_before_terminal_variant"]["expected"]["state"] == "ABANDONED_ATTEMPT_UNKNOWN_TERMINATION"


def test_future_validation_requires_all_59_not_just_T05(documents):
    plan = documents["future_independent_59_scenario_revalidation_plan"]
    assert plan["requires_separate_authorization"]
    assert plan["required_original_scenario_count"] == len(plan["scenario_ids"]) == 59
    assert plan["R0_rerun_started"] is False
    assert plan["old_D_directory_appends_allowed"] is False


def test_audit_has_no_runtime_mutation_or_network_calls():
    forbidden = {"transport_scenario", "crash_scenario", "integrated_scenario", "actual_bound_failure", "actual_incomplete_read",
        "start_attempt", "commit_terminal", "classify", "classify_transport_failure_and_decide_retry_v2",
        "semantic_retry_decision", "receive_headers", "record_body", "freeze_response", "guarded_parse",
        "urlopen", "open_url", "create_connection", "connect", "connect_ex", "sleep"}
    for node in ast.walk(ast.parse(Path(r.__file__).read_text())):
        if isinstance(node, ast.Call):
            name = node.func.attr if isinstance(node.func, ast.Attribute) else node.func.id if isinstance(node.func, ast.Name) else None
            assert name not in forbidden


def test_summary_preserves_all_firewalls():
    summary = r.summary_record()
    assert all(summary[key] == 0 for key in r.NO_CALLS)
    assert all(summary[key] is False for key in r.NO_CHANGE)
    assert summary["original_22d_status_preserved"] == "failed"
    assert summary["phase_binding_v2_design_frozen"] is True
    assert summary["repair_fixture_execution_count"] == 0


def test_output_overwrite_is_rejected_before_any_audit(tmp_path, monkeypatch):
    monkeypatch.setattr(r, "OUT", tmp_path)
    with pytest.raises(ValueError, match="R0_EXISTS"):
        r.freeze_design(tmp_path / "no-verification-file.json")


def test_readonly_audit_rejects_changed_frozen_mapping_without_edits(monkeypatch):
    real = r.obj
    def changed(path):
        result = real(path)
        if Path(path).name == "mapped_observation.json":
            result = copy.deepcopy(result)
            result["mapping"]["phase"] = "RAW_RESPONSE_FROZEN"
        return result
    monkeypatch.setattr(r, "obj", changed)
    with r.d.master.prior.offline_guard(), pytest.raises(ValueError, match="MAPPING_SNAPSHOT_DRIFT"):
        r.audit_t05()
