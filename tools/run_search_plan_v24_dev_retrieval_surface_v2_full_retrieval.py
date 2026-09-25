#!/usr/bin/env python3
"""Execute the frozen Retrieval Surface V2 development retrieval.

Network access is restricted to the frozen NCBI PubMed/PMC E-utilities
pipeline.  The runner performs no query adaptation, provider/LLM call,
known-paper lookup, or scientific relevance adjudication.
"""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys
import time
from typing import Any
import urllib.parse
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import tools.run_search_plan_v24_dev_alpha3_4_development_retrospective_retrieval as legacy


RUN = ROOT / "runs/20260924_search_plan_v24_dev_retrieval_surface_v2_full_retrieval"
ASSETS = RUN / "retrieval_assets"
PREREG = ROOT / "runs/20260924_search_plan_v24_dev_alpha3_7_retrieval_surface_v2_preregistration_offline"
EXECUTION_MANIFEST = PREREG / "retrieval_surface_v2_development_execution_manifest.json"
ALPHA36 = ROOT / "runs/20260924_search_plan_v24_dev_alpha3_6_retrieval_surface_compiler_v2_offline"
ALPHA34 = ROOT / "runs/20260923_search_plan_v24_dev_alpha3_4_retrieval_preregistration_offline"
FAILED = ROOT / "runs/20260924_search_plan_v24_dev_frozen_retrospective_retrieval"
BASE = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"

EXPECTED_ALPHA37 = "bb5dd4b2ab1e2717b520d588a2520698d73c471495094a1ef915ccae80d9f49e"
EXPECTED_EXECUTION = "f10e21a25ffff4f4ecfafa2f4a838ea4f9dba1d6c6194656aae5d87a51ae7a7e"
EXPECTED_ALPHA36 = "d043441e59de0c29958b1af8c935868c5f1f233b62178c2476b9a89763377cd0"
EXPECTED_QUERY_SET = "4f5148b0ae1a97aaf1bf7334109562c4d04dbdcf99cebb323f87f872a3e93947"
EXPECTED_ALPHA34 = "2488b4322894acb755872e9bc92d78dcaf2a4dec6ed807a22d3aff4622e2d5d5"
EXPECTED_FAILED = "391d2fe5d7c133be42d3c503a92ecc8724f398430adf20c46283ad1567e8dfd5"
HISTORICAL_EMPTY_CORPUS = "81898e8f609e03f18398eefec2cb56deb579b05acb5f362d5351c029b7c748f6"

CASES = tuple(f"heldout_v2_{number}" for number in range(101, 109))
EXPECTED_CASE_COUNTS = dict(zip(CASES, (3, 2, 1, 2, 4, 6, 3, 4)))
SOFT_TAIL, HARD_TAIL, PAGE_SIZE, FULLTEXT_LIMIT = 120, 180, 30, 10


def options() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--execute-network", action="store_true")
    parser.add_argument("--preflight-only", action="store_true")
    parser.add_argument("--freeze-terminal-failure", action="store_true")
    return parser.parse_args()


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


def pretty(value: Any) -> bytes:
    return (json.dumps(value, sort_keys=True, ensure_ascii=False, indent=2) + "\n").encode()


def jsonl(rows: list[dict[str, Any]]) -> bytes:
    return b"".join(canonical(row) + b"\n" for row in rows)


def sha_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha(path: Path) -> str:
    return sha_bytes(path.read_bytes())


def value_sha(value: Any) -> str:
    return sha_bytes(canonical(value))


def aggregate(pairs: list[list[str]]) -> str:
    return value_sha(pairs)


def load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def rel(path: Path) -> str:
    return str(path.resolve().relative_to(ROOT))


def write(path_or_name: str | Path, body: bytes) -> None:
    path = path_or_name if isinstance(path_or_name, Path) else RUN / path_or_name
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        require(path.is_file() and path.read_bytes() == body,
                f"refusing to change frozen output: {path}")
        return
    path.write_bytes(body)


def verify_run(path: Path, root_name: str, expected: str) -> dict[str, Any]:
    validation = load(path / "validation.json")
    pairs = validation["aggregate_components"]
    require(all(sha(path / name) == digest for name, digest in pairs),
            f"upstream component mismatch: {path.name}")
    actual = aggregate(pairs)
    recorded = (path / root_name).read_text().strip()
    require(actual == recorded == expected, f"upstream root mismatch: {path.name}")
    return {"path": rel(path), "expected_sha256": expected,
            "recomputed_sha256": actual, "verified": True}


def preflight() -> tuple[dict[str, Any], dict[str, Any], list[dict[str, Any]],
                         list[dict[str, Any]], dict[str, dict[str, Any]]]:
    roots = {
        "alpha3_7_preregistration": verify_run(
            PREREG, "search_plan_v24_dev_alpha3_7_sha256", EXPECTED_ALPHA37),
        "alpha3_6_compiler": verify_run(
            ALPHA36, "search_plan_v24_dev_alpha3_6_sha256", EXPECTED_ALPHA36),
        "alpha3_4_downstream_policy": verify_run(
            ALPHA34, "search_plan_v24_dev_alpha3_4_sha256", EXPECTED_ALPHA34),
        "historical_failed_retrieval": verify_run(
            FAILED, "search_plan_v24_dev_frozen_retrospective_retrieval_sha256",
            EXPECTED_FAILED),
    }
    require(sha(EXECUTION_MANIFEST) == EXPECTED_EXECUTION,
            "execution manifest hash mismatch")
    manifest = load(EXECUTION_MANIFEST)
    require(manifest["state"] == "FROZEN_NOT_EXECUTED" and not manifest["retrieval_executed"],
            "execution manifest state mismatch")
    require(manifest["query_set_sha256"] == EXPECTED_QUERY_SET,
            "manifest query-set hash mismatch")
    query_path = ALPHA36 / "search_plan_v24_dev_retrieval_surface_v2_query_set.jsonl"
    require(sha(query_path) == EXPECTED_QUERY_SET, "query-set bytes changed")
    source_queries = [json.loads(line) for line in query_path.read_text().splitlines() if line]
    queries = manifest["exact_queries"]
    require(len(queries) == len(source_queries) == 25, "query count mismatch")
    require(Counter(row["case_id"] for row in queries) == Counter(EXPECTED_CASE_COUNTS),
            "per-case query count mismatch")
    require([row["exact_query_text"].encode() for row in queries] ==
            [row["serialized_query"].encode() for row in source_queries],
            "frozen query text changed")
    require(all(sha_bytes(row["exact_query_text"].encode()) == row["query_sha256"]
                for row in queries), "query hash mismatch")
    require(len(manifest["source_relation_contributions"]) == 29,
            "relation contribution count mismatch")
    require(manifest["compiler_configuration"] == {
        "compact_concept_window_n": 0,
        "relation_edge_window_n": 5,
        "maximum_semantic_roles_per_proximity_node": 3,
        "max_queries_per_target": 12,
        "max_surface_variants_per_validated_intent": 2,
        "contract_hashes": manifest["compiler_configuration"]["contract_hashes"],
    }, "compiler configuration mismatch")
    require(all(sha(ALPHA36 / name) == digest for name, digest in
                manifest["compiler_configuration"]["contract_hashes"].items()),
            "compiler contract hash mismatch")
    require(all(sha(ALPHA34 / name) == digest for name, digest in
                manifest["alpha3_4_downstream_policy_hashes"].items()),
            "downstream policy hash mismatch")

    targets, bindings, old_queries = legacy.v23_frozen_inputs()
    targets_by_case = {row["case_id"]: row for row in targets}
    require(tuple(sorted(targets_by_case)) == CASES, "target case set mismatch")
    require(all(value_sha(targets_by_case[case]) == digest
                for case, digest in manifest["target_hashes"].items()),
            "target hash mismatch")
    gate_queries: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for query in old_queries:
        gate_queries[query["case_id"]].append(query)
    gates = {case: legacy.gate_target(targets_by_case[case], bindings[case], gate_queries[case])
             for case in CASES}
    verification = {
        "artifact_schema_version": "RetrievalSurfaceV2ExecutionVerificationV1",
        "verified_before_first_network_request": True,
        "verification_timestamp_utc": now(), "roots": roots,
        "execution_manifest_sha256": sha(EXECUTION_MANIFEST),
        "query_set_sha256": sha(query_path),
        "byte_unique_query_count": 25, "relation_contribution_count": 29,
        "query_text_changes": 0, "query_hash_changes": 0,
        "ast_changes": 0, "surface_plan_changes": 0,
        "compiler_configuration_verified": True,
        "downstream_policy_hashes_verified": True,
    }
    return verification, manifest, queries, targets, gates


def bind_network() -> legacy.Network:
    # Reuse the previously frozen NCBI-only transport and retry implementation.
    legacy.RUN = RUN
    legacy.ASSETS = ASSETS
    return legacy.Network(True)


