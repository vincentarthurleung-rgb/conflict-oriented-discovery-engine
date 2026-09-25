#!/usr/bin/env python3
"""Continue exactly the six incomplete Retrieval Surface V2 queries."""

from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import tools.run_search_plan_v24_dev_alpha3_4_development_retrospective_retrieval as legacy
import tools.run_search_plan_v24_dev_retrieval_surface_v2_full_retrieval as full


RUN = ROOT / "runs/20260925_search_plan_v24_dev_retrieval_surface_v2_technical_continuation"
ASSETS = RUN / "retrieval_assets"
FAILED_RUN = ROOT / "runs/20260924_search_plan_v24_dev_retrieval_surface_v2_full_retrieval"
PREREG = ROOT / "runs/20260924_search_plan_v24_dev_alpha3_7_retrieval_surface_v2_preregistration_offline"
ALPHA36 = ROOT / "runs/20260924_search_plan_v24_dev_alpha3_6_retrieval_surface_compiler_v2_offline"
EXECUTION_MANIFEST = PREREG / "retrieval_surface_v2_development_execution_manifest.json"

EXPECTED_FAILED_ROOT = "c09a492021e5476a7f76d183eeacb49043a867f5882d818d3965c245f9549c87"
EXPECTED_PARTIAL_CORPUS = "272a292f915b86a0dce07432cc171e0136b6d0c8c52f4a89b609815d61aacaa9"
EXPECTED_ALPHA37 = "bb5dd4b2ab1e2717b520d588a2520698d73c471495094a1ef915ccae80d9f49e"
EXPECTED_EXECUTION = "f10e21a25ffff4f4ecfafa2f4a838ea4f9dba1d6c6194656aae5d87a51ae7a7e"
EXPECTED_QUERY_SET = "4f5148b0ae1a97aaf1bf7334109562c4d04dbdcf99cebb323f87f872a3e93947"
ORIGINAL_EPOCH = "ORIGINAL_EXECUTION_EPOCH"
CONTINUATION_EPOCH = "TECHNICAL_CONTINUATION_EPOCH"


def args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--execute-network", action="store_true")
    parser.add_argument("--preflight-only", action="store_true")
    parser.add_argument("--resume-frozen-responses", action="store_true")
    return parser.parse_args()


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


def pretty(value: Any) -> bytes:
    return (json.dumps(value, sort_keys=True, ensure_ascii=False, indent=2) + "\n").encode()


def sha_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha(path: Path) -> str:
    return sha_bytes(path.read_bytes())


def aggregate(pairs: list[list[str]]) -> str:
    return sha_bytes(canonical(pairs))


def load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def rows(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text().splitlines() if line]


def write(path_or_name: str | Path, body: bytes) -> None:
    path = path_or_name if isinstance(path_or_name, Path) else RUN / path_or_name
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        require(path.is_file() and path.read_bytes() == body,
                f"refusing to alter frozen continuation artifact: {path}")
        return
    path.write_bytes(body)


def verify_run(path: Path, root_name: str, expected: str) -> dict[str, Any]:
    validation = load(path / "validation.json")
    pairs = validation["aggregate_components"]
    require(all(sha(path / name) == digest for name, digest in pairs),
            f"component mismatch: {path.name}")
    actual = aggregate(pairs)
    recorded = (path / root_name).read_text().strip()
    require(actual == recorded == expected, f"root mismatch: {path.name}")
    return {"path": str(path.relative_to(ROOT)), "expected_sha256": expected,
            "recomputed_sha256": actual, "verified": True}


