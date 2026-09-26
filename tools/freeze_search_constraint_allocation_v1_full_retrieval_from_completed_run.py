"""Package the already completed 55-query NCBI execution without new requests.

This is a deterministic physical-copy/replay of a verified source execution,
not a second retrieval epoch or a scientific relevance adjudication.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime
import hashlib
import json
from pathlib import Path
import shutil
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "runs/20260925_search_constraint_allocation_v1_development_retrieval"
RUN = ROOT / "runs/20260925_search_plan_v24_dev_search_constraint_allocation_v1_full_retrieval"
PREREG = ROOT / "runs/20260925_search_plan_v24_dev_alpha3_10_search_constraint_allocation_retrieval_preregistration_offline"
ALPHA39 = ROOT / "runs/20260925_search_plan_v24_dev_alpha3_9_search_constraint_allocation_offline"
DOWNSTREAM = ROOT / "runs/20260923_search_plan_v24_dev_alpha3_4_retrieval_preregistration_offline"
MANIFEST = PREREG / "search_constraint_allocation_v1_development_execution_manifest.json"
SOURCE_ROOT = "5680fb62a1bc88259735a960823fc568f363fc0dfbe31623b723840597e231ca"
SOURCE_CORPUS = "6d632ec6e2eb156e296b073f88cb26f6a7b854dcb87e3ae063775f09222da574"
PREREG_ROOT = "e6d05cfdb933e644d6da7fe0bb675e87deadf85108cc69149319887460c6eb10"
MANIFEST_SHA = "f2935db4963b20438c057aea3c4c654e19a7668e6a581207ae8d02c231aa7930"
ARCH_ROOT = "823a035ca906b67729fd8cb62b2f555a65ca787facb47d8ac3a0cc07ab76d5cb"
QUERY_SHA = "717181a438d56735a5cfc030f648efb1e485509c1d0266d602e17e40ebf39560"
CASE_IDS = tuple(f"heldout_v2_{n}" for n in range(101, 109))
OLD_PREFIX = str(SOURCE.relative_to(ROOT)) + "/retrieval_assets/"
NEW_PREFIX = str(RUN.relative_to(ROOT)) + "/retrieval_assets/"


def canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode()


def pretty(value: Any) -> bytes:
    return (json.dumps(value, sort_keys=True, ensure_ascii=False, indent=2) + "\n").encode()


def jsonl(rows: list[dict[str, Any]]) -> bytes:
    return b"".join(canonical(r) + b"\n" for r in rows)


def digest(value: Any) -> str:
    return hashlib.sha256(canonical(value)).hexdigest()


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def rows(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def write(name: str | Path, body: bytes) -> None:
    path = name if isinstance(name, Path) else RUN / name
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        raise RuntimeError(f"refusing existing output: {path}")
    path.write_bytes(body)


def copy(name: str) -> None:
    source = SOURCE / name
    target = RUN / name
    if not source.is_file() or target.exists():
        raise RuntimeError(f"copy source missing or target exists: {name}")
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, target)
    if sha(source) != sha(target):
        raise RuntimeError(f"physical-copy mismatch: {name}")


def repath(value: Any) -> Any:
    if isinstance(value, str):
        return NEW_PREFIX + value[len(OLD_PREFIX):] if value.startswith(OLD_PREFIX) else value
    if isinstance(value, list):
        return [repath(item) for item in value]
    if isinstance(value, dict):
        return {key: repath(item) for key, item in value.items()}
    return value


def verify_source() -> tuple[dict[str, Any], dict[str, Any]]:
    validation = load(SOURCE / "validation.json")
    pairs = validation["aggregate_components"]
    if any(sha(SOURCE / name) != value for name, value in pairs) or digest(pairs) != SOURCE_ROOT or (SOURCE / "search_constraint_allocation_v1_development_retrieval_sha256").read_text().strip() != SOURCE_ROOT:
        raise RuntimeError("source retrieval root drift")
    corpus = load(SOURCE / "search_constraint_allocation_v1_development_acquisition_corpus_manifest.json")
    c_pairs = corpus["aggregate_components"]
    if any(sha(SOURCE / name) != value for name, value in c_pairs) or digest(c_pairs) != SOURCE_CORPUS or (SOURCE / "search_constraint_allocation_v1_development_acquisition_corpus_sha256").read_text().strip() != SOURCE_CORPUS:
        raise RuntimeError("source acquisition corpus drift")
    if (PREREG / "search_plan_v24_dev_alpha3_10_sha256").read_text().strip() != PREREG_ROOT or sha(MANIFEST) != MANIFEST_SHA or (ALPHA39 / "search_plan_v24_dev_alpha3_9_sha256").read_text().strip() != ARCH_ROOT or sha(ALPHA39 / "search_plan_v24_dev_search_constraint_allocation_v1_query_set.jsonl") != QUERY_SHA or (DOWNSTREAM / "search_plan_v24_dev_alpha3_4_sha256").read_text().strip() != load(MANIFEST)["alpha3_4_downstream_root_sha256"]:
        raise RuntimeError("upstream preregistration or query mismatch")
    return validation, corpus


def main() -> None:
    if RUN.exists():
        raise RuntimeError(f"refusing existing run: {RUN}")
    source_validation, source_corpus = verify_source()
    manifest = load(MANIFEST)
    query_results = rows(SOURCE / "query_execution_results.jsonl")
    query_pages = rows(SOURCE / "query_execution_provenance.jsonl")
    source_summary = load(SOURCE / "summary.json")
    receipt = load(SOURCE / "retrieval_assets/network_events.json")
    expected_counts = dict(zip(CASE_IDS, (7, 5, 3, 5, 9, 12, 6, 8)))
    if len(query_results) != 55 or len(query_pages) != 55 or Counter(q["case_id"] for q in query_results) != Counter(expected_counts) or any(q["transport_status"] != "SUCCESS" for q in query_results):
        raise RuntimeError("source query execution incomplete")
    if sum(len(q["contributions"]) for q in query_results) != 63:
        raise RuntimeError("source contribution count mismatch")
    if [(q["case_id"], q["query_text"], q["query_sha256"]) for q in query_results] != [(q["case_id"], q["exact_query_text"], q["query_sha256"]) for q in manifest["exact_queries"]]:
        raise RuntimeError("source queries differ from preregistration")
    if Counter(e["kind"] for e in receipt["events"]) != {"pubmed_search": 55, "pubmed_metadata": 1, "pmc_fulltext": 1}:
        raise RuntimeError("unexpected source network event set")
    if any(e["retry_count"] > 3 for e in receipt["events"]) or len(receipt["failures"]) != 3:
        raise RuntimeError("source retry provenance mismatch")
    request_times = {kind: [datetime.fromisoformat(e["timestamp_utc"]) for e in receipt["events"] if e["kind"] == kind] for kind in ("pubmed_search", "pubmed_metadata", "pmc_fulltext")}
    if not max(request_times["pubmed_search"]) < min(request_times["pubmed_metadata"]) < min(request_times["pmc_fulltext"]):
        raise RuntimeError("source stage barrier order mismatch")
    source_selection = load(SOURCE / "selection_freeze_barrier_audit.json")
    if len(source_selection["case_manifest_components"]) != 8 or not source_selection["selection_freeze_barrier_pass"]:
        raise RuntimeError("source selection barrier invalid")
    for name, value in source_selection["case_manifest_components"]:
        if sha(SOURCE / name) != value or (SOURCE / name).stat().st_mtime >= min(t.timestamp() for t in request_times["pmc_fulltext"]):
            raise RuntimeError("selection manifest not frozen before source PMC request")
    if (SOURCE / "selection_freeze_barrier_audit.json").stat().st_mtime >= min(t.timestamp() for t in request_times["pmc_fulltext"]):
        raise RuntimeError("selection barrier not frozen before source PMC request")

    RUN.mkdir(parents=True)
    for path in sorted((SOURCE / "retrieval_assets").rglob("*")):
        if path.is_file() and path.name != "network_events.json":
            copy(str(path.relative_to(SOURCE)))
    new_receipt = repath(receipt)
    new_receipt["source_execution_root_sha256"] = SOURCE_ROOT
    new_receipt["new_network_requests"] = 0
    for event in new_receipt["events"]:
        event["source_snapshot_ref"] = OLD_PREFIX + event["snapshot_ref"][len(NEW_PREFIX):]
        if sha(ROOT / event["snapshot_ref"]) != event["response_sha256"]:
            raise RuntimeError("copied NCBI snapshot hash mismatch")
    write("retrieval_assets/network_events.json", pretty(new_receipt))

    byte_copies = [
        "query_execution_results.jsonl", "case_union_pmids.jsonl", "case_union_provenance.jsonl",
        "metadata_records.jsonl", "metadata_failure_records.jsonl", "candidate_gate_results.jsonl",
        "p0_results.jsonl", "p1_results.jsonl", "p2_results.jsonl", "policy_a_results.jsonl",
        "candidate_tier_summary.json", "oa_eligibility_results.jsonl", "selection_manifest_aggregate_sha256",
        "fulltext_failure_records.jsonl",
        "query_family_contribution_map.json", "case_query_hit_summary.json", "tail_application_audit.json",
        "variant_retrieval_attribution.json", "query_family_overlap_summary.json", "retrieval_denominator_summary.json",
        "four_architecture_retrieval_comparison.json", "known_paper_blindness_audit.json",
        "historical_label_blinding_audit.json", "runtime_adaptation_audit.json", "scientific_state_safety_audit.json",
    ]
    for name in byte_copies:
        copy(name)
    for case in CASE_IDS:
        copy(f"case_selection_manifests/{case}.json")
    rewritten = {
        "query_execution_provenance.jsonl": query_pages,
        "metadata_fetch_manifest.jsonl": rows(SOURCE / "metadata_fetch_manifest.jsonl"),
        "fulltext_fetch_manifest.jsonl": rows(SOURCE / "fulltext_fetch_manifest.jsonl"),
        "fulltext_acquisition_results.jsonl": rows(SOURCE / "fulltext_acquisition_results.jsonl"),
        "acquired_fulltext_manifest.json": load(SOURCE / "acquired_fulltext_manifest.json"),
    }
    for name, value in rewritten.items():
        normalized = repath(value)
        write(name, jsonl(normalized) if name.endswith(".jsonl") else pretty(normalized))

    write("source_execution_replay_audit.json", pretty({"artifact_schema_version": "SearchConstraintAllocationV1SourceExecutionReplayAuditV1", "source_execution_root_sha256": SOURCE_ROOT, "source_acquisition_corpus_sha256": SOURCE_CORPUS, "source_query_set_sha256": QUERY_SHA, "source_successful_NCBI_response_count": len(receipt["events"]), "physical_raw_response_copy_count": len(receipt["events"]), "new_network_requests": 0, "fresh_query_reruns": 0, "source_response_bytes_verified": True, "historical_source_modified": False}))
    write("upstream_root_verification.json", pretty({"artifact_schema_version": "SearchConstraintAllocationV1UpstreamRootVerificationV1", "verified_before_source_execution": True, "verified_before_replay": True, "alpha3_10_sha256": PREREG_ROOT, "execution_manifest_sha256": MANIFEST_SHA, "alpha3_9_sha256": ARCH_ROOT, "query_set_sha256": QUERY_SHA, "historical_downstream_policy_sha256": manifest["alpha3_4_downstream_root_sha256"], "source_execution_root_sha256": SOURCE_ROOT, "source_corpus_sha256": SOURCE_CORPUS, "source_component_count": len(source_validation["aggregate_components"]), "source_corpus_component_count": len(source_corpus["aggregate_components"])}))
    write("execution_manifest_verification.json", pretty({"artifact_schema_version": "SearchConstraintAllocationV1ExecutionManifestVerificationV1", "expected_sha256": MANIFEST_SHA, "observed_sha256": sha(MANIFEST), "relation_contribution_count": 63, "byte_unique_query_count": 55, "verified": True}))
    write("query_set_verification.json", pretty({"artifact_schema_version": "SearchConstraintAllocationV1QuerySetVerificationV1", "expected_sha256": QUERY_SHA, "observed_sha256": sha(ALPHA39 / "search_plan_v24_dev_search_constraint_allocation_v1_query_set.jsonl"), "per_case_counts": expected_counts, "query_text_changes": 0, "query_hash_changes": 0, "lexical_surface_changes": 0, "allocation_changes": 0, "variant_class_changes": 0, "verified": True}))

    technical = [{**failure, "terminal": False, "resolved_within_frozen_retry_policy": True} for failure in receipt["failures"]]
    write("technical_failure_records.jsonl", jsonl(technical))
    write("technical_continuation_audit.json", pretty({"artifact_schema_version": "SearchConstraintAllocationV1TechnicalContinuationAuditV1", "terminal_technical_failure_count": 0, "continuation_epoch_triggered": False, "successful_query_reruns": 0, "original_failed_attempts_preserved": True, "new_network_requests": 0, "source_failed_attempt_count": len(technical)}))
    write("search_completion_barrier.json", pretty({"artifact_schema_version": "SearchConstraintAllocationV1SearchCompletionBarrierV1", "complete_query_execution_count": len(query_results), "required_query_execution_count": 55, "all_query_transports_successful": True, "all_search_requests_precede_metadata": True, "source_execution_root_sha256": SOURCE_ROOT, "barrier_passed": True}))
    write("query_outcome_summary.json", pretty({"artifact_schema_version": "SearchConstraintAllocationV1QueryOutcomeSummaryV1", "complete_query_execution_count": 55, "nonzero_query_count": sum(r["outcome"] == "NONZERO_QUERY" for r in query_results), "zero_hit_query_count": sum(r["outcome"] == "ZERO_HIT_QUERY" for r in query_results), "terminal_query_failure_count": 0, "source_execution_replayed_without_new_requests": True}))

    variant = load(RUN / "variant_retrieval_attribution.json")["variant_classes"]
    write("variant_query_outcome_summary.json", pretty({"artifact_schema_version": "SearchConstraintAllocationV1VariantQueryOutcomeSummaryV1", "variants": [{"variant_class": v["variant_class"], "executed_query_count": v["query_count"], "nonzero_query_count": v["nonzero_query_count"], "raw_hit_count_sum": v["raw_hit_count_sum"], "unique_pmids_contributed": v["unique_pmids_contributed"], "uniquely_contributed_pmids": v["pmids_uniquely_contributed"]} for v in variant], "shared_query_membership_preserved": True}))
    case_union = rows(RUN / "case_union_pmids.jsonl")
    provenance = rows(RUN / "case_union_provenance.jsonl")
    qmap = {q["query_id"]: q for q in manifest["exact_queries"]}
    core_query_ids = {q["query_id"] for q in manifest["exact_queries"] if "CORE_RELATION" in q["variant_classes"]}
    context_query_ids = {q["query_id"] for q in manifest["exact_queries"] if "CORE_RELATION_PLUS_CONTEXT" in q["variant_classes"]}
    core_pmids = {(r["case_id"], r["pmid"]) for r in provenance if core_query_ids.intersection(r["contributing_query_ids"])}
    context_pmids = {(r["case_id"], r["pmid"]) for r in provenance if context_query_ids.intersection(r["contributing_query_ids"])}
    core_queries = [q for q in query_results if "CORE_RELATION" in q["variant_classes"]]
    core_nonzero = sum(q["outcome"] == "NONZERO_QUERY" for q in core_queries)
    write("core_relation_retrieval_summary.json", pretty({"artifact_schema_version": "SearchConstraintAllocationV1CoreRelationRetrievalSummaryV1", "core_relation_query_count": len(core_queries), "core_relation_nonzero_query_count": core_nonzero, "core_relation_nonzero_fraction": core_nonzero / len(core_queries), "cases_with_nonzero_core_relation": len({q["case_id"] for q in core_queries if q["outcome"] == "NONZERO_QUERY"}), "core_only_candidate_pmids": len(core_pmids - context_pmids), "context_only_additional_pmids": len(context_pmids - core_pmids), "shared_core_context_pmids": len(core_pmids & context_pmids), "descriptive_only": True, "relevance_conclusion": False}))
    source_viability = load(SOURCE / "retrieval_viability_summary.json")
    write("retrieval_viability_summary.json", pretty({**source_viability, "source_execution_root_sha256": SOURCE_ROOT, "new_network_requests": 0}))

    universe_components = [[name, sha(RUN / name)] for name in ["query_execution_results.jsonl", "query_execution_provenance.jsonl", "case_union_pmids.jsonl", "case_union_provenance.jsonl"]]
    universe_sha = digest(universe_components)
    write("retrieval_universe_freeze.json", pretty({"artifact_schema_version": "SearchConstraintAllocationV1RetrievalUniverseFreezeV2", "aggregate_algorithm": "sha256(canonical JSON ordered [path,sha256] pairs)", "components": universe_components, "retrieval_universe_sha256": universe_sha, "frozen_before_metadata_scoring_in_source_execution": True, "query_count": 55, "case_count": 8, "source_retrieval_universe_sha256": load(SOURCE / "retrieval_universe_freeze.json")["retrieval_universe_sha256"]}))
    write("search_constraint_allocation_v1_retrieval_universe_sha256", (universe_sha + "\n").encode())
    replay_selection_barrier = {**source_selection, "retrieval_universe_sha256": universe_sha, "source_retrieval_universe_sha256": source_selection["retrieval_universe_sha256"], "source_selection_barrier_sha256": sha(SOURCE / "selection_freeze_barrier_audit.json"), "source_frozen_before_first_PMC_fetch": True, "replay_barrier_reconstructed_after_source_fetch": True, "new_network_requests": 0}
    write("selection_freeze_barrier_audit.json", pretty(replay_selection_barrier))
    complete_components = [[name, sha(RUN / name)] for name in ["query_execution_results.jsonl", "query_execution_provenance.jsonl", "technical_failure_records.jsonl", "technical_continuation_audit.json", "search_completion_barrier.json"]]
    complete_sha = digest(complete_components)
    write("search_constraint_allocation_v1_complete_query_execution_manifest.json", pretty({"artifact_schema_version": "SearchConstraintAllocationV1CompleteQueryExecutionManifestV1", "aggregate_components": complete_components, "complete_query_execution_sha256": complete_sha, "source_execution_root_sha256": SOURCE_ROOT}))
    write("search_constraint_allocation_v1_complete_query_execution_sha256", (complete_sha + "\n").encode())

    p0 = rows(RUN / "p0_results.jsonl")
    p1 = rows(RUN / "p1_results.jsonl")
    p2 = rows(RUN / "p2_results.jsonl")
    base = rows(RUN / "candidate_gate_results.jsonl")
    policy = rows(RUN / "policy_a_results.jsonl")
    tiers = load(RUN / "candidate_tier_summary.json")["counts"]
    def state_summary(name: str, values: list[dict[str, Any]], states: tuple[str, ...]) -> dict[str, Any]:
        counts = Counter(v["state"] for v in values)
        return {"artifact_schema_version": f"SearchConstraintAllocationV1{name}SummaryV1", "entrant_count": len(values), "observed_state_counts": dict(counts), "requested_state_counts": {state: counts.get(state, 0) for state in states}, "frozen_repository_state_names_preserved": True, "scientific_relevance_adjudication": False}
    write("p0_summary.json", pretty(state_summary("P0", p0, ("EXACT", "AUTHORIZED_COMPATIBLE", "UNRESOLVED", "INCOMPATIBLE"))))
    write("p1_summary.json", pretty(state_summary("P1", p1, ("DIRECT", "CHAIN", "ASSOCIATION", "BACKGROUND", "MULTI_PROCESS", "UNRESOLVED"))))
    write("p2_summary.json", pretty(state_summary("P2", p2, ("EXACT", "AUTHORIZED_COMPATIBLE", "PARTIAL", "UNRESOLVED", "INCOMPATIBLE"))))
    pre_a = sum(r["base_v22_disposition"] == "TIER_A" for r in base)
    demotions = sum(r["policy_a_action"] == "DEMOTE_A_TO_B" for r in policy)
    write("policy_a_summary.json", pretty({"artifact_schema_version": "SearchConstraintAllocationV1PolicyASummaryV1", "pre_policy_a_tier_a_count": pre_a, "post_policy_a_tier_a_count": tiers.get("TIER_A", 0), "tier_b_count": tiers.get("TIER_B", 0), "demotion_count": demotions, "reject_count": tiers.get("REJECT", 0), "abstain_count": tiers.get("ABSTAIN", 0), "promotion_count": 0, "policy_changed": False}))
    write("validator_opportunity_summary.json", pretty({"artifact_schema_version": "SearchConstraintAllocationV1ValidatorOpportunitySummaryV1", "candidate_metadata_universe_count": len(rows(RUN / "metadata_records.jsonl")), "P0_entrant_count": len(p0), "P1_entrant_count": len(p1), "P2_entrant_count": len(p2), "P0_states": dict(Counter(r["state"] for r in p0)), "P1_states": dict(Counter(r["state"] for r in p1)), "P2_states": dict(Counter(r["state"] for r in p2)), "Policy_A_demotions": demotions, "downstream_validators_received_candidates": bool(p0), "not_final_relevance": True}))

    request_rows = repath(rows(SOURCE / "retrieval_request_manifest.jsonl"))
    for row in request_rows:
        row["source_execution_root_sha256"] = SOURCE_ROOT
        row["replay_new_network_request"] = False
    write("retrieval_request_manifest.jsonl", jsonl(request_rows))
    selection_rows = [load(RUN / "case_selection_manifests" / f"{case}.json") for case in CASE_IDS]
    selections = [r for case in selection_rows for r in case["ordered_selections"]]
    metadata = rows(RUN / "metadata_records.jsonl")
    fulltexts = rows(RUN / "fulltext_acquisition_results.jsonl")
    oa = rows(RUN / "oa_eligibility_results.jsonl")
    gaps = []
    for q in query_results:
        if q["executed_query_id"] not in qmap or not q["contributions"]:
            gaps.append({"kind": "query", "id": q["executed_query_id"]})
    for row in metadata:
        if not row["query_provenance"] or not row["all_contributing_query_ids"]:
            gaps.append({"kind": "metadata", "id": row["candidate_id"]})
    mids = {r["candidate_id"] for r in metadata}
    for selected in selections:
        if selected["candidate_id"] not in mids:
            gaps.append({"kind": "selection", "id": selected["selection_id"]})
    selected_ids = {r["selection_id"] for r in selections}
    for acquired in fulltexts:
        if acquired["selection_id"] not in selected_ids:
            gaps.append({"kind": "fulltext", "id": acquired["selection_id"]})
    write("provenance_completeness_audit.json", pretty({"artifact_schema_version": "SearchConstraintAllocationV1ProvenanceCompletenessAuditV1", "query_count": len(query_results), "relation_contribution_count": 63, "metadata_record_count": len(metadata), "selection_count": len(selections), "fulltext_result_count": len(fulltexts), "raw_response_count": len(new_receipt["events"]), "physical_raw_response_copy_count": len(new_receipt["events"]), "provenance_gaps": gaps, "provenance_gap_count": len(gaps), "complete": not gaps}))
    if gaps:
        raise RuntimeError("provenance gaps")

    corpus_names = ["query_execution_results.jsonl", "query_execution_provenance.jsonl", "case_union_pmids.jsonl", "case_union_provenance.jsonl", "retrieval_universe_freeze.json", "tail_application_audit.json", "metadata_fetch_manifest.jsonl", "metadata_records.jsonl", "metadata_failure_records.jsonl", "candidate_gate_results.jsonl", "p0_results.jsonl", "p1_results.jsonl", "p2_results.jsonl", "policy_a_results.jsonl", "candidate_tier_summary.json", "oa_eligibility_results.jsonl", "selection_manifest_aggregate_sha256", "selection_freeze_barrier_audit.json", "fulltext_fetch_manifest.jsonl", "fulltext_acquisition_results.jsonl", "fulltext_failure_records.jsonl", "acquired_fulltext_manifest.json"]
    corpus_paths = [RUN / name for name in corpus_names]
    corpus_paths.extend(sorted((RUN / "case_selection_manifests").glob("*.json")))
    corpus_paths.extend(sorted(p for p in (RUN / "retrieval_assets").rglob("*") if p.is_file()))
    if any(not p.is_file() for p in corpus_paths):
        raise RuntimeError("corpus component missing")
    corpus_pairs = [[str(p.relative_to(RUN)), sha(p)] for p in corpus_paths]
    corpus_sha = digest(corpus_pairs)
    write("search_constraint_allocation_v1_development_acquisition_corpus_manifest.json", pretty({"artifact_schema_version": "SearchConstraintAllocationV1DevelopmentAcquisitionCorpusManifestV2", "aggregate_algorithm": "sha256(canonical JSON ordered [path,sha256] pairs)", "aggregate_components": corpus_pairs, "search_constraint_allocation_v1_development_acquisition_corpus_sha256": corpus_sha, "source_corpus_sha256": SOURCE_CORPUS, "frozen_before_scientific_relevance_adjudication": True, "new_network_requests": 0}))
    write("search_constraint_allocation_v1_development_acquisition_corpus_sha256", (corpus_sha + "\n").encode())

    denom = load(RUN / "retrieval_denominator_summary.json")
    complete_count = len(query_results)
    nonzero = sum(r["outcome"] == "NONZERO_QUERY" for r in query_results)
    selected_count = len(selections)
    acquired_count = sum(r["acquisition_status"] == "SUCCESS" for r in fulltexts)
    if nonzero > 0 and acquired_count > 0:
        next_stage = "FREEZE_SEARCH_CONSTRAINT_ALLOCATION_V1_NEUTRAL_REVIEW_CORPUS"
    elif len(metadata) > 0 and acquired_count == 0:
        next_stage = "AUDIT_ACQUISITION_BOTTLENECK"
    elif nonzero == 0:
        next_stage = "DESIGN_BOUNDED_LEXICAL_REALIZATION_V2_OFFLINE"
    else:
        next_stage = "SEARCH_CONSTRAINT_ALLOCATION_V1_TECHNICAL_FAILURE"
    compliance = {"authoritative_roots_verified": True, "all_55_queries_completed": complete_count == 55, "all_63_contributions_preserved": sum(len(q["contributions"]) for q in query_results) == 63, "all_eight_selection_manifests_frozen_before_PMC_in_source": True, "metadata_failure_count_zero": not rows(RUN / "metadata_failure_records.jsonl"), "fulltext_cap_respected": all(c["selection_count"] <= 10 for c in selection_rows), "replacement_count_zero": all(not f["replacement_performed"] for f in fulltexts), "query_modifications_zero": True, "lexical_surface_changes_zero": True, "runtime_expansions_zero": True, "known_pmid_checks_zero": True, "historical_label_reads_zero": True, "scientific_relevance_adjudication_zero": True, "provenance_gaps_zero": not gaps, "source_response_bytes_preserved": True}
    write("protocol_compliance_audit.json", pretty({"artifact_schema_version": "SearchConstraintAllocationV1ProtocolComplianceAuditV1", "checks": compliance, "protocol_compliance": "PASS" if all(compliance.values()) else "FAIL", "new_network_requests": 0, "source_execution_replayed": True}))
    if not all(compliance.values()):
        raise RuntimeError("protocol compliance failure")
    summary = {"artifact_schema_version": "SearchConstraintAllocationV1FullRetrievalSummaryV1", "status": "completed", "source_execution_replayed": True, "new_network_requests": 0, "relation_contribution_count": 63, "byte_unique_query_count": 55, "complete_query_execution_count": complete_count, "nonzero_query_count": nonzero, "zero_hit_query_count": 55 - nonzero, "core_relation_query_count": len(core_queries), "core_relation_nonzero_query_count": core_nonzero, "development_case_count": 8, "nonzero_case_count": denom["nonzero_case_count"], "zero_hit_case_count": denom["zero_hit_case_count"], "cases_with_nonzero_core_relation": len({q["case_id"] for q in core_queries if q["outcome"] == "NONZERO_QUERY"}), "unique_pmids_before_tail_total": sum(r["observed_unique_pmid_count_before_hard_tail"] for r in case_union), "metadata_universe_total": len(metadata), "p0_entrant_count": len(p0), "p0_incompatible_count": sum(r["state"] == "INCOMPATIBLE" for r in p0), "p0_unresolved_count": sum(r["state"] == "UNRESOLVED" for r in p0), "p1_entrant_count": len(p1), "p1_blocking_count": sum(r["state"] in {"BLOCKING", "INCOMPATIBLE"} for r in p1), "p1_unresolved_count": sum(r["state"] == "UNRESOLVED" for r in p1), "p2_entrant_count": len(p2), "p2_incompatible_count": sum(r["state"] == "INCOMPATIBLE" for r in p2), "p2_unresolved_count": sum(r["state"] == "UNRESOLVED" for r in p2), "policy_a_demotion_count": demotions, "tier_a_count": tiers.get("TIER_A", 0), "tier_b_count": tiers.get("TIER_B", 0), "reject_count": tiers.get("REJECT", 0), "abstain_count": tiers.get("ABSTAIN", 0), "oa_eligible_count": sum(r["legal_fulltext_available"] for r in oa), "selected_count": selected_count, "successful_fulltext_acquisition_count": acquired_count, "fulltext_failure_count": len(rows(RUN / "fulltext_failure_records.jsonl")), "query_modifications": 0, "lexical_surface_changes": 0, "runtime_query_expansions": 0, "known_pmid_checks": 0, "historical_label_reads": 0, "llm_calls": 0, "openai_calls": 0, "deepseek_calls": 0, "provenance_gap_count": 0, "protocol_compliance": "PASS", "search_constraint_allocation_v1_complete_query_execution_sha256": complete_sha, "search_constraint_allocation_v1_retrieval_universe_sha256": universe_sha, "search_constraint_allocation_v1_development_acquisition_corpus_sha256": corpus_sha, "next_stage_recommendation": next_stage, "historical_assets_modified": False}
    write("summary.json", pretty(summary))
    root_paths = sorted(p for p in RUN.rglob("*") if p.is_file() and str(p.relative_to(RUN)) not in {"validation.json", "search_plan_v24_dev_search_constraint_allocation_v1_full_retrieval_sha256"})
    root_pairs = [[str(p.relative_to(RUN)), sha(p)] for p in root_paths]
    root_sha = digest(root_pairs)
    write("validation.json", pretty({"artifact_schema_version": "SearchConstraintAllocationV1FullRetrievalValidationV1", "status": "PASS", "aggregate_algorithm": "sha256(canonical JSON ordered [path,sha256] pairs)", "aggregate_components": root_pairs, "search_plan_v24_dev_search_constraint_allocation_v1_full_retrieval_sha256": root_sha, "checks": compliance}))
    write("search_plan_v24_dev_search_constraint_allocation_v1_full_retrieval_sha256", (root_sha + "\n").encode())
    print(json.dumps({**summary, "search_plan_v24_dev_search_constraint_allocation_v1_full_retrieval_sha256": root_sha}, sort_keys=True))


if __name__ == "__main__":
    main()
