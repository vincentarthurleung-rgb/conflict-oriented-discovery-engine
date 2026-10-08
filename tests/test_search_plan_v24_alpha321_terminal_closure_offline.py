"""Terminal accounting/exposure tests, not scientific or retry-policy tests."""

import json
import socket
from copy import deepcopy
from pathlib import Path
from unittest.mock import patch

import pytest

from scripts import run_search_plan_v24_alpha321_terminal_closure_offline as a


def forbidden(*args, **kwargs):
    raise AssertionError("CLOSURE_NETWORK_XML_SCIENCE_OR_AUTHORITY_REOPEN_FORBIDDEN")


@pytest.fixture(autouse=True)
def offline_and_no_scientific_execution(monkeypatch):
    for target, name in ((socket.socket, "connect"), (socket.socket, "connect_ex"), (socket, "create_connection"),
                         (a.d2.ET, "fromstring"), (a.d2.ET, "parse"), (a.d2.legacy.PMCTransport, "__init__"),
                         (a.d, "requests_for"), (a.d2, "execute_oa"), (a.d2, "execute_jats"),
                         (a.terminal, "collect_audit"), (a.prior, "collect_audit"), (a.b, "run")):
        monkeypatch.setattr(target, name, forbidden)


@pytest.fixture(scope="module")
def closure():
    # Module fixtures precede function fixtures, so independently enforce the
    # same important prohibitions during the shared real-artifact reconciliation.
    with a.prior.offline_guard(), patch.object(a.d2.ET, "fromstring", forbidden), \
            patch.object(a.d2.ET, "parse", forbidden), patch.object(a.d2.legacy.PMCTransport, "__init__", forbidden), \
            patch.object(a.terminal, "collect_audit", forbidden), patch.object(a.prior, "collect_audit", forbidden):
        return a.collect_closure()


def test_all_twelve_authorities_and_historical_failures_preserved(closure):
    inventory = closure["alpha3_21_phase_root_inventory"]
    assert inventory["critical_root_count"] == 12
    assert inventory["before"] == inventory["after"]
    assert all(r["verified"] for r in inventory["before"])
    states = {r["phase"]: r["execution_status"] for r in inventory["before"]}
    assert {k for k, v in states.items() if v == "failed"} == {"21C", "21D", "21D2"}
    assert states["21C.1"] == states["21D.1"] == "completed"
    assert inventory["before"][-1]["computed_sha256"] == a.D22_SHA


def test_stage_completed_does_not_mean_primary_attempt_completed(closure):
    summary = closure["summary"]
    assert summary["status"] == "completed"
    assert summary["stage_identity"] == a.STAGE
    assert summary["alpha3_21_terminal_classification"] == a.CLASSIFICATION
    assert summary["fresh_primary_attempt_started"]
    assert summary["fresh_primary_attempt_terminated"]
    assert not summary["fresh_primary_attempt_completed"]


def test_source_funnel_independent_frozen_partition_and_six_strata(closure):
    funnel = closure["alpha3_21_complete_source_funnel"]
    assert (funnel["raw_pmid_occurrence_count"], funnel["unique_acquired_pmid_count"],
            funnel["sampled_source_count"], funnel["unsampled_fresh_source_count"]) == (1200, 1015, 72, 943)
    assert funnel["preexisting_seen_pmid_intersection_count"] == 0
    assert len(funnel["per_stratum_sampled_sources"]) == 6
    assert set(funnel["per_stratum_sampled_sources"].values()) == {12}
    assert not funnel["sampling_or_deduplication_rerun"]


def test_metadata_dimension_counts_not_reinterpreted(closure):
    m = closure["alpha3_21_metadata_funnel"]
    assert (m["metadata_valid_count"], m["metadata_terminal_failure_count"]) == (72, 0)
    assert (m["date_clear_in_window_count"], m["date_clear_outside_window_count"], m["date_unresolved_count"]) == (54, 0, 18)
    assert (m["publication_type_eligible_count"], m["publication_type_excluded_count"]) == (67, 5)
    assert (m["correction_update_clear_count"], m["correction_update_deferred_count"], m["correction_update_excluded_count"]) == (69, 3, 0)
    assert (m["pre_oa_handoff_count"], m["pre_oa_clear_count"], m["pre_oa_deferred_count"]) == (49, 46, 3)
    assert m["dimension_counts_overlap"] and not m["eligibility_rules_reexecuted"]