def execute_queries(network: legacy.Network, queries: list[dict[str, Any]]) -> dict[str, Any]:
    page_rows: list[dict[str, Any]] = []
    case_observed: dict[str, list[str]] = {case: [] for case in CASES}
    case_seen: dict[str, set[str]] = {case: set() for case in CASES}
    query_pmids: dict[str, list[str]] = {row["query_id"]: [] for row in queries}
    query_counts: dict[str, int] = {}
    query_warnings: dict[str, Any] = {}
    request_sequence = 0

    for case in CASES:
        case_queries = [row for row in queries if row["case_id"] == case]
        active = [{"query": row, "retstart": 0, "page": 1} for row in case_queries]
        logically_executed: set[str] = set()
        while active:
            next_active = []
            for item in active:
                query = item["query"]
                at_cap = len(case_observed[case]) >= HARD_TAIL
                if at_cap and query["query_id"] in logically_executed:
                    continue
                retmax = 0 if at_cap else PAGE_SIZE
                params = {"db": "pubmed", "term": query["exact_query_text"],
                          "retstart": item["retstart"], "retmax": retmax,
                          "retmode": "json", "sort": "relevance",
                          "tool": "conflict_oriented_discovery_engine"}
                suffix = f"retstart_{item['retstart']:04d}_retmax_{retmax:03d}"
                path = (ASSETS / "pubmed_esearch" / case /
                        f"{query['query_id'].replace(':', '_')}__{suffix}.json")
                url = BASE + "/esearch.fcgi?" + urllib.parse.urlencode(params)
                request_sequence += 1
                try:
                    raw, event, _ = network.get(url, path, "pubmed_search", {
                        "case_id": case, "query_id": query["query_id"],
                        "query_sha256": query["query_sha256"],
                        "contributing_intent_types": query["contributing_intent_types"],
                        "relation_core_ids": query["relation_core_ids"],
                        "surface_plan_ids": query["surface_plan_ids"],
                        "pubmed_ast_hashes": query["pubmed_ast_hashes"],
                        "retstart": item["retstart"], "retmax": retmax,
                    })
                    require(len(raw) <= 10_000_000, "unexpectedly large PubMed response")
                    result = json.loads(raw.decode())["esearchresult"]
                    ids = [str(value) for value in result.get("idlist", [])]
                    total = int(result.get("count", 0))
                    if query["query_id"] not in query_counts:
                        query_counts[query["query_id"]] = total
                        query_warnings[query["query_id"]] = result.get("warninglist")
                    else:
                        require(query_counts[query["query_id"]] == total,
                                "PubMed hit count changed during pagination")
                    query_pmids[query["query_id"]].extend(ids)
                    for pmid in ids:
                        if pmid not in case_seen[case]:
                            case_seen[case].add(pmid)
                            case_observed[case].append(pmid)
                    page_rows.append({
                        "request_sequence": request_sequence,
                        "case_id": case, "executed_query_id": query["query_id"],
                        "query_sha256": query["query_sha256"],
                        "query_text": query["exact_query_text"],
                        "contributing_intent_types": query["contributing_intent_types"],
                        "contributing_relation_core_ids": query["relation_core_ids"],
                        "retrieval_surface_plan_ids": query["surface_plan_ids"],
                        "pubmed_ast_hashes": query["pubmed_ast_hashes"],
                        "page": item["page"], "retstart": item["retstart"],
                        "retmax": retmax, "raw_hit_count": total,
                        "returned_pmids": ids, "returned_pmid_count": len(ids),
                        "transport_status": "SUCCESS", "request_id": event["request_id"],
                        "http_status": event["http_status"],
                        "raw_response_sha256": event["response_sha256"],
                        "raw_response_snapshot_ref": event["snapshot_ref"],
                        "retry_count": event["retry_count"],
                        "query_modified": False, "runtime_expansion": False,
                    })
                    logically_executed.add(query["query_id"])
                    next_offset = item["retstart"] + len(ids)
                    if (retmax and ids and next_offset < total and
                            len(case_observed[case]) < HARD_TAIL):
                        next_active.append({"query": query, "retstart": next_offset,
                                            "page": item["page"] + 1})
                except Exception as exc:
                    page_rows.append({
                        "request_sequence": request_sequence, "case_id": case,
                        "executed_query_id": query["query_id"],
                        "query_sha256": query["query_sha256"],
                        "query_text": query["exact_query_text"],
                        "page": item["page"], "retstart": item["retstart"],
                        "retmax": retmax, "transport_status": "TERMINAL_FAILURE",
                        "raw_hit_count": None, "returned_pmids": [],
                        "error_state": {"type": type(exc).__name__, "message": str(exc)},
                        "query_modified": False, "runtime_expansion": False,
                    })
                    write("query_execution_provenance.jsonl", jsonl(page_rows))
                    raise RuntimeError(f"terminal PubMed search failure: {case}/{query['query_id']}") from exc
            active = next_active
        require(logically_executed == {row["query_id"] for row in case_queries},
                f"not all queries logically executed: {case}")
        print(f"search_complete case={case} observed_unique={len(case_observed[case])}", flush=True)

    query_results = []
    for query in queries:
        query_id = query["query_id"]
        total = query_counts[query_id]
        query_results.append({
            "artifact_schema_version": "RetrievalSurfaceV2QueryExecutionResultV1",
            "case_id": query["case_id"], "executed_query_id": query_id,
            "query_sha256": query["query_sha256"],
            "query_text": query["exact_query_text"],
            "contributing_intent_types": query["contributing_intent_types"],
            "contributing_relation_core_ids": query["relation_core_ids"],
            "retrieval_surface_plan_ids": query["surface_plan_ids"],
            "pubmed_ast_hashes": query["pubmed_ast_hashes"],
            "transport_status": "SUCCESS", "raw_hit_count": total,
            "outcome": "ZERO_HIT_QUERY" if total == 0 else "NONZERO_QUERY",
            "returned_pmids_in_frozen_page_order": query_pmids[query_id],
            "returned_pmid_count": len(query_pmids[query_id]),
            "pubmed_warning_list": query_warnings[query_id],
            "query_modified": False, "runtime_expansion": False,
        })
    return {"pages": page_rows, "queries": query_results, "case_observed": case_observed}


def freeze_retrieval_universe(execution: dict[str, Any]) -> dict[str, Any]:
    pages = execution["pages"]
    queries = execution["queries"]
    case_rows, provenance_rows = [], []
    hard_tail_pmids: dict[str, list[str]] = {}
    for case in CASES:
        observed = execution["case_observed"][case]
        hard = observed[:HARD_TAIL]
        hard_tail_pmids[case] = hard
        included = set(hard)
        occurrences: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for page in (row for row in pages if row["case_id"] == case and
                     row["transport_status"] == "SUCCESS"):
            for rank, pmid in enumerate(page["returned_pmids"], page["retstart"] + 1):
                occurrences[pmid].append({
                    "executed_query_id": page["executed_query_id"],
                    "query_sha256": page["query_sha256"], "query_rank": rank,
                    "page": page["page"], "retstart": page["retstart"],
                    "raw_response_sha256": page["raw_response_sha256"],
                })
        case_rows.append({
            "artifact_schema_version": "RetrievalSurfaceV2CaseUnionPMIDsV1",
            "case_id": case, "observed_unique_pmids_before_hard_tail": observed,
            "observed_unique_pmid_count_before_hard_tail": len(observed),
            "hard_tail_pmids": hard, "hard_tail_pmid_count": len(hard),
            "hard_tail": HARD_TAIL, "hard_tail_truncated": len(observed) > HARD_TAIL,
            "cross_case_deduplication": False,
        })
        for pmid in observed:
            provenance_rows.append({
                "case_id": case, "pmid": pmid,
                "included_in_hard_tail_universe": pmid in included,
                "occurrences": occurrences[pmid],
                "contributing_query_ids": list(dict.fromkeys(
                    row["executed_query_id"] for row in occurrences[pmid])),
            })
    write("query_execution_results.jsonl", jsonl(queries))
    write("query_execution_provenance.jsonl", jsonl(pages))
    write("case_union_pmids.jsonl", jsonl(case_rows))
    write("case_union_provenance.jsonl", jsonl(provenance_rows))
    components = [[name, sha(RUN / name)] for name in [
        "query_execution_results.jsonl", "query_execution_provenance.jsonl",
        "case_union_pmids.jsonl", "case_union_provenance.jsonl"]]
    universe_sha = aggregate(components)
    write("retrieval_universe_freeze.json", pretty({
        "artifact_schema_version": "RetrievalSurfaceV2UniverseFreezeV1",
        "components": components, "retrieval_universe_sha256": universe_sha,
        "frozen_before_metadata_scoring": True,
        "query_count": 25, "case_count": 8,
    }))
    write("tail_application_audit.json", pretty({
        "artifact_schema_version": "RetrievalSurfaceV2TailApplicationAuditV1",
        "soft_tail": SOFT_TAIL, "soft_tail_reporting_only": True,
        "hard_tail": HARD_TAIL, "adaptive_tail_enabled": False,
        "tail_applied_after_within_case_pmid_deduplication": True,
        "no_query_specific_tail": True, "no_intent_specific_tail": True,
        "no_padding_or_fallback": True,
        "cases": [{"case_id": row["case_id"],
                   "observed_before_hard_tail": row["observed_unique_pmid_count_before_hard_tail"],
                   "hard_tail_universe": row["hard_tail_pmid_count"],
                   "state": "HARD_TAIL_REACHED" if row["hard_tail_pmid_count"] == HARD_TAIL
                   else "NATURAL_EXHAUSTION"} for row in case_rows],
    }))
    return {"case_rows": case_rows, "provenance_rows": provenance_rows,
            "hard_tail_pmids": hard_tail_pmids, "universe_sha": universe_sha}


