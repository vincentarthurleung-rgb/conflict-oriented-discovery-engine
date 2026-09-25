import hashlib
import json
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RUN = ROOT / "runs/20260925_search_plan_v24_dev_retrieval_surface_v2_technical_continuation"
FAILED_RUN = ROOT / "runs/20260924_search_plan_v24_dev_retrieval_surface_v2_full_retrieval"

EXPECTED_FAILED_ROOT = "c09a492021e5476a7f76d183eeacb49043a867f5882d818d3965c245f9549c87"
EXPECTED_PARTIAL_CORPUS = "272a292f915b86a0dce07432cc171e0136b6d0c8c52f4a89b609815d61aacaa9"
EXPECTED_COMPLETE_ROOT = "71aa6b9720c14cd8afe7a0887894672d209db1c8e9f8840b7f06caadce5a156a"
EXPECTED_COMPLETE_CORPUS = "8b40a35c5976f3c6e084e2e467fbefc01e3b925a4aad135341c99daa90b0c353"
EXPECTED_EXECUTION_CORPUS = "052d332ecdf2042713ab07f608c934457908c6d5d9f15536c433c55c92f8b4d1"
EXPECTED_CONTINUATION_ROOT = "24455644753df479e441d54c7b05b889c9607947466bc73e2d4cc46d3bfdfd95"


def load(run, name):
    return json.loads((run / name).read_text())


def rows(run, name):
    return [json.loads(line) for line in (run / name).read_text().splitlines() if line]


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def assert_aggregate(run, manifest_name, root_key, root_file, expected):
    manifest = load(run, manifest_name)
    for name, digest in manifest["aggregate_components"]:
        assert sha(run / name) == digest
    actual = hashlib.sha256(canonical(manifest["aggregate_components"])).hexdigest()
    assert actual == manifest[root_key] == (run / root_file).read_text().strip() == expected


def test_continuation_set_is_exactly_the_six_failed_run_incomplete_queries():
    original = rows(FAILED_RUN, "query_execution_results.jsonl")
    continuation = load(RUN, "technical_continuation_set.json")
    expected = [
        row["executed_query_id"] for row in original
        if row["transport_status"] in {"TERMINAL_FAILURE", "NOT_EXECUTED_AFTER_ABORT"}
    ]
    assert Counter(row["transport_status"] for row in original) == Counter({
        "SUCCESS": 19, "TERMINAL_FAILURE": 1, "NOT_EXECUTED_AFTER_ABORT": 5,
    })
    assert continuation["continuation_query_count"] == 6
    assert continuation["excluded_successful_query_count"] == 19
    assert [row["query_id"] for row in continuation["queries"]] == expected
    assert continuation["query_modifications"] == 0
    assert sha(RUN / "technical_continuation_set.json") == (
        RUN / "technical_continuation_set_sha256").read_text().strip()


def test_epoch_receipt_preserves_original_attempts_and_records_bounded_retries():
    receipt = load(RUN, "retrieval_assets/network_events.json")
    event_epochs = Counter(row["execution_epoch"] for row in receipt["events"])
    failure_epochs = Counter(row["execution_epoch"] for row in receipt["failures"])
    assert event_epochs == Counter({"ORIGINAL_EXECUTION_EPOCH": 19,
                                    "TECHNICAL_CONTINUATION_EPOCH": 6})
    assert failure_epochs == Counter({"ORIGINAL_EXECUTION_EPOCH": 4,
                                      "TECHNICAL_CONTINUATION_EPOCH": 5})
    assert max(row["retry_count"] for row in receipt["events"]
               if row["execution_epoch"] == "TECHNICAL_CONTINUATION_EPOCH") == 3
    result = load(RUN, "technical_continuation_epoch_result.json")
    assert result["successful_query_count"] == 6
    assert result["terminal_failure_count"] == 0
    assert result["original_successful_queries_rerun"] == 0
    assert result["original_exhausted_attempts_preserved"] is True
    assert result["continuation_failed_attempt_count"] == 5
    assert all(count <= 3 for count in result["per_query_retry_counts"].values())


def test_original_success_snapshots_are_physical_byte_identical_copies():
    old_receipt = load(FAILED_RUN, "retrieval_assets/network_events.json")
    new_receipt = load(RUN, "retrieval_assets/network_events.json")
    old_events = {row["request_id"]: row for row in old_receipt["events"]}
    copied = [row for row in new_receipt["events"]
              if row["execution_epoch"] == "ORIGINAL_EXECUTION_EPOCH"]
    assert len(copied) == 19
    for event in copied:
        old = old_events[event["request_id"]]
        old_path = ROOT / old["snapshot_ref"]
        copied_path = ROOT / event["snapshot_ref"]
        assert copied_path.read_bytes() == old_path.read_bytes()
        assert copied_path.stat().st_ino != old_path.stat().st_ino


