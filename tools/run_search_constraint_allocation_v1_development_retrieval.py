#!/usr/bin/env python3
"""Execute frozen alpha3.10 NCBI-only development retrieval/acquisition.

No planner, model, known-paper lookup, relevance review, or query adaptation.
"""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import tools.run_search_plan_v24_dev_alpha3_4_development_retrospective_retrieval as legacy
import tools.run_search_plan_v24_dev_retrieval_surface_v2_full_retrieval as surface

PREREG = ROOT / "runs/20260925_search_plan_v24_dev_alpha3_10_search_constraint_allocation_retrieval_preregistration_offline"
ALPHA39 = ROOT / "runs/20260925_search_plan_v24_dev_alpha3_9_search_constraint_allocation_offline"
ALPHA34 = ROOT / "runs/20260923_search_plan_v24_dev_alpha3_4_retrieval_preregistration_offline"
RUN = ROOT / "runs/20260925_search_constraint_allocation_v1_development_retrieval"
ASSETS = RUN / "retrieval_assets"
MANIFEST_PATH = PREREG / "search_constraint_allocation_v1_development_execution_manifest.json"
QUERY_PATH = ALPHA39 / "search_plan_v24_dev_search_constraint_allocation_v1_query_set.jsonl"
EXPECTED_PREREG = "e6d05cfdb933e644d6da7fe0bb675e87deadf85108cc69149319887460c6eb10"
EXPECTED_MANIFEST = "f2935db4963b20438c057aea3c4c654e19a7668e6a581207ae8d02c231aa7930"
EXPECTED_ALPHA39 = "823a035ca906b67729fd8cb62b2f555a65ca787facb47d8ac3a0cc07ab76d5cb"
EXPECTED_QUERIES = "717181a438d56735a5cfc030f648efb1e485509c1d0266d602e17e40ebf39560"
EXPECTED_ALPHA34 = "2488b4322894acb755872e9bc92d78dcaf2a4dec6ed807a22d3aff4622e2d5d5"
CASES = tuple(f"heldout_v2_{n}" for n in range(101, 109))
CASE_COUNTS = dict(zip(CASES, (7, 5, 3, 5, 9, 12, 6, 8)))
SOFT_TAIL, HARD_TAIL, FULLTEXT_LIMIT = 120, 180, 10


