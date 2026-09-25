#!/usr/bin/env python3
"""Freeze the alpha3.7 Retrieval Surface V2 execution preregistration offline."""

from __future__ import annotations

from collections import Counter
import hashlib
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
RUN = ROOT / "runs/20260924_search_plan_v24_dev_alpha3_7_retrieval_surface_v2_preregistration_offline"
ALPHA36 = ROOT / "runs/20260924_search_plan_v24_dev_alpha3_6_retrieval_surface_compiler_v2_offline"
ALPHA34 = ROOT / "runs/20260923_search_plan_v24_dev_alpha3_4_retrieval_preregistration_offline"
ALPHA33 = ROOT / "runs/20260923_search_plan_v24_dev_alpha3_3_role_scoped_polarity_offline"
FAILED = ROOT / "runs/20260924_search_plan_v24_dev_frozen_retrospective_retrieval"

EXPECTED_ALPHA36 = "d043441e59de0c29958b1af8c935868c5f1f233b62178c2476b9a89763377cd0"
EXPECTED_QUERY_SET = "4f5148b0ae1a97aaf1bf7334109562c4d04dbdcf99cebb323f87f872a3e93947"
EXPECTED_ALPHA34 = "2488b4322894acb755872e9bc92d78dcaf2a4dec6ed807a22d3aff4622e2d5d5"
EXPECTED_OLD_EXECUTION_MANIFEST = "559b09754580bb06f05c51cc58f513e5364d2a5e2d541a8a074351a8b09f9320"
EXPECTED_FAILED = "391d2fe5d7c133be42d3c503a92ecc8724f398430adf20c46283ad1567e8dfd5"
EXPECTED_EMPTY_CORPUS = "81898e8f609e03f18398eefec2cb56deb579b05acb5f362d5351c029b7c748f6"
EXPECTED_OLD_QUERY_SET = "b7117825db0cde698ca2a9e5b882cac2f60ab4635e5b2e213243b8473d9d4ed0"
EXPECTED_CASE_COUNTS = {
    "heldout_v2_101": 3, "heldout_v2_102": 2, "heldout_v2_103": 1,
    "heldout_v2_104": 2, "heldout_v2_105": 4, "heldout_v2_106": 6,
    "heldout_v2_107": 3, "heldout_v2_108": 4,
}

SOFT_TAIL = 120
HARD_TAIL = 180
MAX_FULLTEXTS = 10


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


def value_sha(value: Any) -> str:
    return sha_bytes(canonical(value))


def aggregate(pairs: list[list[str]]) -> str:
    return value_sha(pairs)


def load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def verify_run(path: Path, root_file: str, expected: str) -> dict[str, Any]:
    validation = load(path / "validation.json")
    pairs = validation["aggregate_components"]
    require(all(sha(path / name) == digest for name, digest in pairs),
            f"component mismatch: {path.name}")
    actual = aggregate(pairs)
    recorded = (path / root_file).read_text().strip()
    require(actual == recorded == expected, f"root mismatch: {path.name}")
    return {
        "path": str(path.relative_to(ROOT)), "expected_sha256": expected,
        "recorded_sha256": recorded, "recomputed_sha256": actual,
        "component_count": len(pairs), "verified": True,
    }


def source_policy(name: str, expected_hashes: dict[str, str]) -> tuple[bytes, str]:
    body = (ALPHA34 / name).read_bytes()
    digest = sha_bytes(body)
    require(expected_hashes[name] == digest, f"alpha3.4 policy changed: {name}")
    return body, digest