def test_combined_execution_is_complete_and_zero_hit_without_query_changes():
    query_results = rows(RUN, "query_execution_results.jsonl")
    assert len(query_results) == 25
    assert all(row["transport_status"] == "SUCCESS" for row in query_results)
    assert all(row["outcome"] == "ZERO_HIT_QUERY" for row in query_results)
    assert all(row["raw_hit_count"] == 0 for row in query_results)
    assert Counter(row["successful_execution_epoch"] for row in query_results) == Counter({
        "ORIGINAL_EXECUTION_EPOCH": 19, "TECHNICAL_CONTINUATION_EPOCH": 6,
    })
    audit = load(RUN, "runtime_adaptation_audit.json")
    assert audit["query_modifications"] == 0
    assert audit["runtime_query_expansions"] == 0
    assert audit["proximity_window_changes"] == 0


def test_downstream_empty_state_and_selection_freeze_are_complete():
    summary = load(RUN, "summary.json")
    barrier = load(RUN, "selection_freeze_barrier_audit.json")
    assert summary["status"] == "completed"
    assert summary["query_execution_success_count"] == 25
    assert summary["zero_hit_query_count"] == 25
    assert summary["zero_hit_case_count"] == 8
    assert summary["metadata_universe_total"] == 0
    assert summary["selected_count"] == 0
    assert summary["successful_fulltext_acquisition_count"] == 0
    assert summary["protocol_compliance"] == "PASS"
    assert summary["next_stage_recommendation"] == (
        "RETRIEVAL_SURFACE_V2_SYNTAX_OR_RIGIDITY_AUTOPSY_NEEDED")
    assert barrier["selection_freeze_barrier_pass"] is True
    assert barrier["all_eight_manifests_frozen_and_hashed"] is True
    assert barrier["frozen_before_first_pmc_fulltext_fetch"] is True
    cases = {f"heldout_v2_{number}" for number in range(101, 109)}
    manifests = {path.stem: json.loads(path.read_text())
                 for path in (RUN / "case_selection_manifests").glob("*.json")}
    assert set(manifests) == cases
    assert all(row["selection_count"] == 0 for row in manifests.values())
    assert all(row["ordered_selections"] == [] for row in manifests.values())


def test_complete_corpus_and_retrieval_roots_recompute():
    assert_aggregate(
        RUN, "retrieval_surface_v2_development_acquisition_corpus_manifest.json",
        "retrieval_surface_v2_development_acquisition_corpus_sha256",
        "retrieval_surface_v2_development_acquisition_corpus_sha256",
        EXPECTED_COMPLETE_CORPUS,
    )
    assert_aggregate(
        RUN, "validation.json",
        "search_plan_v24_dev_retrieval_surface_v2_full_retrieval_sha256",
        "search_plan_v24_dev_retrieval_surface_v2_full_retrieval_sha256",
        EXPECTED_COMPLETE_ROOT,
    )


def test_authoritative_failed_run_remains_unchanged_and_no_symlinks_exist():
    assert (FAILED_RUN / "search_plan_v24_dev_retrieval_surface_v2_full_retrieval_sha256").read_text().strip() == EXPECTED_FAILED_ROOT
    assert (FAILED_RUN / "retrieval_surface_v2_development_acquisition_corpus_sha256").read_text().strip() == EXPECTED_PARTIAL_CORPUS
    assert not any(path.is_symlink() for path in RUN.rglob("*"))


def test_required_continuation_contract_artifacts_exist():
    required = {
        "upstream_root_verification.json", "failed_run_preservation_audit.json",
        "continuation_set_derivation.json", "technical_continuation_manifest.json",
        "technical_continuation_manifest_sha256", "continuation_request_manifest.jsonl",
        "continuation_attempt_records.jsonl", "continuation_query_results.jsonl",
        "continuation_execution_provenance.jsonl", "completed_query_reuse_audit.json",
        "search_completion_barrier.json", "composite_query_execution_results.jsonl",
        "composite_query_execution_provenance.jsonl", "composite_query_outcome_summary.json",
        "case_query_hit_summary.json", "case_union_pmids.jsonl", "case_union_provenance.jsonl",
        "tail_application_audit.json", "retrieval_universe_freeze.json",
        "metadata_fetch_manifest.jsonl", "metadata_records.jsonl",
        "metadata_failure_records.jsonl", "candidate_gate_results.jsonl",
        "p0_results.jsonl", "p1_results.jsonl", "p2_results.jsonl",
        "policy_a_results.jsonl", "candidate_tier_summary.json",
        "oa_eligibility_results.jsonl", "selection_manifest_aggregate_sha256",
        "selection_freeze_barrier_audit.json", "fulltext_fetch_manifest.jsonl",
        "fulltext_acquisition_results.jsonl", "fulltext_failure_records.jsonl",
        "acquired_fulltext_manifest.json", "retrieval_denominator_summary.json",
        "intent_retrieval_attribution.json", "runtime_adaptation_audit.json",
        "known_paper_blindness_audit.json", "historical_label_blinding_audit.json",
        "provenance_completeness_audit.json", "protocol_compliance_audit.json",
        "scientific_state_safety_audit.json", "validation.json", "summary.json",
        "retrieval_surface_v2_complete_execution_corpus_sha256",
        "retrieval_surface_v2_completed_development_acquisition_corpus_sha256",
        "search_plan_v24_dev_retrieval_surface_v2_technical_continuation_sha256",
    }
    assert required <= {path.name for path in RUN.iterdir() if path.is_file()}