def canon(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()


def pretty(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode()


def jsonl(rows: list[dict[str, Any]]) -> bytes:
    return b"".join(canon(row) + b"\n" for row in rows)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def digest(value: Any) -> str:
    return hashlib.sha256(canon(value)).hexdigest()


def load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def read_rows(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def write(name: str | Path, body: bytes) -> None:
    path = name if isinstance(name, Path) else RUN / name
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        if path.read_bytes() != body:
            raise RuntimeError(f"refusing to overwrite frozen output: {path}")
        return
    path.write_bytes(body)


def verify_aggregate(directory: Path, root_name: str, expected: str) -> int:
    pairs = load(directory / "validation.json")["aggregate_components"]
    if any(sha(directory / name) != value for name, value in pairs):
        raise RuntimeError(f"component drift: {directory.name}")
    if digest(pairs) != expected or (directory / root_name).read_text().strip() != expected:
        raise RuntimeError(f"root drift: {directory.name}")
    return len(pairs)


def verify_alpha39() -> None:
    files = {p.name: sha(p) for p in sorted(ALPHA39.iterdir()) if p.is_file() and p.name != "search_plan_v24_dev_alpha3_9_sha256"}
    if digest({"artifact_schema_version": "SearchPlanV24DevAlpha39FreezeV1", "files": files}) != EXPECTED_ALPHA39:
        raise RuntimeError("alpha3.9 components changed")
    if (ALPHA39 / "search_plan_v24_dev_alpha3_9_sha256").read_text().strip() != EXPECTED_ALPHA39:
        raise RuntimeError("alpha3.9 root changed")


def verify_alpha310() -> int:
    files = {p.name: sha(p) for p in sorted(PREREG.iterdir()) if p.is_file() and p.name != "search_plan_v24_dev_alpha3_10_sha256"}
    pairs = [[name, value] for name, value in sorted(files.items())]
    if digest(pairs) != EXPECTED_PREREG or (PREREG / "search_plan_v24_dev_alpha3_10_sha256").read_text().strip() != EXPECTED_PREREG:
        raise RuntimeError("alpha3.10 components changed")
    return len(files)


def preflight() -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]], dict[str, dict[str, Any]]]:
    counts = {
        "alpha3_10_components": verify_alpha310(),
        "alpha3_4_components": verify_aggregate(ALPHA34, "search_plan_v24_dev_alpha3_4_sha256", EXPECTED_ALPHA34),
    }
    verify_alpha39()
    if sha(MANIFEST_PATH) != EXPECTED_MANIFEST or (PREREG / "search_constraint_allocation_v1_development_execution_manifest_sha256").read_text().strip() != EXPECTED_MANIFEST:
        raise RuntimeError("execution manifest changed")
    if sha(QUERY_PATH) != EXPECTED_QUERIES:
        raise RuntimeError("query set changed")
    manifest = load(MANIFEST_PATH)
    source_queries = read_rows(QUERY_PATH)
    queries = manifest["exact_queries"]
    if len(queries) != 55 or len(source_queries) != 55:
        raise RuntimeError("query count mismatch")
    if Counter(q["case_id"] for q in queries) != Counter(CASE_COUNTS):
        raise RuntimeError("per-case query mismatch")
    if sum(len(q["contributions"]) for q in queries) != 63:
        raise RuntimeError("relation contribution count mismatch")
    if len({q["query_id"] for q in queries}) != 55:
        raise RuntimeError("transport adapter requires globally distinct frozen query IDs")
    for q, source in zip(queries, source_queries):
        if q["exact_query_text"].encode() != source["query"].encode() or q["query_id"] != source["query_id"] or q["query_sha256"] != hashlib.sha256(q["exact_query_text"].encode()).hexdigest():
            raise RuntimeError("query bytes or identity changed")
        if {c["query_ast_sha256"] for c in q["contributions"]} != {c["ast_sha256"] for c in source["contributions"]}:
            raise RuntimeError("query AST contribution changed")
    for name, expected in manifest["downstream_policy_hashes"].items():
        if sha(ALPHA34 / name) != expected:
            raise RuntimeError(f"downstream policy changed: {name}")
    for name, field in [
        ("query_execution_policy.json", "execution_policy_sha256"),
        ("tail_policy.json", "tail_policy_sha256"),
        ("metadata_policy.json", "metadata_policy_sha256"),
        ("candidate_validation_policy.json", "candidate_validation_policy_sha256"),
        ("oa_eligibility_policy.json", "OA_policy_sha256"),
        ("selection_fulltext_policy.json", "fulltext_selection_policy_sha256"),
        ("technical_retry_policy.json", "retry_policy_sha256"),
        ("technical_continuation_policy.json", "technical_continuation_policy_sha256"),
        ("known_paper_blindness_policy.json", "known_paper_blindness_policy_sha256"),
        ("historical_label_blinding_policy.json", "historical_label_blinding_policy_sha256"),
    ]:
        if sha(PREREG / name) != manifest[field]:
            raise RuntimeError(f"alpha3.10 policy changed: {name}")
    targets, bindings, old_queries = legacy.v23_frozen_inputs()
    targets_by_case = {row["case_id"]: row for row in targets}
    if tuple(sorted(targets_by_case)) != CASES:
        raise RuntimeError("target case set changed")
    for case, value in manifest["target_sha256_by_case"].items():
        if digest(targets_by_case[case]) != value:
            raise RuntimeError(f"target hash changed: {case}")
    gate_queries: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for query in old_queries:
        gate_queries[query["case_id"]].append(query)
    gates = {case: legacy.gate_target(targets_by_case[case], bindings[case], gate_queries[case]) for case in CASES}
    verification = {"artifact_schema_version": "SearchConstraintAllocationV1ExecutionPreflightV1", "verified_before_first_network_request": True, "alpha3_10_root_sha256": EXPECTED_PREREG, "execution_manifest_sha256": EXPECTED_MANIFEST, "alpha3_9_root_sha256": EXPECTED_ALPHA39, "query_set_sha256": EXPECTED_QUERIES, "alpha3_4_root_sha256": EXPECTED_ALPHA34, "component_counts": counts, "target_hashes_verified": True, "query_text_changes": 0, "relation_contribution_count": 63, "byte_unique_query_count": 55, "downstream_policy_hashes_verified": True}
    return verification, queries, targets, gates