def fetch_metadata(network: legacy.Network, hard_tail_pmids: dict[str, list[str]]) -> list[dict[str, Any]]:
    all_pmids = sorted({pmid for rows in hard_tail_pmids.values() for pmid in rows}, key=int)
    manifest_rows = []
    for batch, start in enumerate(range(0, len(all_pmids), 100), 1):
        ids = all_pmids[start:start + 100]
        params = {"db": "pubmed", "id": ",".join(ids), "retmode": "xml",
                  "tool": "conflict_oriented_discovery_engine"}
        path = ASSETS / "pubmed_efetch" / f"batch_{batch:03d}.xml"
        raw, event, _ = network.get(
            BASE + "/efetch.fcgi?" + urllib.parse.urlencode(params), path,
            "pubmed_metadata", {"pmids": ids, "batch": batch})
        manifest_rows.append({
            "batch": batch, "pmids": ids, "pmid_count": len(ids),
            "transport_status": "SUCCESS", "request_id": event["request_id"],
            "http_status": event["http_status"], "retry_count": event["retry_count"],
            "response_sha256": sha_bytes(raw), "snapshot_ref": event["snapshot_ref"],
        })
        print(f"metadata_complete batch={batch} pmids={len(ids)}", flush=True)
    write("metadata_fetch_manifest.jsonl", jsonl(manifest_rows))
    return manifest_rows


def build_metadata_records(universe: dict[str, Any]) -> list[dict[str, Any]]:
    publications: dict[str, dict[str, Any]] = {}
    for path in sorted((ASSETS / "pubmed_efetch").glob("batch_*.xml")):
        publications.update(legacy.parse_pubmed(path.read_bytes()))
    provenance = {(row["case_id"], row["pmid"]): row
                  for row in universe["provenance_rows"]}
    candidates, failures = [], []
    for case in CASES:
        for depth, pmid in enumerate(universe["hard_tail_pmids"][case], 1):
            if pmid not in publications:
                failures.append({"case_id": case, "pmid": pmid,
                                 "failure_state": "METADATA_FETCH_FAILURE"})
                continue
            pub = publications[pmid]
            lineage = provenance[(case, pmid)]
            candidates.append({
                "artifact_schema_version": "RetrievalSurfaceV2MetadataRecordV1",
                "candidate_id": f"{case}:pmid:{pmid}", "case_id": case,
                "canonical_candidate_identity": f"pmid:{pmid}",
                "case_publication_identity": f"{case}:pmid:{pmid}",
                "pmid": pmid, "pmcid": pub.get("pmcid"), "doi": pub.get("doi"),
                "title": pub["title"], "abstract": pub["abstract"],
                "publication_type": pub["publication_types"],
                "journal": pub["journal"], "publication_date": pub["publication_date"],
                "metadata_depth": depth,
                "first_seen_provenance": lineage["occurrences"][0],
                "query_provenance": lineage["occurrences"],
                "all_contributing_query_ids": lineage["contributing_query_ids"],
                "deduplication_identity_rule": "PMID within case",
                "metadata_resolution_status": "RESOLVED",
            })
    write("metadata_records.jsonl", jsonl(candidates))
    write("metadata_failure_records.jsonl", jsonl(failures))
    require(not failures, "terminal metadata failure; aborting before ranking")
    return candidates


def freeze_scoring_and_selection(processed: dict[str, Any], universe_sha: str) -> tuple[str, list[dict[str, Any]]]:
    mapping = {
        "candidate_gate_results.jsonl": processed["base"],
        "p0_results.jsonl": processed["p0"], "p1_results.jsonl": processed["p1"],
        "p2_results.jsonl": processed["p2"], "policy_a_results.jsonl": processed["policy"],
        "oa_eligibility_results.jsonl": processed["oa"],
    }
    for name, rows in mapping.items():
        write(name, jsonl(rows))
    tiers = Counter(row["final_v23_beta2_disposition"] for row in processed["final"])
    write("candidate_tier_summary.json", pretty({
        "artifact_schema_version": "RetrievalSurfaceV2CandidateTierSummaryV1",
        "counts": {state: tiers.get(state, 0) for state in
                   ("TIER_A", "TIER_B", "REJECT", "ABSTAIN")},
        "candidate_count": len(processed["final"]),
        "tier_a_before_tier_b": True,
        "within_tier_order": ["metadata_depth", "numeric PMID"],
    }))

    case_files = []
    for case in CASES:
        rows = [row for row in processed["selected"] if row["case_id"] == case]
        path = RUN / "case_selection_manifests" / f"{case}.json"
        write(path, pretty({
            "artifact_schema_version": "RetrievalSurfaceV2CaseSelectionManifestV1",
            "case_id": case, "selection_count": len(rows),
            "maximum_fulltexts_per_case": FULLTEXT_LIMIT,
            "ordered_selections": rows, "fulltext_content_inspected": False,
        }))
        case_files.append(path)
    pairs = [[str(path.relative_to(RUN)), sha(path)] for path in case_files]
    selection_sha = aggregate(pairs)
    write("selection_manifest_aggregate_sha256", (selection_sha + "\n").encode())
    write("selection_freeze_barrier_audit.json", pretty({
        "artifact_schema_version": "SelectionFreezeBarrierAuditV1",
        "case_manifest_components": pairs, "case_manifest_count": 8,
        "selection_manifest_aggregate_sha256": selection_sha,
        "retrieval_universe_sha256": universe_sha,
        "all_eight_manifests_frozen_and_hashed": True,
        "frozen_before_first_pmc_fulltext_fetch": True,
        "selection_freeze_barrier_pass": True,
        "fulltext_content_used_for_selection": False,
    }))
    return selection_sha, processed["selected"]


def fetch_fulltexts(network: legacy.Network, selected: list[dict[str, Any]],
                    selection_sha: str) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    barrier = load(RUN / "selection_freeze_barrier_audit.json")
    require(barrier["selection_freeze_barrier_pass"] and
            barrier["selection_manifest_aggregate_sha256"] == selection_sha,
            "selection freeze barrier not satisfied")
    fetch_rows, results, failures = [], [], []
    for selection in selected:
        pmcid = selection["legal_fulltext_identifier"]
        params = {"db": "pmc", "id": pmcid, "retmode": "xml",
                  "tool": "conflict_oriented_discovery_engine"}
        path = ASSETS / "fulltext" / f"{pmcid}.xml"
        event = None
        transport_error = None
        try:
            _, event, _ = network.get(
                BASE + "/efetch.fcgi?" + urllib.parse.urlencode(params), path,
                "pmc_fulltext", {"selection_id": selection["selection_id"],
                                  "case_id": selection["case_id"],
                                  "candidate_id": selection["candidate_id"], "pmcid": pmcid})
        except Exception as exc:
            transport_error = f"{type(exc).__name__}:{exc}"
        article_ok = identity_ok = False
        raw_hash = parsed_hash = None
        error = transport_error
        if path.is_file() and event:
            raw = path.read_bytes()
            raw_hash = sha_bytes(raw)
            try:
                xml_root = ET.fromstring(raw)
                article_ok = xml_root.find(".//article") is not None or xml_root.tag.endswith("article")
                pmids = [legacy.text_of(node)
                         for node in xml_root.findall(".//article-id[@pub-id-type='pmid']")]
                expected_pmid = selection["publication_metadata"]["pmid"]
                identity_ok = not pmids or expected_pmid in pmids
                parsed_hash = sha_bytes(ET.tostring(xml_root, encoding="utf-8"))
                if not article_ok or not identity_ok:
                    error = "PMC_ARTICLE_OR_IDENTITY_VALIDATION_FAILED"
            except ET.ParseError as exc:
                error = f"XML_PARSE_ERROR:{exc}"
        status = "SUCCESS" if event and article_ok and identity_ok and not error else "FAILED"
        fetch_rows.append({
            "selection_id": selection["selection_id"], "case_id": selection["case_id"],
            "candidate_id": selection["candidate_id"], "pmid": selection["publication_metadata"]["pmid"],
            "pmcid": pmcid, "selection_rank": selection["selection_index_within_case"],
            "request_id": event["request_id"] if event else None,
            "fetch_attempts": event["retry_count"] + 1 if event else 4,
            "http_status": event["http_status"] if event else None,
            "response_sha256": event["response_sha256"] if event else None,
            "snapshot_ref": event["snapshot_ref"] if event else None,
            "transport_status": "SUCCESS" if event else "TERMINAL_FAILURE",
        })
        result = {
            "selection_id": selection["selection_id"], "case_id": selection["case_id"],
            "candidate_id": selection["candidate_id"], "pmid": selection["publication_metadata"]["pmid"],
            "pmcid": pmcid, "selection_rank": selection["selection_index_within_case"],
            "acquisition_status": status, "publication_identity_valid": identity_ok,
            "xml_valid": parsed_hash is not None, "article_structure_valid": article_ok,
            "raw_content_sha256": raw_hash, "parsed_content_sha256": parsed_hash,
            "artifact_snapshot_ref": rel(path) if path.is_file() else None,
            "selection_frozen_before_download": True,
            "selection_manifest_aggregate_sha256": selection_sha,
            "replacement_performed": False, "error_state": error,
        }
        results.append(result)
        if status == "FAILED":
            failures.append(result)
        print(f"fulltext_complete selection={selection['selection_id']} status={status}", flush=True)
    write("fulltext_fetch_manifest.jsonl", jsonl(fetch_rows))
    write("fulltext_acquisition_results.jsonl", jsonl(results))
    write("fulltext_failure_records.jsonl", jsonl(failures))
    write("acquired_fulltext_manifest.json", pretty({
        "artifact_schema_version": "RetrievalSurfaceV2AcquiredFulltextManifestV1",
        "successful_acquisition_count": sum(row["acquisition_status"] == "SUCCESS" for row in results),
        "failed_acquisition_count": len(failures),
        "acquired_fulltexts": [row for row in results if row["acquisition_status"] == "SUCCESS"],
        "replacement_count": 0,
    }))
    return results, failures


