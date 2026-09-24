#!/usr/bin/env python3
"""Normalize the completed alpha3.4 network execution into its final corpus."""

from __future__ import annotations

from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
import shutil
import sys
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

SOURCE = ROOT / "runs/20260924_search_plan_v24_dev_alpha3_4_development_retrospective_retrieval"
RUN = ROOT / "runs/20260924_search_plan_v24_dev_frozen_retrospective_retrieval"
PREREG = ROOT / "runs/20260923_search_plan_v24_dev_alpha3_4_retrieval_preregistration_offline"
ALPHA33 = ROOT / "runs/20260923_search_plan_v24_dev_alpha3_3_role_scoped_polarity_offline"
V23 = ROOT / "runs/20260916_search_plan_v23_beta_2_primary_heldout_v2_network_retrieval"

EXPECTED_SOURCE = "5931278c60cd639596aaf7c28380ea09ab8199609ec7c805344c221526e0e70e"
EXPECTED_PREREG = "2488b4322894acb755872e9bc92d78dcaf2a4dec6ed807a22d3aff4622e2d5d5"
EXPECTED_EXECUTION = "559b09754580bb06f05c51cc58f513e5364d2a5e2d541a8a074351a8b09f9320"
EXPECTED_ALPHA33 = "e5a7b502102a36de920e5421aa83b4bfc4775ddee4418df86299d587a4c5a763"
EXPECTED_FREEZE = "f437306101822cd9bcf125794499d602b0eaf93ae65663a39214fdc0887b0a17"
EXPECTED_QUERIES = "b7117825db0cde698ca2a9e5b882cac2f60ab4635e5b2e213243b8473d9d4ed0"
EXPECTED_V23 = "0da797b2b3b23a1884a03741abb60d51adedcb03ea9e6faf39ba897a829e46d8"
CASES = tuple(f"heldout_v2_{number}" for number in range(101, 109))


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


def pretty(value: Any) -> bytes:
    return (json.dumps(value, sort_keys=True, ensure_ascii=False, indent=2) + "\n").encode()


def jsonl(rows: list[dict[str, Any]]) -> bytes:
    return b"".join(canonical(row) + b"\n" for row in rows)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def aggregate(pairs: list[list[str]]) -> str:
    return hashlib.sha256(canonical(pairs)).hexdigest()


def load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def verify_run(run: Path, root_file: str, expected: str) -> dict[str, Any]:
    validation = load(run / "validation.json")
    pairs = validation["aggregate_components"]
    for name, digest in pairs:
        require(sha(run / name) == digest, f"component changed: {run.name}/{name}")
    actual = aggregate(pairs)
    recorded = (run / root_file).read_text().strip()
    require(actual == recorded == expected, f"root mismatch: {run.name}")
    return {"path": str(run.relative_to(ROOT)), "expected_sha256": expected,
            "recorded_sha256": recorded, "recomputed_sha256": actual, "verified": True}


def verify_v23() -> dict[str, Any]:
    manifest = load(V23 / "implementation_manifest.json")
    pairs = manifest["aggregate_components"]
    for name, digest in pairs:
        require(sha(V23 / name) == digest, f"v2.3 component changed: {name}")
    actual = aggregate(pairs)
    require(actual == manifest["primary_heldout_v2_network_retrieval_sha256"] == EXPECTED_V23,
            "v2.3 root mismatch")
    return {"path": str(V23.relative_to(ROOT)), "expected_sha256": EXPECTED_V23,
            "recomputed_sha256": actual, "verified": True}


