import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RUN = ROOT / "runs/20260924_search_plan_v24_dev_retrieval_surface_v2_full_retrieval"


def load(name):
    return json.loads((RUN / name).read_text())


def rows(name):
    return [json.loads(line) for line in (RUN / name).read_text().splitlines() if line]


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_terminal_failure_exhausted_frozen_retry_policy():
    failure = load("technical_terminal_failure.json")
    assert failure["failure_class"] == "NETWORK_FAILURE"
    assert failure["stage"] == "PUBMED_SEARCH"
    assert failure["attempt_count"] == failure["maximum_total_attempts"] == 4
    assert [row["attempt"] for row in failure["errors"]] == [1, 2, 3, 4]
    assert failure["backoff_seconds"] == [2, 4, 8]
    assert failure["fail_closed"] is True
    assert failure["further_network_requests_after_failure"] == 0


def test_partial_query_outcomes_are_not_misclassified():
    query_rows = rows("query_execution_results.jsonl")
    assert len(query_rows) == 25
    states = {state: sum(row["transport_status"] == state for row in query_rows)
              for state in {row["transport_status"] for row in query_rows}}
    assert states == {"SUCCESS": 19, "TERMINAL_FAILURE": 1,
                      "NOT_EXECUTED_AFTER_ABORT": 5}
    assert sum(row["outcome"] == "ZERO_HIT_QUERY" for row in query_rows) == 19
    assert sum(row["outcome"] == "TERMINAL_TECHNICAL_FAILURE" for row in query_rows) == 1
    assert sum(row["outcome"] == "NOT_OBSERVED" for row in query_rows) == 5


def test_downstream_stages_are_not_reached_not_observed_zero():
    denominators = load("retrieval_denominator_summary.json")
    barrier = load("selection_freeze_barrier_audit.json")
    assert denominators["state"] == "PARTIAL_TERMINAL_TECHNICAL_FAILURE"
    assert denominators["downstream_zero_counts_are_not_reached_not_observed"] is True
    assert barrier["selection_freeze_barrier_pass"] is False
    assert barrier["pmc_fulltext_fetch_count"] == 0
    assert rows("metadata_records.jsonl") == []
    assert rows("fulltext_acquisition_results.jsonl") == []


def test_query_and_scientific_safety_boundaries_hold():
    safety = load("scientific_state_safety_audit.json")
    assert safety["successful_ncbi_requests"] == 19
    assert safety["failed_ncbi_attempts"] == 4
    for key in ["query_modifications", "runtime_query_expansions",
                "proximity_window_changes", "manual_candidate_injections",
                "known_pmid_checks", "historical_label_reads",
                "scientific_relevance_adjudications", "llm_calls",
                "openai_calls", "deepseek_calls", "general_web_calls",
                "publisher_calls", "pmc_fulltext_fetches"]:
        assert safety[key] == 0


def test_partial_corpus_root_verifies_and_is_not_historical_empty_root():
    manifest = load("retrieval_surface_v2_development_acquisition_corpus_manifest.json")
    assert manifest["complete"] is False
    assert manifest["state"] == "PARTIAL_TERMINAL_TECHNICAL_FAILURE"
    for name, expected in manifest["aggregate_components"]:
        assert sha(RUN / name) == expected
    actual = hashlib.sha256(canonical(manifest["aggregate_components"])).hexdigest()
    assert actual == manifest["retrieval_surface_v2_development_acquisition_corpus_sha256"]
    assert actual == (RUN / "retrieval_surface_v2_development_acquisition_corpus_sha256").read_text().strip()
    assert actual != "81898e8f609e03f18398eefec2cb56deb579b05acb5f362d5351c029b7c748f6"


def test_failed_retrieval_root_verifies():
    validation = load("validation.json")
    assert validation["status"] == "FAIL"
    assert validation["failure_class"] == "TERMINAL_TECHNICAL_FAILURE"
    for name, expected in validation["aggregate_components"]:
        assert sha(RUN / name) == expected
    actual = hashlib.sha256(canonical(validation["aggregate_components"])).hexdigest()
    assert actual == validation["search_plan_v24_dev_retrieval_surface_v2_full_retrieval_sha256"]
    assert actual == (RUN / "search_plan_v24_dev_retrieval_surface_v2_full_retrieval_sha256").read_text().strip()


def test_required_failure_artifacts_and_case_placeholders_exist():
    required = {
        "upstream_root_verification.json", "execution_manifest_verification.json",
        "query_set_verification.json", "compiler_configuration_verification.json",
        "relation_contribution_to_executed_query_map.json", "retrieval_request_manifest.jsonl",
        "query_execution_results.jsonl", "query_execution_provenance.jsonl",
        "query_outcome_summary.json", "case_query_hit_summary.json",
        "case_union_pmids.jsonl", "case_union_provenance.jsonl",
        "retrieval_universe_freeze.json", "tail_application_audit.json",
        "metadata_fetch_manifest.jsonl", "metadata_records.jsonl",
        "metadata_failure_records.jsonl", "candidate_gate_results.jsonl",
        "p0_results.jsonl", "p1_results.jsonl", "p2_results.jsonl",
        "policy_a_results.jsonl", "candidate_tier_summary.json",
        "oa_eligibility_results.jsonl", "selection_manifest_aggregate_sha256",
        "selection_freeze_barrier_audit.json", "fulltext_fetch_manifest.jsonl",
        "fulltext_acquisition_results.jsonl", "fulltext_failure_records.jsonl",
        "acquired_fulltext_manifest.json", "retrieval_denominator_summary.json",
        "intent_retrieval_attribution.json", "three_way_retrieval_level_comparison.json",
        "known_paper_blindness_audit.json", "historical_label_blinding_audit.json",
        "runtime_adaptation_audit.json", "provenance_completeness_audit.json",
        "retrieval_policy_compliance_audit.json", "scientific_state_safety_audit.json",
        "validation.json", "summary.json",
        "search_plan_v24_dev_retrieval_surface_v2_full_retrieval_sha256",
        "retrieval_surface_v2_development_acquisition_corpus_sha256",
    }
    assert required <= {path.name for path in RUN.iterdir() if path.is_file()}
    cases = {f"heldout_v2_{number}" for number in range(101, 109)}
    assert {path.stem for path in (RUN / "case_selection_manifests").glob("*.json")} == cases
    assert all(load(f"case_selection_manifests/{case}.json")["valid_selection_manifest"] is False
               for case in cases)


def test_summary_reports_protocol_failure_without_scientific_inference():
    summary = load("summary.json")
    assert summary["status"] == "failed"
    assert summary["protocol_compliance"] == "FAIL"
    assert summary["query_execution_success_count"] == 19
    assert summary["query_terminal_failure_count"] == 1
    assert summary["selection_manifests_frozen_before_download"] is False
    assert summary["next_stage_recommendation"] == "RETRIEVAL_SURFACE_V2_TERMINAL_TECHNICAL_FAILURE"
    assert summary["historical_assets_modified"] is False