def contribution_records(
        queries: list[dict[str, Any]], plans: list[dict[str, Any]],
        ast_rows: list[dict[str, Any]], old_queries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_relation_query: dict[str, dict[str, Any]] = {}
    for query in queries:
        for relation_ref in query["source_relation_core_ids"]:
            require(relation_ref not in by_relation_query, "relation contribution maps twice")
            by_relation_query[relation_ref] = query
    by_relation_plan = {row["source_relation_core_sha256"]: row for row in plans}
    by_relation_ast = {row["source_relation_core_sha256"]: row for row in ast_rows}
    by_relation_old = {row["source_link_sha256"]: row for row in old_queries}
    relation_refs = set(by_relation_query)
    require(relation_refs == set(by_relation_plan) == set(by_relation_ast) == set(by_relation_old),
            "source relation contribution sets differ")

    result = []
    for relation_ref in sorted(relation_refs, key=lambda ref: (
            by_relation_old[ref]["case_id"], by_relation_old[ref]["intent_index"],
            by_relation_old[ref]["link_index"], ref)):
        query = by_relation_query[relation_ref]
        plan = by_relation_plan[relation_ref]
        ast_row = by_relation_ast[relation_ref]
        old = by_relation_old[relation_ref]
        ast_hash = ast_row["ast"]["ast_sha256"]
        plan_hash = value_sha(plan)
        require(ast_hash in query["provenance"]["ast_hashes"], "AST provenance lost")
        require(plan_hash in query["provenance"]["surface_plan_hashes"], "surface provenance lost")
        require(plan["surface_plan_id"] in query["surface_plan_ids"], "surface plan ID lost")
        require(old["intent_type"] == ast_row["intent_type"] == plan["intent_type"],
                "intent provenance mismatch")
        result.append({
            "contribution_order": len(result) + 1,
            "case_id": old["case_id"],
            "intent_id": f"{old['case_id']}:intent:{old['intent_index']}",
            "intent_index": old["intent_index"],
            "intent_type": old["intent_type"],
            "link_index": old["link_index"],
            "relation_core_sha256": relation_ref,
            "retrieval_surface_plan_id": plan["surface_plan_id"],
            "retrieval_surface_plan_sha256": plan_hash,
            "pubmed_ast_sha256": ast_hash,
            "target_sha256": plan["source_target_sha256"],
            "executed_query_id": query["query_id"],
            "executed_query_sha256": query["query_sha256"],
        })
    require(len(result) == 29, "relation contribution count changed")
    return result


def compatibility_rows(alpha34_hashes: dict[str, str]) -> list[dict[str, Any]]:
    specs = [
        ("query execution", "query_execution_policy.json", "one logical execution per byte-unique query; relevance ordering"),
        ("pagination", "query_execution_policy.json", "page size 30; pagination is transport continuation"),
        ("round-robin scheduling", "query_execution_policy.json", "deterministic breadth-first round-robin within case"),
        ("within-case union", "case_union_policy.json", "first-seen union across case queries"),
        ("PMID deduplication", "pmid_deduplication_policy.json", "PMID identity within case; no cross-case collapse"),
        ("soft tail", "tail_policy.json", "120, reporting only"),
        ("hard tail", "tail_policy.json", "180 unique PMIDs after within-case deduplication"),
        ("adaptive tail", "tail_policy.json", "disabled"),
        ("metadata fields", "metadata_policy.json", "exact alpha3.4 projection"),
        ("candidate scoring", "preacquisition_scoring_policy.json", "frozen deterministic stack"),
        ("P0/P1/P2", "preacquisition_scoring_policy.json", "P0 v1.1, P1 v1.1, P2 v1"),
        ("Policy A", "preacquisition_scoring_policy.json", "minimal demotion-only Policy A"),
        ("Tier ordering", "preacquisition_scoring_policy.json", "Tier A before Tier B, then depth and PMID"),
        ("OA eligibility", "oa_eligibility_policy.json", "preserved PMCID only"),
        ("selection", "fulltext_acquisition_policy.json", "frozen metadata-only ordering"),
        ("fulltext cap", "fulltext_acquisition_policy.json", "maximum 10 per case"),
        ("replacement", "replacement_policy.json", "none"),
        ("retry", "retrieval_retry_policy.json", "four total attempts; 60 seconds; 2/4/8 backoff"),
        ("failure semantics", "retrieval_failure_taxonomy.json", "technical failure is not scientific zero"),
        ("provenance", "provenance_contract.json", "all contributions retained; V2 many-to-one projection added"),
        ("known-paper blinding", "known_paper_blindness_policy.json", "unchanged"),
        ("historical-label blinding", "acquisition_label_blinding_policy.json", "unchanged"),
        ("future metrics", "future_metric_preregistration.json", "alpha3.4 metrics retained; descriptive V2 attribution added"),
    ]
    return [{
        "dimension": dimension,
        "compatibility": "REUSED_IDENTICALLY",
        "material_downstream_change": False,
        "alpha3_4_source_artifact": source,
        "alpha3_4_source_sha256": alpha34_hashes[source],
        "frozen_policy": policy,
    } for dimension, source, policy in specs]


def main() -> None:
    require(not RUN.exists(), f"refusing overwrite: {RUN}")

    roots = {
        "alpha3_6_compiler": verify_run(
            ALPHA36, "search_plan_v24_dev_alpha3_6_sha256", EXPECTED_ALPHA36),
        "alpha3_4_downstream_policy": verify_run(
            ALPHA34, "search_plan_v24_dev_alpha3_4_sha256", EXPECTED_ALPHA34),
        "historical_failed_retrieval": verify_run(
            FAILED, "search_plan_v24_dev_frozen_retrospective_retrieval_sha256", EXPECTED_FAILED),
    }

    old_execution_manifest_path = ALPHA34 / "development_retrospective_retrieval_execution_manifest.json"
    require(sha(old_execution_manifest_path) == EXPECTED_OLD_EXECUTION_MANIFEST,
            "alpha3.4 execution manifest changed")
    old_execution_manifest = load(old_execution_manifest_path)
    alpha34_hashes = old_execution_manifest["downstream_policy_hashes"]
    for name, digest in alpha34_hashes.items():
        require(sha(ALPHA34 / name) == digest, f"alpha3.4 downstream policy changed: {name}")

    corpus_manifest = load(FAILED / "development_retrospective_acquisition_corpus_manifest.json")
    corpus_pairs = corpus_manifest["aggregate_components"]
    require(all(sha(FAILED / name) == digest for name, digest in corpus_pairs),
            "historical corpus component changed")
    require(aggregate(corpus_pairs) == EXPECTED_EMPTY_CORPUS ==
            (FAILED / "development_retrospective_acquisition_corpus_sha256").read_text().strip(),
            "historical empty corpus root mismatch")

    query_path = ALPHA36 / "search_plan_v24_dev_retrieval_surface_v2_query_set.jsonl"
    require(sha(query_path) == EXPECTED_QUERY_SET ==
            (ALPHA36 / "search_plan_v24_dev_retrieval_surface_v2_query_set_sha256").read_text().strip(),
            "Retrieval Surface V2 query-set hash mismatch")
    queries = load_jsonl(query_path)
    require(len(queries) == 25, "query count changed")
    require(Counter(row["case_id"] for row in queries) == Counter(EXPECTED_CASE_COUNTS),
            "per-case query counts changed")
    require(len({row["query_id"] for row in queries}) == 25, "query IDs not unique")
    require(len({(row["case_id"], row["serialized_query"].encode()) for row in queries}) == 25,
            "query bytes not case-unique")

    plans = load_jsonl(ALPHA36 / "empirical_v3_to_surface_plan.jsonl")
    ast_rows = load_jsonl(ALPHA36 / "surface_plan_to_pubmed_ast.jsonl")
    old_freeze = load(ALPHA33 / "development_retrieval_freeze_manifest.json")
    old_queries = old_freeze["exact_compiled_query_set"]
    require(len(old_queries) == 29 and value_sha(old_queries) == EXPECTED_OLD_QUERY_SET,
            "historical failed query set changed")
    contributions = contribution_records(queries, plans, ast_rows, old_queries)

    query_verifications = []
    exact_queries = []
    for order, query in enumerate(queries, 1):
        checks = {
            "case_present": query["case_id"] in EXPECTED_CASE_COUNTS,
            "intent_provenance_present": bool(query["contributing_intent_types"]),
            "relation_core_provenance_present": bool(query["source_relation_core_ids"]),
            "surface_plan_provenance_present": bool(query["surface_plan_ids"]),
            "pubmed_ast_hash_present": bool(query["provenance"]["ast_hashes"]),
            "serialized_text_present": bool(query["serialized_query"]),
            "query_sha_verified": sha_bytes(query["serialized_query"].encode()) == query["query_sha256"],
            "safety_linter_pass": query["safety_linter_result"] == "PASS",
            "relation_certificate_certified": query["relation_serialization_certificate_state"] == "CERTIFIED",
        }
        require(all(checks.values()), f"query verification failed: {query['query_id']}")
        query_verifications.append({"query_id": query["query_id"], "checks": checks, "verified": True})
        exact_queries.append({
            "execution_order": order,
            "execution_status": "NOT_EXECUTED_PREREGISTRATION",
            "case_id": query["case_id"],
            "query_id": query["query_id"],
            "query_sha256": query["query_sha256"],
            "exact_query_text": query["serialized_query"],
            "query_record_sha256": value_sha(query),
            "contributing_intent_types": query["contributing_intent_types"],
            "relation_core_ids": query["source_relation_core_ids"],
            "surface_plan_ids": query["surface_plan_ids"],
            "pubmed_ast_hashes": query["provenance"]["ast_hashes"],
        })

    target_hashes: dict[str, str] = {}
    for plan in plans:
        prior = target_hashes.setdefault(plan["case_id"], plan["source_target_sha256"])
        require(prior == plan["source_target_sha256"], "multiple target hashes in case")
    require(set(target_hashes) == set(EXPECTED_CASE_COUNTS), "target hash set changed")

    compiler_contract_names = [
        "retrieval_surface_plan_v1_contract.json", "relation_edge_v1_contract.json",
        "retrieval_surface_coverage_v1_contract.json",
        "relation_serialization_certificate_v1_contract.json",
        "pubmed_query_ast_v1_contract.json", "pubmed_syntax_contract_v1.json",
        "pubmed_query_serializer_v2_contract.json",
        "query_serialization_safety_linter_v1_contract.json",
        "surface_variant_policy.json", "query_budget_policy.json",
    ]
    compiler_hashes = {name: sha(ALPHA36 / name) for name in compiler_contract_names}
    syntax = load(ALPHA36 / "pubmed_syntax_contract_v1.json")
    edge = load(ALPHA36 / "relation_edge_v1_contract.json")
    variants = load(ALPHA36 / "surface_variant_policy.json")
    budget = load(ALPHA36 / "query_budget_policy.json")
    require(syntax["compact_concept_window_n"] == 0, "compact window changed")
    require(edge["relation_edge_window_n"] == 5, "relation window changed")
    require(edge["maximum_semantic_roles_per_proximity"] == 3, "role maximum changed")
    require(variants["max_surface_variants_per_validated_intent"] == 2,
            "surface variant maximum changed")
    require(budget["max_queries_per_target"] == 12, "query budget changed")

    outputs: dict[str, bytes] = {}
    outputs["upstream_root_verification.json"] = pretty({
        "artifact_schema_version": "Alpha37UpstreamRootVerificationV1",
        "roots": roots,
        "alpha3_4_execution_manifest": {
            "expected_sha256": EXPECTED_OLD_EXECUTION_MANIFEST,
            "recomputed_sha256": sha(old_execution_manifest_path), "verified": True,
        },
        "historical_empty_acquisition_corpus": {
            "expected_sha256": EXPECTED_EMPTY_CORPUS,
            "recomputed_sha256": aggregate(corpus_pairs), "verified": True,
        },
        "historical_failed_query_set": {
            "expected_sha256": EXPECTED_OLD_QUERY_SET,
            "recomputed_sha256": value_sha(old_queries), "query_count": 29, "verified": True,
        },
        "all_verified_offline": True,
    })
    outputs["alpha3_6_query_set_verification.json"] = pretty({
        "artifact_schema_version": "Alpha36QuerySetVerificationV1",
        "source_path": str(query_path.relative_to(ROOT)),
        "expected_sha256": EXPECTED_QUERY_SET,
        "recomputed_sha256": sha(query_path),
        "query_count": len(queries), "per_case_counts": dict(sorted(Counter(
            row["case_id"] for row in queries).items())),
        "query_text_changes": 0, "query_verifications": query_verifications,
        "new_query_set_verified": True,
    })
    outputs["historical_zero_hit_run_preservation_audit.json"] = pretty({
        "artifact_schema_version": "HistoricalZeroHitRunPreservationAuditV1",
        "failed_retrieval_root_sha256": EXPECTED_FAILED,
        "empty_acquisition_corpus_sha256": EXPECTED_EMPTY_CORPUS,
        "failed_query_set_sha256": EXPECTED_OLD_QUERY_SET,
        "failed_query_count": 29, "zero_hit_query_count": 29,
        "historical_evidence_reinterpreted": False,
        "historical_assets_modified": False, "preserved": True,
    })
    outputs["compiler_parameter_freeze.json"] = pretty({
        "artifact_schema_version": "RetrievalSurfaceV2CompilerParameterFreezeV1",
        "alpha3_6_root_sha256": EXPECTED_ALPHA36,
        "compact_concept_window_n": 0, "relation_edge_window_n": 5,
        "maximum_semantic_roles_per_proximity_node": 3,
        "max_queries_per_target": 12,
        "max_surface_variants_per_validated_intent": 2,
        "ast_version": "PubMedQueryASTV1",
        "serializer_version": "PubMedQuerySerializerV2",
        "syntax_contract_version": "PubMedSyntaxContractV1",
        "safety_linter_version": "QuerySerializationSafetyLinterV1",
        "contract_hashes": compiler_hashes,
        "parameters_mutable_at_runtime": False,
        "compiler_parameters_frozen": True,
    })

    reuse_rows = compatibility_rows(alpha34_hashes)
    require(all(row["compatibility"] == "REUSED_IDENTICALLY" for row in reuse_rows),
            "incompatible downstream policy")
    outputs["downstream_policy_compatibility_audit.json"] = pretty({
        "artifact_schema_version": "DownstreamPolicyCompatibilityAuditAlpha37V1",
        "alpha3_4_root_sha256": EXPECTED_ALPHA34,
        "experimental_variable_change": "QUERY_SERIALIZATION_ARCHITECTURE",
        "old_query_count": 29, "new_query_count": 25,
        "query_set_change_is_downstream_policy_change": False,
        "provenance_projection_is_decision_policy_change": False,
        "audited_dimension_count": len(reuse_rows),
        "material_downstream_policy_changes": 0,
        "incompatible_dimension_count": 0,
        "downstream_policy_compatible": True,
    })
    outputs["downstream_policy_reuse_matrix.json"] = pretty({
        "artifact_schema_version": "DownstreamPolicyReuseMatrixAlpha37V1",
        "allowed_states": ["REUSED_IDENTICALLY", "INCOMPATIBLE"],
        "rows": reuse_rows,
        "status_counts": {"REUSED_IDENTICALLY": len(reuse_rows), "INCOMPATIBLE": 0},
    })

    outputs["query_execution_policy.json"] = pretty({
        "artifact_schema_version": "RetrievalSurfaceV2QueryExecutionPolicyV1",
        "source_alpha3_4_policy_sha256": alpha34_hashes["query_execution_policy.json"],
        "query_set_sha256": EXPECTED_QUERY_SET,
        "case_order": list(EXPECTED_CASE_COUNTS),
        "query_count": 25, "logical_execution_count_per_query": 1,
        "within_case_order": "frozen query-set file order",
        "pubmed_sort": "relevance", "page_size": 30,
        "page_scheduling": "breadth-first round-robin across active queries within case",
        "pagination_is_transport_continuation_not_query_rerun": True,
        "runtime_query_modification_allowed": False,
        "zero_hit_behavior": "record ZERO_HIT_QUERY; no repair or fallback",
        "exact_queries": exact_queries,
    })
    outputs["query_dedup_provenance_policy.json"] = pretty({
        "artifact_schema_version": "QueryDedupProvenancePolicyAlpha37V1",
        "relation_contribution_count": 29, "byte_unique_query_count": 25,
        "deduplicated_contribution_count": 4,
        "execution_identity": ["case_id", "serialized_query_bytes"],
        "execute_duplicate_text_multiple_times": False,
        "all_source_provenance_preserved": True,
        "required_source_refs": ["intent_id", "relation_core_sha256",
                                 "retrieval_surface_plan_id", "pubmed_ast_sha256"],
        "contributions": contributions,
    })
    outputs["case_union_policy.json"] = pretty({
        "artifact_schema_version": "CaseUnionPolicyAlpha37V1",
        "source_alpha3_4_policy_sha256": alpha34_hashes["case_union_policy.json"],
        "union_scope": "WITHIN_CASE", "identity": "PMID",
        "cross_case_duplicate_elimination": False,
        "order": "first appearance in frozen query/page round-robin order",
        "preserve_all_contributing_provenance": True,
        "query_provenance_resolves_to_all_29_relation_contributions": True,
        "hard_tail_applied_after_within_case_deduplication": True,
    })

    # These policies are reused as physical byte-identical copies.
    for name in ["tail_policy.json", "metadata_policy.json",
                 "preacquisition_scoring_policy.json", "oa_eligibility_policy.json",
                 "replacement_policy.json", "retrieval_retry_policy.json",
                 "retrieval_failure_taxonomy.json", "known_paper_blindness_policy.json"]:
        outputs[name] = source_policy(name, alpha34_hashes)[0]

    fulltext = load(ALPHA34 / "fulltext_acquisition_policy.json")
    outputs["selection_fulltext_policy.json"] = pretty({
        "artifact_schema_version": "SelectionFulltextPolicyAlpha37V1",
        "source_alpha3_4_policy_sha256": alpha34_hashes["fulltext_acquisition_policy.json"],
        "selection_order": fulltext["selection_order"],
        "maximum_fulltexts_per_case": fulltext["maximum_fulltexts_per_case"],
        "source": fulltext["source"], "PMCID_required": fulltext["PMCID_required"],
        "selection_manifest_frozen_before_download": True,
        "fulltext_content_may_influence_selection": False,
        "empty_or_invalid_body": fulltext["empty_or_invalid_body"],
        "policy_reused_identically": True,
    })
    outputs["selection_freeze_barrier_policy.json"] = pretty({
        "artifact_schema_version": "SelectionFreezeBarrierPolicyAlpha37V1",
        "all_eight_ordered_case_manifests_required": True,
        "case_count": 8, "freeze_and_hash_before_first_pmc_fetch": True,
        "fulltext_peeking_before_global_selection_freeze": False,
        "source_alpha3_4_fulltext_policy_sha256": alpha34_hashes["fulltext_acquisition_policy.json"],
    })
    blinding = load(ALPHA34 / "acquisition_label_blinding_policy.json")
    outputs["historical_label_blinding_policy.json"] = pretty({
        "artifact_schema_version": "HistoricalLabelBlindingPolicyAlpha37V1",
        "source_alpha3_4_policy_sha256": alpha34_hashes["acquisition_label_blinding_policy.json"],
        "candidate_selection_label_blind": blinding["candidate_selection_label_blind"],
        "direct_relevance_labels_visible": blinding["direct_relevance_labels_visible"],
        "historical_pass_a_labels_visible": blinding["historical_pass_a_labels_visible"],
        "historical_pass_b_labels_visible": blinding["historical_pass_b_labels_visible"],
        "historical_label_blinding_frozen": True,
    })
    outputs["runtime_adaptation_prohibition.json"] = pretty({
        "artifact_schema_version": "RuntimeAdaptationProhibitionAlpha37V1",
        "runtime_adaptation_allowed": False,
        "prohibited": [
            "proximity-window tuning", "Boolean restructuring", "field-tag changes",
            "alias addition or removal", "relation-edge removal", "endpoint removal",
            "historical query execution", "V2/V3 fallback query", "query-specific tail",
            "intent-specific tail", "result-driven query priority changes",
        ],
        "zero_hit_query_state": "ZERO_HIT_QUERY",
        "zero_hit_case_state": "ZERO_HIT_CASE",
        "unexpected_syntax_behavior": "freeze as evidence for a later version",
    })

    old_metrics = load(ALPHA34 / "future_metric_preregistration.json")
    additional_metrics = [
        "nonzero_query_count", "nonzero_case_count", "per_query_raw_hit_counts",
        "per_case_unique_pmid_counts", "query_overlap_rate",
        "proximity_query_contribution", "intent_family_contribution",
        "relation_contribution_to_executed_query_dedup_count",
    ]
    outputs["future_retrieval_metrics.json"] = pretty({
        "artifact_schema_version": "FutureRetrievalMetricsAlpha37V1",
        "source_alpha3_4_policy_sha256": alpha34_hashes["future_metric_preregistration.json"],
        "alpha3_4_metrics_reused": old_metrics["metrics"],
        "alpha3_4_denominators_reused": old_metrics["denominators_kept_distinct"],
        "retrieval_surface_v2_additional_metrics": additional_metrics,
        "observed_values_present": False, "relevance_labels_present": False,
        "true_literature_recall_defined": False,
        "interpretation": "descriptive development retrospective retrieval",
        "retrieval_behavior_changed_by_metric_additions": False,
    })
    outputs["three_way_comparison_plan.json"] = pretty({
        "artifact_schema_version": "ThreeWayQueryArchitectureComparisonPlanV1",
        "comparison_type": "DESCRIPTIVE_DEVELOPMENT_RETROSPECTIVE",
        "levels": [
            {"level": "A", "architecture": "historical v2.3", "query_count": 32,
             "candidate_universe": "NONZERO_HISTORICAL"},
            {"level": "B", "architecture": "v2.4 exact-proposition serializer",
             "query_count": 29, "zero_hit_query_count": 29,
             "root_sha256": EXPECTED_FAILED},
            {"level": "C", "architecture": "Retrieval Surface V2",
             "byte_unique_query_count": 25, "relation_contribution_count": 29,
             "query_set_sha256": EXPECTED_QUERY_SET, "retrieval_state": "NOT_EXECUTED"},
        ],
        "fresh_heldout_validation": False, "independent_confirmation": False,
        "literature_recall_estimate": False,
        "relevance_conclusions_allowed_before_acquisition_and_neutral_review": False,
    })

    # Bind every policy artifact before constructing the execution manifest.
    manifest_policy_names = [
        "query_execution_policy.json", "query_dedup_provenance_policy.json",
        "case_union_policy.json", "tail_policy.json", "metadata_policy.json",
        "preacquisition_scoring_policy.json", "oa_eligibility_policy.json",
        "selection_fulltext_policy.json", "replacement_policy.json",
        "retrieval_retry_policy.json", "retrieval_failure_taxonomy.json",
        "selection_freeze_barrier_policy.json", "known_paper_blindness_policy.json",
        "historical_label_blinding_policy.json", "runtime_adaptation_prohibition.json",
        "future_retrieval_metrics.json", "three_way_comparison_plan.json",
    ]
    new_policy_hashes = {name: sha_bytes(outputs[name]) for name in manifest_policy_names}
    manifest = {
        "artifact_schema_version": "RetrievalSurfaceV2DevelopmentExecutionManifestV1",
        "state": "FROZEN_NOT_EXECUTED",
        "experimental_interpretation": "DEVELOPMENT_RETROSPECTIVE_RETRIEVAL",
        "alpha3_6_root_sha256": EXPECTED_ALPHA36,
        "query_set_sha256": EXPECTED_QUERY_SET,
        "byte_unique_query_count": 25, "relation_contribution_count": 29,
        "exact_queries": exact_queries, "source_relation_contributions": contributions,
        "target_hashes": dict(sorted(target_hashes.items())),
        "compiler_configuration": {
            "compact_concept_window_n": 0, "relation_edge_window_n": 5,
            "maximum_semantic_roles_per_proximity_node": 3,
            "max_queries_per_target": 12,
            "max_surface_variants_per_validated_intent": 2,
            "contract_hashes": compiler_hashes,
        },
        "alpha3_4_root_sha256": EXPECTED_ALPHA34,
        "superseded_alpha3_4_execution_manifest_sha256": EXPECTED_OLD_EXECUTION_MANIFEST,
        "alpha3_4_downstream_policy_hashes": alpha34_hashes,
        "alpha3_7_policy_hashes": new_policy_hashes,
        "tail_parameters": {"soft_tail": SOFT_TAIL, "hard_tail": HARD_TAIL,
                            "adaptive_tail_enabled": False},
        "metadata_fields": load(ALPHA34 / "metadata_policy.json")["fields"],
        "scoring_stack_sha256": load(ALPHA34 / "preacquisition_scoring_policy.json")["stack_sha256"],
        "oa_policy_sha256": alpha34_hashes["oa_eligibility_policy.json"],
        "max_fulltexts_per_case": MAX_FULLTEXTS,
        "selection_freeze_barrier": "ALL_8_CASE_MANIFESTS_HASHED_BEFORE_FIRST_PMC_FETCH",
        "replacement_allowed": False,
        "observed_retrieval_values_present": False,
        "hit_counts_present": False, "candidate_records_present": False,
        "retrieval_executed": False,
    }
    manifest_body = pretty(manifest)
    manifest_sha = sha_bytes(manifest_body)
    require(manifest_sha != EXPECTED_OLD_EXECUTION_MANIFEST,
            "new execution manifest unexpectedly equals alpha3.4 manifest")
    outputs["retrieval_surface_v2_development_execution_manifest.json"] = manifest_body
    outputs["retrieval_surface_v2_development_execution_manifest_sha256"] = (
        manifest_sha + "\n").encode()

    protected = {
        str(path.relative_to(ROOT)): sha(path) for path in [
            ALPHA36 / "validation.json", query_path,
            ALPHA34 / "validation.json", old_execution_manifest_path,
            FAILED / "validation.json",
            FAILED / "development_retrospective_acquisition_corpus_manifest.json",
        ]
    }
    outputs["scientific_state_safety_audit.json"] = pretty({
        "artifact_schema_version": "ScientificStateSafetyAuditAlpha37V1",
        "protected_hashes_before": protected, "protected_hashes_after": protected,
        "query_text_changes": 0, "compiler_parameter_changes": 0,
        "material_downstream_policy_changes": 0,
        "production_case_specific_rules": 0,
        "known_pmid_checks": 0, "hit_counts_seen": 0, "candidate_records_seen": 0,
        "provider_calls": 0, "llm_calls": 0, "network_calls": 0,
        "retrieval_calls": 0, "historical_assets_modified": False,
    })
    summary = {
        "artifact_schema_version": "SearchPlanV24DevAlpha37SummaryV1",
        "status": "completed", "new_query_set_verified": True,
        "relation_contribution_count": 29, "byte_unique_query_count": 25,
        "query_text_changes": 0, "compiler_parameters_frozen": True,
        "material_downstream_policy_changes": 0,
        "downstream_policy_compatible": True,
        "soft_tail": SOFT_TAIL, "hard_tail": HARD_TAIL,
        "adaptive_tail_enabled": False, "max_fulltexts_per_case": MAX_FULLTEXTS,
        "known_paper_blindness_frozen": True,
        "historical_label_blinding_frozen": True,
        "runtime_adaptation_allowed": False,
        "new_execution_manifest_created": True,
        "retrieval_surface_v2_development_execution_manifest_sha256": manifest_sha,
        "production_case_specific_rules": 0,
        "next_stage_recommendation": "AUTHORIZE_RETRIEVAL_SURFACE_V2_FULL_DEVELOPMENT_RETRIEVAL",
        "provider_calls": 0, "llm_calls": 0, "network_calls": 0,
        "retrieval_calls": 0, "hit_counts_seen": 0, "candidate_records_seen": 0,
        "historical_assets_modified": False,
    }
    outputs["summary.json"] = pretty(summary)

    RUN.mkdir(parents=True)
    for name, body in outputs.items():
        (RUN / name).write_bytes(body)
    pairs = [[name, sha(RUN / name)] for name in sorted(outputs)]
    root = aggregate(pairs)
    validation = {
        "artifact_schema_version": "SearchPlanV24DevAlpha37ValidationV1",
        "status": "PASS", "offline_only": True,
        "checks": {
            "all_upstream_roots_verified": True,
            "new_query_set_verified": True,
            "all_25_queries_verified": True,
            "all_29_relation_contributions_bound": True,
            "query_text_changes_zero": True,
            "compiler_parameters_frozen": True,
            "downstream_policy_compatible": True,
            "material_downstream_policy_changes_zero": True,
            "historical_failure_preserved": True,
            "new_execution_manifest_created": True,
            "new_execution_manifest_differs_from_alpha3_4": True,
            "runtime_adaptation_prohibited": True,
            "provider_llm_network_retrieval_calls_zero": True,
            "hit_counts_and_candidate_records_zero": True,
        },
        "aggregate_algorithm": "sha256(canonical JSON ordered [path, sha256] pairs)",
        "aggregate_components": pairs,
        "search_plan_v24_dev_alpha3_7_sha256": root,
    }
    (RUN / "validation.json").write_bytes(pretty(validation))
    (RUN / "search_plan_v24_dev_alpha3_7_sha256").write_text(root + "\n")

    # Reverify immutable sources and the complete new freeze after writes.
    require(verify_run(ALPHA36, "search_plan_v24_dev_alpha3_6_sha256", EXPECTED_ALPHA36)["verified"],
            "alpha3.6 changed")
    require(verify_run(ALPHA34, "search_plan_v24_dev_alpha3_4_sha256", EXPECTED_ALPHA34)["verified"],
            "alpha3.4 changed")
    require(verify_run(FAILED, "search_plan_v24_dev_frozen_retrospective_retrieval_sha256",
                       EXPECTED_FAILED)["verified"], "historical failed run changed")
    require(aggregate([[name, sha(RUN / name)] for name in sorted(outputs)]) == root,
            "alpha3.7 root mismatch after write")
    require(sha(query_path) == EXPECTED_QUERY_SET, "query set changed after write")
    require(all(sha(ALPHA34 / name) == digest for name, digest in alpha34_hashes.items()),
            "alpha3.4 downstream policy changed after write")
    print(json.dumps({
        "status": "completed", "run": str(RUN), "root": root,
        "manifest_sha256": manifest_sha, "query_count": 25,
        "relation_contribution_count": 29, "component_count": len(pairs),
    }, sort_keys=True))


if __name__ == "__main__":
    main()
