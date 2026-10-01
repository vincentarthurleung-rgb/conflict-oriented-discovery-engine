"""Offline integrity and nonadaptation checks for alpha3.19A.1."""
from scripts import search_plan_v24_alpha319a1_audit_backend_failure_offline as audit
from scripts import search_plan_v24_alpha319_master_preregister_offline as master
from scripts import search_plan_v24_alpha319a_preregister_source_acquisition_offline as prereg
from scripts import search_plan_v24_alpha319a1_esearch_response_validity_v2_1 as v21


def test_frozen_failure_and_audit_root():
    assert audit.failed.root_hash() == audit.FAILED_SHA
    assert audit.root_hash() == (audit.OUT / audit.ROOT_MARKER).read_text().strip()
    assert audit.load(audit.OUT / "summary.json")["historical_failure_classification"] == "RESPONSE_SCHEMA_INVALID"
    assert not (audit.FAILED / "deterministic_source_sampling_results.jsonl").exists()


def test_raw_backend_envelope_and_historical_accounting():
    raw = audit.FAILED / "source_query_raw_responses/05_150_attempt2.bin"
    assert master.digest(raw) == "aef9ad596fe089f1907c40ea6126abd35414ec1746a310a04e5453bb24bf5b67"
    assert v21.validate_response(200, raw.read_bytes(), 150, 50)["state"] == "NCBI_ESearch_BACKEND_ERROR"
    accounting = audit.load(audit.OUT / "historical_retry_accounting.json")
    assert accounting["logical_page_requests"] == 20
    assert accounting["actual_ncbi_attempts"] == 22
    assert accounting["failing_logical_request_attempts"] == 2
    assert not accounting["third_historical_attempt_allowed_now"]


def test_a2_manifest_preserves_science_and_restarts_from_zero():
    old = audit.load(prereg.OUT / "alpha3_19a_source_acquisition_execution_manifest.json")
    new = audit.load(audit.OUT / "alpha3_19a2_source_acquisition_execution_manifest.json")
    keys = audit.load(audit.OUT / "scientific_configuration_nonadaptation_audit.json")[
        "scientific_manifest_keys_preserved"]
    assert all(new[key] == old[key] for key in keys)
    assert new["restart_mode"] == "FULL_SIX_FRAME_FROM_FRAME_1_RETSTART_0"
    assert new["source_run_disposition"] == "FAILED_19A_PROVENANCE_ONLY_NO_DIRECT_IMPORT"
    assert new["response_aware_retry_adapter_required"]
    assert new["material_runtime_policy_unresolved_count"] == 0
    assert master.digest(audit.OUT / "alpha3_19a2_source_acquisition_execution_manifest.json") == (
        audit.OUT / "alpha3_19a2_source_acquisition_execution_manifest_sha256").read_text().strip()
    assert master.digest(audit.OUT / "pubmed_esearch_response_validity_v2_1.json") == (
        audit.OUT / "pubmed_esearch_response_validity_v2_1_sha256").read_text().strip()


def test_retry_boundaries_and_no_network():
    retry = audit.load(audit.OUT / "alpha3_19a2_retry_policy.json")
    assert retry["attempts_max_per_logical_page"] == 4
    assert retry["HTTP200_NCBI_ESearch_BACKEND_ERROR"] == "RETRY_WITHIN_SAME_FOUR_ATTEMPTS"
    assert retry["HTTP200_QUERY_SEMANTIC_ERROR"] == "FAIL_CLOSED_NO_RETRY"
    assert not retry["technical_budget_increased"]
    summary = audit.load(audit.OUT / "summary.json")
    assert summary["network_calls"] == summary["provider_calls"] == summary["llm_calls"] == 0
    assert summary["full_six_frame_restart_eligible"]
