"""Static preregistration validation. No prospective runtime/fault test is run."""

from copy import deepcopy
from pathlib import Path
from unittest.mock import patch

import pytest

from scripts import run_search_plan_v24_alpha322_master_prereg_offline as a


def forbidden(*args, **kwargs):
    raise AssertionError("MASTER_RUNTIME_NETWORK_PARSER_OR_HISTORICAL_EXECUTION_FORBIDDEN")


@pytest.fixture(autouse=True)
def no_transport_science_or_historical_execution(monkeypatch):
    for target, name in ((a.d2.legacy.PMCTransport, "__init__"), (a.d2, "execute_oa"), (a.d2, "execute_jats"),
                         (a.d2.ET, "fromstring"), (a.d2.ET, "parse"), (a.closed, "run"),
                         (a.closed, "collect_closure"), (a.prior, "collect_audit"), (a.closed.terminal, "collect_audit")):
        monkeypatch.setattr(target, name, forbidden)
    with a.prior.offline_guard():
        yield


@pytest.fixture(scope="module")
def protocol():
    with a.prior.offline_guard(), patch.object(a.d2.ET, "fromstring", forbidden), \
            patch.object(a.d2.ET, "parse", forbidden), patch.object(a.d2.legacy.PMCTransport, "__init__", forbidden), \
            patch.object(a.closed, "collect_closure", forbidden), patch.object(a.prior, "collect_audit", forbidden):
        return a.build_protocol()


def test_terminal_closure_and_sole_contamination_baseline_verified(protocol):
    assert protocol["alpha3_21_closure_root_verification"]["computed_sha256"] == a.CLOSURE_SHA
    terminal = protocol["alpha3_21_terminal_state_binding"]
    assert terminal["alpha3_21_terminal_classification"] == a.closed.CLASSIFICATION
    for k in ("alpha3_21_reopen_allowed", "alpha3_21_network_continuation_allowed", "alpha3_21_builder_execution_allowed", "alpha3_21_quality_execution_allowed"):
        assert terminal[k] is False
    baseline = protocol["future_fresh_contamination_baseline"]
    assert baseline["alpha3_21_future_contamination_registry_sha256"] == a.REGISTRY_SHA
    assert {k: baseline[k] for k in a.COUNTS} == a.COUNTS
    assert not baseline["competing_registry_created"]
    assert not baseline["registry_content_copied_or_modified"]
    assert not baseline["baseline_reduction_allowed"]


def test_development_only_no_runtime_or_fresh_attempt(protocol):
    assert protocol["summary"]["alpha3_22_master_classification"] == a.CLASSIFICATION
    assert protocol["summary"]["stage_identity"] == a.STAGE
    assert protocol["summary"]["development_mode"]
    for k in a.NO_FRESH:
        assert protocol["summary"][k] is False
    for k in a.NO_CALLS:
        assert protocol["summary"][k] == 0
    assert not protocol["summary"]["production_runtime_modified"]
    assert not protocol["alpha3_22_development_identity"]["runtime_implementation_performed"]


def test_scientific_firewall_complete_and_hash_bound(protocol):
    firewall = protocol["alpha3_22_scientific_policy_firewall"]
    assert all(v is False for k, v in firewall.items() if k.endswith("_allowed"))
    expected = {"selected_V1_relation_sentence_prompt_change_allowed", "BuilderOutputSchemaV4_change_allowed",
                "EvidenceReferenceContractV4_change_allowed", "GroundingContractV4_change_allowed",
                "PropositionAbstractionContractV1_change_allowed", "leakage_policy_change_allowed",
                "QualityResponseEnvelopeV3_change_allowed", "source_scientific_query_design_change_allowed"}
    assert expected <= set(firewall)
    for binding in firewall["frozen_scientific_authority_bindings"].values():
        assert a.digest(a.ROOT / binding["artifact_path"]) == binding["sha256"]


def test_lifecycle_contains_body_states_and_explicit_parser_guard(protocol):
    lifecycle = protocol["transport_lifecycle_contract_v2_draft"]
    assert lifecycle["states"] == a.STATES
    assert lifecycle["implementation_state"] == "NOT_IMPLEMENTED"
    body_guard = next(r["guard"] for r in lifecycle["transitions"] if r["to"] == "RESPONSE_BODY_COMPLETE")
    assert "normal read return" in body_guard and "framing/integrity" in body_guard
    assert "partial RAW_RESPONSE_FROZEN" in lifecycle["forbidden_transition"]
    complete = protocol["response_body_completion_semantics"]
    assert not complete["HTTP_status_or_headers_sufficient"]
    assert complete["encoded_wire_length_must_not_be_compared_to_decoded_length"]
    assert complete["alternate_representation_requires_explicit_frozen_client_semantics"]