def test_abort_partition_is_not_scientific_failure(closure):
    p = closure["alpha3_21_oa_jats_partial_funnel"]
    assert (p["oa_eligible_count"], p["oa_ineligible_count"], p["oa_terminal_failure_count"]) == (47, 2, 0)
    assert p["activated_jats_request_count"] == 47
    assert p["completed_valid_jats_count"] + p["pending_interrupted_jats_count"] + p["not_executed_after_abort_count"] == 47
    assert p["not_executed_after_abort_count"] == 37
    assert {r["state"] for r in p["not_executed_request_identities"]} == {"NOT_EXECUTED_AFTER_ABORT"}
    assert not p["unexecuted_sources_scientifically_classified"]
    assert not p["completed_identity_outcomes_extrapolated"]


def test_license_body_and_updateof_are_partial_not_cohort_outcomes(closure):
    p = closure["alpha3_21_oa_jats_partial_funnel"]
    assert (p["jats_identity_exactly_bound_count"], p["jats_identity_failure_count"]) == (9, 0)
    assert (p["license_eligible_count"], p["license_ineligible_count"], p["license_unresolved_count"]) == (6, 3, 0)
    assert (p["canonical_body_usable_count"], p["canonical_body_paragraph_count"]) == (6, 318)
    assert (p["initial_updateof_deferred_count"], p["updateof_clear_count"], p["updateof_not_reached_due_to_abort_count"]) == (3, 1, 2)
    assert p["JATS_license_BODY_construction_count_semantics"] == "PARTIAL_ONLY"


@pytest.mark.parametrize("artifact,state,count", [
    ("alpha3_21_partial_handoff_semantics", "final_construction_source_state", "final_construction_source_count"),
    ("alpha3_21_final_pool_state", "eligible_proposition_pool_state", "eligible_proposition_pool_size"),
    ("alpha3_21_final_pool_state", "fresh_primary_eligible_proposition_pool_state", "fresh_primary_eligible_proposition_count"),
])
def test_unknown_final_counts_are_null_never_zero(closure, artifact, state, count):
    assert closure[artifact][state] == "NOT_DERIVED"
    assert closure[artifact][count] is None
    assert json.loads(a.canonical(closure[artifact]))[count] is None


def test_frozen_authority_is_consumed_without_another_proof_audit(closure):
    authority = closure["alpha3_21_terminal_authority_verification"]
    assert authority["retry_authority_model"] == "UNRESOLVED"
    assert authority["body_read_interruption_covered_by_preexisting_retry_authority"] is None
    for key in ("positive_retry_authority_established", "positive_retry_exclusion_established",
                "same_attempt_network_continuation_allowed", "same_attempt_retry_policy_development_allowed",
                "additional_alpha3_21_retry_authority_audit_allowed", "alpha3_21e_allowed"):
        assert authority[key] is False
    failure = closure["alpha3_21_runtime_terminal_reason"]
    assert (failure["pmid"], failure["attempts_consumed"], failure["partial_bytes"]) == ("42731998", 1, 188590)
    assert failure["actual_qualified_exception_class"] == "UNKNOWN"
    assert failure["runtime_behavior_label"] == "RUNTIME_FAILURE_WITH_UNRESOLVED_RETRY_AUTHORITY"


def test_builder_quality_retrieval_not_evaluated_not_failed(closure):
    assert closure["alpha3_21_builder_state"]["fresh_builder_outcome"] == "NOT_EVALUATED"
    assert closure["alpha3_21_quality_state"]["fresh_quality_outcome"] == "NOT_EVALUATED"
    r = closure["alpha3_21_retrieval_evaluation_state"]
    assert r["retrieval_outcome"] == "NOT_EVALUATED"
    assert not r["search_plan_primary_evaluation_started"]
    assert not r["minimum_eight_source_group_threshold_evaluated"]
    assert not r["scientific_threshold_failure_claimed"]
    for key in a.NO_CALLS:
        assert closure["summary"][key] == 0


