#!/usr/bin/env python3
"""Complete V2 NCBI-only source rerun from the frozen first query and page."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

try:
    from scripts import search_plan_v24_alpha318a_execute_ncbi_source_acquisition as base
    from scripts import search_plan_v24_alpha318a4_esearch_response_validity as validity
    from scripts import search_plan_v24_alpha318a4_freeze_query_runtime_amendment_offline as freeze
except ModuleNotFoundError:
    import search_plan_v24_alpha318a_execute_ncbi_source_acquisition as base
    import search_plan_v24_alpha318a4_esearch_response_validity as validity
    import search_plan_v24_alpha318a4_freeze_query_runtime_amendment_offline as freeze


ROOT = base.ROOT
OUT = ROOT / "runs/20260928_search_plan_v24_dev_alpha3_18a_v2_ncbi_only_source_acquisition"
ROOT_MARKER = "search_plan_v24_dev_alpha3_18a_v2_sha256"
AMEND_ROOT = "cc222ad4566c4b54ac243f63341c58df98ec68627c8b992814002ac05567d17b"
QUERY_SHA = "762d3fff84539b3f7d4ed919498d5e5421deeff37cd95bdebb88558f79ac8254"
VALIDITY_SHA = "cb936a2f1b560f613f6d3be9acaf5a4a771155aa4c5abfb1ccb809969ce416f1"
MANIFEST_SHA = "ddcf9619bf8d5ecec26e0ce71486c2c1617629034cf2d464c3214637c2ad89b3"


def verify_before_network() -> dict[str, Any]:
    freeze.verify()
    if base.prior.all_file_root(freeze.OUT, freeze.ROOT_MARKER) != AMEND_ROOT:
        raise RuntimeError("alpha3.18A.4 root mismatch")
    if (freeze.OUT / freeze.ROOT_MARKER).read_text().strip() != AMEND_ROOT:
        raise RuntimeError("alpha3.18A.4 root marker mismatch")
    path = freeze.OUT / "alpha3_18a4_source_acquisition_execution_manifest_v2.json"
    if base.sha(path.read_bytes()) != MANIFEST_SHA or (
        freeze.OUT / "alpha3_18a4_source_acquisition_execution_manifest_v2_sha256").read_text().strip() != MANIFEST_SHA:
        raise RuntimeError("V2 manifest mismatch")
    query_path = freeze.OUT / "source_query_set_v2.jsonl"
    if base.sha(query_path.read_bytes()) != QUERY_SHA or (
        freeze.OUT / "source_query_set_v2_sha256").read_text().strip() != QUERY_SHA:
        raise RuntimeError("V2 query set mismatch")
    if (freeze.OUT / "pubmed_esearch_response_validity_v2_sha256").read_text().strip() != VALIDITY_SHA:
        raise RuntimeError("V2 validator root mismatch")
    rows = [json.loads(line) for line in query_path.read_bytes().splitlines()]
    if len(rows) != 6 or [row["stratum_id"] for row in rows] != base.STRATA:
        raise RuntimeError("V2 query order mismatch")
    for index, row in enumerate(rows):
        if (row["stratum_order"] != index or row["query_utf8"].count(freeze.REPLACEMENT) != 1
            or freeze.INVALID in row["query_utf8"] or base.sha(row["query_utf8"].encode()) != row["query_sha256"]):
            raise RuntimeError("V2 query literal mismatch")
    manifest = json.loads(path.read_text(encoding="utf-8"))
    if manifest["queries"] != [{"stratum_id": r["stratum_id"], "stratum_order": r["stratum_order"],
                                 "query_utf8": r["query_utf8"], "query_sha256": r["query_sha256"]} for r in rows]:
        raise RuntimeError("V2 manifest query mismatch")
    if manifest["pubmed_esearch_response_validity_v2_sha256"] != VALIDITY_SHA:
        raise RuntimeError("V2 validator not bound by manifest")
    if manifest["active_source_frame_policy_v2"]["query_bytes_source"] != "source_query_set_v2.jsonl":
        raise RuntimeError("inactive V2 source query set")
    if manifest["network_scope"]["allowed_host"] != "eutils.ncbi.nlm.nih.gov":
        raise RuntimeError("NETWORK_SCOPE_VIOLATION")
    references: list[dict[str, str]] = []
    def walk(node: Any) -> None:
        if isinstance(node, dict):
            if "path" in node and "sha256" in node:
                references.append(node)
            for value in node.values():
                walk(value)
        elif isinstance(node, list):
            for value in node:
                walk(value)
    walk(manifest)
    for ref in references:
        file = ROOT / ref["path"]
        if not file.is_file() or base.sha(file.read_bytes()) != ref["sha256"]:
            raise RuntimeError("V2 manifest reference mismatch: " + ref["path"])
    if manifest["material_runtime_policy_unresolved_count"] != 0:
        raise RuntimeError("V2 manifest incomplete")
    return manifest


def write_json(name: str, value: Any) -> None:
    base.write_json(OUT / name, value)


def write_jsonl(name: str, rows: list[Any]) -> None:
    base.write_jsonl(OUT / name, rows)


def marker(name: str, value: str) -> None:
    base.write_bytes(OUT / name, (value + "\n").encode("ascii"))


def finalize(status: str, failure_code: str | None, counts: dict[str, Any],
             transport: base.Transport) -> str:
    write_jsonl("ncbi_transport_attempts.jsonl", transport.log)
    safety = {"builder_calls": 0, "quality_calls": 0, "deepseek_calls": 0,
        "openai_calls": 0, "llm_calls": 0, "non_ncbi_network_calls": 0,
        "ncbi_network_attempts": transport.calls, "historical_assets_modified": False,
        "scientific_propositions_generated": 0}
    complete = status == "PASS" and counts.get("source_frames_completed") == 6
    write_json("scientific_state_safety_audit.json", safety)
    write_json("validation.json", {"status": status, "failure_code": failure_code,
        "source_query_set_v2_verified": True, "source_query_changes": 0,
        "pubmed_pmc_subset_clause_verified": True, "network_scope_ncbi_only": True,
        "esearch_response_validity_v2_used": True,
        "esearch_errorlist_checked_before_count": True,
        "semantic_warning_policy_used": True,
        "source_frames_completed": counts["source_frames_completed"],
        "six_source_frames_frozen": complete,
        "sampling_after_all_frames": complete,
        "dynamic_source_replacement_used": False,
        "development_labels_used_for_source_selection": False,
        "all_source_eligibility_contracts_unchanged": True,
        "construction_source_manifest_frozen": complete and (OUT / "construction_source_manifest_sha256").exists(),
        "builder_request_manifest_frozen": complete and (OUT / "proposition_builder_v2_request_manifest_sha256").exists(),
        **safety})
    write_json("summary.json", {"status": "completed" if complete else "failed",
        "failure_code": failure_code, **counts,
        "next_stage_recommendation": "PREREGISTER_ALPHA3_18B_BUILDER_EXECUTION_AUTHORIZATION"
        if complete else "AUDIT_ALPHA3_18A_V2_RUNTIME_FAILURE_OFFLINE",
        "original_invalid_run_consumed": False, "builder_executed": False})
    root = base.root_hash()
    marker(ROOT_MARKER, root)
    return root


def run_v2(manifest: dict[str, Any], transport: base.Transport, counts: dict[str, Any]) -> None:
    queries = manifest["queries"]
    policy = manifest["active_source_frame_policy_v2"]
    requests = [{"stratum_id": query["stratum_id"], "query_sha256": query["query_sha256"],
        "page_retstart": offset, "endpoint": base.ES,
        "parameters": {"db": "pubmed", "retmode": "json", "sort": "relevance", "retmax": "50",
                       "retstart": str(offset), "term": query["query_utf8"]}}
        for query in queries for offset in policy["retstart_sequence"]]
    write_jsonl("source_query_request_manifest.jsonl", requests)
    frames: list[dict[str, Any]] = []
    query_results: list[dict[str, Any]] = []
    for query in queries:
        ordered_raw: list[str] = []
        pages: list[dict[str, Any]] = []
        for offset in policy["retstart_sequence"]:
            params = {"db": "pubmed", "retmode": "json", "sort": "relevance", "retmax": "50",
                      "retstart": str(offset), "term": query["query_utf8"]}
            key = f"{query['stratum_order']:02d}_{offset:03d}"
            raw, attempts = transport.get("SOURCE_FRAME_V2", key, base.ES, params,
                                          "source_query_raw_responses")
            if raw is None:
                verdict = {"state": "TRANSPORT_FAILURE", "reason": "TECHNICAL_RETRY_EXHAUSTED"}
            else:
                verdict = validity.validate_response(attempts[-1]["status"], raw, offset, 50)
            result = {"stratum_id": query["stratum_id"], "retstart": offset,
                "request_key": key, "query_sha256": query["query_sha256"],
                "attempts": attempts, "response_sha256": base.sha(raw) if raw is not None else None,
                "validity": verdict}
            query_results.append(result)
            if verdict["state"] not in validity.VALID_STATES:
                if verdict["state"] == "QUERY_SEMANTIC_ERROR":
                    counts["esearch_query_semantic_errors"] += 1
                if verdict["state"] == "QUERY_WARNING_UNRESOLVED":
                    counts["esearch_query_warning_failures"] += 1
                write_jsonl("source_query_execution_results.jsonl", query_results)
                raise RuntimeError("SOURCE_FRAME_ACQUISITION_FAILED_CLOSED:" + verdict["state"])
            ids = verdict["idlist"]
            count = verdict["count"]
            assert ids is not None and count is not None
            ordered_raw.extend(ids)
            pages.append({"retstart": offset, "count": count, "pmids": ids,
                "response_sha256": base.sha(raw), "validity": verdict, "attempts": attempts})
            if len(ids) < 50 or offset + len(ids) >= count:
                break
        seen: set[str] = set()
        ordered_unique = []
        for pmid in ordered_raw:
            if pmid not in seen:
                seen.add(pmid)
                ordered_unique.append(pmid)
        frame = {"stratum_id": query["stratum_id"], "query_sha256": query["query_sha256"],
            "raw_pmid_order": ordered_raw, "ordered_unique_pmids": ordered_unique,
            "page_records": pages, "status": "COMPLETE_VALID_V2"}
        base.write_json(OUT / "six_source_frame_manifests" /
            f"{query['stratum_order']:02d}_{query['stratum_id']}.json", frame)
        frames.append(frame)
        counts["source_frames_completed"] += 1
        counts["raw_source_records"] += len(ordered_raw)
        print(json.dumps({"stage": "source_frame_v2", "completed": counts["source_frames_completed"],
            "stratum": query["stratum_id"], "raw": len(ordered_raw),
            "unique": len(ordered_unique)}), flush=True)
    write_jsonl("source_query_execution_results.jsonl", query_results)
    frame_paths = sorted((OUT / "six_source_frame_manifests").glob("*.json"))
    marker("six_source_frames_sha256", base.sha(base.canonical(
        [[p.name, base.sha(p.read_bytes())] for p in frame_paths])))
    membership: dict[str, list[str]] = {}
    for frame in frames:
        for pmid in frame["ordered_unique_pmids"]:
            membership.setdefault(pmid, []).append(frame["stratum_id"])
    sampling_frame = []
    for frame in frames:
        stratum = frame["stratum_id"]
        for position, pmid in enumerate(frame["ordered_unique_pmids"]):
            if membership[pmid][0] == stratum:
                sampling_frame.append({"pmid": pmid, "owner_stratum": stratum,
                    "owner_frame_position": position, "all_strata": membership[pmid]})
    write_json("cross_stratum_duplicate_audit.json", {
        "raw_frame_records": counts["raw_source_records"],
        "canonical_unique_pmids": len(sampling_frame),
        "cross_stratum_duplicate_pmids": sum(len(value) > 1 for value in membership.values()),
        "earliest_stratum_owner": True, "all_memberships_preserved": True})
    write_jsonl("new_pool_source_sampling_frame.jsonl", sampling_frame)
    marker("new_pool_source_sampling_frame_sha256", base.sha(
        (OUT / "new_pool_source_sampling_frame.jsonl").read_bytes()))
    counts["deduplicated_source_records"] = len(sampling_frame)
    seed = base.prior.load(base.prior.SOURCE, "source_sampling_algorithm.json")["seed_sha256"]
    sampled = []
    for stratum in base.STRATA:
        owned = [row for row in sampling_frame if row["owner_stratum"] == stratum]
        keyed = [(base.sha(f"{seed}:{stratum}:{row['pmid']}".encode()), row) for row in owned]
        selected = sorted(keyed, key=lambda item: (bytes.fromhex(item[0]), int(item[1]["pmid"])))[:12]
        sampled.extend({**row, "sample_key_sha256": key, "sample_rank_in_stratum": index + 1}
                       for index, (key, row) in enumerate(selected))
    write_jsonl("deterministic_source_sampling_results.jsonl", sampled)
    write_json("source_sampling_summary.json", {"sample_count": len(sampled),
        "per_stratum": {s: sum(row["owner_stratum"] == s for row in sampled) for s in base.STRATA},
        "seed_sha256": seed, "no_replacement": True, "six_frame_barrier_passed": True})
    counts["sampled_source_count"] = len(sampled)
    print(json.dumps({"stage": "sampling_v2", "deduplicated": len(sampling_frame),
        "sampled": len(sampled)}), flush=True)
    base.finish_sampled_sources(manifest, transport, counts, sampled)


def main() -> None:
    if OUT.exists():
        raise RuntimeError("V2 run directory already exists; refusing rerun or overwrite")
    manifest = verify_before_network()
    OUT.mkdir()
    for name in ("source_query_raw_responses", "six_source_frame_manifests",
                 "sampled_metadata_raw_responses", "pmc_oa_raw_responses",
                 "construction_fulltext_raw_responses", "construction_evidence_documents",
                 "private_anchor_vault_source_tokens"):
        (OUT / name).mkdir()
    base.OUT = OUT
    base.ROOT_MARKER = ROOT_MARKER
    write_json("authoritative_v2_manifest_verification.json", {
        "alpha3_18a4_root_sha256": AMEND_ROOT, "query_set_v2_sha256": QUERY_SHA,
        "response_validity_v2_sha256": VALIDITY_SHA, "manifest_v2_sha256": MANIFEST_SHA,
        "all_manifest_references_verified_before_network": True,
        "original_invalid_run_consumed": False})
    transport = base.Transport(OUT, manifest["active_source_frame_policy_v2"])
    counts: dict[str, Any] = {"source_frames_completed": 0, "esearch_query_semantic_errors": 0,
        "esearch_query_warning_failures": 0, "raw_source_records": 0,
        "deduplicated_source_records": None, "sampled_source_count": None,
        "pmc_jats_requested": 0, "pmc_jats_success": 0, "pmc_jats_failed": 0,
        "construction_document_valid": 0, "construction_document_invalid": 0,
        "construction_document_unresolved": 0, "construction_source_count": None,
        "actual_builder_scientific_call_count": None,
        "builder_request_manifest_frozen": False, "builder_request_count": None}
    try:
        run_v2(manifest, transport, counts)
    except Exception as exc:
        failure = type(exc).__name__ + ":" + str(exc)
        root = finalize("FAILED_CLOSED", failure, counts, transport)
        print(json.dumps({"status": "failed_closed", "failure": failure,
            "run_root": root, **counts}, sort_keys=True), flush=True)
        return
    root = finalize("PASS", None, counts, transport)
    print(json.dumps({"status": "completed", "run_root": root, **counts}, sort_keys=True), flush=True)


if __name__ == "__main__":
    main()