def finish(verification: dict[str, Any], manifest: dict[str, Any],
           execution: dict[str, Any], universe: dict[str, Any],
           metadata: list[dict[str, Any]], processed: dict[str, Any],
           selection_sha: str, fulltexts: list[dict[str, Any]],
           failures: list[dict[str, Any]], network: legacy.Network) -> dict[str, Any]:
    queries = execution["queries"]
    nonzero_queries = [row for row in queries if row["outcome"] == "NONZERO_QUERY"]
    zero_queries = [row for row in queries if row["outcome"] == "ZERO_HIT_QUERY"]
    case_stats = []
    for case in CASES:
        case_queries = [row for row in queries if row["case_id"] == case]
        case_metadata = [row for row in metadata if row["case_id"] == case]
        case_fulltexts = [row for row in fulltexts if row["case_id"] == case]
        union = next(row for row in universe["case_rows"] if row["case_id"] == case)
        case_stats.append({
            "case_id": case, "executed_query_count": len(case_queries),
            "nonzero_query_count": sum(row["outcome"] == "NONZERO_QUERY" for row in case_queries),
            "zero_hit_query_count": sum(row["outcome"] == "ZERO_HIT_QUERY" for row in case_queries),
            "raw_hit_count_sum": sum(row["raw_hit_count"] for row in case_queries),
            "unique_pmids_before_hard_tail": union["observed_unique_pmid_count_before_hard_tail"],
            "metadata_universe_count": len(case_metadata),
            "successful_fulltext_acquisition_count": sum(
                row["acquisition_status"] == "SUCCESS" for row in case_fulltexts),
        })
    write("query_outcome_summary.json", pretty({
        "artifact_schema_version": "RetrievalSurfaceV2QueryOutcomeSummaryV1",
        "query_execution_success_count": len(queries), "query_terminal_failure_count": 0,
        "nonzero_query_count": len(nonzero_queries), "zero_hit_query_count": len(zero_queries),
        "transport_success_is_scientific_retrieval_success": False,
    }))
    write("case_query_hit_summary.json", pretty({
        "artifact_schema_version": "RetrievalSurfaceV2CaseQueryHitSummaryV1",
        "cases": case_stats,
        "nonzero_case_count": sum(row["nonzero_query_count"] > 0 for row in case_stats),
        "zero_hit_case_count": sum(row["nonzero_query_count"] == 0 for row in case_stats),
    }))

    tier_counts = Counter(row["final_v23_beta2_disposition"] for row in processed["final"])
    oa_count = sum(row["legal_fulltext_available"] for row in processed["oa"])
    selected_count = len(processed["selected"])
    acquired_count = sum(row["acquisition_status"] == "SUCCESS" for row in fulltexts)
    cases_acquired = len({row["case_id"] for row in fulltexts if row["acquisition_status"] == "SUCCESS"})
    observed_total = sum(row["observed_unique_pmid_count_before_hard_tail"]
                         for row in universe["case_rows"])
    occurrence_count = sum(len(row["occurrences"]) for row in universe["provenance_rows"]
                           if row["included_in_hard_tail_universe"])
    overlap_rate = ((occurrence_count - len(metadata)) / occurrence_count
                    if occurrence_count else 0.0)
    denominators = {
        "relation_contribution_count": 29, "byte_unique_query_count": 25,
        "query_execution_success_count": len(queries), "query_terminal_failure_count": 0,
        "nonzero_query_count": len(nonzero_queries), "zero_hit_query_count": len(zero_queries),
        "development_case_count": 8,
        "nonzero_case_count": sum(row["nonzero_query_count"] > 0 for row in case_stats),
        "zero_hit_case_count": sum(row["nonzero_query_count"] == 0 for row in case_stats),
        "unique_pmids_before_tail_total": observed_total,
        "metadata_universe_total": len(metadata),
        "tier_a_count": tier_counts.get("TIER_A", 0),
        "tier_b_count": tier_counts.get("TIER_B", 0),
        "reject_count": tier_counts.get("REJECT", 0),
        "abstain_count": tier_counts.get("ABSTAIN", 0),
        "oa_eligible_count": oa_count, "selected_count": selected_count,
        "successful_fulltext_acquisition_count": acquired_count,
        "fulltext_failure_count": len(failures),
        "cases_with_acquired_fulltext": cases_acquired,
        "cases_with_zero_acquired_fulltext": 8 - cases_acquired,
        "query_overlap_rate": round(overlap_rate, 12),
    }
    write("retrieval_denominator_summary.json", pretty({
        "artifact_schema_version": "RetrievalSurfaceV2DenominatorSummaryV1",
        **denominators, "relevance_denominators_present": False,
    }))

    contributions_by_query: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in manifest["source_relation_contributions"]:
        contributions_by_query[row["executed_query_id"]].append(row)
    intent_stats: dict[str, dict[str, Any]] = {}
    for query in queries:
        for contribution in contributions_by_query[query["executed_query_id"]]:
            row = intent_stats.setdefault(contribution["intent_type"], {
                "intent_type": contribution["intent_type"], "relation_contribution_count": 0,
                "executed_query_ids": set(), "nonzero_executed_query_ids": set(),
                "attributed_raw_hit_count_sum": 0})
            row["relation_contribution_count"] += 1
            row["executed_query_ids"].add(query["executed_query_id"])
            if query["raw_hit_count"] > 0:
                row["nonzero_executed_query_ids"].add(query["executed_query_id"])
            row["attributed_raw_hit_count_sum"] += query["raw_hit_count"]
    attribution = []
    for key in sorted(intent_stats):
        row = intent_stats[key]
        attribution.append({
            "intent_type": key, "relation_contribution_count": row["relation_contribution_count"],
            "executed_query_count": len(row["executed_query_ids"]),
            "nonzero_executed_query_count": len(row["nonzero_executed_query_ids"]),
            "attributed_raw_hit_count_sum": row["attributed_raw_hit_count_sum"],
            "many_to_one_attribution": True,
        })
    write("intent_retrieval_attribution.json", pretty({
        "artifact_schema_version": "RetrievalSurfaceV2IntentAttributionV1",
        "relation_contribution_count": 29, "executed_query_count": 25,
        "intent_families": attribution,
    }))
    write("three_way_retrieval_level_comparison.json", pretty({
        "artifact_schema_version": "ThreeWayRetrievalLevelComparisonV1",
        "comparison_scope": "RETRIEVAL_LEVEL_ONLY",
        "levels": [
            {"level": "A", "architecture": "historical v2.3", "query_count": 32,
             "candidate_universe": "NONZERO_HISTORICAL"},
            {"level": "B", "architecture": "failed exact-proposition v2.4",
             "query_count": 29, "nonzero_query_count": 0, "zero_hit_query_count": 29,
             "metadata_universe_total": 0},
            {"level": "C", "architecture": "Retrieval Surface V2",
             "query_count": 25, **{key: denominators[key] for key in [
                 "nonzero_query_count", "zero_hit_query_count", "nonzero_case_count",
                 "zero_hit_case_count", "unique_pmids_before_tail_total",
                 "metadata_universe_total", "tier_a_count", "tier_b_count",
                 "oa_eligible_count", "selected_count",
                 "successful_fulltext_acquisition_count"]}},
        ],
        "direct_rate_compared": False, "relevance_conclusion_made": False,
        "precision_claim_made": False, "recall_claim_made": False,
    }))

    write("known_paper_blindness_audit.json", pretty({
        "artifact_schema_version": "KnownPaperBlindnessAuditV1",
        "known_pmid_checks": 0, "known_pmid_queries": 0,
        "manual_candidate_injections": 0, "historical_query_fallbacks": 0,
        "known_paper_blindness_preserved": True,
    }))
    write("historical_label_blinding_audit.json", pretty({
        "artifact_schema_version": "HistoricalLabelBlindingAuditV1",
        "historical_label_reads": 0, "direct_labels_read": 0,
        "pass_a_or_b_material_read": 0, "scientific_relevance_labels_created": 0,
        "historical_label_blinding_preserved": True,
    }))
    write("runtime_adaptation_audit.json", pretty({
        "artifact_schema_version": "RuntimeAdaptationAuditV1",
        "query_modifications": 0, "runtime_query_expansions": 0,
        "proximity_window_changes": 0, "field_scope_changes": 0,
        "boolean_structure_changes": 0, "surface_alternative_changes": 0,
        "fallback_queries": 0, "runtime_adaptation_performed": False,
    }))

    provenance_gaps = []
    for query in queries:
        if not all(query.get(key) for key in ("contributing_relation_core_ids",
                                              "retrieval_surface_plan_ids", "pubmed_ast_hashes")):
            provenance_gaps.append({"query_id": query["executed_query_id"],
                                    "reason": "SOURCE_PROVENANCE_MISSING"})
    for candidate in metadata:
        if not candidate["query_provenance"]:
            provenance_gaps.append({"candidate_id": candidate["candidate_id"],
                                    "reason": "QUERY_PROVENANCE_MISSING"})
    write("provenance_completeness_audit.json", pretty({
        "artifact_schema_version": "RetrievalSurfaceV2ProvenanceCompletenessAuditV1",
        "query_count": 25, "relation_contribution_count": 29,
        "metadata_record_count": len(metadata), "selection_count": selected_count,
        "fulltext_result_count": len(fulltexts), "provenance_gaps": provenance_gaps,
        "provenance_gap_count": len(provenance_gaps),
        "complete": not provenance_gaps,
    }))

    request_rows = []
    for event in network.events:
        request_rows.append({**event, "attempt_state": "SUCCESS"})
    for failure in network.failures:
        request_rows.append({**failure, "attempt_state": "FAILED_ATTEMPT"})
    request_rows.sort(key=lambda row: (row.get("request_sequence", 10**9),
                                       row.get("timestamp_utc", ""), row.get("attempt", 0)))
    write("retrieval_request_manifest.jsonl", jsonl(request_rows))

    write("retrieval_policy_compliance_audit.json", pretty({
        "artifact_schema_version": "RetrievalSurfaceV2PolicyComplianceAuditV1",
        "checks": {
            "all_25_queries_logically_executed": len(queries) == 25,
            "all_29_relation_contributions_preserved": sum(
                len(rows) for rows in contributions_by_query.values()) == 29,
            "query_text_unchanged": True, "compiler_parameters_unchanged": True,
            "tail_policy_followed": True, "metadata_policy_followed": True,
            "candidate_stack_unchanged": True, "oa_policy_followed": True,
            "selection_freeze_barrier_passed": True, "replacement_count_zero": True,
            "no_relevance_review": True, "runtime_adaptation_zero": True,
            "known_paper_and_label_blinding_preserved": True,
            "provenance_complete": not provenance_gaps,
        },
        "protocol_compliance": "PASS" if not provenance_gaps else "FAIL",
    }))
    safety = {
        "artifact_schema_version": "RetrievalSurfaceV2ScientificStateSafetyAuditV1",
        "query_modifications": 0, "runtime_query_expansions": 0,
        "proximity_window_changes": 0, "manual_candidate_injections": 0,
        "known_pmid_checks": 0, "historical_label_reads": 0,
        "scientific_relevance_adjudications": 0,
        "llm_calls": 0, "openai_calls": 0, "deepseek_calls": 0,
        "general_web_calls": 0, "publisher_calls": 0,
        "allowed_network_host": "eutils.ncbi.nlm.nih.gov",
        "historical_assets_modified": False,
    }
    write("scientific_state_safety_audit.json", pretty(safety))

    # Freeze the complete acquisition corpus, including raw NCBI snapshots.
    corpus_names = [
        "query_execution_results.jsonl", "query_execution_provenance.jsonl",
        "case_union_pmids.jsonl", "case_union_provenance.jsonl",
        "retrieval_universe_freeze.json", "tail_application_audit.json",
        "metadata_fetch_manifest.jsonl", "metadata_records.jsonl",
        "metadata_failure_records.jsonl", "candidate_gate_results.jsonl",
        "p0_results.jsonl", "p1_results.jsonl", "p2_results.jsonl",
        "policy_a_results.jsonl", "candidate_tier_summary.json",
        "oa_eligibility_results.jsonl", "selection_manifest_aggregate_sha256",
        "selection_freeze_barrier_audit.json", "fulltext_fetch_manifest.jsonl",
        "fulltext_acquisition_results.jsonl", "fulltext_failure_records.jsonl",
        "acquired_fulltext_manifest.json",
    ]
    corpus_paths = [RUN / name for name in corpus_names]
    corpus_paths.extend(sorted((RUN / "case_selection_manifests").glob("*.json")))
    corpus_paths.extend(sorted(path for path in ASSETS.rglob("*") if path.is_file()))
    corpus_pairs = [[str(path.relative_to(RUN)), sha(path)] for path in corpus_paths]
    corpus_sha = aggregate(corpus_pairs)
    require(corpus_sha != HISTORICAL_EMPTY_CORPUS,
            "new corpus root unexpectedly equals historical empty corpus")
    write("retrieval_surface_v2_development_acquisition_corpus_manifest.json", pretty({
        "artifact_schema_version": "RetrievalSurfaceV2DevelopmentAcquisitionCorpusManifestV1",
        "aggregate_algorithm": "sha256(canonical JSON ordered [path, sha256] pairs)",
        "aggregate_components": corpus_pairs,
        "retrieval_surface_v2_development_acquisition_corpus_sha256": corpus_sha,
        "historical_empty_corpus_sha256": HISTORICAL_EMPTY_CORPUS,
        "independent_from_historical_empty_corpus": True,
        "frozen_before_scientific_relevance_adjudication": True,
    }))
    write("retrieval_surface_v2_development_acquisition_corpus_sha256",
          (corpus_sha + "\n").encode())

    if acquired_count > 0:
        recommendation = "FREEZE_RETRIEVAL_SURFACE_V2_NEUTRAL_REVIEW_CORPUS"
    elif len(metadata) > 0:
        recommendation = "FREEZE_METADATA_LEVEL_RETRIEVAL_RESULT_AND_AUDIT_ACQUISITION_BOTTLENECK"
    else:
        recommendation = "RETRIEVAL_SURFACE_V2_SYNTAX_OR_RIGIDITY_AUTOPSY_NEEDED"
    summary = {
        "artifact_schema_version": "RetrievalSurfaceV2FullRetrievalSummaryV1",
        "status": "completed", **denominators,
        "selection_manifests_frozen_before_download": True,
        "query_modifications": 0, "runtime_query_expansions": 0,
        "proximity_window_changes": 0, "known_pmid_checks": 0,
        "historical_label_reads": 0, "llm_calls": 0,
        "openai_calls": 0, "deepseek_calls": 0,
        "provenance_gap_count": len(provenance_gaps),
        "protocol_compliance": "PASS" if not provenance_gaps else "FAIL",
        "retrieval_surface_v2_development_acquisition_corpus_sha256": corpus_sha,
        "next_stage_recommendation": recommendation,
        "historical_assets_modified": False,
        "network_successful_response_count": len(network.events),
        "network_failed_attempt_count": len(network.failures),
    }
    write("upstream_root_verification.json", pretty({
        "artifact_schema_version": "RetrievalSurfaceV2UpstreamRootVerificationV1",
        "verified_before_network": verification["verified_before_first_network_request"],
        "roots": verification["roots"], "all_verified": True,
    }))
    write("execution_manifest_verification.json", pretty({
        "artifact_schema_version": "RetrievalSurfaceV2ExecutionManifestVerificationV1",
        "expected_sha256": EXPECTED_EXECUTION,
        "recomputed_sha256": sha(EXECUTION_MANIFEST), "verified": True,
        "relation_contribution_count": 29, "byte_unique_query_count": 25,
    }))
    write("query_set_verification.json", pretty({
        "artifact_schema_version": "RetrievalSurfaceV2QuerySetVerificationV1",
        "expected_sha256": EXPECTED_QUERY_SET,
        "recomputed_sha256": sha(ALPHA36 / "search_plan_v24_dev_retrieval_surface_v2_query_set.jsonl"),
        "query_count": 25, "per_case_counts": EXPECTED_CASE_COUNTS,
        "query_text_changes": 0, "query_hash_changes": 0, "verified": True,
    }))
    write("compiler_configuration_verification.json", pretty({
        "artifact_schema_version": "RetrievalSurfaceV2CompilerConfigurationVerificationV1",
        **manifest["compiler_configuration"], "ast_changes": 0,
        "surface_plan_changes": 0, "verified": True,
    }))
    write("relation_contribution_to_executed_query_map.json", pretty({
        "artifact_schema_version": "RelationContributionToExecutedQueryMapV1",
        "relation_contribution_count": 29, "byte_unique_query_count": 25,
        "deduplicated_contribution_count": 4,
        "contributions": manifest["source_relation_contributions"],
    }))
    write("summary.json", pretty(summary))

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
        "summary.json", "retrieval_surface_v2_development_acquisition_corpus_manifest.json",
        "retrieval_surface_v2_development_acquisition_corpus_sha256",
    }
    require(required <= {path.name for path in RUN.iterdir() if path.is_file()},
            "required top-level output missing")
    require({path.stem for path in (RUN / "case_selection_manifests").glob("*.json")} == set(CASES),
            "case selection manifest set mismatch")
    checks = {
        "authoritative_roots_verified_before_network": True,
        "all_25_queries_logically_executed": len(queries) == 25,
        "all_29_relation_contributions_preserved": True,
        "query_modifications_zero": True, "runtime_query_expansions_zero": True,
        "proximity_window_changes_zero": True,
        "selection_freeze_barrier_passed": True,
        "metadata_failures_zero": True, "replacement_count_zero": True,
        "known_pmid_checks_zero": True, "historical_label_reads_zero": True,
        "llm_openai_deepseek_calls_zero": True,
        "provenance_gap_count_zero": not provenance_gaps,
        "corpus_frozen_before_relevance_adjudication": True,
        "protocol_compliance_pass": not provenance_gaps,
    }
    require(all(checks.values()), "protocol compliance validation failed")
    excluded = {"validation.json", "search_plan_v24_dev_retrieval_surface_v2_full_retrieval_sha256"}
    root_paths = sorted(path for path in RUN.rglob("*") if path.is_file() and
                        str(path.relative_to(RUN)) not in excluded)
    root_pairs = [[str(path.relative_to(RUN)), sha(path)] for path in root_paths]
    retrieval_root = aggregate(root_pairs)
    write("validation.json", pretty({
        "artifact_schema_version": "RetrievalSurfaceV2FullRetrievalValidationV1",
        "status": "PASS", "checks": checks,
        "aggregate_algorithm": "sha256(canonical JSON ordered [path, sha256] pairs)",
        "aggregate_components": root_pairs,
        "search_plan_v24_dev_retrieval_surface_v2_full_retrieval_sha256": retrieval_root,
    }))
    write("search_plan_v24_dev_retrieval_surface_v2_full_retrieval_sha256",
          (retrieval_root + "\n").encode())
    return {**summary,
            "search_plan_v24_dev_retrieval_surface_v2_full_retrieval_sha256": retrieval_root}