def test_semantic_matrix_distinguishes_body_HTTP_backend_parser_and_unknown(protocol):
    matrix = protocol["transport_retryability_matrix"]["entries"]
    assert [r["semantic_state"] for r in matrix] == a.TAXONOMY
    by_state = {r["semantic_state"]: r for r in matrix}
    assert by_state["RESPONSE_BODY_TRANSPORT_INTERRUPTION"]["retryable_technical_class"]
    assert by_state["RESPONSE_BODY_LENGTH_MISMATCH"]["retryable_technical_class"]
    assert not by_state["UNKNOWN_RUNTIME_FAILURE"]["retryable_technical_class"]
    assert not by_state["COMPLETE_BODY_RESPONSE_VALIDITY_FAILURE"]["retryable_technical_class"]
    assert "component-specific" in by_state["RETRYABLE_PROVIDER_BACKEND_FAILURE"]["additional_authority_requirement"]
    retry = protocol["transport_retry_semantics_v2_draft"]
    assert retry["future_body_interruption_retry_requires_replay_safe_request"]
    assert not retry["retroactive_alpha321_authorization"]
    assert not retry["catch_Exception_OSError_IOError_retry_authorized"]


def test_numeric_policies_and_replay_safety_supported_but_not_assumed_for_arbitrary_GET(protocol):
    inventory = protocol["repository_runtime_authority_inventory"]
    assert len(inventory["components"]) == 3
    for component in inventory["components"]:
        assert (component["maximum_attempts_per_logical_request"], component["timeout_seconds"], component["backoff_seconds"]) == (4, 60, [2, 4, 8])
    assert [r["request_count"] for r in inventory["request_route_evidence"]] == [24, 72, 98]
    replay = protocol["replay_safe_request_design_contract"]
    assert replay["repository_read_only_acquisition_routes_confirmed"]
    assert replay["explicit_frozen_request_replay_safe_declaration_required"]
    assert not replay["method_GET_alone_sufficient"]
    assert not replay["arbitrary_future_request_replay_safety_assumed"]


def test_concrete_mapper_is_deferred_to_B_not_frozen_by_exception_name(protocol):
    mapping = protocol["transport_exception_mapping_design_contract"]
    assert mapping["mapping_entries"] == []
    assert not mapping["concrete_mapping_inventory_frozen"]
    assert mapping["inventory_phase"] == "alpha3.22B"
    assert not mapping["exception_name_string_only_mapping_allowed"]
    assert not mapping["broad_base_class_retry_allowed"]


@pytest.mark.parametrize("name,fields", [
    ("exception_provenance_schema", {"root_exception_node_id", "exception_nodes", "runtime_identity", "redaction_paths"}),
    ("http_response_provenance_schema", {"status", "reason", "response_headers", "content_length_raw", "transfer_encoding", "content_encoding", "request_url_without_secrets", "HTTP_provenance_trusted"}),
    ("body_read_provenance_schema", {"body_read_started_at", "body_read_ended_at", "body_read_failed_at", "bytes_read", "partial_body_artifact_path", "partial_body_sha256", "expected_content_length_bytes", "completion_state", "semantic_failure_state"}),
    ("retry_decision_provenance_schema", {"retryable", "retry_decision_authority", "remaining_attempts_before_decision", "remaining_attempts_after_decision", "backoff_selected_seconds", "decision"}),
])
def test_provenance_schemas_static_required_fields_no_unavailable_inference(protocol, name, fields):
    schema = protocol[name]
    assert fields <= set(schema["required"])
    assert set(schema["required"]) == set(schema["properties"])
    assert schema["additionalProperties"] is False
    assert "unavailable_fields" in schema["required"]
    assert schema["$schema"] == "http://json-schema.org/draft-07/schema#"


def test_exception_nodes_include_module_qualified_class_chain_and_args(protocol):
    node = protocol["exception_provenance_schema"]["properties"]["exception_nodes"]["items"]
    assert {"module", "class_name", "qualified_class_name", "message", "repr", "args", "traceback", "cause_node_id", "context_node_id", "suppress_context"} <= set(node["required"])
    observable = protocol["transport_observability_contract_v1_draft"]
    assert observable["broad_exception_capture_for_observability_allowed"]
    assert not observable["broad_exception_capture_implies_retry"]
    assert "redaction" in observable["secrets_policy"]