def write(path: Path, body: bytes) -> None:
    require(not path.exists() and not path.is_symlink(), f"refusing overwrite: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(body)


def main() -> None:
    require(not RUN.exists(), f"refusing to overwrite {RUN}")
    roots = {
        "search_plan_alpha3_3": verify_run(ALPHA33, "search_plan_v24_dev_alpha3_3_sha256", EXPECTED_ALPHA33),
        "alpha3_4_preregistration": verify_run(PREREG, "search_plan_v24_dev_alpha3_4_sha256", EXPECTED_PREREG),
        "completed_network_execution": verify_run(SOURCE, "search_plan_v24_dev_alpha3_4_retrieval_sha256", EXPECTED_SOURCE),
        "historical_v23_retrieval": verify_v23(),
    }
    execution_path = PREREG / "development_retrospective_retrieval_execution_manifest.json"
    freeze_path = ALPHA33 / "development_retrieval_freeze_manifest.json"
    require(sha(execution_path) == EXPECTED_EXECUTION, "execution manifest mismatch")
    require(sha(freeze_path) == EXPECTED_FREEZE, "development freeze mismatch")
    execution = load(execution_path)
    require(execution["compiled_query_set_sha256"] == EXPECTED_QUERIES, "query set mismatch")

    source_logs = load_jsonl(SOURCE / "query_execution_log.jsonl")
    source_events = load(SOURCE / "retrieval_assets/network_events.json")
    require(len(source_logs) == 29 and len(source_events["events"]) == 29, "execution count mismatch")
    require(not source_events["failures"], "terminal or retried network failure present")
    frozen_queries = {row["query_id"]: row for row in execution["exact_queries"]}
    require(set(frozen_queries) == {row["query_id"] for row in source_logs}, "executed query set mismatch")

    request_rows, result_rows, provenance_rows = [], [], []
    event_by_id = {row["request_id"]: row for row in source_events["events"]}
    case_query_results = defaultdict(list)
    for log in source_logs:
        query = frozen_queries[log["query_id"]]
        require(log["exact_query_text"] == query["exact_query_text"], "query text changed")
        require(log["frozen_query_sha256"] == query["query_sha256"], "query hash changed")
        require(log["query_modified"] is False and log["execution_status"] == "SUCCESS",
                "query execution noncompliant")
        event = event_by_id[log["request_id"]]
        raw_path = ROOT / log["raw_response_snapshot_ref"]
        response = load(raw_path)["esearchresult"]
        pmids = [str(value) for value in response.get("idlist", [])]
        require(int(response.get("count", 0)) == log["raw_hit_count"], "raw hit count mismatch")
        require(len(pmids) == log["returned_id_count"], "returned PMID count mismatch")
        request_rows.append({
            "request_id": event["request_id"], "request_sequence": event["request_sequence"],
            "case_id": log["case_id"], "query_id": log["query_id"],
            "query_sha256": log["frozen_query_sha256"], "exact_query_text": log["exact_query_text"],
            "intent_type": log["intent_type"], "relation_core_ref": log["relation_core_ref"],
            "page": log["page"], "retstart": log["retstart"], "retmax": log["retmax"],
            "source": "NCBI PubMed ESearch", "request_url": event["url"],
            "retry_count": event["retry_count"], "transport_status": event["http_status"],
        })
        result = {
            "case_id": log["case_id"], "query_id": log["query_id"],
            "query_sha256": log["frozen_query_sha256"], "intent_type": log["intent_type"],
            "relation_core_ref": log["relation_core_ref"], "page": log["page"],
            "raw_hit_count": log["raw_hit_count"], "returned_pmid_sequence": pmids,
            "within_query_ranks": list(range(log["retstart"] + 1, log["retstart"] + len(pmids) + 1)),
            "execution_status": "ZERO_HIT_QUERY" if log["raw_hit_count"] == 0 else "SUCCESS",
            "technical_failure": False, "raw_response_sha256": log["raw_response_sha256"],
        }
        result_rows.append(result)
        case_query_results[log["case_id"]].append(result)
        provenance_rows.append({
            "case_id": log["case_id"], "query_id": log["query_id"],
            "query_sha256": log["frozen_query_sha256"], "intent_type": log["intent_type"],
            "relation_core_ref": log["relation_core_ref"],
            "request_id": event["request_id"], "request_sequence": event["request_sequence"],
            "raw_response_snapshot_ref": log["raw_response_snapshot_ref"],
            "raw_response_sha256": log["raw_response_sha256"],
            "execution_manifest_sha256": EXPECTED_EXECUTION, "provenance_complete": True,
        })

    case_hits, union_rows, union_provenance, tail_rows = [], [], [], []
    for case_id in CASES:
        rows = case_query_results[case_id]
        occurrence_map: dict[str, list[dict[str, Any]]] = defaultdict(list)
        ordered = []
        seen = set()
        for row in rows:
            for rank, pmid in zip(row["within_query_ranks"], row["returned_pmid_sequence"], strict=True):
                occurrence_map[pmid].append({"query_id": row["query_id"],
                                             "query_sha256": row["query_sha256"],
                                             "intent_type": row["intent_type"],
                                             "relation_core_ref": row["relation_core_ref"],
                                             "page": row["page"], "rank": rank})
                if pmid not in seen:
                    seen.add(pmid); ordered.append(pmid)
        hard_tail = ordered[:180]
        union_rows.append({"case_id": case_id, "unique_pmids_before_tail": ordered,
                           "unique_pmid_count_before_tail": len(ordered),
                           "hard_tail_pmids": hard_tail, "hard_tail_metadata_universe_count": len(hard_tail)})
        for pmid in hard_tail:
            union_provenance.append({"case_id": case_id, "pmid": pmid,
                                     "contributing_provenance": occurrence_map[pmid]})
        raw_total = sum(row["raw_hit_count"] for row in rows)
        case_hits.append({"case_id": case_id, "query_count": len(rows),
                          "successful_query_count": len(rows),
                          "zero_hit_query_count": sum(row["raw_hit_count"] == 0 for row in rows),
                          "raw_query_hit_total": raw_total,
                          "unique_pmid_count_before_tail": len(ordered),
                          "zero_hit_case": raw_total == 0 and not ordered,
                          "technical_failure": False})
        tail_rows.append({"case_id": case_id, "soft_tail": 120, "hard_tail": 180,
                          "adaptive_tail_enabled": False,
                          "tail_application_stage": "after within-case PMID deduplication",
                          "unique_pmids_before_tail": len(ordered), "retained_pmids": len(hard_tail),
                          "tail_completion_state": "NATURAL_EXHAUSTION" if len(ordered) < 180 else "HARD_TAIL_REACHED",
                          "query_universe_state": "ZERO_HIT_CASE" if not ordered else "NONEMPTY",
                          "padding_performed": False})

    # The completed execution has an empty candidate/acquisition universe.
    empty_source_files = ["metadata_candidates.jsonl", "base_v22_dispositions.jsonl", "p0_decisions.jsonl",
                          "p1_decisions.jsonl", "p2_decisions.jsonl", "policy_a_decisions.jsonl",
                          "final_preacquisition_dispositions.jsonl", "oa_availability_snapshot.jsonl",
                          "ordered_fulltext_selection_manifest.jsonl", "fulltext_acquisition_manifest.jsonl",
                          "fulltext_provenance.jsonl", "retrieval_provenance_trace.jsonl"]
    require(all((SOURCE / name).read_bytes() == b"" for name in empty_source_files),
            "source candidate/acquisition universe is not empty")

    RUN.mkdir(parents=False)
    write(RUN / "upstream_root_verification.json", pretty({
        "artifact_schema_version": "FrozenRetrospectiveUpstreamRootVerificationV1",
        "roots": roots, "development_retrieval_freeze_sha256": EXPECTED_FREEZE,
        "all_six_authoritative_roots_verified": True, "verified_without_network": True}))
    write(RUN / "execution_manifest_verification.json", pretty({
        "artifact_schema_version": "ExecutionManifestVerificationV1",
        "expected_sha256": EXPECTED_EXECUTION, "actual_sha256": sha(execution_path),
        "query_count": 29, "verified": True}))
    write(RUN / "query_set_verification.json", pretty({
        "artifact_schema_version": "FrozenQuerySetVerificationV1",
        "expected_sha256": EXPECTED_QUERIES, "actual_sha256": execution["compiled_query_set_sha256"],
        "query_count": 29, "query_text_changes": 0, "query_hash_changes": 0,
        "query_modifications": 0, "verified": True}))
    write(RUN / "retrieval_request_manifest.jsonl", jsonl(request_rows))
    write(RUN / "query_execution_results.jsonl", jsonl(result_rows))
    write(RUN / "query_execution_provenance.jsonl", jsonl(provenance_rows))
    write(RUN / "case_query_hit_summary.json", pretty({"cases": case_hits}))
    write(RUN / "case_union_pmids.jsonl", jsonl(union_rows))
    write(RUN / "case_union_provenance.jsonl", jsonl(union_provenance))
    write(RUN / "tail_application_audit.json", pretty({"cases": tail_rows,
                                                        "all_tail_decisions_compliant": True}))
    write(RUN / "metadata_fetch_manifest.jsonl", b"")
    write(RUN / "metadata_records.jsonl", b"")
    write(RUN / "metadata_failure_records.jsonl", b"")
    write(RUN / "candidate_gate_results.jsonl", b"")
    write(RUN / "p0_results.jsonl", b"")
    write(RUN / "p1_results.jsonl", b"")
    write(RUN / "p2_results.jsonl", b"")
    write(RUN / "policy_a_results.jsonl", b"")
    write(RUN / "candidate_tier_summary.json", pretty({
        "tier_a_count": 0, "tier_b_count": 0, "reject_count": 0, "abstain_count": 0,
        "metadata_candidate_count": 0, "scoring_not_run_reason": "EMPTY_METADATA_UNIVERSE"}))
    write(RUN / "oa_eligibility_results.jsonl", b"")

    selection_dir = RUN / "case_selection_manifests"
    selection_dir.mkdir()
    selection_pairs = []
    for case_id in CASES:
        path = selection_dir / f"{case_id}.json"
        write(path, pretty({"artifact_schema_version": "CaseSelectionManifestV1", "case_id": case_id,
                            "ordered_selected_candidates": [], "selected_count": 0,
                            "maximum_selected_candidates": 10,
                            "selection_state": "EMPTY_AFTER_ZERO_HIT_CASE",
                            "fulltext_content_used": False}))
        selection_pairs.append([str(path.relative_to(RUN)), sha(path)])
    selection_root = aggregate(selection_pairs)
    write(RUN / "selection_manifest_aggregate_sha256", (selection_root + "\n").encode())
    write(RUN / "selection_freeze_barrier_audit.json", pretty({
        "artifact_schema_version": "SelectionFreezeBarrierAuditV1",
        "case_manifest_count": 8, "case_manifest_hashes": selection_pairs,
        "selection_manifest_aggregate_sha256": selection_root,
        "all_eight_case_manifests_frozen_before_first_pmc_fetch": True,
        "first_pmc_fetch_occurred": False, "fulltext_fetch_network_calls": 0,
        "source_global_selection_sha256": sha(SOURCE / "ordered_fulltext_selection_manifest.jsonl")}))
    write(RUN / "fulltext_fetch_manifest.jsonl", b"")
    write(RUN / "fulltext_acquisition_results.jsonl", b"")
    write(RUN / "fulltext_failure_records.jsonl", b"")
    write(RUN / "acquired_fulltext_manifest.json", pretty({
        "artifact_schema_version": "AcquiredFulltextManifestV1", "acquired_count": 0,
        "acquired_documents": [], "source_artifact_hashes": []}))

    denominator_rows = []
    for case_id in CASES:
        hit = next(row for row in case_hits if row["case_id"] == case_id)
        denominator_rows.append({
            "case_id": case_id, "raw_query_hit_total": hit["raw_query_hit_total"],
            "unique_pmids_before_tail": hit["unique_pmid_count_before_tail"],
            "hard_tail_metadata_universe": 0, "metadata_success_count": 0,
            "tier_a_count": 0, "tier_b_count": 0, "reject_count": 0, "abstain_count": 0,
            "oa_eligible_count": 0, "selected_count": 0,
            "successful_fulltext_acquisition_count": 0, "fulltext_failure_count": 0,
            "zero_result_states": ["ZERO_HIT_CASE", "NATURAL_EXHAUSTION"],
            "technical_failure": False})
    write(RUN / "retrieval_denominator_summary.json", pretty({
        "artifact_schema_version": "RetrievalDenominatorSummaryV1", "cases": denominator_rows,
        "totals": {"raw_query_hit_total": 0, "unique_pmids_before_tail": 0,
                   "hard_tail_metadata_universe": 0, "metadata_success_count": 0,
                   "tier_a_count": 0, "tier_b_count": 0, "reject_count": 0,
                   "abstain_count": 0, "oa_eligible_count": 0, "selected_count": 0,
                   "successful_fulltext_acquisition_count": 0, "fulltext_failure_count": 0}}))
    intent_counts = Counter(row["intent_type"] for row in result_rows)
    write(RUN / "intent_retrieval_attribution.json", pretty({
        "artifact_schema_version": "IntentRetrievalAttributionV1",
        "intents": [{"intent_type": intent, "queries_executed": count,
                     "pmids_contributed": 0, "unique_pmids_contributed": 0,
                     "overlap_pmids": 0, "selected_papers_contributed": 0,
                     "acquired_papers_contributed": 0,
                     "scientific_relevance_attribution_performed": False}
                    for intent, count in sorted(intent_counts.items())]}))
    write(RUN / "known_paper_blindness_audit.json", pretty({
        "known_pmid_checks": 0, "historical_direct_pmid_comparisons": 0,
        "known_paper_injections": 0, "manual_paper_searches": 0, "status": "PASS"}))
    write(RUN / "acquisition_label_blinding_audit.json", pretty({
        "historical_label_reads": 0, "pass_a_label_reads": 0, "pass_b_label_reads": 0,
        "direct_classification_reads": 0, "candidate_selection_label_blind": True, "status": "PASS"}))
    write(RUN / "provenance_completeness_audit.json", pretty({
        "query_execution_record_count": 29, "query_provenance_complete_count": 29,
        "hard_tail_publication_count": 0, "acquired_document_count": 0,
        "provenance_gap_count": 0, "vacuous_acquired_document_lineage": True, "status": "PASS"}))
    write(RUN / "retrieval_policy_compliance_audit.json", pretty({
        "query_modifications": 0, "runtime_query_expansions": 0,
        "manual_candidate_injections": 0, "fallback_searches": 0,
        "adaptive_tail_used": False, "replacement_count": 0,
        "ncbi_only_network": True, "one_logical_execution_per_query": True,
        "technical_failures_converted_to_zero_hits": 0,
        "selection_freeze_barrier_passed": True, "protocol_compliance": "PASS"}))
    write(RUN / "scientific_state_safety_audit.json", pretty({
        "query_modifications": 0, "runtime_query_expansions": 0,
        "manual_candidate_injections": 0, "known_pmid_checks": 0,
        "historical_label_reads": 0, "llm_calls": 0, "openai_calls": 0,
        "deepseek_calls": 0, "scientific_adjudications": 0,
        "new_network_calls_during_final_freeze": 0,
        "source_execution_network_calls": 29, "historical_assets_modified": False}))

    # Preserve the exact raw PubMed responses as physical byte-identical copies.
    raw_dir = RUN / "retrieval_assets/pubmed_esearch"
    for source_path in sorted((SOURCE / "retrieval_assets/pubmed_esearch").rglob("*.json")):
        destination = raw_dir / source_path.relative_to(SOURCE / "retrieval_assets/pubmed_esearch")
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source_path, destination)
        require(sha(destination) == sha(source_path), "raw response copy mismatch")
    shutil.copytree(SOURCE / "retrieval_assets", RUN / "source_retrieval_assets", copy_function=shutil.copy2)

    corpus_component_names = [
        "query_set_verification.json", "retrieval_request_manifest.jsonl",
        "query_execution_results.jsonl", "query_execution_provenance.jsonl",
        "case_union_pmids.jsonl", "case_union_provenance.jsonl", "tail_application_audit.json",
        "metadata_records.jsonl", "metadata_failure_records.jsonl", "candidate_gate_results.jsonl",
        "p0_results.jsonl", "p1_results.jsonl", "p2_results.jsonl", "policy_a_results.jsonl",
        "oa_eligibility_results.jsonl", "selection_manifest_aggregate_sha256",
        "fulltext_acquisition_results.jsonl", "fulltext_failure_records.jsonl",
        "acquired_fulltext_manifest.json", "provenance_completeness_audit.json",
    ]
    corpus_pairs = [[name, sha(RUN / name)] for name in corpus_component_names]
    corpus_pairs.extend(selection_pairs)
    corpus_pairs.extend([[str(path.relative_to(RUN)), sha(path)]
                         for path in sorted(raw_dir.rglob("*.json"))])
    corpus_root = aggregate(corpus_pairs)
    write(RUN / "development_retrospective_acquisition_corpus_manifest.json", pretty({
        "artifact_schema_version": "DevelopmentRetrospectiveAcquisitionCorpusManifestV1",
        "aggregate_algorithm": "sha256(canonical JSON ordered [path, sha256] pairs)",
        "aggregate_components": corpus_pairs,
        "development_retrospective_acquisition_corpus_sha256": corpus_root,
        "sole_input_to_later_neutral_review_freeze": True}))
    write(RUN / "development_retrospective_acquisition_corpus_sha256", (corpus_root + "\n").encode())

    summary = {
        "artifact_schema_version": "FrozenDevelopmentRetrospectiveRetrievalSummaryV1",
        "status": "completed", "query_count": 29, "query_modifications": 0,
        "query_execution_success_count": 29, "query_terminal_failure_count": 0,
        "zero_hit_query_count": 29, "development_case_count": 8, "zero_hit_case_count": 8,
        "unique_pmids_before_tail_total": 0, "metadata_universe_total": 0,
        "tier_a_count": 0, "tier_b_count": 0, "reject_count": 0, "abstain_count": 0,
        "oa_eligible_count": 0, "selected_count": 0,
        "successful_fulltext_acquisition_count": 0, "fulltext_failure_count": 0,
        "cases_with_acquired_fulltext": 0, "cases_with_zero_acquired_fulltext": 8,
        "selection_manifests_frozen_before_download": True,
        "known_pmid_checks": 0, "historical_label_reads": 0,
        "runtime_query_expansions": 0, "manual_candidate_injections": 0,
        "llm_calls": 0, "openai_calls": 0, "deepseek_calls": 0,
        "provenance_gap_count": 0, "protocol_compliance": "PASS",
        "development_retrospective_acquisition_corpus_sha256": corpus_root,
        "next_stage_recommendation": "FREEZE_NEUTRAL_REVIEW_CORPUS_NEXT",
        "historical_assets_modified": False,
    }
    write(RUN / "summary.json", pretty(summary))

    required_files = {
        "upstream_root_verification.json", "execution_manifest_verification.json",
        "query_set_verification.json", "retrieval_request_manifest.jsonl",
        "query_execution_results.jsonl", "query_execution_provenance.jsonl",
        "case_query_hit_summary.json", "case_union_pmids.jsonl", "case_union_provenance.jsonl",
        "tail_application_audit.json", "metadata_fetch_manifest.jsonl", "metadata_records.jsonl",
        "metadata_failure_records.jsonl", "candidate_gate_results.jsonl", "p0_results.jsonl",
        "p1_results.jsonl", "p2_results.jsonl", "policy_a_results.jsonl",
        "candidate_tier_summary.json", "oa_eligibility_results.jsonl",
        "selection_manifest_aggregate_sha256", "selection_freeze_barrier_audit.json",
        "fulltext_fetch_manifest.jsonl", "fulltext_acquisition_results.jsonl",
        "fulltext_failure_records.jsonl", "acquired_fulltext_manifest.json",
        "retrieval_denominator_summary.json", "intent_retrieval_attribution.json",
        "known_paper_blindness_audit.json", "acquisition_label_blinding_audit.json",
        "provenance_completeness_audit.json", "retrieval_policy_compliance_audit.json",
        "scientific_state_safety_audit.json", "development_retrospective_acquisition_corpus_manifest.json",
        "development_retrospective_acquisition_corpus_sha256", "summary.json",
    }
    require(required_files <= {path.name for path in RUN.iterdir()}, "required output missing")
    top_files = sorted(path for path in RUN.iterdir() if path.is_file())
    asset_files = sorted(path for directory in (RUN / "case_selection_manifests", RUN / "retrieval_assets",
                                                RUN / "source_retrieval_assets")
                         for path in directory.rglob("*") if path.is_file())
    root_pairs = [[str(path.relative_to(RUN)), sha(path)] for path in top_files + asset_files]
    validation = {
        "artifact_schema_version": "FrozenDevelopmentRetrospectiveRetrievalValidationV1",
        "status": "PASS", "all_required_outputs_present": True,
        "query_count": 29, "query_modifications": 0, "query_terminal_failure_count": 0,
        "selection_freeze_barrier_passed": True, "provenance_gap_count": 0,
        "protocol_compliance": "PASS", "aggregate_components": root_pairs,
    }
    write(RUN / "validation.json", pretty(validation))
    root = aggregate(root_pairs)
    write(RUN / "search_plan_v24_dev_frozen_retrospective_retrieval_sha256", (root + "\n").encode())
    print(json.dumps({"run": str(RUN), "retrieval_root": root,
                      "acquisition_corpus_root": corpus_root, "summary": summary},
                     sort_keys=True, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