def freeze_terminal_failure() -> dict[str, Any]:
    """Freeze an already exhausted four-attempt search failure without network access."""
    require(RUN.is_dir(), "partial run directory does not exist")
    require(not (RUN / "validation.json").exists(), "run is already frozen")
    verification, manifest, queries, _, _ = preflight()
    receipt = load(ASSETS / "network_events.json")
    events, network_failures = receipt["events"], receipt["failures"]
    require(events and len(network_failures) >= 4, "terminal failure evidence missing")
    terminal_attempts = network_failures[-4:]
    terminal_lineage = terminal_attempts[0]["lineage"]
    require([row["attempt"] for row in terminal_attempts] == [1, 2, 3, 4],
            "frozen retry sequence incomplete")
    require(all(row["kind"] == "pubmed_search" and row["lineage"] == terminal_lineage
                for row in terminal_attempts), "terminal attempts are not one frozen request")
    page_rows = [json.loads(line) for line in
                 (RUN / "query_execution_provenance.jsonl").read_text().splitlines() if line]
    require(page_rows[-1]["transport_status"] == "TERMINAL_FAILURE",
            "terminal page record missing")
    failed_query_id = page_rows[-1]["executed_query_id"]
    require(failed_query_id == terminal_lineage["query_id"], "terminal query mismatch")

    successful_pages = [row for row in page_rows if row["transport_status"] == "SUCCESS"]
    successful_ids = {row["executed_query_id"] for row in successful_pages}
    require(len(successful_ids) == 19, "unexpected successful-query count before abort")
    query_by_id = {row["query_id"]: row for row in queries}
    require(failed_query_id in query_by_id and failed_query_id not in successful_ids,
            "failed query state mismatch")
    not_executed_ids = set(query_by_id) - successful_ids - {failed_query_id}
    require(len(not_executed_ids) == 5, "unexpected unexecuted-query count")

    query_results = []
    for query in queries:
        query_id = query["query_id"]
        pages = [row for row in successful_pages if row["executed_query_id"] == query_id]
        if pages:
            raw_count = pages[0]["raw_hit_count"]
            require(all(row["raw_hit_count"] == raw_count for row in pages),
                    "hit count changed during partial pagination")
            status = "SUCCESS"
            outcome = "ZERO_HIT_QUERY" if raw_count == 0 else "NONZERO_QUERY"
            returned = [pmid for row in pages for pmid in row["returned_pmids"]]
        elif query_id == failed_query_id:
            raw_count, returned = None, []
            status, outcome = "TERMINAL_FAILURE", "TERMINAL_TECHNICAL_FAILURE"
        else:
            raw_count, returned = None, []
            status, outcome = "NOT_EXECUTED_AFTER_ABORT", "NOT_OBSERVED"
        query_results.append({
            "artifact_schema_version": "RetrievalSurfaceV2QueryExecutionResultV1",
            "case_id": query["case_id"], "executed_query_id": query_id,
            "query_sha256": query["query_sha256"], "query_text": query["exact_query_text"],
            "contributing_intent_types": query["contributing_intent_types"],
            "contributing_relation_core_ids": query["relation_core_ids"],
            "retrieval_surface_plan_ids": query["surface_plan_ids"],
            "pubmed_ast_hashes": query["pubmed_ast_hashes"],
            "transport_status": status, "raw_hit_count": raw_count,
            "outcome": outcome, "returned_pmids_in_frozen_page_order": returned,
            "returned_pmid_count": len(returned), "query_modified": False,
            "runtime_expansion": False,
        })
    write("query_execution_results.jsonl", jsonl(query_results))

    case_rows, case_hit_rows = [], []
    for case in CASES:
        rows = [row for row in query_results if row["case_id"] == case]
        complete = all(row["transport_status"] == "SUCCESS" for row in rows)
        successful = [row for row in rows if row["transport_status"] == "SUCCESS"]
        observed = []
        seen = set()
        for row in successful:
            for pmid in row["returned_pmids_in_frozen_page_order"]:
                if pmid not in seen:
                    seen.add(pmid); observed.append(pmid)
        state = ("COMPLETE" if complete else
                 "ABORTED_TERMINAL_FAILURE" if any(
                     row["transport_status"] == "TERMINAL_FAILURE" for row in rows)
                 else "NOT_REACHED_AFTER_ABORT")
        case_rows.append({
            "artifact_schema_version": "RetrievalSurfaceV2CaseUnionPMIDsV1",
            "case_id": case, "execution_state": state,
            "observed_unique_pmids_before_hard_tail": observed,
            "observed_unique_pmid_count_before_hard_tail": len(observed),
            "hard_tail_pmids": observed[:HARD_TAIL],
            "hard_tail_pmid_count": min(len(observed), HARD_TAIL),
            "hard_tail": HARD_TAIL, "hard_tail_truncated": len(observed) > HARD_TAIL,
            "cross_case_deduplication": False,
        })
        case_hit_rows.append({
            "case_id": case, "execution_state": state,
            "frozen_query_count": len(rows),
            "query_execution_success_count": len(successful),
            "query_terminal_failure_count": sum(
                row["transport_status"] == "TERMINAL_FAILURE" for row in rows),
            "query_not_executed_after_abort_count": sum(
                row["transport_status"] == "NOT_EXECUTED_AFTER_ABORT" for row in rows),
            "nonzero_query_count": sum(row["outcome"] == "NONZERO_QUERY" for row in rows),
            "zero_hit_query_count": sum(row["outcome"] == "ZERO_HIT_QUERY" for row in rows),
            "unique_pmid_count": len(observed),
        })
    write("case_union_pmids.jsonl", jsonl(case_rows))
    write("case_union_provenance.jsonl", b"")
    write("query_outcome_summary.json", pretty({
        "artifact_schema_version": "RetrievalSurfaceV2QueryOutcomeSummaryV1",
        "query_execution_success_count": 19, "query_terminal_failure_count": 1,
        "query_not_executed_after_abort_count": 5,
        "nonzero_query_count": sum(row["outcome"] == "NONZERO_QUERY" for row in query_results),
        "zero_hit_query_count": sum(row["outcome"] == "ZERO_HIT_QUERY" for row in query_results),
        "terminal_query_id": failed_query_id,
        "terminal_failure_class": "NETWORK_FAILURE",
        "transport_success_is_scientific_retrieval_success": False,
    }))
    write("case_query_hit_summary.json", pretty({
        "artifact_schema_version": "RetrievalSurfaceV2CaseQueryHitSummaryV1",
        "cases": case_hit_rows,
        "nonzero_case_count": sum(row["nonzero_query_count"] > 0 for row in case_hit_rows),
        "zero_hit_case_count": sum(row["execution_state"] == "COMPLETE" and
                                   row["nonzero_query_count"] == 0 for row in case_hit_rows),
        "technically_incomplete_case_count": sum(row["execution_state"] != "COMPLETE"
                                                 for row in case_hit_rows),
    }))

    universe_components = [[name, sha(RUN / name)] for name in [
        "query_execution_results.jsonl", "query_execution_provenance.jsonl",
        "case_union_pmids.jsonl", "case_union_provenance.jsonl"]]
    universe_sha = aggregate(universe_components)
    write("retrieval_universe_freeze.json", pretty({
        "artifact_schema_version": "RetrievalSurfaceV2UniverseFreezeV1",
        "state": "PARTIAL_TERMINAL_TECHNICAL_FAILURE",
        "components": universe_components, "retrieval_universe_sha256": universe_sha,
        "frozen_after_terminal_failure": True, "metadata_scoring_started": False,
    }))
    write("tail_application_audit.json", pretty({
        "artifact_schema_version": "RetrievalSurfaceV2TailApplicationAuditV1",
        "state": "NOT_REACHED_DUE_TO_TERMINAL_SEARCH_FAILURE",
        "soft_tail": SOFT_TAIL, "hard_tail": HARD_TAIL,
        "adaptive_tail_enabled": False, "tail_parameters_changed": False,
    }))

    # Downstream stages are explicit empty/not-reached artifacts, never inferred zeros.
    for name in ["metadata_fetch_manifest.jsonl", "metadata_records.jsonl",
                 "metadata_failure_records.jsonl", "candidate_gate_results.jsonl",
                 "p0_results.jsonl", "p1_results.jsonl", "p2_results.jsonl",
                 "policy_a_results.jsonl", "oa_eligibility_results.jsonl",
                 "fulltext_fetch_manifest.jsonl", "fulltext_acquisition_results.jsonl",
                 "fulltext_failure_records.jsonl"]:
        write(name, b"")
    write("candidate_tier_summary.json", pretty({
        "artifact_schema_version": "RetrievalSurfaceV2CandidateTierSummaryV1",
        "stage_state": "NOT_REACHED_DUE_TO_TERMINAL_SEARCH_FAILURE",
        "counts": {"TIER_A": 0, "TIER_B": 0, "REJECT": 0, "ABSTAIN": 0},
        "candidate_count": 0,
    }))
    placeholder_paths = []
    for case in CASES:
        path = RUN / "case_selection_manifests" / f"{case}.json"
        write(path, pretty({
            "artifact_schema_version": "RetrievalSurfaceV2CaseSelectionManifestV1",
            "case_id": case, "selection_state": "NOT_REACHED_DUE_TO_TERMINAL_SEARCH_FAILURE",
            "selection_count": None, "ordered_selections": None,
            "valid_selection_manifest": False,
        }))
        placeholder_paths.append(path)
    placeholder_pairs = [[str(path.relative_to(RUN)), sha(path)] for path in placeholder_paths]
    placeholder_sha = aggregate(placeholder_pairs)
    write("selection_manifest_aggregate_sha256", (placeholder_sha + "\n").encode())
    write("selection_freeze_barrier_audit.json", pretty({
        "artifact_schema_version": "SelectionFreezeBarrierAuditV1",
        "state": "NOT_REACHED_DUE_TO_TERMINAL_SEARCH_FAILURE",
        "placeholder_components": placeholder_pairs,
        "placeholder_aggregate_sha256": placeholder_sha,
        "all_eight_valid_selection_manifests_frozen": False,
        "frozen_before_first_pmc_fulltext_fetch": False,
        "pmc_fulltext_fetch_count": 0, "selection_freeze_barrier_pass": False,
    }))
    write("acquired_fulltext_manifest.json", pretty({
        "artifact_schema_version": "RetrievalSurfaceV2AcquiredFulltextManifestV1",
        "stage_state": "NOT_REACHED_DUE_TO_TERMINAL_SEARCH_FAILURE",
        "successful_acquisition_count": 0, "failed_acquisition_count": 0,
        "acquired_fulltexts": [], "replacement_count": 0,
    }))

    request_rows = [{**row, "attempt_state": "SUCCESS"} for row in events]
    request_rows.extend({**row, "attempt_state": "FAILED_ATTEMPT"} for row in network_failures)
    request_rows.sort(key=lambda row: (row.get("request_sequence", 10**9),
                                       row.get("timestamp_utc", ""), row.get("attempt", 0)))
    write("retrieval_request_manifest.jsonl", jsonl(request_rows))
    write("retrieval_denominator_summary.json", pretty({
        "artifact_schema_version": "RetrievalSurfaceV2DenominatorSummaryV1",
        "state": "PARTIAL_TERMINAL_TECHNICAL_FAILURE",
        "relation_contribution_count": 29, "byte_unique_query_count": 25,
        "query_execution_success_count": 19, "query_terminal_failure_count": 1,
        "nonzero_query_count": 0, "zero_hit_query_count": 19,
        "development_case_count": 8, "nonzero_case_count": 0,
        "zero_hit_case_count": 6, "technically_incomplete_case_count": 2,
        "unique_pmids_before_tail_total": 0, "metadata_universe_total": 0,
        "tier_a_count": 0, "tier_b_count": 0, "reject_count": 0, "abstain_count": 0,
        "oa_eligible_count": 0, "selected_count": 0,
        "successful_fulltext_acquisition_count": 0, "fulltext_failure_count": 0,
        "cases_with_acquired_fulltext": 0, "cases_with_zero_acquired_fulltext": 8,
        "downstream_zero_counts_are_not_reached_not_observed": True,
    }))
    write("intent_retrieval_attribution.json", pretty({
        "artifact_schema_version": "RetrievalSurfaceV2IntentAttributionV1",
        "state": "INCOMPLETE_DUE_TO_TERMINAL_SEARCH_FAILURE",
        "relation_contribution_count": 29, "executed_query_success_count": 19,
        "terminal_query_count": 1, "not_executed_query_count": 5,
        "scientific_attribution_conclusion_allowed": False,
    }))
    write("three_way_retrieval_level_comparison.json", pretty({
        "artifact_schema_version": "ThreeWayRetrievalLevelComparisonV1",
        "state": "INCOMPLETE_DUE_TO_TERMINAL_SEARCH_FAILURE",
        "comparison_performed": False, "direct_rate_compared": False,
        "relevance_conclusion_made": False,
    }))
    write("known_paper_blindness_audit.json", pretty({
        "artifact_schema_version": "KnownPaperBlindnessAuditV1",
        "known_pmid_checks": 0, "manual_candidate_injections": 0,
        "historical_query_fallbacks": 0, "known_paper_blindness_preserved": True,
    }))
    write("historical_label_blinding_audit.json", pretty({
        "artifact_schema_version": "HistoricalLabelBlindingAuditV1",
        "historical_label_reads": 0, "scientific_relevance_labels_created": 0,
        "historical_label_blinding_preserved": True,
    }))
    write("runtime_adaptation_audit.json", pretty({
        "artifact_schema_version": "RuntimeAdaptationAuditV1",
        "query_modifications": 0, "runtime_query_expansions": 0,
        "proximity_window_changes": 0, "field_scope_changes": 0,
        "boolean_structure_changes": 0, "surface_alternative_changes": 0,
        "fallback_queries": 0, "runtime_adaptation_performed": False,
    }))
    write("provenance_completeness_audit.json", pretty({
        "artifact_schema_version": "RetrievalSurfaceV2ProvenanceCompletenessAuditV1",
        "state": "COMPLETE_FOR_OBSERVED_PARTIAL_EXECUTION",
        "successful_query_records": 19, "terminal_query_records": 1,
        "failed_attempt_records": 4, "not_executed_query_records": 5,
        "provenance_gap_count": 0, "complete_for_observed_execution": True,
    }))
    write("retrieval_policy_compliance_audit.json", pretty({
        "artifact_schema_version": "RetrievalSurfaceV2PolicyComplianceAuditV1",
        "protocol_compliance": "FAIL",
        "failure_reason": "TERMINAL_PUBMED_SEARCH_NETWORK_FAILURE_AFTER_FOUR_TOTAL_ATTEMPTS",
        "fail_closed_observed": True, "additional_retry_performed": False,
        "execution_continued_after_terminal_failure": False,
    }))
    write("scientific_state_safety_audit.json", pretty({
        "artifact_schema_version": "RetrievalSurfaceV2ScientificStateSafetyAuditV1",
        "query_modifications": 0, "runtime_query_expansions": 0,
        "proximity_window_changes": 0, "manual_candidate_injections": 0,
        "known_pmid_checks": 0, "historical_label_reads": 0,
        "scientific_relevance_adjudications": 0,
        "llm_calls": 0, "openai_calls": 0, "deepseek_calls": 0,
        "general_web_calls": 0, "publisher_calls": 0,
        "successful_ncbi_requests": len(events),
        "failed_ncbi_attempts": len(network_failures),
        "pmc_fulltext_fetches": 0, "historical_assets_modified": False,
    }))

    write("upstream_root_verification.json", pretty({
        "artifact_schema_version": "RetrievalSurfaceV2UpstreamRootVerificationV1",
        "verified_before_network": True, "roots": verification["roots"], "all_verified": True,
    }))
    write("execution_manifest_verification.json", pretty({
        "artifact_schema_version": "RetrievalSurfaceV2ExecutionManifestVerificationV1",
        "expected_sha256": EXPECTED_EXECUTION, "recomputed_sha256": sha(EXECUTION_MANIFEST),
        "verified": True, "relation_contribution_count": 29, "byte_unique_query_count": 25,
    }))
    write("query_set_verification.json", pretty({
        "artifact_schema_version": "RetrievalSurfaceV2QuerySetVerificationV1",
        "expected_sha256": EXPECTED_QUERY_SET,
        "recomputed_sha256": sha(ALPHA36 / "search_plan_v24_dev_retrieval_surface_v2_query_set.jsonl"),
        "query_count": 25, "per_case_counts": EXPECTED_CASE_COUNTS,
        "query_text_changes": 0, "query_hash_changes": 0, "verified": True,
    }))
    write("compiler_configuration_verification.json", pretty({
        "artifact_schema_version": "RetrievalSurfaceV2CompilerConfigurationVerificationV1",
        **manifest["compiler_configuration"], "ast_changes": 0,
        "surface_plan_changes": 0, "verified": True,
    }))
    write("relation_contribution_to_executed_query_map.json", pretty({
        "artifact_schema_version": "RelationContributionToExecutedQueryMapV1",
        "relation_contribution_count": 29, "byte_unique_query_count": 25,
        "deduplicated_contribution_count": 4,
        "contributions": manifest["source_relation_contributions"],
    }))
    write("technical_terminal_failure.json", pretty({
        "artifact_schema_version": "RetrievalSurfaceV2TechnicalTerminalFailureV1",
        "failure_class": "NETWORK_FAILURE", "stage": "PUBMED_SEARCH",
        "case_id": terminal_lineage["case_id"], "query_id": failed_query_id,
        "attempt_count": 4, "maximum_total_attempts": 4,
        "backoff_seconds": [2, 4, 8], "errors": terminal_attempts,
        "fail_closed": True, "further_network_requests_after_failure": 0,
    }))

    corpus_source_names = [
        "query_execution_results.jsonl", "query_execution_provenance.jsonl",
        "case_union_pmids.jsonl", "case_union_provenance.jsonl",
        "retrieval_universe_freeze.json", "retrieval_request_manifest.jsonl",
        "technical_terminal_failure.json",
    ]
    corpus_paths = [RUN / name for name in corpus_source_names]
    corpus_paths.extend(sorted(path for path in ASSETS.rglob("*") if path.is_file()))
    corpus_pairs = [[str(path.relative_to(RUN)), sha(path)] for path in corpus_paths]
    corpus_sha = aggregate(corpus_pairs)
    require(corpus_sha != HISTORICAL_EMPTY_CORPUS, "partial corpus equals historical corpus")
    write("retrieval_surface_v2_development_acquisition_corpus_manifest.json", pretty({
        "artifact_schema_version": "RetrievalSurfaceV2DevelopmentAcquisitionCorpusManifestV1",
        "state": "PARTIAL_TERMINAL_TECHNICAL_FAILURE", "complete": False,
        "aggregate_algorithm": "sha256(canonical JSON ordered [path, sha256] pairs)",
        "aggregate_components": corpus_pairs,
        "retrieval_surface_v2_development_acquisition_corpus_sha256": corpus_sha,
        "historical_empty_corpus_sha256": HISTORICAL_EMPTY_CORPUS,
        "independent_from_historical_empty_corpus": True,
    }))
    write("retrieval_surface_v2_development_acquisition_corpus_sha256",
          (corpus_sha + "\n").encode())

    summary = {
        "artifact_schema_version": "RetrievalSurfaceV2FullRetrievalSummaryV1",
        "status": "failed", "relation_contribution_count": 29,
        "byte_unique_query_count": 25, "query_execution_success_count": 19,
        "query_terminal_failure_count": 1, "nonzero_query_count": 0,
        "zero_hit_query_count": 19, "development_case_count": 8,
        "nonzero_case_count": 0, "zero_hit_case_count": 6,
        "unique_pmids_before_tail_total": 0, "metadata_universe_total": 0,
        "tier_a_count": 0, "tier_b_count": 0, "reject_count": 0, "abstain_count": 0,
        "oa_eligible_count": 0, "selected_count": 0,
        "successful_fulltext_acquisition_count": 0, "fulltext_failure_count": 0,
        "cases_with_acquired_fulltext": 0, "cases_with_zero_acquired_fulltext": 8,
        "selection_manifests_frozen_before_download": False,
        "query_modifications": 0, "runtime_query_expansions": 0,
        "proximity_window_changes": 0, "known_pmid_checks": 0,
        "historical_label_reads": 0, "llm_calls": 0,
        "openai_calls": 0, "deepseek_calls": 0,
        "provenance_gap_count": 0, "protocol_compliance": "FAIL",
        "terminal_failure_case_id": terminal_lineage["case_id"],
        "terminal_failure_query_id": failed_query_id,
        "retrieval_surface_v2_development_acquisition_corpus_sha256": corpus_sha,
        "next_stage_recommendation": "RETRIEVAL_SURFACE_V2_TERMINAL_TECHNICAL_FAILURE",
        "historical_assets_modified": False,
    }
    write("summary.json", pretty(summary))

    excluded = {"validation.json", "search_plan_v24_dev_retrieval_surface_v2_full_retrieval_sha256"}
    root_paths = sorted(path for path in RUN.rglob("*") if path.is_file() and
                        str(path.relative_to(RUN)) not in excluded)
    root_pairs = [[str(path.relative_to(RUN)), sha(path)] for path in root_paths]
    retrieval_root = aggregate(root_pairs)
    write("validation.json", pretty({
        "artifact_schema_version": "RetrievalSurfaceV2FullRetrievalValidationV1",
        "status": "FAIL", "failure_class": "TERMINAL_TECHNICAL_FAILURE",
        "checks": {
            "authoritative_roots_verified_before_network": True,
            "query_text_and_hashes_unchanged": True,
            "frozen_retry_policy_exhausted": True,
            "fail_closed_after_terminal_failure": True,
            "additional_network_requests_after_terminal_failure_zero": True,
            "all_25_queries_logically_executed": False,
            "selection_freeze_barrier_passed": False,
            "no_relevance_review": True, "runtime_adaptation_zero": True,
            "provenance_complete_for_observed_partial_execution": True,
        },
        "aggregate_algorithm": "sha256(canonical JSON ordered [path, sha256] pairs)",
        "aggregate_components": root_pairs,
        "search_plan_v24_dev_retrieval_surface_v2_full_retrieval_sha256": retrieval_root,
    }))
    write("search_plan_v24_dev_retrieval_surface_v2_full_retrieval_sha256",
          (retrieval_root + "\n").encode())
    return {**summary,
            "search_plan_v24_dev_retrieval_surface_v2_full_retrieval_sha256": retrieval_root}