def test_quarantine_complete_invalid_and_unknown_never_broad_retry(protocol):
    quarantine = protocol["partial_response_quarantine_contract"]
    assert not quarantine["partial_response_authoritative"]
    assert not quarantine["partial_response_parser_allowed"]
    assert {"XML parser", "complete-body JSON parser", "JATS identity validator", "license parser", "BODY normalization", "scientific extraction"} == set(quarantine["blocked_consumers"])
    retry = protocol["transport_retry_semantics_v2_draft"]
    assert not retry["complete_validity_failure_automatic_transport_retry"]
    assert not retry["unknown_runtime_failure_automatic_retry"]


def test_open_attempt_rule_is_explicitly_frozen_and_consumes_ordinal(protocol):
    restart = protocol["process_restart_semantics"]
    assert restart["open_attempt_rule"] == "ACCEPTED_PROSPECTIVELY_FOR_FUTURE_VERSIONED_RUNTIME"
    assert restart["started_without_trusted_terminal_state"] == "ABANDONED_ATTEMPT_UNKNOWN_TERMINATION"
    assert restart["abandoned_attempt_consumes_ordinal"]
    assert restart["no_reuse_of_abandoned_ordinal"]
    assert not restart["retry_budget_reset"]
    assert "attempt 3" in restart["example"]
    attempt = protocol["attempt_consumption_contract"]
    assert attempt["retries_backoff_by_consumed_ordinal"] == {"1_to_2": 2, "2_to_3": 4, "3_to_4": 8}
    assert attempt["backoff_persists_across_process_restart"]


def test_append_only_journal_and_barrier_resume_design(protocol):
    journal = protocol["append_only_attempt_journal_contract_v1_draft"]
    assert journal["append_only_attempt_journal_required"]
    assert not journal["overwrite_or_delete_prior_events_allowed"]
    assert journal["write_ahead_start_before_network_required"]
    assert journal["one_active_writer_or_locked_atomic_reservation_required"]
    assert "never truncate" in journal["torn_tail_policy"]
    assert protocol["continuation_order_contract"]["successful_request_refresh_allowed"] is False
    barrier = protocol["two_phase_barrier_resume_contract"]
    assert barrier["frozen_activation_barrier_must_be_consumed"]
    assert not barrier["live_OA_recomputation_allowed"]
    assert not barrier["completed_OA_phase_refresh_allowed"]


def test_fourteen_fault_requirements_are_frozen_not_executed(protocol):
    matrix = protocol["fault_injection_matrix_contract"]
    cases = {r["case_id"]: r for r in matrix["cases"]}
    assert len(cases) == 14
    assert {"connection_failure_before_headers", "timeout_before_headers", "HTTP_retryable_status", "HTTP_nonretryable_status", "connection_reset_during_body_read", "timeout_during_body_read", "incomplete_body_transfer", "declared_Content_Length_mismatch", "complete_valid_body", "complete_malformed_XML_body", "complete_JATS_identity_mismatch", "unknown_exception_during_body_read", "process_termination_with_open_attempt"} <= set(cases)
    assert all(r["execution_state"] == "NOT_EXECUTED" for r in cases.values())
    assert not matrix["matrix_executed_in_master"]
    assert not protocol["historical_regression_contract"]["regressions_run_in_master"]
    fixture = protocol["seen_failure_fixture_usage_contract"]
    assert fixture["expected_bytes"] == 188590
    assert fixture["partial_qualified_exception_class"] == "UNKNOWN"
    assert not fixture["successful_full_JATS_claim_allowed"]
    assert not fixture["fixture_parsed_in_master"]


def test_phase_chain_and_release_gate_cannot_start_fresh_attempt(protocol):
    phases = protocol["alpha3_22_phase_plan"]["phases"]
    assert [r["phase"] for r in phases] == [r[0] for r in a.PHASES]
    assert [r["depends_on"] for r in phases] == ["MASTER_PREREGISTRATION", *[r[0] for r in a.PHASES[:-1]]]
    assert all(r["execution_state"] == "NOT_STARTED" for r in phases)
    gate = protocol["alpha3_22_release_gate"]
    assert len(gate["require_all"]) == 12
    assert not gate["implementation_release_gate_satisfied"]
    assert not gate["fresh_primary_start_allowed"]
    assert protocol["summary"]["next_stage_recommendation"] == a.NEXT


