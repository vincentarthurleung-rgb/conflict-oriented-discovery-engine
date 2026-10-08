"""Offline authority proof tests; synthetic findings are never pre-D2 authority."""

import socket
from copy import deepcopy
from pathlib import Path
from unittest.mock import patch

import pytest

from scripts import run_search_plan_v24_alpha321d22_final_retry_authority_offline as a


@pytest.fixture(autouse=True)
def no_network_or_actual_XML_processing(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("NETWORK_ACTUAL_JATS_OR_EXECUTION_FORBIDDEN")
    monkeypatch.setattr(socket.socket, "connect", forbidden)
    monkeypatch.setattr(socket.socket, "connect_ex", forbidden)
    monkeypatch.setattr(socket, "create_connection", forbidden)
    # Preserve callable-source hash bindings while prohibiting the actual XML
    # parsing underneath every frozen identity/license/BODY helper.
    monkeypatch.setattr(a.d2.ET, "fromstring", forbidden)
    monkeypatch.setattr(a.d2.ET, "parse", forbidden)
    monkeypatch.setattr(a.d2.legacy.PMCTransport, "__init__", forbidden)
    monkeypatch.setattr(a.d2.d1.d, "requests_for", forbidden)
    monkeypatch.setattr(a.d2, "execute_oa", forbidden)
    monkeypatch.setattr(a.d2, "execute_jats", forbidden)


def evidence(kind, *, tier=1, **fields):
    return {"evidence_id": "synthetic_proof_evaluator_fixture", "tier": tier,
            "pre_d2_proven": True, "same_PMC_JATS_authority": True, "kind": kind, **fields}


@pytest.mark.parametrize("kind", sorted(a.INCLUSION_KINDS))
def test_positive_inclusion_requires_explicit_positive_preexisting_proof(kind):
    e = evidence(kind, positive_proof=True, equivalent_mid_body_mechanics=True,
                 broader_frozen_semantic_contract_bound=True)
    result = a.classify_evidence([e])
    assert result["classification"] == a.CLASS_A
    assert result["positive_retry_authority_established"]
    assert result["body_read_interruption_covered_by_preexisting_retry_authority"] is True
    assert result["runtime_behavior_label"] == "IMPLEMENTATION_COVERAGE_DEFECT"
    e["positive_proof"] = False
    assert a.classify_evidence([e])["classification"] == a.CLASS_C


@pytest.mark.parametrize("kind", ["UNDEFINED_TRANSPORT_WORD", "GENERIC_CONNECTION_RESET", "TIMEOUT_SUPPORT",
                                 "HTTP_5XX_SUPPORT", "CLOSED_STATUS_PREDICATE_NOT_BODY_STATE_DOMAIN",
                                 "SYNTHETIC_INCOMPLETE_READ", "CONVENIENT_RECOVERY", "PARTIAL_BYTE_COUNT"])
def test_weak_evidence_does_not_establish_inclusion_or_exclusion(kind):
    result = a.classify_evidence([evidence(kind, positive_proof=True)])
    assert result["classification"] == a.CLASS_C
    assert result["body_read_interruption_covered_by_preexisting_retry_authority"] is None
    assert not result["positive_retry_authority_established"]
    assert not result["positive_retry_exclusion_established"]
    assert result["runtime_behavior_label"] == "RUNTIME_FAILURE_WITH_UNRESOLVED_RETRY_AUTHORITY"


@pytest.mark.parametrize("field", ["pre_d2_proven", "same_PMC_JATS_authority"])
def test_post_D2_or_different_authority_cannot_satisfy_threshold(field):
    e = evidence("EXPLICIT_FROZEN_BODY_READ_RETRY_TEXT", positive_proof=True)
    e[field] = False
    assert a.classify_evidence([e])["classification"] == a.CLASS_C


def test_generic_web_synthetic_or_fresh_scientific_authority_is_forbidden():
    e = evidence("EXPLICIT_FROZEN_BODY_READ_RETRY_TEXT", positive_proof=True, forbidden_authority=True)
    assert a.classify_evidence([e])["classification"] == a.CLASS_C


def test_read_inside_transport_does_not_define_retry_state_without_bound_semantic_contract():
    e = evidence("BOUND_FULL_BODY_COMPLETION_RETRY_STATE", positive_proof=True,
                 broader_frozen_semantic_contract_bound=False)
    assert a.classify_evidence([e])["classification"] == a.CLASS_C


@pytest.mark.parametrize("kind", ["PRE_D2_EQUIVALENT_MID_BODY_RETRY_TEST", "PRE_D2_EQUIVALENT_HISTORICAL_BODY_RETRY"])
def test_connection_or_timeout_without_equivalent_read_mechanics_is_insufficient(kind):
    e = evidence(kind, positive_proof=True, equivalent_mid_body_mechanics=False)
    assert a.classify_evidence([e])["classification"] == a.CLASS_C


def test_positive_exclusion_requires_both_closed_domain_and_explicit_body_exclusion():
    e = evidence("EXPLICIT_CLOSED_BODY_INTERRUPTION_EXCLUSION", closed_domain_positive_proof=True,
                 body_interruption_exclusion_positive_proof=True)
    result = a.classify_evidence([e])
    assert result["classification"] == a.CLASS_B
    assert result["positive_retry_exclusion_established"]
    assert result["body_read_interruption_covered_by_preexisting_retry_authority"] is False
    assert not result["runtime_recovery_within_same_primary_attempt_allowed"]
    for field in ("closed_domain_positive_proof", "body_interruption_exclusion_positive_proof"):
        changed = {**e, field: False}
        assert a.classify_evidence([changed])["classification"] == a.CLASS_C


def test_higher_tier_explicit_authority_is_not_overridden_by_lower_tier():
    inclusion = evidence("EXPLICIT_FROZEN_BODY_READ_RETRY_TEXT", positive_proof=True)
    exclusion = evidence("EXPLICIT_CLOSED_BODY_INTERRUPTION_EXCLUSION", tier=4,
                         closed_domain_positive_proof=True, body_interruption_exclusion_positive_proof=True)
    assert a.classify_evidence([inclusion, exclusion])["classification"] == a.CLASS_A
    inclusion["tier"], exclusion["tier"] = 4, 1
    assert a.classify_evidence([inclusion, exclusion])["classification"] == a.CLASS_B
    inclusion["tier"] = 1
    result = a.classify_evidence([inclusion, exclusion])
    assert result["classification"] == a.CLASS_C
    assert result["same_tier_positive_evidence_conflict"]


@pytest.fixture(scope="module")
def snapshot():
    def forbidden(*args, **kwargs):
        raise AssertionError("ACTUAL_JATS_OR_TRANSPORT_CONSTRUCTION_FORBIDDEN")
    with a.prior.offline_guard(), patch.object(a.d2.ET, "fromstring", forbidden), \
            patch.object(a.d2.ET, "parse", forbidden), patch.object(a.d2.legacy.PMCTransport, "__init__", forbidden):
        return a.collect_audit()


def test_actual_frozen_authority_remains_unresolved_with_enforced_pre_D2_cutoff(snapshot):
    result = snapshot["summary"]
    assert result["alpha3_21d22_classification"] == a.CLASS_C
    assert result["pre_d2_authority_cutoff_enforced"]
    assert not result["positive_retry_authority_established"]
    assert not result["positive_retry_exclusion_established"]
    assert result["body_read_interruption_covered_by_preexisting_retry_authority"] is None
    assert not result["actual_exception_qualified_class_known"]
    assert not result["further_same_attempt_authority_audit_allowed"]
    assert result["primary_attempt_must_close_incomplete"]
    assert result["next_stage_recommendation"] == a.NEXT_C


def test_exact_contract_text_and_git_temporal_proofs_are_preserved(snapshot):
    for item in snapshot["frozen_retry_contract_exact_text_evidence"]["documents"]:
        raw = (a.ROOT / item["document"]["artifact_path"]).read_bytes()
        assert item["exact_UTF8_text"].encode() == raw
        assert a.sha(raw) == item["exact_text_bytes_sha256"] == item["document"]["sha256"]
    for item in snapshot["pre_d2_git_history_retry_semantics_audit"]["files"]:
        assert item["current_bytes_proven_pre_D2_by_git"]
        assert any(s["predates_cutoff"] and s["matches_current_frozen_bytes"] for s in item["snapshots"])


def test_historical_connection_reset_retry_and_nonretried_read_timeout_are_not_positive_coverage(snapshot):
    history = snapshot["pre_d2_historical_transport_failure_inventory"]
    assert history["PMC_attempt_count"] == 167
    assert history["JATS_attempt_count"] == 82
    assert len(history["failures"]) == 2
    assert history["equivalent_historical_body_interruption_retry_count"] == 0
    assert history["IncompleteRead_label_count"] == 0
    connection = next(r for r in history["failures"] if "Connection reset" in r["transport_error"])
    timeout = next(r for r in history["failures"] if r["transport_error"].startswith("TimeoutError:"))
    assert connection["http_status"] is None and connection["later_attempts_recorded"] == 1
    assert timeout["http_status"] == 200 and timeout["later_attempts_recorded"] == 0
    assert not connection["equivalent_mid_body_retry_positive_proof"]
    assert not timeout["equivalent_mid_body_retry_positive_proof"]


def test_attempt_budget_arithmetic_does_not_authorize_execution(snapshot):
    budget = snapshot["d2_attempt_budget_audit"]
    assert (budget["maximum_attempts"], budget["attempts_consumed"], budget["remaining_attempts"]) == (4, 1, 3)
    assert budget["hypothetical_next_ordinal_if_A"] == 2
    assert len(budget["original_remaining_order_ids"]) == 37
    assert budget["conditional_arithmetic_additional_ceiling_if_A"] == 3 + 37 * 4 == 151
    assert budget["conditional_arithmetic_cumulative_ceiling_if_A"] == 66 + 151 == 217
    assert budget["maximum_additional_transport_attempts"] is None
    assert budget["maximum_final_cumulative_transport_attempts"] is None
    assert snapshot["d2_continuation_eligibility"]["executable"] is False


def test_oa_and_successful_jats_are_skipped_without_new_request_universe(snapshot):
    result = snapshot["summary"]
    assert result["oa_phase_reexecution_allowed"] is False
    assert result["successful_jats_refresh_allowed"] is False
    original = a.rows(a.d2.d1.REQUESTS)
    rest = snapshot["d2_attempt_budget_audit"]["original_remaining_order_ids"]
    successful = snapshot["successful_jats_immutability_audit"]["preserved_state"]["successful_logical_request_ids"]
    by_id = {r["logical_request_id"]: r for r in original}
    assert all(by_id[key]["request_class"] == "PMC_JATS" for key in rest)
    assert not set(rest) & set(successful)
    assert len(successful) == 9
    assert not snapshot["d2_continuation_eligibility"]["new_request_universe_created"]


def test_partial_response_and_partial_handoff_never_become_final_or_parser_input(snapshot):
    partial = snapshot["partial_response_quarantine_audit"]["preserved_state"]
    assert partial["preserved_bytes"] == 188590
    assert not partial["trusted_jats_parsed"]
    assert not partial["identity_authoritative"]
    assert not partial["body_authoritative"]
    handoff = snapshot["partial_handoff_nonfinal_audit"]["preserved_state"]
    assert handoff["partial_construction_source_count"] == 6
    assert handoff["final_construction_source_count"] == "NOT_DERIVED"
    assert not handoff["alpha3_21e_handoff_eligible"]


def test_future_exposure_history_is_preserved_without_self_exclusion_or_restoring_freshness(snapshot):
    exposure = snapshot["fresh_attempt_exposure_preservation_audit"]
    assert exposure["current_authoritative_fulltext_exposure_count"] == 9
    assert exposure["current_partial_non_authoritative_observation_count"] == 1
    assert not exposure["current_attempt_self_exclusion_allowed"]
    assert not exposure["return_exposed_assets_to_fresh_after_failure_allowed"]
    assert not exposure["registry_mutated"]
    assert exposure["partial_non_authoritative_identity_not_promoted"]


def test_append_only_freeze_preserves_all_upstream_roots_and_has_no_overlay(monkeypatch, tmp_path, snapshot):
    upstream = [(a.prior.OUT, a.prior.ROOT_MARKER), (a.d2.OUT, a.d2.ROOT_MARKER),
                (a.d2.D1, a.d2.d1.ROOT_MARKER), (a.d2.D, a.d2.d1.d.ROOT_MARKER)]
    before = [a.root_hash(path, marker) for path, marker in upstream]
    monkeypatch.setattr(a, "OUT", tmp_path / "output")
    # collect_audit was already tested with real read-only frozen evidence.
    monkeypatch.setattr(a, "collect_audit", lambda: deepcopy(snapshot))
    result = a.run()
    assert result["status"] == "completed"
    assert result["alpha3_21d22_classification"] == a.CLASS_C
    assert all(result[key] == 0 for key in a.NO_CALLS)
    assert a.root_hash(a.OUT, a.ROOT_MARKER) == result[a.ROOT_MARKER]
    assert all((a.OUT / (name + ".json")).is_file() for name in a.REQUIRED)
    assert not any((a.OUT / name).exists() for name in a.A_ONLY)
    assert [a.root_hash(path, marker) for path, marker in upstream] == before
    with pytest.raises(Exception, match="NO_OVERWRITE"):
        a.run()


def test_integrity_barrier_failure_closes_without_retry_or_more_authority_audits(monkeypatch, tmp_path):
    def failed():
        raise RuntimeError("ARTIFACT_ROOT_MISMATCH:synthetic")
    monkeypatch.setattr(a, "collect_audit", failed)
    monkeypatch.setattr(a, "OUT", tmp_path / "integrity_failure")
    result = a.run()
    assert result["status"] == "failed"
    assert result["alpha3_21d22_classification"] == a.CLASS_INTEGRITY
    assert not result["runtime_recovery_within_same_primary_attempt_allowed"]
    assert not result["further_same_attempt_authority_audit_allowed"]
    assert result["next_stage_recommendation"] == a.NEXT_INTEGRITY


def test_mutating_git_commands_are_never_allowed():
    with pytest.raises(Exception, match="MUTATING_GIT_COMMAND_FORBIDDEN"):
        a.git_read(["checkout", "synthetic-do-not-execute"])