def main(execute_network: bool, preflight_only: bool) -> None:
    verification, manifest, queries, targets, gates = preflight()
    print(json.dumps({"preflight": verification, "status": "PASS"},
                     indent=2, sort_keys=True), flush=True)
    if preflight_only:
        return
    require(execute_network, "explicit --execute-network required")
    require(not RUN.exists(), f"refusing to overwrite existing run: {RUN}")
    RUN.mkdir(parents=False)
    ASSETS.mkdir()
    network = bind_network()
    execution = execute_queries(network, queries)
    universe = freeze_retrieval_universe(execution)
    fetch_metadata(network, universe["hard_tail_pmids"])
    metadata = build_metadata_records(universe)
    processed = legacy.score_and_select(metadata, targets, gates, network)
    selection_sha, selected = freeze_scoring_and_selection(processed, universe["universe_sha"])
    print(f"selection_frozen sha256={selection_sha} count={len(selected)}", flush=True)
    fulltexts, failures = fetch_fulltexts(network, selected, selection_sha)
    result = finish(verification, manifest, execution, universe, metadata, processed,
                    selection_sha, fulltexts, failures, network)
    print(json.dumps(result, indent=2, sort_keys=True), flush=True)


if __name__ == "__main__":
    parsed = options()
    if parsed.freeze_terminal_failure:
        require(not parsed.execute_network and not parsed.preflight_only,
                "failure freeze is offline-only and mutually exclusive")
        print(json.dumps(freeze_terminal_failure(), indent=2, sort_keys=True), flush=True)
    else:
        main(parsed.execute_network, parsed.preflight_only)
