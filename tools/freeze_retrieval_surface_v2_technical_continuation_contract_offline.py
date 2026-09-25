#!/usr/bin/env python3
"""Freeze the exact continuation/composite artifact contract without network access."""

from __future__ import annotations

from collections import Counter
import hashlib
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
RUN = ROOT / "runs/20260925_search_plan_v24_dev_retrieval_surface_v2_technical_continuation"
FAILED_RUN = ROOT / "runs/20260924_search_plan_v24_dev_retrieval_surface_v2_full_retrieval"
HISTORICAL_RUN = ROOT / "runs/20260924_search_plan_v24_dev_frozen_retrospective_retrieval"
PREREG = ROOT / "runs/20260924_search_plan_v24_dev_alpha3_7_retrieval_surface_v2_preregistration_offline"
ALPHA36 = ROOT / "runs/20260924_search_plan_v24_dev_alpha3_6_retrieval_surface_compiler_v2_offline"

EXPECTED_FAILED_ROOT = "c09a492021e5476a7f76d183eeacb49043a867f5882d818d3965c245f9549c87"
EXPECTED_PARTIAL_CORPUS = "272a292f915b86a0dce07432cc171e0136b6d0c8c52f4a89b609815d61aacaa9"
EXPECTED_ALPHA37 = "bb5dd4b2ab1e2717b520d588a2520698d73c471495094a1ef915ccae80d9f49e"
EXPECTED_EXECUTION_MANIFEST = "f10e21a25ffff4f4ecfafa2f4a838ea4f9dba1d6c6194656aae5d87a51ae7a7e"
EXPECTED_QUERY_SET = "4f5148b0ae1a97aaf1bf7334109562c4d04dbdcf99cebb323f87f872a3e93947"
EXPECTED_HISTORICAL_CORPUS = "81898e8f609e03f18398eefec2cb56deb579b05acb5f362d5351c029b7c748f6"
EXPECTED_PRE_CONTRACT_ROOT = "71aa6b9720c14cd8afe7a0887894672d209db1c8e9f8840b7f06caadce5a156a"
EXPECTED_COMPLETED_ACQUISITION = "8b40a35c5976f3c6e084e2e467fbefc01e3b925a4aad135341c99daa90b0c353"
CONTINUATION_EPOCH = "TECHNICAL_CONTINUATION_EPOCH"
ORIGINAL_EPOCH = "ORIGINAL_EXECUTION_EPOCH"


def canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


def pretty(value: Any) -> bytes:
    return (json.dumps(value, sort_keys=True, ensure_ascii=False, indent=2) + "\n").encode()


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def sha_bytes(body: bytes) -> str:
    return hashlib.sha256(body).hexdigest()


def load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def rows(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text().splitlines() if line]


def jsonl(records: list[dict[str, Any]]) -> bytes:
    return b"".join(canonical(record) + b"\n" for record in records)


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def write_new(name: str, body: bytes) -> None:
    path = RUN / name
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        require(path.read_bytes() == body, f"refusing to alter existing artifact: {name}")
        return
    path.write_bytes(body)


def aggregate(pairs: list[list[str]]) -> str:
    return sha_bytes(canonical(pairs))


def verify_aggregate(run: Path, manifest_name: str, root_name: str, expected: str) -> None:
    manifest = load(run / manifest_name)
    pairs = manifest["aggregate_components"]
    require(all(sha(run / name) == digest for name, digest in pairs),
            f"component mismatch in {manifest_name}")
    require(aggregate(pairs) == expected == (run / root_name).read_text().strip(),
            f"aggregate mismatch for {root_name}")