def test_future_contamination_is_exact_union_not_sample_only(closure):
    registry = closure["alpha3_21_future_contamination_registry"]
    history = a.obj(a.d2.MASTER / "alpha3_21_seen_contamination_registry.json")
    current = a.obj(a.b.A1 / "alpha3_21_current_attempt_source_exposure_registry.json")
    meta = a.obj(a.d2.C2 / "alpha3_21_current_attempt_metadata_identity_exposure_registry.json")
    for field, records in (("pmid", current["exposed_unique_pmids"]),
                           ("pmcid", meta["source_identities"]), ("doi", meta["source_identities"])):
        old = {r[field] for r in history["source_identities"] if r[field] is not None}
        new = {r[field] for r in records}
        assert not old & new
        assert set(registry["source_identifier_sets"][field + "s"]) == old | new
    assert len(registry["source_identifier_sets"]["pmids"]) == 3560
    assert len(registry["source_identifier_sets"]["pmcids"]) == 218
    assert len(registry["source_identifier_sets"]["dois"]) == 252
    assert registry["candidate_identities"] == history["candidate_identities"]
    assert len(registry["candidate_identities"]) == 271
    assert a.digest(a.d2.MASTER / "alpha3_21_seen_contamination_registry.json") == a.b.SEEN_SHA


def test_all_excluded_unsampled_and_unexecuted_sources_stay_seen(closure):
    contract = closure["alpha3_21_incomplete_attempt_assets_remain_seen_contract"]
    registry = closure["alpha3_21_future_contamination_registry"]
    for key in ("unsampled_acquired_PMIDs_remain_seen", "metadata_excluded_PMIDs_remain_seen",
                "OA_ineligible_PMIDs_remain_seen", "JATS_unexecuted_PMIDs_remain_source_and_metadata_seen"):
        assert set(contract[key]) <= set(registry["source_identifier_sets"]["pmids"])
    assert not contract["failed_or_incomplete_attempt_assets_return_to_fresh"]
    assert not contract["JATS_unexecuted_fulltexts_exposed"]


def test_exposure_layers_and_partial_response_quarantine(closure):
    registry = closure["alpha3_21_future_contamination_registry"]
    assert len(registry["current_attempt_source_exposures"]) == 1015
    assert len(registry["current_attempt_metadata_identities"]) == 72
    assert len(registry["current_authoritative_fulltext_exposures"]) == 9
    assert len(registry["current_partial_non_authoritative_transport_observations"]) == 1
    assert len(registry["current_seen_canonical_BODY_artifacts"]) == 6
    partial = registry["current_partial_non_authoritative_transport_observations"][0]
    assert not partial["authoritative_identity"]
    assert partial["canonical_future_source_identity"] is None
    for body in registry["current_seen_canonical_BODY_artifacts"]:
        assert a.digest(a.ROOT / body["canonical_BODY"]["artifact_path"]) == body["canonical_BODY_sha256"]


def test_scientific_zero_accounting_separate_from_external_data(closure):
    network = closure["alpha3_21_network_accounting"]
    assert network["alpha3_21_total_external_logical_requests"] == 155
    assert network["alpha3_21_total_transport_attempts"] == 166
    assert [(r["logical_requests"], r["transport_attempts"]) for r in network["by_stage"].values()] == [(24, 25), (72, 75), (49, 55), (10, 11)]
    assert closure["alpha3_21_llm_inference_accounting"]["total_LLM_scientific_calls"] == 0


def test_publication_wording_and_future_boundary_no_runtime_implementation(closure):
    wording = closure["alpha3_21_publication_safe_interpretation"]
    assert wording["long_wording"] == a.LONG
    assert wording["short_wording"] == a.SHORT
    assert not wording["positive_or_negative_generalization_claim"]
    assert closure["future_development_boundary"]["next_stage_recommendation"] == a.NEXT
    assert not closure["future_development_boundary"]["next_fresh_attempt_preregistered"]
    assert not closure["alpha3_21_no_post_outcome_repair_audit"]["runtime_fix_implemented"]
    issue = closure["known_preexisting_test_environment_issue"]
    assert issue["not_D2_protocol_or_scientific_failure"]
    assert not issue["issue_claimed_fixed"]


@pytest.mark.parametrize("value", [None, "", " 42", "0", 42, "unresolved"])
def test_unresolved_source_identity_fails_closed(value):
    with pytest.raises(RuntimeError):
        a.exact_ids([{"pmid": value}])


def registry_inputs():
    return [a.obj(a.d2.MASTER / "alpha3_21_seen_contamination_registry.json"),
            a.obj(a.b.A1 / "alpha3_21_current_attempt_source_exposure_registry.json"),
            a.obj(a.d2.C2 / "alpha3_21_current_attempt_metadata_identity_exposure_registry.json"),
            a.obj(a.d2.OUT / "alpha3_21_current_attempt_fulltext_exposure_registry.json"),
            a.rows(a.d2.OUT / "canonical_body_manifest.jsonl")]