def test_required_manifest_is_byte_identical_to_actual_pre_network_freeze():
    assert (RUN / "technical_continuation_manifest.json").read_bytes() == (
        RUN / "technical_continuation_set.json").read_bytes()
    assert sha(RUN / "technical_continuation_manifest.json") == (
        RUN / "technical_continuation_manifest_sha256").read_text().strip()
    provenance = load(RUN, "technical_continuation_manifest_provenance.json")
    assert provenance["source_frozen_before_first_continuation_network_request"] is True
    assert provenance["projection_filename_created_after_transport"] is True
    assert provenance["projection_does_not_claim_a_false_creation_timestamp"] is True


def test_continuation_attempt_and_composite_partitions_are_exact():
    attempts = rows(RUN, "continuation_attempt_records.jsonl")
    continuation_results = rows(RUN, "continuation_query_results.jsonl")
    continuation_provenance = rows(RUN, "continuation_execution_provenance.jsonl")
    composite_results = rows(RUN, "composite_query_execution_results.jsonl")
    composite_provenance = rows(RUN, "composite_query_execution_provenance.jsonl")
    assert len(attempts) == 11
    assert Counter(row["attempt_state"] for row in attempts) == Counter({
        "SUCCESS": 6, "FAILED_ATTEMPT": 5,
    })
    assert len(continuation_results) == len(continuation_provenance) == 6
    assert len(composite_results) == len(composite_provenance) == 25
    assert all(row["transport_status"] == "SUCCESS" for row in composite_results)
    assert all(row["transport_status"] == "SUCCESS" for row in composite_provenance)
    assert all("timestamp_utc" in row for row in composite_provenance)


def test_search_completion_and_reuse_barriers_pass():
    barrier = load(RUN, "search_completion_barrier.json")
    reuse = load(RUN, "completed_query_reuse_audit.json")
    assert barrier["historical_successful_query_count"] == 19
    assert barrier["continuation_successful_query_count"] == 6
    assert barrier["complete_query_execution_count"] == 25
    assert barrier["search_completion_barrier_pass"] is True
    assert reuse["completed_query_reexecution_count"] == 0
    assert reuse["all_reused_responses_byte_identical"] is True


def test_exact_contract_roots_recompute():
    execution_manifest = load(
        RUN, "retrieval_surface_v2_complete_execution_corpus_manifest.json")
    for name, digest in execution_manifest["aggregate_components"]:
        assert sha(RUN / name) == digest
    execution_root = hashlib.sha256(
        canonical(execution_manifest["aggregate_components"])).hexdigest()
    assert execution_root == execution_manifest[
        "retrieval_surface_v2_complete_execution_corpus_sha256"]
    assert execution_root == (
        RUN / "retrieval_surface_v2_complete_execution_corpus_sha256").read_text().strip()
    assert execution_root == EXPECTED_EXECUTION_CORPUS
    continuation_manifest = load(
        RUN, "search_plan_v24_dev_retrieval_surface_v2_technical_continuation_manifest.json")
    for name, digest in continuation_manifest["aggregate_components"]:
        assert sha(RUN / name) == digest
    continuation_root = hashlib.sha256(
        canonical(continuation_manifest["aggregate_components"])).hexdigest()
    assert continuation_root == continuation_manifest[
        "search_plan_v24_dev_retrieval_surface_v2_technical_continuation_sha256"]
    assert continuation_root == (
        RUN / "search_plan_v24_dev_retrieval_surface_v2_technical_continuation_sha256").read_text().strip()
    assert continuation_root == EXPECTED_CONTINUATION_ROOT
    assert (RUN / "retrieval_surface_v2_completed_development_acquisition_corpus_sha256").read_text().strip() == EXPECTED_COMPLETE_CORPUS
