#!/usr/bin/env python3
"""Execute the frozen alpha3.12 55-query NCBI-only development run.

The alpha3.10 transport, candidate gates, ranking, selection and PMC routes
are reused unchanged. This adapter changes only the frozen query input and
reporting identity; it never plans, expands, adjudicates or repairs queries.
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

import tools.run_search_constraint_allocation_v1_development_retrieval as core
import tools.run_search_plan_v24_dev_alpha3_4_development_retrospective_retrieval as legacy
import tools.run_search_plan_v24_dev_retrieval_surface_v2_full_retrieval as surface


PREREG = ROOT / "runs/20260925_search_plan_v24_dev_alpha3_12_bounded_lexical_realization_v2_retrieval_preregistration_offline"
ALPHA311 = ROOT / "runs/20260925_search_plan_v24_dev_alpha3_11_bounded_lexical_realization_v2_offline"
ALPHA310 = ROOT / "runs/20260925_search_plan_v24_dev_alpha3_10_search_constraint_allocation_retrieval_preregistration_offline"
RUN = ROOT / "runs/20260925_bounded_lexical_realization_v2_development_retrieval"
ASSETS = RUN / "retrieval_assets"
MANIFEST_PATH = PREREG / "bounded_lexical_realization_v2_development_execution_manifest.json"
QUERY_PATH = ALPHA311 / "search_plan_v24_dev_bounded_lexical_realization_v2_query_set.jsonl"
OLD_MANIFEST_PATH = ALPHA310 / "search_constraint_allocation_v1_development_execution_manifest.json"
EXPECTED_PREREG = "b83bd10cc758c9cd751f5f0b3429a1208d68e70264823d4fa45d427335695343"
EXPECTED_MANIFEST = "bf768829eebd006a2239feb13fd1c4ae4ca58e903e93dca6f6de869f093ce1d9"
EXPECTED_ALPHA311 = "2a006173d4bc4c512631303b5ab29142c465a0ece2ab64c9382a604652a5b2ad"
EXPECTED_QUERY_SET = "6edd5be9b9cdc6d1bf522585c214aa524e716ff27b1f244dfb7ca8b99ab99cb9"
EXPECTED_ALPHA310 = "e6d05cfdb933e644d6da7fe0bb675e87deadf85108cc69149319887460c6eb10"
EXPECTED_CANONICAL = "b918c60ea7efdf7ea10758b6e84199f8c5c06e3718589afb85468263af7d63a7"
CASES = tuple(f"heldout_v2_{i}" for i in range(101, 109))
CASE_COUNTS = dict(zip(CASES, (7, 5, 3, 5, 9, 12, 6, 8)))


def canon(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()


def pretty(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode()


def jsonl(values: list[dict[str, Any]]) -> bytes:
    return b"".join(canon(value) + b"\n" for value in values)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def digest(value: Any) -> str:
    return hashlib.sha256(canon(value)).hexdigest()


def load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def rows(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def write(name: str, body: bytes) -> None:
    path = RUN / name
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        raise RuntimeError(f"refusing existing output: {path}")
    path.write_bytes(body)


def verify_root(run: Path, root_name: str, expected: str, *, validation: bool = True) -> int:
    if (run / root_name).read_text().strip() != expected:
        raise RuntimeError(f"root-file drift: {root_name}")
    if validation:
        pairs = load(run / "validation.json")["aggregate_components"]
    else:
        pairs = [[p.name, sha(p)] for p in sorted(run.iterdir()) if p.is_file() and p.name != root_name]
    if any(sha(run / name) != value for name, value in pairs) or digest(pairs) != expected:
        raise RuntimeError(f"component drift: {root_name}")
    return len(pairs)


def preflight() -> tuple[dict[str, Any], dict[str, Any], list[dict[str, Any]], list[dict[str, Any]], dict[str, dict[str, Any]]]:
    counts = {
        "alpha3_12_components": verify_root(PREREG, "search_plan_v24_dev_alpha3_12_sha256", EXPECTED_PREREG, validation=False),
        "alpha3_11_components": verify_root(ALPHA311, "search_plan_v24_dev_alpha3_11_sha256", EXPECTED_ALPHA311),
        "alpha3_10_components": verify_root(ALPHA310, "search_plan_v24_dev_alpha3_10_sha256", EXPECTED_ALPHA310, validation=False),
    }
    if sha(MANIFEST_PATH) != EXPECTED_MANIFEST or (PREREG / "bounded_lexical_realization_v2_development_execution_manifest_sha256").read_text().strip() != EXPECTED_MANIFEST:
        raise RuntimeError("execution manifest drift")
    if sha(QUERY_PATH) != EXPECTED_QUERY_SET or (ALPHA311 / "search_plan_v24_dev_bounded_lexical_realization_v2_query_set_sha256").read_text().strip() != EXPECTED_QUERY_SET:
        raise RuntimeError("query-set drift")
    manifest = load(MANIFEST_PATH)
    frozen_queries = rows(QUERY_PATH)
    if manifest["new_query_set_sha256"] != EXPECTED_QUERY_SET or manifest["alpha3_11_root_sha256"] != EXPECTED_ALPHA311 or manifest["alpha3_10_downstream_protocol_sha256"] != EXPECTED_ALPHA310 or manifest["canonical_scientific_corpus_sha256"] != EXPECTED_CANONICAL or manifest["execution_status"] != "NOT_EXECUTED_PREREGISTRATION" or manifest["observed_retrieval_values"] is not None:
        raise RuntimeError("manifest scope mismatch")
    if manifest["exact_queries"] != frozen_queries or len(frozen_queries) != 55 or sum(len(q["contributions"]) for q in frozen_queries) != 63 or Counter(q["case_id"] for q in frozen_queries) != Counter(CASE_COUNTS) or len({q["query_id"] for q in frozen_queries}) != 55:
        raise RuntimeError("frozen query family mismatch")
    if any(hashlib.sha256(q["query"].encode()).hexdigest() != q["query_sha256"] for q in frozen_queries):
        raise RuntimeError("query bytes differ from frozen SHA")
    if len(manifest["per_contribution_provenance"]) != 63 or manifest["query_present_set_source"] != "LexicalCoverageCertificateV2.role_alternatives":
        raise RuntimeError("lexical contribution provenance mismatch")
    if sha(PREREG / "query_pair_mapping.jsonl") != manifest["query_pair_mapping_sha256"] or sha(ALPHA311 / "lexical_alternative_sets.jsonl") != manifest["lexical_alternative_sets_sha256"] or sha(ALPHA311 / "lexical_coverage_certificates.jsonl") != manifest["lexical_coverage_certificates_sha256"]:
        raise RuntimeError("lexical authority artifact drift")
    for name, value in manifest["alpha3_12_policy_file_sha256"].items():
        if sha(PREREG / name) != value:
            raise RuntimeError(f"downstream policy drift: {name}")
    policy = load(PREREG / "query_execution_policy.json")
    retry = load(PREREG / "technical_retry_policy.json")
    continuation = load(PREREG / "technical_continuation_policy.json")
    tail = load(PREREG / "tail_policy.json")
    selection = load(PREREG / "selection_fulltext_policy.json")
    if policy["query_set_input_sha256"] != EXPECTED_QUERY_SET or policy["page_size"] != 30 or policy["pubmed_sort"] != "relevance" or retry["maximum_total_attempts"] != 4 or retry["timeout_seconds"] != 60 or retry["backoff_seconds"] != [2, 4, 8] or not continuation["preregistered_before_retrieval"] or tail["soft_tail"] != 120 or tail["hard_tail"] != 180 or tail["adaptive_tail_enabled"] or selection["maximum_fulltexts_per_case"] != 10 or not selection["all_eight_ordered_manifests_frozen_before_first_fetch"]:
        raise RuntimeError("frozen execution or acquisition policy mismatch")
    old_manifest = load(OLD_MANIFEST_PATH)
    old_contributions = {}
    for query in old_manifest["exact_queries"]:
        for c in query["contributions"]:
            key = (c["case_id"], c["surface_plan_id"], c["intent_type"], c["variant_class"])
            old_contributions[key] = c
    adapted = []
    for index, query in enumerate(frozen_queries, 1):
        contributions = []
        for c in query["contributions"]:
            key = (query["case_id"], c["surface_plan_id"], c["intent_type"], c["variant_class"])
            old = old_contributions.get(key)
            if old is None or old["relation_core_sha256"] != c["relation_core_sha256"] or old["target_sha256"] != manifest["target_sha256_by_case"][query["case_id"]]:
                raise RuntimeError("query-family adapter provenance mismatch")
            contributions.append({"case_id": query["case_id"], "surface_plan_id": c["surface_plan_id"], "query_family_id": old["query_family_id"], "intent_type": c["intent_type"], "variant_class": c["variant_class"], "relation_core_sha256": c["relation_core_sha256"], "query_ast_sha256": c["ast_sha256"], "lexical_coverage_certificate_sha256": c["lexical_coverage_certificate_sha256"]})
        adapted.append({"case_id": query["case_id"], "query_id": query["query_id"], "query_sha256": query["query_sha256"], "exact_query_text": query["query"], "execution_order": index, "variant_classes": sorted({c["variant_class"] for c in contributions}), "contributions": contributions})
    targets, bindings, old_queries = legacy.v23_frozen_inputs()
    targets_by_case = {r["case_id"]: r for r in targets}
    if tuple(sorted(targets_by_case)) != CASES or any(digest(targets_by_case[case]) != manifest["target_sha256_by_case"][case] for case in CASES):
        raise RuntimeError("frozen target hash mismatch")
    gate_queries: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for q in old_queries:
        gate_queries[q["case_id"]].append(q)
    gates = {case: legacy.gate_target(targets_by_case[case], bindings[case], gate_queries[case]) for case in CASES}
    verification = {"artifact_schema_version": "BoundedLexicalRealizationV2ExecutionPreflightV1", "verified_before_first_network_request": True, "alpha3_12_root_sha256": EXPECTED_PREREG, "execution_manifest_sha256": EXPECTED_MANIFEST, "alpha3_11_root_sha256": EXPECTED_ALPHA311, "query_set_sha256": EXPECTED_QUERY_SET, "alpha3_10_downstream_protocol_sha256": EXPECTED_ALPHA310, "canonical_scientific_corpus_sha256": EXPECTED_CANONICAL, "component_counts": counts, "relation_contribution_count": 63, "byte_unique_query_count": 55, "query_text_changes": 0, "downstream_policy_changes": 0, "target_hashes_verified": True, "lexical_authority_hashes_verified": True, "provider_calls": 0, "llm_calls": 0}
    return verification, manifest, adapted, targets, gates


def bind_pipeline() -> legacy.Network:
    core.RUN = RUN
    core.ASSETS = ASSETS
    legacy.RUN = RUN
    legacy.ASSETS = ASSETS
    surface.RUN = RUN
    surface.ASSETS = ASSETS
    return legacy.Network(True)


def rebind_adapter_reports() -> str:
    """Name this run's lexicalized results accurately before outer freeze."""
    comparison_path = RUN / "four_architecture_retrieval_comparison.json"
    comparison = load(comparison_path)
    comparison["architectures"][-1]["architecture"] = "SearchConstraintAllocationV1 + BoundedLexicalRealizationV2"
    comparison["reporting_adapter_rebound_before_outer_freeze"] = True
    comparison_path.write_bytes(pretty(comparison))
    summary_path = RUN / "summary.json"
    summary = load(summary_path)
    summary["artifact_schema_version"] = "BoundedLexicalRealizationV2DevelopmentRetrievalSummaryV1"
    summary["search_plan_v24_dev_alpha3_12_sha256"] = EXPECTED_PREREG
    summary["lexicalized_query_set_sha256"] = EXPECTED_QUERY_SET
    summary["reporting_adapter_rebound_before_outer_freeze"] = True
    summary_path.write_bytes(pretty(summary))
    validation_path = RUN / "validation.json"
    validation = load(validation_path)
    pairs = validation["aggregate_components"]
    changed = {"four_architecture_retrieval_comparison.json", "summary.json"}
    for pair in pairs:
        if pair[0] in changed:
            pair[1] = sha(RUN / pair[0])
    new_inner_root = digest(pairs)
    validation["aggregate_components"] = pairs
    validation["root_sha256"] = new_inner_root
    validation["reporting_adapter_rebound_before_outer_freeze"] = True
    validation_path.write_bytes(pretty(validation))
    (RUN / "search_constraint_allocation_v1_development_retrieval_sha256").write_text(new_inner_root + "\n")
    return new_inner_root