def derive_continuation_set() -> tuple[dict[str, Any], list[dict[str, Any]],
                                       dict[str, Any], dict[str, Any]]:
    failed_root = verify_run(
        FAILED_RUN, "search_plan_v24_dev_retrieval_surface_v2_full_retrieval_sha256",
        EXPECTED_FAILED_ROOT)
    corpus_manifest = load(
        FAILED_RUN / "retrieval_surface_v2_development_acquisition_corpus_manifest.json")
    corpus_pairs = corpus_manifest["aggregate_components"]
    require(all(sha(FAILED_RUN / name) == digest for name, digest in corpus_pairs),
            "partial corpus component mismatch")
    require(aggregate(corpus_pairs) == EXPECTED_PARTIAL_CORPUS ==
            (FAILED_RUN / "retrieval_surface_v2_development_acquisition_corpus_sha256").read_text().strip(),
            "partial corpus root mismatch")
    alpha37 = verify_run(PREREG, "search_plan_v24_dev_alpha3_7_sha256", EXPECTED_ALPHA37)
    require(sha(EXECUTION_MANIFEST) == EXPECTED_EXECUTION,
            "execution manifest changed")
    query_path = ALPHA36 / "search_plan_v24_dev_retrieval_surface_v2_query_set.jsonl"
    require(sha(query_path) == EXPECTED_QUERY_SET, "query set changed")
    manifest = load(EXECUTION_MANIFEST)
    failed_results = rows(FAILED_RUN / "query_execution_results.jsonl")
    require(len(failed_results) == 25, "failed-run query record count changed")
    status_counts = Counter(row["transport_status"] for row in failed_results)
    require(status_counts == Counter({"SUCCESS": 19, "TERMINAL_FAILURE": 1,
                                     "NOT_EXECUTED_AFTER_ABORT": 5}),
            "failed-run execution-state partition changed")
    incomplete = [row for row in failed_results if row["transport_status"] in {
        "TERMINAL_FAILURE", "NOT_EXECUTED_AFTER_ABORT"}]
    require(len(incomplete) == 6, "continuation set is not exactly six queries")
    manifest_queries = {row["query_id"]: row for row in manifest["exact_queries"]}
    successful_ids = {row["executed_query_id"] for row in failed_results
                      if row["transport_status"] == "SUCCESS"}
    require(not successful_ids.intersection(row["executed_query_id"] for row in incomplete),
            "successful query leaked into continuation set")
    continuation = []
    for order, failed in enumerate(incomplete, 1):
        query = manifest_queries[failed["executed_query_id"]]
        require(query["query_sha256"] == failed["query_sha256"] and
                query["exact_query_text"].encode() == failed["query_text"].encode(),
                "continuation query differs from frozen manifest")
        continuation.append({
            **query, "continuation_order": order,
            "source_failed_run_transport_status": failed["transport_status"],
            "continuation_epoch": CONTINUATION_EPOCH,
        })
    freeze = {
        "artifact_schema_version": "RetrievalSurfaceV2TechnicalContinuationSetV1",
        "execution_epoch": CONTINUATION_EPOCH,
        "source_failed_run_root_sha256": EXPECTED_FAILED_ROOT,
        "source_partial_corpus_sha256": EXPECTED_PARTIAL_CORPUS,
        "source_execution_manifest_sha256": EXPECTED_EXECUTION,
        "source_query_set_sha256": EXPECTED_QUERY_SET,
        "derivation_rule": "transport_status in {TERMINAL_FAILURE, NOT_EXECUTED_AFTER_ABORT}",
        "previously_terminal_query_count": 1,
        "previously_not_executed_query_count": 5,
        "continuation_query_count": 6,
        "excluded_successful_query_count": 19,
        "queries": continuation,
        "query_modifications": 0,
    }
    verification = {
        "artifact_schema_version": "RetrievalSurfaceV2TechnicalContinuationPreflightV1",
        "failed_run": failed_root, "partial_corpus_verified": True,
        "alpha3_7": alpha37, "execution_manifest_sha256": EXPECTED_EXECUTION,
        "query_set_sha256": EXPECTED_QUERY_SET,
        "continuation_query_count": 6, "excluded_successful_query_count": 19,
        "derived_mechanically_from_failed_execution_records": True,
        "query_text_changes": 0, "query_hash_changes": 0,
        "maximum_total_attempts_per_continuation_query": 4,
        "timeout_seconds": 60, "backoff_seconds": [2, 4, 8],
    }
    return verification, continuation, freeze, manifest