def project_queries(manifest_queries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    # Transport-only adapter for the proven NCBI pagination implementation.
    return [{**q,
             "contributing_intent_types": sorted({c["intent_type"] for c in q["contributions"]}),
             "relation_core_ids": sorted({c["relation_core_sha256"] for c in q["contributions"]}),
             "surface_plan_ids": sorted({c["surface_plan_id"] for c in q["contributions"]}),
             "pubmed_ast_hashes": sorted({c["query_ast_sha256"] for c in q["contributions"]})}
            for q in manifest_queries]


def bind_transport() -> legacy.Network:
    legacy.RUN = RUN
    legacy.ASSETS = ASSETS
    surface.RUN = RUN
    surface.ASSETS = ASSETS
    return legacy.Network(True)


def freeze_universe(execution: dict[str, Any], query_map: dict[str, dict[str, Any]]) -> dict[str, Any]:
    pages = execution["pages"]
    queries = execution["queries"]
    if len(queries) != 55 or any(row["transport_status"] != "SUCCESS" for row in queries):
        raise RuntimeError("query execution barrier not complete")
    query_rows = []
    for row in queries:
        q = query_map[row["executed_query_id"]]
        query_rows.append({**row, "artifact_schema_version": "SearchConstraintAllocationV1QueryExecutionResultV1", "variant_classes": q["variant_classes"], "contributions": [{"query_family_id": c["query_family_id"], "intent_type": c["intent_type"], "variant_class": c["variant_class"], "relation_core_sha256": c["relation_core_sha256"], "query_ast_sha256": c["query_ast_sha256"]} for c in q["contributions"]]})
    page_rows = []
    for row in pages:
        q = query_map[row["executed_query_id"]]
        page_rows.append({**row, "variant_classes": q["variant_classes"], "contributing_query_family_ids": sorted({c["query_family_id"] for c in q["contributions"]}), "execution_epoch": "INITIAL_EXECUTION_EPOCH"})
    case_rows, provenance_rows = [], []
    hard_tail_pmids = {}
    for case in CASES:
        observed = execution["case_observed"][case]
        hard = observed[:HARD_TAIL]
        hard_tail_pmids[case] = hard
        included = set(hard)
        occurrences: dict[str, list[dict[str, Any]]] = defaultdict(list)
        case_pages = [p for p in page_rows if p["case_id"] == case and p["transport_status"] == "SUCCESS"]
        for page in case_pages:
            q = query_map[page["executed_query_id"]]
            for rank, pmid in enumerate(page["returned_pmids"], page["retstart"] + 1):
                occurrences[pmid].append({"executed_query_id": page["executed_query_id"], "query_sha256": page["query_sha256"], "variant_classes": q["variant_classes"], "query_family_ids": sorted({c["query_family_id"] for c in q["contributions"]}), "relation_core_sha256s": sorted({c["relation_core_sha256"] for c in q["contributions"]}), "query_rank": rank, "page": page["page"], "retstart": page["retstart"], "raw_response_sha256": page["raw_response_sha256"]})
        cap_reached = len(hard) == HARD_TAIL
        count_only = any(p["retmax"] == 0 for p in case_pages)
        case_rows.append({"artifact_schema_version": "SearchConstraintAllocationV1CaseUnionPMIDsV1", "case_id": case, "observed_unique_pmids_before_hard_tail": observed, "observed_unique_pmid_count_before_hard_tail": len(observed), "hard_tail_pmids": hard, "hard_tail_pmid_count": len(hard), "hard_tail": HARD_TAIL, "hard_tail_reached": cap_reached, "count_only_censoring_after_hard_tail": count_only, "cross_case_deduplication": False})
        for pmid in observed:
            provenance_rows.append({"case_id": case, "pmid": pmid, "included_in_hard_tail_universe": pmid in included, "occurrences": occurrences[pmid], "contributing_query_ids": list(dict.fromkeys(o["executed_query_id"] for o in occurrences[pmid]))})
    write("query_execution_results.jsonl", jsonl(query_rows))
    write("query_execution_provenance.jsonl", jsonl(page_rows))
    write("case_union_pmids.jsonl", jsonl(case_rows))
    write("case_union_provenance.jsonl", jsonl(provenance_rows))
    components = [[name, sha(RUN / name)] for name in ["query_execution_results.jsonl", "query_execution_provenance.jsonl", "case_union_pmids.jsonl", "case_union_provenance.jsonl"]]
    universe_sha = digest(components)
    write("retrieval_universe_freeze.json", pretty({"artifact_schema_version": "SearchConstraintAllocationV1RetrievalUniverseFreezeV1", "components": components, "retrieval_universe_sha256": universe_sha, "query_count": 55, "case_count": 8, "frozen_before_metadata_scoring": True}))
    write("tail_application_audit.json", pretty({"artifact_schema_version": "SearchConstraintAllocationV1TailApplicationAuditV1", "soft_tail": SOFT_TAIL, "soft_tail_reporting_only": True, "hard_tail": HARD_TAIL, "adaptive_tail_enabled": False, "tail_after_within_case_deduplication": True, "cases": [{"case_id": r["case_id"], "hard_tail_count": r["hard_tail_pmid_count"], "count_only_censoring": r["count_only_censoring_after_hard_tail"]} for r in case_rows]}))
    return {"case_rows": case_rows, "provenance_rows": provenance_rows, "hard_tail_pmids": hard_tail_pmids, "universe_sha": universe_sha}


def build_metadata(universe: dict[str, Any], query_map: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    publications = {}
    for path in sorted((ASSETS / "pubmed_efetch").glob("batch_*.xml")):
        publications.update(legacy.parse_pubmed(path.read_bytes()))
    lineage = {(r["case_id"], r["pmid"]): r for r in universe["provenance_rows"]}
    rows, failures = [], []
    for case in CASES:
        for depth, pmid in enumerate(universe["hard_tail_pmids"][case], 1):
            if pmid not in publications:
                failures.append({"case_id": case, "pmid": pmid, "failure_state": "METADATA_FETCH_FAILURE"})
                continue
            pub = publications[pmid]
            prov = lineage[(case, pmid)]
            query_ids = prov["contributing_query_ids"]
            rows.append({"artifact_schema_version": "SearchConstraintAllocationV1MetadataRecordV1", "candidate_id": f"{case}:pmid:{pmid}", "case_id": case, "canonical_candidate_identity": f"pmid:{pmid}", "case_publication_identity": f"{case}:pmid:{pmid}", "pmid": pmid, "pmcid": pub.get("pmcid"), "doi": pub.get("doi"), "title": pub["title"], "abstract": pub["abstract"], "publication_type": pub["publication_types"], "journal": pub["journal"], "publication_date": pub["publication_date"], "metadata_depth": depth, "first_seen_provenance": prov["occurrences"][0], "query_provenance": prov["occurrences"], "all_contributing_query_ids": query_ids, "all_contributing_variant_classes": sorted({variant for qid in query_ids for variant in query_map[qid]["variant_classes"]}), "deduplication_identity_rule": "PMID within case", "metadata_resolution_status": "RESOLVED"})
    write("metadata_records.jsonl", jsonl(rows))
    write("metadata_failure_records.jsonl", jsonl(failures))
    if failures:
        raise RuntimeError("terminal metadata failure; stop before candidate ranking")
    return rows


def freeze_selection(processed: dict[str, Any], universe_sha: str) -> tuple[str, list[dict[str, Any]]]:
    for name, rows in [("candidate_gate_results.jsonl", processed["base"]), ("p0_results.jsonl", processed["p0"]), ("p1_results.jsonl", processed["p1"]), ("p2_results.jsonl", processed["p2"]), ("policy_a_results.jsonl", processed["policy"]), ("oa_eligibility_results.jsonl", processed["oa"])]:
        write(name, jsonl(rows))
    tiers = Counter(r["final_v23_beta2_disposition"] for r in processed["final"])
    write("candidate_tier_summary.json", pretty({"artifact_schema_version": "SearchConstraintAllocationV1CandidateTierSummaryV1", "counts": {state: tiers.get(state, 0) for state in ("TIER_A", "TIER_B", "REJECT", "ABSTAIN")}, "candidate_count": len(processed["final"]), "tier_a_before_tier_b": True, "within_tier_order": ["metadata_depth", "numeric PMID"]}))
    case_files = []
    for case in CASES:
        selected = [r for r in processed["selected"] if r["case_id"] == case]
        if len(selected) > FULLTEXT_LIMIT:
            raise RuntimeError("fulltext cap exceeded")
        path = RUN / "case_selection_manifests" / f"{case}.json"
        write(path, pretty({"artifact_schema_version": "SearchConstraintAllocationV1CaseSelectionManifestV1", "case_id": case, "selection_count": len(selected), "maximum_fulltexts_per_case": FULLTEXT_LIMIT, "ordered_selections": selected, "fulltext_content_inspected": False}))
        case_files.append(path)
    pairs = [[str(path.relative_to(RUN)), sha(path)] for path in case_files]
    selection_sha = digest(pairs)
    write("selection_manifest_aggregate_sha256", (selection_sha + "\n").encode())
    write("selection_freeze_barrier_audit.json", pretty({"artifact_schema_version": "SearchConstraintAllocationV1SelectionFreezeBarrierAuditV1", "case_manifest_components": pairs, "case_manifest_count": 8, "selection_manifest_aggregate_sha256": selection_sha, "retrieval_universe_sha256": universe_sha, "all_eight_manifests_frozen_and_hashed": True, "frozen_before_first_pmc_fulltext_fetch": True, "selection_freeze_barrier_pass": True, "fulltext_content_used_for_selection": False}))
    return selection_sha, processed["selected"]


def freeze_terminal_search_failure(exc: Exception, queries: list[dict[str, Any]], network: legacy.Network) -> dict[str, Any]:
    pages = read_rows(RUN / "query_execution_provenance.jsonl") if (RUN / "query_execution_provenance.jsonl").exists() else []
    failure = next((p for p in reversed(pages) if p["transport_status"] == "TERMINAL_FAILURE"), None)
    if failure is None:
        raise RuntimeError("search failed without frozen terminal page") from exc
    successful_pages = defaultdict(list)
    for page in pages:
        if page["transport_status"] == "SUCCESS":
            successful_pages[page["executed_query_id"]].append(page)
    failed_id = failure["executed_query_id"]
    cause = exc.__cause__ or exc
    transport = isinstance(cause, (ConnectionError, TimeoutError, OSError))
    # Only a terminal transport failure qualifies for the preregistered epoch.
    status_rows = []
    for query in queries:
        qid = query["query_id"]
        prior = successful_pages[qid]
        if qid == failed_id:
            status = "TERMINAL_TECHNICAL_FAILURE" if transport else "TERMINAL_SEARCH_FAILURE"
        elif prior:
            last = prior[-1]
            exhausted = last["retmax"] == 0 or last["retstart"] + last["returned_pmid_count"] >= last["raw_hit_count"]
            status = "SUCCESS" if exhausted else "NOT_EXECUTED_AFTER_ABORT"
        else:
            status = "NOT_EXECUTED_AFTER_ABORT"
        status_rows.append({"case_id": query["case_id"], "executed_query_id": qid, "query_sha256": query["query_sha256"], "query_text": query["exact_query_text"], "transport_status": status, "successful_page_count": len(prior), "raw_hit_count": prior[0]["raw_hit_count"] if prior else None, "returned_pmids_in_frozen_page_order": [pmid for p in prior for pmid in p["returned_pmids"]]})
    write("query_execution_results.jsonl", jsonl(status_rows))
    incomplete = [r for r in status_rows if r["transport_status"] in {"TERMINAL_TECHNICAL_FAILURE", "NOT_EXECUTED_AFTER_ABORT"}]
    frozen = {"artifact_schema_version": "SearchConstraintAllocationV1InitialTechnicalFailureV1", "terminal_query_id": failed_id, "terminal_case_id": failure["case_id"], "failure_type": type(cause).__name__, "technical_continuation_permitted": transport, "successful_query_count": sum(r["transport_status"] == "SUCCESS" for r in status_rows), "incomplete_query_count": len(incomplete), "incomplete_query_ids": [r["executed_query_id"] for r in incomplete], "original_attempts_preserved": True, "no_scientific_zero_inferred": True, "original_run_frozen_before_continuation": True}
    write("terminal_failure_summary.json", pretty(frozen))
    write("retrieval_request_manifest.jsonl", jsonl([{**e, "attempt_state": "SUCCESS"} for e in network.events] + [{**e, "attempt_state": "FAILED_ATTEMPT"} for e in network.failures]))
    paths = sorted(p for p in RUN.rglob("*") if p.is_file() and p.name not in {"validation.json", "search_constraint_allocation_v1_initial_retrieval_sha256"})
    pairs = [[str(p.relative_to(RUN)), sha(p)] for p in paths]
    root = digest(pairs)
    write("validation.json", pretty({"artifact_schema_version": "SearchConstraintAllocationV1InitialFailureValidationV1", "status": "FAILED_CLOSED", "aggregate_components": pairs, "search_constraint_allocation_v1_initial_retrieval_sha256": root}))
    write("search_constraint_allocation_v1_initial_retrieval_sha256", (root + "\n").encode())
    return {**frozen, "initial_run_sha256": root}


def freeze_nonsearch_failure(stage: str, exc: Exception, network: legacy.Network) -> dict[str, Any]:
    failure = {"artifact_schema_version": "SearchConstraintAllocationV1NonSearchFailureV1", "status": "FAILED_CLOSED", "stage": stage, "error_type": type(exc).__name__, "error": str(exc), "technical_query_continuation_permitted": False, "no_relevance_adjudication": True, "no_result_driven_policy_change": True}
    write("terminal_stage_failure_summary.json", pretty(failure))
    request_rows = [{**e, "attempt_state": "SUCCESS"} for e in network.events] + [{**e, "attempt_state": "FAILED_ATTEMPT"} for e in network.failures]
    request_rows.sort(key=lambda r: (r.get("request_sequence", 10**9), r.get("timestamp_utc", ""), r.get("attempt", 0)))
    write("retrieval_request_manifest.jsonl", jsonl(request_rows))
    paths = sorted(p for p in RUN.rglob("*") if p.is_file() and p.name not in {"validation.json", "search_constraint_allocation_v1_development_retrieval_sha256"})
    pairs = [[str(p.relative_to(RUN)), sha(p)] for p in paths]
    root = digest(pairs)
    write("validation.json", pretty({"artifact_schema_version": "SearchConstraintAllocationV1NonSearchFailureValidationV1", "status": "FAILED_CLOSED", "aggregate_components": pairs, "root_sha256": root}))
    write("search_constraint_allocation_v1_development_retrieval_sha256", (root + "\n").encode())
    return {**failure, "root_sha256": root}


def finish(verification: dict[str, Any], manifest: dict[str, Any], execution: dict[str, Any], universe: dict[str, Any], metadata: list[dict[str, Any]], processed: dict[str, Any], selection_sha: str, fulltexts: list[dict[str, Any]], failures: list[dict[str, Any]], network: legacy.Network) -> dict[str, Any]:
    query_rows = read_rows(RUN / "query_execution_results.jsonl")
    page_rows = read_rows(RUN / "query_execution_provenance.jsonl")
    if len(query_rows) != 55 or sum(len(q["contributions"]) for q in manifest["exact_queries"]) != 63:
        raise RuntimeError("execution corpus count mismatch")
    nonzero = [q for q in query_rows if q["outcome"] == "NONZERO_QUERY"]
    zero = [q for q in query_rows if q["outcome"] == "ZERO_HIT_QUERY"]
    query_map = {q["query_id"]: q for q in manifest["exact_queries"]}
    case_stats = []
    for case in CASES:
        qs = [q for q in query_rows if q["case_id"] == case]
        union = next(r for r in universe["case_rows"] if r["case_id"] == case)
        case_stats.append({"case_id": case, "executed_query_count": len(qs), "nonzero_query_count": sum(q["outcome"] == "NONZERO_QUERY" for q in qs), "zero_hit_query_count": sum(q["outcome"] == "ZERO_HIT_QUERY" for q in qs), "raw_hit_count_sum": sum(q["raw_hit_count"] for q in qs), "observed_unique_pmids_before_tail": union["observed_unique_pmid_count_before_hard_tail"], "hard_tail_pmid_count": union["hard_tail_pmid_count"], "hard_tail_count_only_censoring": union["count_only_censoring_after_hard_tail"], "metadata_universe_count": sum(r["case_id"] == case for r in metadata), "selected_count": sum(r["case_id"] == case for r in processed["selected"]), "acquired_count": sum(r["case_id"] == case and r["acquisition_status"] == "SUCCESS" for r in fulltexts)})
    core_queries = [q for q in query_rows if "CORE_RELATION" in q["variant_classes"]]
    write("retrieval_viability_summary.json", pretty({"artifact_schema_version": "SearchConstraintAllocationV1RetrievalViabilitySummaryV1", "nonzero_query_count": len(nonzero), "zero_hit_query_count": len(zero), "nonzero_case_count": sum(c["nonzero_query_count"] > 0 for c in case_stats), "zero_hit_case_count": sum(c["nonzero_query_count"] == 0 for c in case_stats), "CORE_RELATION_queries_executed": len(core_queries), "CORE_RELATION_nonzero_query_count": sum(q["raw_hit_count"] > 0 for q in core_queries), "cases_with_nonzero_CORE_RELATION": len({q["case_id"] for q in core_queries if q["raw_hit_count"] > 0}), "observed_unique_pmids_before_tail_total": sum(c["observed_unique_pmids_before_tail"] for c in case_stats), "hard_tail_censored_cases": [c["case_id"] for c in case_stats if c["hard_tail_count_only_censoring"]], "no_relevance_claim": True}))
    write("case_query_hit_summary.json", pretty({"artifact_schema_version": "SearchConstraintAllocationV1CaseQueryHitSummaryV1", "cases": case_stats}))
    tier = Counter(r["final_v23_beta2_disposition"] for r in processed["final"])
    dispositions = {r["candidate_id"]: r for r in processed["final"]}
    oa_by_candidate = {r["candidate_id"]: r for r in processed["oa"]}
    selected_ids = {r["candidate_id"] for r in processed["selected"]}
    by_candidate = {r["candidate_id"]: r for r in metadata}
    variant_stats = []
    for variant in ("CORE_RELATION", "ENDPOINT_RELATION_FOCUSED", "CORE_RELATION_PLUS_CONTEXT"):
        vqs = [q for q in query_rows if variant in q["variant_classes"]]
        qids = {q["executed_query_id"] for q in vqs}
        contributed = {(r["case_id"], r["pmid"]) for r in universe["provenance_rows"] if set(r["contributing_query_ids"]) & qids}
        uniquely = {(r["case_id"], r["pmid"]) for r in universe["provenance_rows"] if set(r["contributing_query_ids"]) & qids and all(variant in query_map[qid]["variant_classes"] for qid in r["contributing_query_ids"])}
        hard = {(r["case_id"], r["pmid"]) for r in universe["provenance_rows"] if r["included_in_hard_tail_universe"] and set(r["contributing_query_ids"]) & qids}
        hard_candidates = {f"{case}:pmid:{pmid}" for case, pmid in hard}
        variant_stats.append({"variant_class": variant, "query_count": len(vqs), "nonzero_query_count": sum(q["raw_hit_count"] > 0 for q in vqs), "raw_hit_count_sum": sum(q["raw_hit_count"] for q in vqs), "unique_pmids_contributed": len(contributed), "pmids_uniquely_contributed": len(uniquely), "hard_tail_pmids_contributed": len(hard), "tier_a_contributions": sum(dispositions[cid]["final_v23_beta2_disposition"] == "TIER_A" for cid in hard_candidates), "tier_b_contributions": sum(dispositions[cid]["final_v23_beta2_disposition"] == "TIER_B" for cid in hard_candidates), "oa_contributions": sum(oa_by_candidate.get(cid, {}).get("legal_fulltext_available", False) for cid in hard_candidates), "selected_contributions": len(hard_candidates & selected_ids), "hard_tail_censoring_applies": any(c["hard_tail_count_only_censoring"] for c in case_stats)})
    write("variant_retrieval_attribution.json", pretty({"artifact_schema_version": "SearchConstraintAllocationV1VariantRetrievalAttributionV1", "variant_classes": variant_stats, "many_to_many_attribution": True, "descriptive_only": True}))
    overlap = []
    for case in CASES:
        core_ids = {q["query_id"] for q in manifest["exact_queries"] if q["case_id"] == case and "CORE_RELATION" in q["variant_classes"]}
        context_ids = {q["query_id"] for q in manifest["exact_queries"] if q["case_id"] == case and "CORE_RELATION_PLUS_CONTEXT" in q["variant_classes"]}
        core_pmids = {r["pmid"] for r in universe["provenance_rows"] if r["case_id"] == case and core_ids.intersection(r["contributing_query_ids"])}
        context_pmids = {r["pmid"] for r in universe["provenance_rows"] if r["case_id"] == case and context_ids.intersection(r["contributing_query_ids"])}
        overlap.append({"case_id": case, "core_only_pmids": len(core_pmids - context_pmids), "context_only_additional_pmids": len(context_pmids - core_pmids), "shared_core_context_pmids": len(core_pmids & context_pmids)})
    write("query_family_overlap_summary.json", pretty({"artifact_schema_version": "SearchConstraintAllocationV1QueryFamilyOverlapV1", "cases": overlap, "descriptive_only": True}))
    p0 = Counter(r["state"] for r in processed["p0"])
    p1 = Counter(r["state"] for r in processed["p1"])
    p2 = Counter(r["state"] for r in processed["p2"])
    write("search_vs_validation_diagnostic_summary.json", pretty({"artifact_schema_version": "SearchVsValidationDiagnosticSummaryV1", "candidates_entering_P0": len(processed["p0"]), "P0_states": dict(p0), "candidates_entering_P1": len(processed["p1"]), "P1_states": dict(p1), "candidates_entering_P2": len(processed["p2"]), "P2_states": dict(p2), "Policy_A_demotions": sum(r["policy_a_action"] == "DEMOTE_A_TO_B" for r in processed["policy"]), "frozen_module_outputs_not_relabelled": True, "scientific_relevance_labels": 0}))
    denominators = {"relation_contribution_count": 63, "byte_unique_query_count": 55, "nonzero_query_count": len(nonzero), "zero_hit_query_count": len(zero), "nonzero_case_count": sum(c["nonzero_query_count"] > 0 for c in case_stats), "zero_hit_case_count": sum(c["nonzero_query_count"] == 0 for c in case_stats), "observed_unique_pmids_before_tail_total": sum(c["observed_unique_pmids_before_tail"] for c in case_stats), "metadata_universe_total": len(metadata), "tier_a_count": tier.get("TIER_A", 0), "tier_b_count": tier.get("TIER_B", 0), "reject_count": tier.get("REJECT", 0), "abstain_count": tier.get("ABSTAIN", 0), "oa_eligible_count": sum(r["legal_fulltext_available"] for r in processed["oa"]), "selected_count": len(processed["selected"]), "successful_fulltext_acquisition_count": sum(r["acquisition_status"] == "SUCCESS" for r in fulltexts), "fulltext_failure_count": len(failures)}
    write("retrieval_denominator_summary.json", pretty({"artifact_schema_version": "SearchConstraintAllocationV1RetrievalDenominatorSummaryV1", **denominators, "relevance_denominators_present": False}))
    write("four_architecture_retrieval_comparison.json", pretty({"artifact_schema_version": "FourArchitectureRetrievalComparisonV1", "scope": "retrieval/acquisition only; no relevance conclusion", "architectures": [{"architecture": "v2.3 historical", "query_count": 32, "historical_aggregate_only": True}, {"architecture": "v2.4 exact-proposition", "query_count": 29, "nonzero_query_count": 0, "historical_aggregate_only": True}, {"architecture": "Retrieval Surface V2", "query_count": 25, "nonzero_query_count": 0, "historical_aggregate_only": True}, {"architecture": "SearchConstraintAllocationV1", **denominators}], "known_pmid_checks": 0, "DIRECT_rate_compared": False, "precision_claim": False, "recall_claim": False}))
    write("known_paper_blindness_audit.json", pretty({"known_pmid_checks": 0, "manual_injections": 0, "historical_query_fallbacks": 0, "preserved": True}))
    write("historical_label_blinding_audit.json", pretty({"historical_label_reads": 0, "PASS_A_or_B_material_read": 0, "relevance_labels_created": 0, "preserved": True}))
    write("runtime_adaptation_audit.json", pretty({"query_modifications": 0, "synonym_or_alias_additions": 0, "morphology_changes": 0, "ATM_changes": 0, "proximity_changes": 0, "fallback_queries": 0, "runtime_adaptation_performed": False}))
    write("scientific_state_safety_audit.json", pretty({"scientific_relevance_adjudications": 0, "DIRECT_or_WRONG_labels": 0, "known_pmid_checks": 0, "historical_label_reads": 0, "provider_calls": 0, "llm_calls": 0, "general_web_calls": 0, "publisher_calls": 0, "allowed_host": "eutils.ncbi.nlm.nih.gov", "historical_assets_modified": False}))
    request_rows = [{**e, "attempt_state": "SUCCESS"} for e in network.events] + [{**e, "attempt_state": "FAILED_ATTEMPT"} for e in network.failures]
    request_rows.sort(key=lambda r: (r.get("request_sequence", 10**9), r.get("timestamp_utc", ""), r.get("attempt", 0)))
    write("retrieval_request_manifest.jsonl", jsonl(request_rows))
    corpus_names = ["query_execution_results.jsonl", "query_execution_provenance.jsonl", "case_union_pmids.jsonl", "case_union_provenance.jsonl", "retrieval_universe_freeze.json", "tail_application_audit.json", "metadata_fetch_manifest.jsonl", "metadata_records.jsonl", "metadata_failure_records.jsonl", "candidate_gate_results.jsonl", "p0_results.jsonl", "p1_results.jsonl", "p2_results.jsonl", "policy_a_results.jsonl", "candidate_tier_summary.json", "oa_eligibility_results.jsonl", "selection_manifest_aggregate_sha256", "selection_freeze_barrier_audit.json", "fulltext_fetch_manifest.jsonl", "fulltext_acquisition_results.jsonl", "fulltext_failure_records.jsonl", "acquired_fulltext_manifest.json"]
    corpus_paths = [RUN / name for name in corpus_names]
    corpus_paths.extend(sorted((RUN / "case_selection_manifests").glob("*.json")))
    corpus_paths.extend(sorted(p for p in ASSETS.rglob("*") if p.is_file()))
    if any(not p.is_file() for p in corpus_paths):
        raise RuntimeError("corpus component missing")
    corpus_pairs = [[str(p.relative_to(RUN)), sha(p)] for p in corpus_paths]
    corpus_sha = digest(corpus_pairs)
    write("search_constraint_allocation_v1_development_acquisition_corpus_manifest.json", pretty({"artifact_schema_version": "SearchConstraintAllocationV1DevelopmentAcquisitionCorpusManifestV1", "aggregate_algorithm": "sha256(canonical JSON ordered [path,sha256] pairs)", "aggregate_components": corpus_pairs, "corpus_sha256": corpus_sha, "frozen_before_scientific_relevance_adjudication": True}))
    write("search_constraint_allocation_v1_development_acquisition_corpus_sha256", (corpus_sha + "\n").encode())
    write("upstream_root_verification.json", pretty(verification))
    write("execution_manifest_verification.json", pretty({"execution_manifest_sha256": EXPECTED_MANIFEST, "query_set_sha256": EXPECTED_QUERIES, "relation_contribution_count": 63, "byte_unique_query_count": 55, "verified": True}))
    write("query_family_contribution_map.json", pretty({"relation_contribution_count": 63, "byte_unique_query_count": 55, "queries": [{"query_id": q["query_id"], "case_id": q["case_id"], "variant_classes": q["variant_classes"], "contributions": [{"family_id": c["query_family_id"], "intent_type": c["intent_type"], "variant_class": c["variant_class"], "relation_core_sha256": c["relation_core_sha256"], "AST_sha256": c["query_ast_sha256"]} for c in q["contributions"]]} for q in manifest["exact_queries"]]}))
    write("retrieval_policy_compliance_audit.json", pretty({"all_55_queries_completed": True, "all_63_contributions_preserved": True, "metadata_failures_zero": True, "selection_barrier_passed": True, "replacement_count_zero": True, "runtime_adaptation_zero": True, "known_paper_blinding_preserved": True, "historical_label_blinding_preserved": True, "relevance_adjudication_zero": True, "status": "PASS"}))
    summary = {"artifact_schema_version": "SearchConstraintAllocationV1DevelopmentRetrievalSummaryV1", "status": "completed", **denominators, "CORE_RELATION_nonzero_query_count": sum(q["raw_hit_count"] > 0 for q in core_queries), "cases_with_nonzero_CORE_RELATION": len({q["case_id"] for q in core_queries if q["raw_hit_count"] > 0}), "selection_manifests_frozen_before_download": True, "replacement_count": 0, "relevance_adjudications": 0, "known_pmid_checks": 0, "historical_label_reads": 0, "provider_calls": 0, "llm_calls": 0, "network_successful_response_count": len(network.events), "network_failed_attempt_count": len(network.failures), "acquisition_corpus_sha256": corpus_sha, "historical_assets_modified": False}
    write("summary.json", pretty(summary))
    root_paths = sorted(p for p in RUN.rglob("*") if p.is_file() and str(p.relative_to(RUN)) not in {"validation.json", "search_constraint_allocation_v1_development_retrieval_sha256"})
    root_pairs = [[str(p.relative_to(RUN)), sha(p)] for p in root_paths]
    root = digest(root_pairs)
    write("validation.json", pretty({"artifact_schema_version": "SearchConstraintAllocationV1DevelopmentRetrievalValidationV1", "status": "PASS", "aggregate_components": root_pairs, "root_sha256": root, "checks": {"all_55_queries_completed": True, "all_63_contributions_preserved": True, "all_eight_selection_manifests_frozen_before_first_PMC_fetch": True, "metadata_failures_zero": True, "no_relevance_adjudication": True}}))
    write("search_constraint_allocation_v1_development_retrieval_sha256", (root + "\n").encode())
    return {**summary, "root_sha256": root}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--preflight-only", action="store_true")
    parser.add_argument("--execute-network", action="store_true")
    args = parser.parse_args()
    if args.preflight_only == args.execute_network:
        parser.error("choose exactly one of --preflight-only or --execute-network")
    verification, queries, targets, gates = preflight()
    if args.preflight_only:
        print(json.dumps({"preflight": verification, "run_path": str(RUN), "network_calls": 0}, sort_keys=True))
        return
    if RUN.exists():
        raise RuntimeError(f"refusing existing run: {RUN}")
    RUN.mkdir(parents=True)
    write("pre_network_verification.json", pretty({**verification, "timestamp_utc": datetime.now(timezone.utc).isoformat()}))
    write("frozen_execution_manifest_sha256", (EXPECTED_MANIFEST + "\n").encode())
    manifest = load(MANIFEST_PATH)
    query_map = {q["query_id"]: q for q in queries}
    network = bind_transport()
    projected = project_queries(queries)
    try:
        execution = surface.execute_queries(network, projected)
    except Exception as exc:
        failure = freeze_terminal_search_failure(exc, queries, network)
        print(json.dumps({"status": "FAILED_CLOSED", **failure}, sort_keys=True), flush=True)
        raise
    stage = "retrieval_universe_freeze"
    try:
        universe = freeze_universe(execution, query_map)
        stage = "metadata_fetch"
        surface.fetch_metadata(network, universe["hard_tail_pmids"])
        stage = "metadata_validation"
        metadata = build_metadata(universe, query_map)
        stage = "candidate_validation_and_selection"
        processed = legacy.score_and_select(metadata, targets, gates, network)
        selection_sha, selected = freeze_selection(processed, universe["universe_sha"])
        print(f"selection_frozen sha256={selection_sha} count={len(selected)}", flush=True)
        stage = "PMC_fulltext_acquisition"
        fulltexts, failures = surface.fetch_fulltexts(network, selected, selection_sha)
        stage = "corpus_freeze"
        result = finish(verification, manifest, execution, universe, metadata, processed, selection_sha, fulltexts, failures, network)
    except Exception as exc:
        failure = freeze_nonsearch_failure(stage, exc, network)
        print(json.dumps(failure, sort_keys=True), flush=True)
        raise
    print(json.dumps(result, sort_keys=True), flush=True)


if __name__ == "__main__":
    main()