def freeze_alpha312_outputs(manifest: dict[str, Any], adapted: list[dict[str, Any]], network: legacy.Network, inner_root: str) -> dict[str, Any]:
    queries = rows(RUN / "query_execution_results.jsonl")
    case_stats = load(RUN / "case_query_hit_summary.json")["cases"]
    denominator = load(RUN / "retrieval_denominator_summary.json")
    variant = load(RUN / "variant_retrieval_attribution.json")
    if len(queries) != 55 or any(q["transport_status"] != "SUCCESS" for q in queries):
        raise RuntimeError("incomplete execution cannot freeze successful corpus")
    new_by_id = {q["query_id"]: q for q in adapted}
    old_mapping = rows(PREREG / "query_pair_mapping.jsonl")
    lexical_sets = {row["lexical_alternative_set_id"]: row for row in rows(ALPHA311 / "lexical_alternative_sets.jsonl")}
    pair_by_new = defaultdict(list)
    for row in old_mapping:
        pair_by_new[row["alpha311_query_id"]].append(row)
    attribution = []
    identical, changed = 0, 0
    for result in queries:
        query = new_by_id[result["executed_query_id"]]
        pairs = pair_by_new[query["query_id"]]
        states = {p["mapping_state"] for p in pairs}
        if states == {"BYTE_IDENTICAL"}:
            identical += 1
            state = "BYTE_IDENTICAL"
        elif states == {"LEXICALLY_CHANGED_ONLY"}:
            changed += 1
            state = "LEXICALLY_CHANGED_ONLY"
        else:
            raise RuntimeError("mixed or unmappable lexical query attribution")
        present_sets = {role: sorted({p["lexical_alternative_set_ids"][role] for p in pairs if role in p["lexical_alternative_set_ids"]}) for role in sorted({role for p in pairs for role in p["lexical_alternative_set_ids"]})}
        classes = sorted({item["authority_class"] for ids in present_sets.values() for identifier in ids for item in lexical_sets[identifier]["alternatives"]})
        attribution.append({"case_id": result["case_id"], "query_id": query["query_id"], "query_sha256": query["query_sha256"], "mapping_state": state, "query_present_lexical_alternative_set_ids": present_sets, "authority_classes_present": classes, "nonzero": result["outcome"] == "NONZERO_QUERY", "association_label": "associated_with_nonzero_retrieval_after_lexical_change" if state == "LEXICALLY_CHANGED_ONLY" and result["outcome"] == "NONZERO_QUERY" else None, "specific_alternative_causal_claim": False})
    write("lexical_query_attribution.jsonl", jsonl(attribution))
    write("lexical_attribution_summary.json", pretty({"artifact_schema_version": "BoundedLexicalRealizationV2LexicalAttributionSummaryV1", "alpha3_9_identical_query_count": identical, "lexically_changed_query_count": changed, "nonzero_alpha3_9_identical_queries": sum(a["mapping_state"] == "BYTE_IDENTICAL" and a["nonzero"] for a in attribution), "nonzero_lexically_changed_queries": sum(a["mapping_state"] == "LEXICALLY_CHANGED_ONLY" and a["nonzero"] for a in attribution), "causal_synonym_claims": 0}))
    old_baseline = load(PREREG / "five_architecture_comparison_plan.json")["historical_baseline_user_supplied_not_read_from_candidate_records"]
    current = {k: denominator[k] for k in ("byte_unique_query_count", "nonzero_query_count", "nonzero_case_count", "observed_unique_pmids_before_tail_total", "metadata_universe_total", "tier_a_count", "tier_b_count", "oa_eligible_count", "selected_count", "successful_fulltext_acquisition_count")}
    write("five_architecture_retrieval_comparison.json", pretty({"artifact_schema_version": "FiveArchitectureRetrievalComparisonV1", "scope": "descriptive retrieval/acquisition only; no relevance, precision or recall", "architectures": [{"architecture": "v2.3", "query_count": 32}, {"architecture": "exact-proposition serializer", "query_count": 29, "historical_nonzero_query_count": 0}, {"architecture": "Surface V2", "query_count": 25, "historical_nonzero_query_count": 0}, {"architecture": "SearchConstraintAllocationV1", "historical_user_supplied_baseline": old_baseline}, {"architecture": "SearchConstraintAllocationV1 + BoundedLexicalRealizationV2", **current}], "no_scientific_relevance_conclusion": True}))
    write("alpha3_12_execution_manifest_verification.json", pretty({"alpha3_12_root_sha256": EXPECTED_PREREG, "execution_manifest_sha256": EXPECTED_MANIFEST, "query_set_sha256": EXPECTED_QUERY_SET, "relation_contribution_count": 63, "byte_unique_query_count": 55, "verified_before_network": True}))
    write("frozen_downstream_policy_reuse_audit.json", pretty({"alpha3_10_downstream_protocol_sha256": EXPECTED_ALPHA310, "material_downstream_policy_changes": 0, "query_set_input_identity_changed_only": True, "retry_policy_changed": False, "ranking_or_selection_policy_changed": False, "relevance_adjudications": 0}))
    write("adapter_reporting_scope.json", pretty({"alpha3_10_transport_and_candidate_pipeline_reused": True, "legacy_adapter_inner_root_sha256": inner_root, "reporting_identity_rebound_before_outer_freeze": True, "authoritative_comparison": "five_architecture_retrieval_comparison.json", "scientific_rules_changed": False}))
    write("bounded_lexical_realization_v2_acquisition_corpus_sha256", (RUN / "search_constraint_allocation_v1_development_acquisition_corpus_sha256").read_bytes())
    summary = {"artifact_schema_version": "BoundedLexicalRealizationV2CompleteDevelopmentRetrievalSummaryV1", "status": "completed", **{k: denominator[k] for k in denominator if k not in {"artifact_schema_version", "relevance_denominators_present"}}, "core_relation_query_count": sum("CORE_RELATION" in q["variant_classes"] for q in queries), "core_relation_nonzero_query_count": sum("CORE_RELATION" in q["variant_classes"] and q["outcome"] == "NONZERO_QUERY" for q in queries), "cases_with_nonzero_core_relation": len({q["case_id"] for q in queries if "CORE_RELATION" in q["variant_classes"] and q["outcome"] == "NONZERO_QUERY"}), "successful_ncbi_response_count": len(network.events), "failed_network_attempt_count": len(network.failures), "fulltext_failure_count": denominator["fulltext_failure_count"], "lexical_attribution_summary_sha256": sha(RUN / "lexical_attribution_summary.json"), "acquisition_corpus_sha256": (RUN / "bounded_lexical_realization_v2_acquisition_corpus_sha256").read_text().strip(), "alpha3_12_root_sha256": EXPECTED_PREREG, "execution_manifest_sha256": EXPECTED_MANIFEST, "query_set_sha256": EXPECTED_QUERY_SET, "relevance_adjudications": 0, "known_pmid_checks": 0, "historical_label_reads": 0, "provider_calls": 0, "llm_calls": 0, "historical_assets_modified": False}
    write("bounded_lexical_realization_v2_summary.json", pretty(summary))
    files = sorted(p for p in RUN.rglob("*") if p.is_file() and str(p.relative_to(RUN)) not in {"bounded_lexical_realization_v2_development_retrieval_validation.json", "bounded_lexical_realization_v2_development_retrieval_sha256"})
    pairs = [[str(p.relative_to(RUN)), sha(p)] for p in files]
    root = digest(pairs)
    write("bounded_lexical_realization_v2_development_retrieval_validation.json", pretty({"artifact_schema_version": "BoundedLexicalRealizationV2DevelopmentRetrievalValidationV1", "status": "PASS", "aggregate_components": pairs, "root_sha256": root, "checks": {"all_55_queries_complete": True, "all_63_contributions_preserved": True, "no_policy_or_query_modification": True, "selection_manifests_frozen_before_PMC": True, "no_scientific_relevance_adjudication": True}}))
    write("bounded_lexical_realization_v2_development_retrieval_sha256", (root + "\n").encode())
    return {**summary, "bounded_lexical_realization_v2_development_retrieval_sha256": root}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--preflight-only", action="store_true")
    parser.add_argument("--execute-network", action="store_true")
    args = parser.parse_args()
    if args.preflight_only == args.execute_network:
        parser.error("choose exactly one execution mode")
    verification, manifest, adapted, targets, gates = preflight()
    if args.preflight_only:
        print(json.dumps({"preflight": verification, "run_path": str(RUN), "network_calls": 0}, sort_keys=True))
        return
    if RUN.exists():
        raise RuntimeError(f"refusing existing run: {RUN}")
    RUN.mkdir(parents=True)
    network = bind_pipeline()
    write("pre_network_verification.json", pretty({**verification, "timestamp_utc": datetime.now(timezone.utc).isoformat()}))
    write("frozen_execution_manifest_sha256", (EXPECTED_MANIFEST + "\n").encode())
    query_map = {q["query_id"]: q for q in adapted}
    try:
        execution = surface.execute_queries(network, core.project_queries(adapted))
    except Exception as exc:
        failure = core.freeze_terminal_search_failure(exc, adapted, network)
        print(json.dumps({"status": "FAILED_CLOSED", **failure}, sort_keys=True), flush=True)
        raise
    stage = "retrieval_universe_freeze"
    try:
        universe = core.freeze_universe(execution, query_map)
        stage = "metadata_fetch"
        surface.fetch_metadata(network, universe["hard_tail_pmids"])
        stage = "metadata_validation"
        metadata = core.build_metadata(universe, query_map)
        stage = "candidate_validation_and_selection"
        processed = legacy.score_and_select(metadata, targets, gates, network)
        selection_sha, selected = core.freeze_selection(processed, universe["universe_sha"])
        print(f"selection_frozen sha256={selection_sha} count={len(selected)}", flush=True)
        stage = "PMC_fulltext_acquisition"
        fulltexts, failures = surface.fetch_fulltexts(network, selected, selection_sha)
        stage = "inner_corpus_freeze"
        core.finish(verification, {"exact_queries": adapted}, execution, universe, metadata, processed, selection_sha, fulltexts, failures, network)
        stage = "adapter_reporting_rebind"
        inner_root = rebind_adapter_reports()
        stage = "outer_corpus_freeze"
        result = freeze_alpha312_outputs(manifest, adapted, network, inner_root)
    except Exception as exc:
        failure = core.freeze_nonsearch_failure(stage, exc, network)
        print(json.dumps(failure, sort_keys=True), flush=True)
        raise
    print(json.dumps(result, sort_keys=True), flush=True)