def initialize_epoch(verification: dict[str, Any], freeze: dict[str, Any]) -> legacy.Network:
    require(not RUN.exists(), f"refusing to overwrite continuation run: {RUN}")
    RUN.mkdir(parents=False)
    ASSETS.mkdir()
    freeze_body = pretty(freeze)
    write("technical_continuation_set.json", freeze_body)
    write("technical_continuation_set_sha256", (sha_bytes(freeze_body) + "\n").encode())
    write("technical_continuation_preflight.json", pretty(verification))
    write("technical_continuation_epoch_freeze.json", pretty({
        "artifact_schema_version": "TechnicalContinuationEpochFreezeV1",
        "execution_epoch": CONTINUATION_EPOCH,
        "continuation_set_sha256": sha_bytes(freeze_body),
        "continuation_query_count": 6,
        "original_exhausted_attempts_preserved": True,
        "original_attempts_relabelled": False,
        "maximum_total_attempts_per_query_in_this_epoch": 4,
        "timeout_seconds": 60, "backoff_seconds": [2, 4, 8],
        "frozen_before_first_continuation_network_request": True,
    }))

    original_receipt = load(FAILED_RUN / "retrieval_assets/network_events.json")
    cloned_events = []
    for event in original_receipt["events"]:
        source = ROOT / event["snapshot_ref"]
        relative = source.relative_to(FAILED_RUN / "retrieval_assets")
        destination = ASSETS / "original_epoch" / relative
        write(destination, source.read_bytes())
        require(sha(destination) == event["response_sha256"], "original response copy mismatch")
        cloned_events.append({
            **event, "execution_epoch": ORIGINAL_EPOCH,
            "original_snapshot_ref": event["snapshot_ref"],
            "snapshot_ref": str(destination.relative_to(ROOT)),
        })
    cloned_failures = [{**row, "execution_epoch": ORIGINAL_EPOCH}
                       for row in original_receipt["failures"]]
    write(ASSETS / "network_events.json", pretty({
        "events": cloned_events, "failures": cloned_failures,
        "provider_calls": 0, "llm_calls": 0, "planner_calls": 0,
        "general_web_fallback_calls": 0, "publisher_fallback_calls": 0,
        "known_pmid_checks": 0, "relevance_adjudication_calls": 0,
    }))
    legacy.RUN = RUN; legacy.ASSETS = ASSETS
    full.RUN = RUN; full.ASSETS = ASSETS
    return legacy.Network(True)


def tag_continuation_epoch(network: legacy.Network, original_event_count: int,
                           original_failure_count: int) -> None:
    for row in network.events[original_event_count:]:
        row["execution_epoch"] = CONTINUATION_EPOCH
        row["lineage"]["execution_epoch"] = CONTINUATION_EPOCH
    for row in network.failures[original_failure_count:]:
        row["execution_epoch"] = CONTINUATION_EPOCH
        row["lineage"]["execution_epoch"] = CONTINUATION_EPOCH
    network.save()