def test_metadata_alias_collision_fails_closed_not_normalized_away():
    data = registry_inputs()
    data[2]["source_identities"][1]["doi"] = data[2]["source_identities"][0]["doi"]
    with pytest.raises(RuntimeError, match="DUPLICATE_IDENTITY:doi"):
        a.future_registry(*data)


def test_partial_response_cannot_be_promoted():
    data = registry_inputs()
    data[3]["untrusted_observations"][0]["authoritative_identity"] = True
    with pytest.raises(RuntimeError, match="PARTIAL_RESPONSE_PROMOTED"):
        a.future_registry(*data)


def test_candidate_identity_not_invented_and_duplicate_candidate_fails_closed():
    data = registry_inputs()
    data[0]["candidate_identities"].append(deepcopy(data[0]["candidate_identities"][0]))
    with pytest.raises(RuntimeError, match="DUPLICATE_IDENTITY:candidate_id"):
        a.future_registry(*data)


def test_attempt_ordinals_fail_closed_without_network(tmp_path):
    raw = tmp_path / "response.bin"
    raw.write_bytes(b"frozen-test-response")
    log = tmp_path / "attempts.jsonl"
    log.write_bytes(a.canonical({"logical_request_id": "synthetic", "attempt": 2,
        "request_payload_sha256": "immutable", "raw_path": raw.name, "raw_bytes": raw.stat().st_size,
        "raw_sha256": a.digest(raw)}) + b"\n")
    with pytest.raises(RuntimeError, match="attempt_ordinal_sequence"):
        a.attempt_accounting(log)


def test_root_mismatch_fails_closed_before_snapshot(monkeypatch):
    monkeypatch.setattr(a, "PHASES", [("master", a.d2.MASTER, a.d1.MASTER_MARKER, "0" * 64)])
    with pytest.raises(RuntimeError, match="ARTIFACT_ROOT_MISMATCH"):
        a.collect_closure()


def test_schema_counts_and_record_reconciliation_mismatch_fail_closed(monkeypatch):
    original = a.rows

    def altered(path):
        records = original(path)
        if path.name == "unsampled_fresh_source_manifest.jsonl":
            return records[:-1]
        return records

    monkeypatch.setattr(a, "rows", altered)
    with pytest.raises(RuntimeError, match="sample_unsampled_partition"):
        a.collect_closure()


def test_required_artifacts_cryptographic_freeze_and_no_overwrite(closure, monkeypatch, tmp_path):
    out = tmp_path / "closure"
    monkeypatch.setattr(a, "OUT", out)
    monkeypatch.setattr(a, "collect_closure", lambda: deepcopy(closure))
    before = a.verify_roots()
    result = a.run()
    assert result["status"] == "completed"
    assert a.verify_roots() == before
    expected_names = {stem + ".json" for stem in a.REQUIRED} | {
        a.ROOT_MARKER, a.REGISTRY_MARKER, "closure_implementation_binding.json", "focused_test_implementation_binding.json",
        "alpha3_21_publication_wording_long.txt", "alpha3_21_publication_wording_short.txt"}
    assert {p.name for p in out.iterdir()} == expected_names
    assert not any(p.is_symlink() for p in out.rglob("*"))
    assert (out / a.ROOT_MARKER).read_text().strip() == a.root_hash(out, a.ROOT_MARKER)
    assert (out / a.REGISTRY_MARKER).read_text().strip() == a.digest(out / "alpha3_21_future_contamination_registry.json")
    assert (out / "alpha3_21_publication_wording_long.txt").read_text() == a.LONG + "\n"
    assert (out / "alpha3_21_publication_wording_short.txt").read_text() == a.SHORT + "\n"
    with pytest.raises(RuntimeError, match="ALREADY_EXISTS_NO_OVERWRITE"):
        a.run()


def test_integrity_failure_does_not_create_successful_terminal_snapshot(monkeypatch, tmp_path):
    monkeypatch.setattr(a, "OUT", tmp_path / "failed")

    def fail():
        raise RuntimeError("FROZEN_REGISTRY_MISMATCH")

    monkeypatch.setattr(a, "collect_closure", fail)
    result = a.run()
    assert result["status"] == "failed"
    assert "FROZEN_REGISTRY_MISMATCH" in result["closure_failure"]
    assert "future_seen_unique_pmid_count" not in result
    assert "alpha3_21_terminal_classification" not in result
    assert not (a.OUT / "alpha3_21_publication_wording_long.txt").exists()