@pytest.mark.parametrize("artifact,field,value", [
    ("transport_retry_semantics_v2_draft", "retroactive_alpha321_authorization", True),
    ("transport_retry_semantics_v2_draft", "unknown_runtime_failure_automatic_retry", True),
    ("transport_retry_semantics_v2_draft", "future_body_interruption_retry_requires_replay_safe_request", False),
    ("partial_response_quarantine_contract", "partial_response_parser_allowed", True),
    ("attempt_consumption_contract", "attempt_ordinal_reset_on_retry", True),
    ("two_phase_barrier_resume_contract", "live_OA_recomputation_allowed", True),
])
def test_static_semantic_safety_drift_fails_closed(protocol, artifact, field, value):
    docs = deepcopy(protocol)
    docs[artifact][field] = value
    with pytest.raises(RuntimeError, match="SEMANTIC_DESIGN_SAFETY_DRIFT"):
        a.validate_design(docs)


def test_frozen_registry_hash_mismatch_fails_closed(monkeypatch):
    monkeypatch.setattr(a, "REGISTRY_SHA", "0" * 64)
    with pytest.raises(RuntimeError, match="CONTAMINATION_BASELINE_MISMATCH"):
        a.build_protocol()


def test_closure_root_mismatch_fails_closed(monkeypatch):
    monkeypatch.setattr(a, "CLOSURE_SHA", "0" * 64)
    with pytest.raises(RuntimeError, match="ARTIFACT_ROOT_MISMATCH"):
        a.build_protocol()


def test_future_release_claim_fails_static_validation(protocol):
    docs = deepcopy(protocol)
    docs["alpha3_22_release_gate"]["implementation_release_gate_satisfied"] = True
    with pytest.raises(RuntimeError, match="PREMATURE_RUNTIME_RELEASE"):
        a.validate_design(docs)


def test_semantic_bundle_and_plan_hash_members_are_deterministic(protocol):
    b1, h1, p1, h2 = a.bundle_documents(protocol)
    assert (b1, h1, p1, h2) == a.bundle_documents(deepcopy(protocol))
    assert len(b1["members"]) == len(a.SEMANTIC_STEMS)
    assert h1 == a.sha(a.canonical(b1) + b"\n")
    assert h2 == a.sha(a.canonical(p1) + b"\n")
    assert not p1["execute_implementation_now"]
    for r in b1["members"]:
        stem = Path(r["artifact_path"]).stem
        assert r["sha256"] == a.sha(a.canonical(protocol[stem]) + b"\n")


def test_official_writer_freezes_only_new_master_and_never_overwrites(protocol, monkeypatch, tmp_path):
    out = tmp_path / "master"
    monkeypatch.setattr(a, "OUT", out)
    # Manifest refs are required to stay repository-relative, even in a
    # writer fixture. Redirect only this path's relative conversion below.
    real_bundle = a.bundle_documents

    def bundle(docs):
        with patch.object(a, "OUT", a.ROOT / "runs/TEST_ONLY_ALPHA322_MASTER"):
            return real_bundle(docs)

    monkeypatch.setattr(a, "bundle_documents", bundle)
    monkeypatch.setattr(a, "build_protocol", lambda: deepcopy(protocol))
    # The synthetic manifest refs above don't point at physical repo files;
    # verify their hashes independently against test output below.
    monkeypatch.setattr(a.d2.d1.d, "checked_tree", lambda x: None)
    result = a.run()
    assert result["status"] == "completed"
    assert (out / a.ROOT_MARKER).read_text().strip() == a.root_hash(out, a.ROOT_MARKER)
    for marker, file in [(a.BUNDLE_MARKER, "alpha3_22_transport_semantics_bundle.json"), (a.PLAN_MARKER, "alpha3_22_master_execution_plan.json")]:
        assert (out / marker).read_text().strip() == a.digest(out / file)
    assert not any(p.is_symlink() for p in out.rglob("*"))
    for member in a.obj(out / "alpha3_22_transport_semantics_bundle.json")["members"]:
        assert a.digest(out / Path(member["artifact_path"]).name) == member["sha256"]
    with pytest.raises(RuntimeError, match="OUTPUT_EXISTS_NO_OVERWRITE"):
        a.run()


def test_blocked_master_does_not_freeze_successful_bundle(monkeypatch, tmp_path):
    monkeypatch.setattr(a, "OUT", tmp_path / "blocked")

    def fail():
        raise RuntimeError("UNVERIFIED_BASELINE")

    monkeypatch.setattr(a, "build_protocol", fail)
    result = a.run()
    assert result["status"] == "failed"
    assert not (a.OUT / a.BUNDLE_MARKER).exists()
    assert not (a.OUT / a.PLAN_MARKER).exists()
    assert not result["runtime_activation_allowed"]