def combine_execution(continuation_execution: dict[str, Any],
                      manifest: dict[str, Any]) -> dict[str, Any]:
    original_results = rows(FAILED_RUN / "query_execution_results.jsonl")
    original_pages = rows(FAILED_RUN / "query_execution_provenance.jsonl")
    continuation_results = {row["executed_query_id"]: row
                            for row in continuation_execution["queries"]}
    combined_results = []
    for original in original_results:
        query_id = original["executed_query_id"]
        if original["transport_status"] == "SUCCESS":
            combined_results.append({**original, "successful_execution_epoch": ORIGINAL_EPOCH})
        else:
            require(query_id in continuation_results, "continuation result missing")
            result = continuation_results[query_id]
            combined_results.append({
                **result, "successful_execution_epoch": CONTINUATION_EPOCH,
                "prior_failed_run_transport_status": original["transport_status"],
                "original_terminal_attempts_preserved": (
                    original["transport_status"] == "TERMINAL_FAILURE"),
            })
    require(len(combined_results) == 25 and
            all(row["transport_status"] == "SUCCESS" for row in combined_results),
            "combined 25-query execution is incomplete")
    tagged_original_pages = [{**row, "execution_epoch": ORIGINAL_EPOCH}
                             for row in original_pages]
    tagged_continuation_pages = [{**row, "execution_epoch": CONTINUATION_EPOCH}
                                 for row in continuation_execution["pages"]]
    combined_pages = tagged_original_pages + tagged_continuation_pages
    case_observed = {case: [] for case in full.CASES}
    for page in combined_pages:
        if page["transport_status"] != "SUCCESS":
            continue
        for pmid in page["returned_pmids"]:
            if pmid not in case_observed[page["case_id"]]:
                case_observed[page["case_id"]].append(pmid)
    manifest_ids = {row["query_id"] for row in manifest["exact_queries"]}
    require({row["executed_query_id"] for row in combined_results} == manifest_ids,
            "combined query identity set mismatch")
    return {"queries": combined_results, "pages": combined_pages,
            "case_observed": case_observed}


def freeze_second_terminal_failure(network: legacy.Network, continuation: list[dict[str, Any]],
                                   exc: Exception, original_event_count: int,
                                   original_failure_count: int) -> None:
    tag_continuation_epoch(network, original_event_count, original_failure_count)
    new_failures = network.failures[original_failure_count:]
    write("technical_continuation_terminal_failure.json", pretty({
        "artifact_schema_version": "TechnicalContinuationTerminalFailureV1",
        "execution_epoch": CONTINUATION_EPOCH,
        "continuation_query_count": len(continuation),
        "failure": f"{type(exc).__name__}:{exc}",
        "new_failed_attempts": new_failures,
        "fail_closed": True, "subsequent_network_requests": 0,
    }))
    paths = sorted(path for path in RUN.rglob("*") if path.is_file() and
                   path.name not in {"validation.json", "search_plan_v24_dev_retrieval_surface_v2_technical_continuation_sha256"})
    pairs = [[str(path.relative_to(RUN)), sha(path)] for path in paths]
    root = aggregate(pairs)
    write("summary.json", pretty({
        "status": "failed", "execution_epoch": CONTINUATION_EPOCH,
        "failure_class": "TERMINAL_TECHNICAL_FAILURE",
        "protocol_compliance": "FAIL", "query_modifications": 0,
        "historical_assets_modified": False,
    }))
    # Recompute after adding summary.
    paths = sorted(path for path in RUN.rglob("*") if path.is_file() and
                   path.name not in {"validation.json", "search_plan_v24_dev_retrieval_surface_v2_technical_continuation_sha256"})
    pairs = [[str(path.relative_to(RUN)), sha(path)] for path in paths]
    root = aggregate(pairs)
    write("validation.json", pretty({
        "status": "FAIL", "failure_class": "TERMINAL_TECHNICAL_FAILURE",
        "aggregate_components": pairs,
        "search_plan_v24_dev_retrieval_surface_v2_technical_continuation_sha256": root,
    }))
    write("search_plan_v24_dev_retrieval_surface_v2_technical_continuation_sha256",
          (root + "\n").encode())