def complete_authority_attribution_draft() -> None:
    """Finish the known new-run outer attribution wrapper, without network."""
    old_root = "5fd0c9c629438e7ef057daefd513aab78f00753eae4cf30a9c191357f7aeca83"
    root_path = RUN / "bounded_lexical_realization_v2_development_retrieval_sha256"
    validation_path = RUN / "bounded_lexical_realization_v2_development_retrieval_validation.json"
    if not RUN.is_dir() or root_path.read_text().strip() != old_root:
        raise RuntimeError("not the known attribution draft")
    validation = load(validation_path)
    pairs = validation["aggregate_components"]
    if validation["root_sha256"] != old_root or digest(pairs) != old_root or any(sha(RUN / name) != value for name, value in pairs):
        raise RuntimeError("draft root components drifted")
    attribution_path = RUN / "lexical_query_attribution.jsonl"
    attribution = rows(attribution_path)
    lexical_sets = {row["lexical_alternative_set_id"]: row for row in rows(ALPHA311 / "lexical_alternative_sets.jsonl")}
    if len(attribution) != 55 or any("authority_classes_present" in row for row in attribution):
        raise RuntimeError("attribution draft is not the expected schema")
    for row in attribution:
        row["authority_classes_present"] = sorted({item["authority_class"] for ids in row["query_present_lexical_alternative_set_ids"].values() for identifier in ids for item in lexical_sets[identifier]["alternatives"]})
    attribution_path.write_bytes(jsonl(attribution))
    new_pairs = [[str(p.relative_to(RUN)), sha(p)] for p in sorted(RUN.rglob("*")) if p.is_file() and str(p.relative_to(RUN)) not in {validation_path.name, root_path.name}]
    new_root = digest(new_pairs)
    validation["aggregate_components"] = new_pairs
    validation["root_sha256"] = new_root
    validation["authority_classes_present_per_query"] = True
    validation_path.write_bytes(pretty(validation))
    root_path.write_text(new_root + "\n")
    print(json.dumps({"authority_attribution_completed": True, "query_count": len(attribution), "new_outer_root_sha256": new_root}, sort_keys=True))


if __name__ == "__main__":
    if sys.argv[1:] == ["--complete-authority-attribution-draft"]:
        complete_authority_attribution_draft()
    else:
        main()