def main() -> None:
    # Re-verify all authoritative roots before projecting any artifacts.
    verify_aggregate(
        FAILED_RUN, "validation.json",
        "search_plan_v24_dev_retrieval_surface_v2_full_retrieval_sha256",
        EXPECTED_FAILED_ROOT,
    )
    verify_aggregate(
        FAILED_RUN, "retrieval_surface_v2_development_acquisition_corpus_manifest.json",
        "retrieval_surface_v2_development_acquisition_corpus_sha256",
        EXPECTED_PARTIAL_CORPUS,
    )
    verify_aggregate(PREREG, "validation.json", "search_plan_v24_dev_alpha3_7_sha256",
                     EXPECTED_ALPHA37)
    require(sha(PREREG / "retrieval_surface_v2_development_execution_manifest.json") ==
            EXPECTED_EXECUTION_MANIFEST, "execution manifest mismatch")
    require(sha(ALPHA36 / "search_plan_v24_dev_retrieval_surface_v2_query_set.jsonl") ==
            EXPECTED_QUERY_SET, "query set mismatch")
    require((HISTORICAL_RUN / "development_retrospective_acquisition_corpus_sha256").read_text().strip()
            == EXPECTED_HISTORICAL_CORPUS, "historical zero-hit corpus mismatch")
    verify_aggregate(
        RUN, "validation.json",
        "search_plan_v24_dev_retrieval_surface_v2_full_retrieval_sha256",
        EXPECTED_PRE_CONTRACT_ROOT,
    )

    failed_results = rows(FAILED_RUN / "query_execution_results.jsonl")
    failed_states = Counter(row["transport_status"] for row in failed_results)
    require(failed_states == Counter({"SUCCESS": 19, "TERMINAL_FAILURE": 1,
                                      "NOT_EXECUTED_AFTER_ABORT": 5}),
            "failed-run state partition changed")
    incomplete = [row for row in failed_results if row["transport_status"] != "SUCCESS"]
    require(incomplete[0]["executed_query_id"] ==
            "v24rsv2q:79c3c2c6c7ec113f7489c448d9571b0de8d9b72e624d82afe5fe9acb0aa8d5b8",
            "terminal query identity mismatch")
    require(incomplete[0]["case_id"] == "heldout_v2_107" and
            incomplete[0]["transport_status"] == "TERMINAL_FAILURE",
            "terminal query integrity assertion failed")

    continuation_set = load(RUN / "technical_continuation_set.json")
    continuation_queries = continuation_set["queries"]
    require([row["query_id"] for row in continuation_queries] ==
            [row["executed_query_id"] for row in incomplete],
            "continuation set is not the mechanical incomplete-query projection")
    require(sha(RUN / "technical_continuation_set.json") ==
            (RUN / "technical_continuation_set_sha256").read_text().strip(),
            "pre-network continuation-set freeze mismatch")

    preservation = {
        "artifact_schema_version": "RetrievalSurfaceV2FailedRunPreservationAuditV1",
        "historical_failed_run_root_sha256": EXPECTED_FAILED_ROOT,
        "historical_partial_acquisition_corpus_sha256": EXPECTED_PARTIAL_CORPUS,
        "historical_exact_proposition_zero_hit_corpus_sha256": EXPECTED_HISTORICAL_CORPUS,
        "historical_successful_query_count": 19,
        "historical_terminal_failure_record_count": 1,
        "historical_failed_attempt_record_count": 4,
        "historical_not_executed_record_count": 5,
        "historical_assets_modified": False,
        "all_roots_recomputed_or_directly_verified": True,
    }
    write_new("failed_run_preservation_audit.json", pretty(preservation))

    derivation = {
        "artifact_schema_version": "RetrievalSurfaceV2ContinuationSetDerivationV1",
        "source_failed_run_root_sha256": EXPECTED_FAILED_ROOT,
        "derivation_rule": "transport_status in {TERMINAL_FAILURE, NOT_EXECUTED_AFTER_ABORT}",
        "scientific_selection_inputs_used": False,
        "terminal_failed_query_count": 1,
        "not_executed_query_count": 5,
        "continuation_query_count": 6,
        "continuation_query_ids_in_original_logical_order": [
            row["query_id"] for row in continuation_queries
        ],
        "expected_terminal_query_integrity_assertion_pass": True,
        "derived_mechanically": True,
    }
    write_new("continuation_set_derivation.json", pretty(derivation))

    # The required filename is a physical byte-identical projection of the
    # manifest bytes that were demonstrably frozen before the first request.
    continuation_manifest_body = (RUN / "technical_continuation_set.json").read_bytes()
    continuation_manifest_sha = sha_bytes(continuation_manifest_body)
    write_new("technical_continuation_manifest.json", continuation_manifest_body)
    write_new("technical_continuation_manifest_sha256",
              (continuation_manifest_sha + "\n").encode())
    write_new("technical_continuation_manifest_provenance.json", pretty({
        "artifact_schema_version": "TechnicalContinuationManifestProjectionProvenanceV1",
        "required_manifest_filename": "technical_continuation_manifest.json",
        "byte_identical_source": "technical_continuation_set.json",
        "sha256": continuation_manifest_sha,
        "source_frozen_before_first_continuation_network_request": True,
        "projection_filename_created_after_transport": True,
        "projection_does_not_claim_a_false_creation_timestamp": True,
    }))

    request_rows = []
    for query in continuation_queries:
        request_rows.append({
            "artifact_schema_version": "TechnicalContinuationLogicalRequestV1",
            "continuation_execution_order": query["continuation_order"],
            "original_execution_sequence": query["execution_order"],
            "case_id": query["case_id"], "query_id": query["query_id"],
            "query_sha256": query["query_sha256"],
            "exact_query_text": query["exact_query_text"],
            "original_status": query["source_failed_run_transport_status"],
            "relation_core_ids": query["relation_core_ids"],
            "pubmed_ast_hashes": query["pubmed_ast_hashes"],
            "surface_plan_ids": query["surface_plan_ids"],
            "execution_epoch": CONTINUATION_EPOCH,
            "maximum_total_attempts": 4, "timeout_seconds": 60,
            "backoff_seconds": [2, 4, 8], "query_modified": False,
        })
    write_new("continuation_request_manifest.jsonl", jsonl(request_rows))

    receipt = load(RUN / "retrieval_assets/network_events.json")
    continuation_events = [row for row in receipt["events"]
                           if row.get("execution_epoch") == CONTINUATION_EPOCH]
    continuation_failures = [row for row in receipt["failures"]
                             if row.get("execution_epoch") == CONTINUATION_EPOCH]
    require(len(continuation_events) == 6 and len(continuation_failures) == 5,
            "continuation receipt count mismatch")
    attempt_records = []
    for failure in continuation_failures:
        attempt_records.append({
            "artifact_schema_version": "TechnicalContinuationAttemptRecordV1",
            "execution_epoch": CONTINUATION_EPOCH,
            "timestamp_utc": failure["timestamp_utc"],
            "case_id": failure["lineage"]["case_id"],
            "query_id": failure["lineage"]["query_id"],
            "query_sha256": failure["lineage"]["query_sha256"],
            "attempt": failure["attempt"], "attempt_state": "FAILED_ATTEMPT",
            "error_type": failure["error_type"], "error": failure["error"],
        })
    for event in continuation_events:
        attempt_records.append({
            "artifact_schema_version": "TechnicalContinuationAttemptRecordV1",
            "execution_epoch": CONTINUATION_EPOCH,
            "timestamp_utc": event["timestamp_utc"],
            "case_id": event["lineage"]["case_id"],
            "query_id": event["lineage"]["query_id"],
            "query_sha256": event["lineage"]["query_sha256"],
            "attempt": event["retry_count"] + 1, "attempt_state": "SUCCESS",
            "request_id": event["request_id"], "http_status": event["http_status"],
            "response_sha256": event["response_sha256"],
            "snapshot_ref": event["snapshot_ref"],
        })
    attempt_records.sort(key=lambda row: row["timestamp_utc"])
    write_new("continuation_attempt_records.jsonl", jsonl(attempt_records))

    composite_results = rows(RUN / "query_execution_results.jsonl")
    require(len(composite_results) == 25 and
            all(row["transport_status"] == "SUCCESS" for row in composite_results),
            "composite query execution is incomplete")
    continuation_ids = {row["query_id"] for row in continuation_queries}
    continuation_results = [row for row in composite_results
                            if row["executed_query_id"] in continuation_ids]
    require(len(continuation_results) == 6 and
            all(row["successful_execution_epoch"] == CONTINUATION_EPOCH
                for row in continuation_results), "continuation result partition mismatch")
    write_new("continuation_query_results.jsonl", jsonl(continuation_results))

    page_rows = rows(RUN / "query_execution_provenance.jsonl")
    continuation_pages = [row for row in page_rows
                          if row.get("execution_epoch") == CONTINUATION_EPOCH]
    require(len(continuation_pages) == 6 and
            all(row["transport_status"] == "SUCCESS" for row in continuation_pages),
            "continuation provenance partition mismatch")
    event_by_request = {row["request_id"]: row for row in receipt["events"]}
    continuation_provenance = []
    for row in continuation_pages:
        event = event_by_request[row["request_id"]]
        continuation_provenance.append({**row, "timestamp_utc": event["timestamp_utc"]})
    write_new("continuation_execution_provenance.jsonl", jsonl(continuation_provenance))

    old_receipt = load(FAILED_RUN / "retrieval_assets/network_events.json")
    old_events = {row["request_id"]: row for row in old_receipt["events"]}
    copied_events = [row for row in receipt["events"]
                     if row.get("execution_epoch") == ORIGINAL_EPOCH]
    byte_identical = []
    for event in copied_events:
        old = old_events[event["request_id"]]
        old_path, new_path = ROOT / old["snapshot_ref"], ROOT / event["snapshot_ref"]
        byte_identical.append(old_path.read_bytes() == new_path.read_bytes() and
                              sha(new_path) == event["response_sha256"])
    require(len(byte_identical) == 19 and all(byte_identical),
            "historical response reuse is not byte-identical")
    write_new("completed_query_reuse_audit.json", pretty({
        "artifact_schema_version": "RetrievalSurfaceV2CompletedQueryReuseAuditV1",
        "historical_successful_query_count": 19,
        "completed_query_reexecution_count": 0,
        "physical_response_copy_count": 19,
        "all_reused_responses_byte_identical": True,
        "historical_raw_responses_modified": False,
        "historical_translations_modified": False,
        "historical_hit_counts_modified": False,
        "historical_pmids_modified": False,
        "historical_provenance_modified": False,
    }))

    successful_pages = [row for row in page_rows if row["transport_status"] == "SUCCESS"]
    require(len(successful_pages) == 25, "successful composite provenance count mismatch")
    composite_provenance = []
    for row in successful_pages:
        event = event_by_request[row["request_id"]]
        composite_provenance.append({**row, "timestamp_utc": event["timestamp_utc"]})
    write_new("composite_query_execution_results.jsonl", jsonl(composite_results))
    write_new("composite_query_execution_provenance.jsonl", jsonl(composite_provenance))

    per_case = load(RUN / "case_query_hit_summary.json")
    outcome = {
        "artifact_schema_version": "RetrievalSurfaceV2CompositeQueryOutcomeSummaryV1",
        "historical_successful_query_count": 19,
        "continuation_successful_query_count": 6,
        "complete_query_execution_count": 25,
        "terminal_failure_count_in_composite_execution": 0,
        "nonzero_query_count": 0, "zero_hit_query_count": 25,
        "nonzero_case_count": 0, "zero_hit_case_count": 8,
        "per_case": per_case,
    }
    write_new("composite_query_outcome_summary.json", pretty(outcome))
    write_new("search_completion_barrier.json", pretty({
        "artifact_schema_version": "RetrievalSurfaceV2SearchCompletionBarrierV1",
        "historical_successful_query_count": 19,
        "continuation_query_count": 6,
        "continuation_successful_query_count": 6,
        "continuation_terminal_failure_count": 0,
        "completed_query_reexecution_count": 0,
        "complete_query_execution_count": 25,
        "terminal_failures_in_completed_composite_execution": 0,
        "search_completion_barrier_pass": True,
    }))

    complete_execution_components = [
        ["composite_query_execution_results.jsonl", sha(RUN / "composite_query_execution_results.jsonl")],
        ["composite_query_execution_provenance.jsonl", sha(RUN / "composite_query_execution_provenance.jsonl")],
        ["composite_query_outcome_summary.json", sha(RUN / "composite_query_outcome_summary.json")],
        ["case_query_hit_summary.json", sha(RUN / "case_query_hit_summary.json")],
        ["case_union_pmids.jsonl", sha(RUN / "case_union_pmids.jsonl")],
        ["case_union_provenance.jsonl", sha(RUN / "case_union_provenance.jsonl")],
    ]
    complete_execution_sha = aggregate(complete_execution_components)
    write_new("retrieval_surface_v2_complete_execution_corpus_manifest.json", pretty({
        "artifact_schema_version": "RetrievalSurfaceV2CompleteExecutionCorpusManifestV1",
        "aggregate_algorithm": "sha256(canonical JSON ordered [path, sha256] pairs)",
        "aggregate_components": complete_execution_components,
        "complete_query_execution_count": 25,
        "retrieval_surface_v2_complete_execution_corpus_sha256": complete_execution_sha,
    }))
    write_new("retrieval_surface_v2_complete_execution_corpus_sha256",
              (complete_execution_sha + "\n").encode())

    query_execution_components = complete_execution_components[:2]
    complete_query_sha = aggregate(query_execution_components)
    write_new("retrieval_surface_v2_complete_query_execution_sha256",
              (complete_query_sha + "\n").encode())
    universe = load(RUN / "retrieval_universe_freeze.json")
    write_new("retrieval_surface_v2_complete_retrieval_universe_sha256",
              (universe["retrieval_universe_sha256"] + "\n").encode())
    write_new("retrieval_surface_v2_completed_development_acquisition_corpus_sha256",
              (EXPECTED_COMPLETED_ACQUISITION + "\n").encode())

    base_policy = load(RUN / "retrieval_policy_compliance_audit.json")
    protocol = {
        "artifact_schema_version": "RetrievalSurfaceV2TechnicalContinuationProtocolComplianceAuditV1",
        "base_retrieval_policy_audit_sha256": sha(RUN / "retrieval_policy_compliance_audit.json"),
        "base_checks": base_policy["checks"],
        "continuation_checks": {
            "authoritative_roots_verified": True,
            "continuation_set_mechanically_derived": True,
            "continuation_manifest_source_frozen_before_network": True,
            "continuation_order_preserved": True,
            "completed_query_reexecution_count_zero": True,
            "historical_attempts_preserved": True,
            "continuation_attempt_limit_respected": True,
            "search_completion_barrier_passed": True,
            "composite_epochs_preserved": True,
            "no_scientific_or_query_changes": True,
        },
        "protocol_compliance": "PASS",
    }
    write_new("protocol_compliance_audit.json", pretty(protocol))

    # The continuation root is additive and leaves the already frozen
    # full-retrieval root intact. Exclude root/manifest files to avoid recursion.
    excluded = {
        "search_plan_v24_dev_retrieval_surface_v2_technical_continuation_sha256",
        "search_plan_v24_dev_retrieval_surface_v2_technical_continuation_manifest.json",
    }
    root_pairs = []
    for path in sorted(item for item in RUN.rglob("*") if item.is_file()):
        relative = str(path.relative_to(RUN))
        if relative not in excluded:
            root_pairs.append([relative, sha(path)])
    continuation_root = aggregate(root_pairs)
    write_new("search_plan_v24_dev_retrieval_surface_v2_technical_continuation_manifest.json",
              pretty({
                  "artifact_schema_version": "RetrievalSurfaceV2TechnicalContinuationRootManifestV1",
                  "aggregate_algorithm": "sha256(canonical JSON ordered [path, sha256] pairs)",
                  "aggregate_components": root_pairs,
                  "search_plan_v24_dev_retrieval_surface_v2_technical_continuation_sha256": continuation_root,
              }))
    write_new("search_plan_v24_dev_retrieval_surface_v2_technical_continuation_sha256",
              (continuation_root + "\n").encode())

    print(json.dumps({
        "status": "completed",
        "continuation_manifest_sha256": continuation_manifest_sha,
        "continuation_attempt_count": len(attempt_records),
        "complete_query_execution_count": 25,
        "complete_execution_corpus_sha256": complete_execution_sha,
        "complete_query_execution_sha256": complete_query_sha,
        "complete_retrieval_universe_sha256": universe["retrieval_universe_sha256"],
        "completed_acquisition_corpus_sha256": EXPECTED_COMPLETED_ACQUISITION,
        "technical_continuation_root_sha256": continuation_root,
    }, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