def replay_continuation_from_frozen_responses(
        continuation: list[dict[str, Any]], network: legacy.Network) -> dict[str, Any]:
    """Reconstruct the six completed continuation queries without issuing requests."""
    query_by_id = {row["query_id"]: row for row in continuation}
    events = [row for row in network.events
              if row.get("execution_epoch") == CONTINUATION_EPOCH]
    require(len(events) == 6, "continuation success-event count is not six")
    require({row["lineage"]["query_id"] for row in events} == set(query_by_id),
            "continuation success-event query set mismatch")
    pages, query_results = [], []
    case_observed = {case: [] for case in full.CASES}
    for order, query in enumerate(continuation, 1):
        event = next(row for row in events if row["lineage"]["query_id"] == query["query_id"])
        path = ROOT / event["snapshot_ref"]
        require(path.is_file() and sha(path) == event["response_sha256"],
                "continuation response snapshot mismatch")
        result = json.loads(path.read_text())["esearchresult"]
        ids = [str(value) for value in result.get("idlist", [])]
        total = int(result.get("count", 0))
        # Every continuation response naturally exhausted on its first page.
        require(not ids and total == 0, "unexpected nonzero frozen continuation response")
        page = {
            "request_sequence": order,
            "case_id": query["case_id"], "executed_query_id": query["query_id"],
            "query_sha256": query["query_sha256"], "query_text": query["exact_query_text"],
            "contributing_intent_types": query["contributing_intent_types"],
            "contributing_relation_core_ids": query["relation_core_ids"],
            "retrieval_surface_plan_ids": query["surface_plan_ids"],
            "pubmed_ast_hashes": query["pubmed_ast_hashes"],
            "page": 1, "retstart": 0, "retmax": 30,
            "raw_hit_count": total, "returned_pmids": ids,
            "returned_pmid_count": 0, "transport_status": "SUCCESS",
            "request_id": event["request_id"], "http_status": event["http_status"],
            "raw_response_sha256": event["response_sha256"],
            "raw_response_snapshot_ref": event["snapshot_ref"],
            "retry_count": event["retry_count"], "query_modified": False,
            "runtime_expansion": False, "execution_epoch": CONTINUATION_EPOCH,
        }
        pages.append(page)
        query_results.append({
            "artifact_schema_version": "RetrievalSurfaceV2QueryExecutionResultV1",
            "case_id": query["case_id"], "executed_query_id": query["query_id"],
            "query_sha256": query["query_sha256"], "query_text": query["exact_query_text"],
            "contributing_intent_types": query["contributing_intent_types"],
            "contributing_relation_core_ids": query["relation_core_ids"],
            "retrieval_surface_plan_ids": query["surface_plan_ids"],
            "pubmed_ast_hashes": query["pubmed_ast_hashes"],
            "transport_status": "SUCCESS", "raw_hit_count": 0,
            "outcome": "ZERO_HIT_QUERY", "returned_pmids_in_frozen_page_order": [],
            "returned_pmid_count": 0, "pubmed_warning_list": result.get("warninglist"),
            "query_modified": False, "runtime_expansion": False,
        })
    return {"pages": pages, "queries": query_results, "case_observed": case_observed}


def complete_successful_continuation(
        verification: dict[str, Any], continuation: list[dict[str, Any]],
        manifest: dict[str, Any], continuation_execution: dict[str, Any],
        network: legacy.Network, original_event_count: int,
        original_failure_count: int) -> dict[str, Any]:
    continuation_events = network.events[original_event_count:]
    continuation_failures = network.failures[original_failure_count:]
    require(len(continuation_events) == 6, "six continuation successes required")
    require({row["lineage"]["query_id"] for row in continuation_events} ==
            {row["query_id"] for row in continuation},
            "continuation success set mismatch")
    require(all(row["retry_count"] <= 3 for row in continuation_events),
            "continuation retry maximum exceeded")
    failure_counts = Counter(row["lineage"]["query_id"] for row in continuation_failures)
    require(all(count <= 3 for count in failure_counts.values()),
            "continuation query exhausted four failed attempts")
    write("technical_continuation_epoch_result.json", pretty({
        "artifact_schema_version": "TechnicalContinuationEpochResultV1",
        "execution_epoch": CONTINUATION_EPOCH,
        "continuation_query_count": 6, "successful_query_count": 6,
        "terminal_failure_count": 0,
        "original_successful_queries_rerun": 0,
        "original_exhausted_attempts_preserved": True,
        "continuation_network_response_count": len(continuation_events),
        "continuation_failed_attempt_count": len(continuation_failures),
        "per_query_retry_counts": {
            row["lineage"]["query_id"]: row["retry_count"] for row in continuation_events},
        "query_modifications": 0, "syntax_adaptations": 0,
    }))

    combined = combine_execution(continuation_execution, manifest)
    universe = full.freeze_retrieval_universe(combined)
    full.fetch_metadata(network, universe["hard_tail_pmids"])
    metadata = full.build_metadata_records(universe)
    targets, bindings, old_queries = legacy.v23_frozen_inputs()
    gate_queries: dict[str, list[dict[str, Any]]] = {case: [] for case in full.CASES}
    for query in old_queries:
        gate_queries[query["case_id"]].append(query)
    targets_by_case = {row["case_id"]: row for row in targets}
    gates = {case: legacy.gate_target(targets_by_case[case], bindings[case], gate_queries[case])
             for case in full.CASES}
    processed = legacy.score_and_select(metadata, targets, gates, network)
    selection_sha, selected = full.freeze_scoring_and_selection(processed, universe["universe_sha"])
    print(f"selection_frozen sha256={selection_sha} count={len(selected)}", flush=True)
    fulltexts, failures = full.fetch_fulltexts(network, selected, selection_sha)
    finish_verification = {"verified_before_first_network_request": True,
                           "roots": {"alpha3_7_preregistration": verification["alpha3_7"],
                                     "authoritative_failed_run": verification["failed_run"]}}
    result = full.finish(finish_verification, manifest, combined, universe, metadata,
                         processed, selection_sha, fulltexts, failures, network)
    require(verify_run(FAILED_RUN,
                       "search_plan_v24_dev_retrieval_surface_v2_full_retrieval_sha256",
                       EXPECTED_FAILED_ROOT)["verified"], "failed run changed")
    return result


def main(execute_network: bool, preflight_only: bool,
         resume_frozen_responses: bool = False) -> None:
    verification, continuation, freeze, manifest = derive_continuation_set()
    print(json.dumps({"preflight": verification,
                      "continuation_query_ids": [row["query_id"] for row in continuation],
                      "status": "PASS"}, indent=2, sort_keys=True), flush=True)
    if preflight_only:
        return
    if resume_frozen_responses:
        require(not execute_network, "frozen-response replay must not reissue query requests")
        require(RUN.is_dir() and not (RUN / "validation.json").exists(),
                "continuation run is absent or already frozen")
        require(sha(RUN / "technical_continuation_set.json") ==
                (RUN / "technical_continuation_set_sha256").read_text().strip(),
                "continuation-set freeze mismatch")
        legacy.RUN = RUN; legacy.ASSETS = ASSETS
        full.RUN = RUN; full.ASSETS = ASSETS
        network = legacy.Network(False)
        original_event_count = sum(row.get("execution_epoch") == ORIGINAL_EPOCH
                                   for row in network.events)
        original_failure_count = sum(row.get("execution_epoch") == ORIGINAL_EPOCH
                                     for row in network.failures)
        continuation_execution = replay_continuation_from_frozen_responses(
            continuation, network)
        result = complete_successful_continuation(
            verification, continuation, manifest, continuation_execution, network,
            original_event_count, original_failure_count)
        print(json.dumps(result, indent=2, sort_keys=True), flush=True)
        return
    require(execute_network, "explicit --execute-network required")
    network = initialize_epoch(verification, freeze)
    original_event_count = len(network.events)
    original_failure_count = len(network.failures)
    try:
        continuation_execution = full.execute_queries(network, continuation)
    except Exception as exc:
        freeze_second_terminal_failure(network, continuation, exc,
                                       original_event_count, original_failure_count)
        raise
    tag_continuation_epoch(network, original_event_count, original_failure_count)
    require(len(network.events) - original_event_count >= 6,
            "not all continuation queries generated successful responses")
    result = complete_successful_continuation(
        verification, continuation, manifest, continuation_execution, network,
        original_event_count, original_failure_count)
    print(json.dumps(result, indent=2, sort_keys=True), flush=True)


if __name__ == "__main__":
    parsed = args()
    main(parsed.execute_network, parsed.preflight_only, parsed.resume_frozen_responses)
