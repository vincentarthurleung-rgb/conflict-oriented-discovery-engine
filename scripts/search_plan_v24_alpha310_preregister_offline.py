"""Freeze alpha3.10 retrieval preregistration; reads policy and query artifacts only."""

from __future__ import annotations

import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
A39 = ROOT / "runs/20260925_search_plan_v24_dev_alpha3_9_search_constraint_allocation_offline"
A34 = ROOT / "runs/20260923_search_plan_v24_dev_alpha3_4_retrieval_preregistration_offline"
A37 = ROOT / "runs/20260924_search_plan_v24_dev_alpha3_7_retrieval_surface_v2_preregistration_offline"
EXACT = ROOT / "runs/20260924_search_plan_v24_dev_frozen_retrospective_retrieval"
SURFACE = ROOT / "runs/20260925_search_plan_v24_dev_retrieval_surface_v2_technical_continuation"
RUN = ROOT / "runs/20260925_search_plan_v24_dev_alpha3_10_search_constraint_allocation_retrieval_preregistration_offline"
KNOWN_DRAFT_ROOT = "17b81ad71ab54bc57214d5cd96ee901acbfd3d9cae6e8ca002c3e3761fc287c4"
REWRITE_DRAFT = False
EXPECTED = {
    "alpha3_9": "823a035ca906b67729fd8cb62b2f555a65ca787facb47d8ac3a0cc07ab76d5cb",
    "query_set": "717181a438d56735a5cfc030f648efb1e485509c1d0266d602e17e40ebf39560",
    "alpha3_4": "2488b4322894acb755872e9bc92d78dcaf2a4dec6ed807a22d3aff4622e2d5d5",
    "exact_zero_hit": "391d2fe5d7c133be42d3c503a92ecc8724f398430adf20c46283ad1567e8dfd5",
    "surface_execution": "052d332ecdf2042713ab07f608c934457908c6d5d9f15536c433c55c92f8b4d1",
}
ROOT_FILES = {
    "alpha3_9": A39 / "search_plan_v24_dev_alpha3_9_sha256",
    "alpha3_4": A34 / "search_plan_v24_dev_alpha3_4_sha256",
    "exact_zero_hit": EXACT / "search_plan_v24_dev_frozen_retrospective_retrieval_sha256",
    "surface_execution": SURFACE / "retrieval_surface_v2_complete_execution_corpus_sha256",
}
QUERY_FILE = A39 / "search_plan_v24_dev_search_constraint_allocation_v1_query_set.jsonl"
REQUIRED_OUTPUTS = {
    "upstream_root_verification.json", "alpha3_9_query_set_verification.json",
    "query_family_provenance_verification.json", "variant_class_verification.json",
    "lexical_freeze_audit.json", "downstream_policy_compatibility_audit.json",
    "downstream_policy_reuse_matrix.json", "query_execution_policy.json",
    "technical_retry_policy.json", "technical_continuation_policy.json",
    "runtime_adaptation_prohibition.json", "case_union_policy.json",
    "tail_policy.json", "metadata_policy.json", "candidate_validation_policy.json",
    "search_vs_validation_diagnostic_metrics.json", "variant_attribution_metric_policy.json",
    "query_family_overlap_metric_policy.json", "retrieval_viability_metrics.json",
    "preacquisition_scoring_policy.json", "oa_eligibility_policy.json",
    "selection_fulltext_policy.json", "known_paper_blindness_policy.json",
    "historical_label_blinding_policy.json", "four_architecture_comparison_plan.json",
    "search_constraint_allocation_v1_development_execution_manifest.json",
    "scientific_state_safety_audit.json", "validation.json", "summary.json",
    "search_plan_v24_dev_alpha3_10_sha256",
    "search_constraint_allocation_v1_development_execution_manifest_sha256",
}


def canonical(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


def digest(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path):
    return json.loads(path.read_text(encoding="utf-8"))


def lines(path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def freeze(name, value):
    path = RUN / name
    if path.exists() and not REWRITE_DRAFT:
        raise RuntimeError(f"refusing existing output: {path}")
    path.write_text(json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")


def ref(path):
    return {"path": str(path.relative_to(ROOT)), "sha256": sha(path)}


def verify_aggregate(directory, validation_path, expected):
    pairs = load(validation_path)["aggregate_components"]
    if any(sha(directory / name) != value for name, value in pairs) or digest(pairs) != expected:
        raise RuntimeError(f"aggregate mismatch: {directory}")
    return len(pairs)


def verify_alpha39(expected):
    files = {p.name: sha(p) for p in sorted(A39.iterdir()) if p.is_file() and p.name != "search_plan_v24_dev_alpha3_9_sha256"}
    actual = digest({"artifact_schema_version": "SearchPlanV24DevAlpha39FreezeV1", "files": files})
    if actual != expected:
        raise RuntimeError("alpha3.9 component drift")
    return len(files)


def policy(name):
    path = A34 / name
    return load(path), ref(path)


def write_policy(name, content, source):
    freeze(name, {"artifact_schema_version": "SearchConstraintAllocationV1" + name.removesuffix(".json").title().replace("_", "") + "Alpha310V1", "source_policy": source, "reuse_state": "REUSED_IDENTICALLY", **content})


def main():
    global REWRITE_DRAFT
    if RUN.exists():
        root_file = RUN / "search_plan_v24_dev_alpha3_10_sha256"
        if not root_file.exists() or root_file.read_text().strip() != KNOWN_DRAFT_ROOT or {p.name for p in RUN.iterdir()} != REQUIRED_OUTPUTS:
            raise RuntimeError("alpha3.10 output exists and is not the known draft; refusing overwrite")
        REWRITE_DRAFT = True
    for key, path in ROOT_FILES.items():
        if path.read_text(encoding="utf-8").strip() != EXPECTED[key]:
            raise RuntimeError(f"upstream root mismatch: {key}")
    if sha(QUERY_FILE) != EXPECTED["query_set"] or (A39 / "search_plan_v24_dev_search_constraint_allocation_v1_query_set_sha256").read_text().strip() != EXPECTED["query_set"]:
        raise RuntimeError("alpha3.9 query set drift")
    component_counts = {
        "alpha3_9": verify_alpha39(EXPECTED["alpha3_9"]),
        "alpha3_4": verify_aggregate(A34, A34 / "validation.json", EXPECTED["alpha3_4"]),
    }
    query_rows = lines(QUERY_FILE)
    ast_rows = lines(A39 / "empirical_query_family_ast.jsonl")
    cert_rows = lines(A39 / "empirical_query_certificates.jsonl")
    families = lines(A39 / "empirical_query_family_plans.jsonl")
    allocations = lines(A39 / "empirical_target_constraint_allocations.jsonl")
    q_summary = load(A39 / "summary.json")
    if q_summary["relation_contribution_count"] != 63 or q_summary["byte_unique_query_count"] != 55 or len(query_rows) != 55 or len(ast_rows) != 63 or len(cert_rows) != 63 or len(families) != 29 or len(allocations) != 29:
        raise RuntimeError("alpha3.9 cardinality mismatch")
    expected_case_counts = {f"heldout_v2_{n}": count for n, count in zip(range(101, 109), (7, 5, 3, 5, 9, 12, 6, 8))}
    actual_case_counts = dict(Counter(row["case_id"] for row in query_rows))
    if actual_case_counts != expected_case_counts:
        raise RuntimeError("alpha3.9 per-case query counts differ")

    ast_idx = {(r["case_id"], r["surface_plan_id"] if "surface_plan_id" in r else r["ast"]["source_surface_plan_id"], r["variant_class"], r["ast"]["ast_sha256"]): r["ast"] for r in ast_rows}
    cert_idx = {(r["case_id"], r["allocation_certificate"]["source_surface_plan_id"], r["variant_class"], r["certificate"]["query_ast_sha256"]): r for r in cert_rows}
    family_idx = {(r["case_id"], r["surface_plan_id"]): r for r in families}
    allocation_idx = {(r["case_id"], r["source_surface_plan_id"]): r for r in allocations}
    query_set_members = set()
    execution_rows = []
    contribution_count = 0
    for index, row in enumerate(query_rows, start=1):
        case = row["case_id"]
        query = row["query"]
        qsha = hashlib.sha256(query.encode("utf-8")).hexdigest()
        if row["query_id"] != "v24scav1q:" + qsha or (case, query.encode("utf-8")) in query_set_members:
            raise RuntimeError("query identity or within-case byte uniqueness failure")
        query_set_members.add((case, query.encode("utf-8")))
        contributions = []
        for contribution in row["contributions"]:
            key = (case, contribution["surface_plan_id"], contribution["variant_class"], contribution["ast_sha256"])
            ast = ast_idx[key]
            cert_row = cert_idx[key]
            family = family_idx[(case, contribution["surface_plan_id"])]
            allocation = allocation_idx[(case, contribution["surface_plan_id"])]
            if cert_row["query_id"] != row["query_id"] or ast["source_relation_core_sha256"] != allocation["source_relation_core_sha256"] or contribution["variant_class"] not in family["variants"]:
                raise RuntimeError("query contribution provenance mismatch")
            if ast["variant_class"] != contribution["variant_class"] or not cert_row["certificate"]["all_paths_certified"] or cert_row["certificate"]["unowned_deferred_scientific_role_count"]:
                raise RuntimeError("query certificate failure")
            family_id = "scafamv3:" + digest([case, contribution["surface_plan_id"], contribution["intent_type"]])
            family_certificate = {
                "artifact_schema_version": "FamilyLevelTargetCoverageV1",
                "family_id": family_id,
                "mandatory_search_roles": allocation["search_required_roles"],
                "context_variant_eligible_roles": allocation["variant_eligible_roles"],
                "deferred_validator_owners": allocation["deferred_validator_owners"],
                "unowned_deferred_roles": allocation["unowned_deferred_roles"],
                "scientific_target_validated_by_query": False,
            }
            contributions.append({
                "case_id": case, "intent_type": contribution["intent_type"],
                "variant_class": contribution["variant_class"], "query_family_id": family_id,
                "surface_plan_id": contribution["surface_plan_id"],
                "relation_core_sha256": ast["source_relation_core_sha256"],
                "target_sha256": allocation["source_target_sha256"],
                "search_constraint_allocation": allocation,
                "search_relation_evidence": {"contract_sha256": sha(A39 / "search_relation_evidence_v1_contract.json"), "mechanism": cert_row["certificate"]["relation_mechanism"], "scientific_proof": False},
                "minimum_relational_retrieval_evidence_certificate": cert_row["certificate"],
                "query_family_certificate": family_certificate,
                "query_ast": ast, "query_ast_sha256": ast["ast_sha256"],
                "serialized_query": query, "query_sha256": qsha,
            })
            contribution_count += 1
        execution_rows.append({"execution_order": index, "execution_status": "NOT_EXECUTED_PREREGISTRATION", "case_id": case, "query_id": row["query_id"], "exact_query_text": query, "query_sha256": qsha, "variant_classes": sorted({c["variant_class"] for c in contributions}), "contributions": contributions})
    if contribution_count != 63 or len(query_set_members) != 55:
        raise RuntimeError("query contribution map incomplete")
    if {c["query_ast_sha256"] for q in execution_rows for c in q["contributions"]} != {r["ast"]["ast_sha256"] for r in ast_rows}:
        raise RuntimeError("AST contribution set mismatch")
    variants = Counter(c["variant_class"] for q in execution_rows for c in q["contributions"])
    if variants != {"CORE_RELATION": 29, "ENDPOINT_RELATION_FOCUSED": 5, "CORE_RELATION_PLUS_CONTEXT": 29}:
        raise RuntimeError("variant-class drift")
    if set(q["variant_classes"][0] for q in execution_rows if len(q["variant_classes"]) == 1) - set(variants):
        raise RuntimeError("unknown variant label")
    target_hashes = defaultdict(set)
    for q in execution_rows:
        for c in q["contributions"]:
            target_hashes[q["case_id"]].add(c["target_sha256"])
    if set(target_hashes) != set(expected_case_counts) or any(len(hashes) != 1 for hashes in target_hashes.values()):
        raise RuntimeError("target identity mismatch")

    # The alpha3.4 scoring stack and each dependency must still be the frozen bytes.
    scoring, scoring_ref = policy("preacquisition_scoring_policy.json")
    component_drift = [name for name, expected in scoring["component_hashes"] if sha(ROOT / name) != expected]
    if component_drift:
        raise RuntimeError(f"frozen scoring dependency drift: {component_drift}")
    alpha34_manifest = load(A34 / "development_retrospective_retrieval_execution_manifest.json")
    for name, expected in alpha34_manifest["downstream_policy_hashes"].items():
        if sha(A34 / name) != expected:
            raise RuntimeError(f"frozen downstream policy drift: {name}")
    source_matrix = load(A37 / "downstream_policy_reuse_matrix.json")
    matrix = source_matrix["rows"]
    if any(row["compatibility"] != "REUSED_IDENTICALLY" or row["material_downstream_change"] or sha(A34 / row["alpha3_4_source_artifact"]) != row["alpha3_4_source_sha256"] for row in matrix):
        raise RuntimeError("alpha3.7 downstream reuse precedent drift")
    if len(matrix) < 21:
        raise RuntimeError("downstream policy matrix incomplete")
    qexec, qexec_ref = policy("query_execution_policy.json")
    retry, retry_ref = policy("retrieval_retry_policy.json")
    union, union_ref = policy("case_union_policy.json")
    tail, tail_ref = policy("tail_policy.json")
    metadata, metadata_ref = policy("metadata_policy.json")
    oa, oa_ref = policy("oa_eligibility_policy.json")
    fulltext, fulltext_ref = policy("fulltext_acquisition_policy.json")
    blind, blind_ref = policy("known_paper_blindness_policy.json")
    labels, labels_ref = policy("acquisition_label_blinding_policy.json")
    replacement, replacement_ref = policy("replacement_policy.json")
    if retry["maximum_total_attempts"] != 4 or retry["timeout_seconds"] != 60 or retry["backoff_seconds_after_failed_attempts"] != [2, 4, 8]:
        raise RuntimeError("technical retry mismatch")
    if tail["soft_tail"] != 120 or tail["hard_tail"] != 180 or tail["adaptive_tail_enabled"] or fulltext["maximum_fulltexts_per_case"] != 10:
        raise RuntimeError("tail/fulltext policy mismatch")
    if scoring["ordered_modules"] != ["base_v2.2_candidate_gate", "P0_BiologicalUnitCompatibilityV1_1", "P1_FunctionalRelationEvidenceV1_1", "P2_EndpointSemanticsV1", "Policy_A_Minimal"]:
        raise RuntimeError("candidate stack mismatch")
    if oa["required_identifier"] != "preserved PMCID" or fulltext["source"] != "NCBI PMC EFetch XML":
        raise RuntimeError("OA source mismatch")
    if qexec["case_order"] != sorted(expected_case_counts) or qexec["logical_execution_count_per_query"] != 1 or qexec["page_size"] != 30 or qexec["pubmed_sort"] != "relevance" or qexec["page_scheduling"] != "breadth-first round-robin across active queries within case":
        raise RuntimeError("query execution policy mismatch")
    if replacement["replacement_after_selection_failure"] or replacement["next_ranked_candidate_substitution"]:
        raise RuntimeError("replacement policy mismatch")

    protected = {"alpha3_9_query_set": QUERY_FILE, "alpha3_9_root": ROOT_FILES["alpha3_9"], "alpha3_4_root": ROOT_FILES["alpha3_4"], "exact_zero_hit_root": ROOT_FILES["exact_zero_hit"], "surface_execution_root": ROOT_FILES["surface_execution"], "alpha3_4_scoring_policy": A34 / "preacquisition_scoring_policy.json"}
    before = {name: sha(path) for name, path in protected.items()}
    RUN.mkdir(parents=True, exist_ok=True)
    freeze("upstream_root_verification.json", {"artifact_schema_version": "Alpha310UpstreamRootVerificationV1", "verified": True, "roots": {key: {"path": str(ROOT_FILES[key].relative_to(ROOT)), "expected": EXPECTED[key], "observed": ROOT_FILES[key].read_text().strip(), "component_count": component_counts.get(key)} for key in ROOT_FILES}, "query_set_sha256": EXPECTED["query_set"]})
    freeze("alpha3_9_query_set_verification.json", {"artifact_schema_version": "Alpha39QuerySetVerificationAlpha310V1", "query_set_verified": True, "query_set_path": str(QUERY_FILE.relative_to(ROOT)), "query_set_sha256": EXPECTED["query_set"], "relation_contribution_count": 63, "byte_unique_query_count": 55, "per_case_byte_unique_query_counts": actual_case_counts, "query_text_changes": 0})
    freeze("query_family_provenance_verification.json", {"artifact_schema_version": "QueryFamilyProvenanceVerificationAlpha310V1", "all_63_contributions_resolved": True, "all_55_queries_have_contributions": True, "family_count": len(families), "AST_count": len(ast_rows), "minimum_certificate_count": len(cert_rows), "allocation_count": len(allocations), "relation_core_refs_present": True, "target_hashes_by_case": {case: next(iter(hashes)) for case, hashes in sorted(target_hashes.items())}, "family_id_derivation": "scafamv3:sha256(canonical [case_id,surface_plan_id,intent_type])", "byte_identical_queries_execute_once_within_case": True, "cross_case_deduplication": False})
    freeze("variant_class_verification.json", {"artifact_schema_version": "VariantClassVerificationAlpha310V1", "labels_preserved_exactly": True, "contribution_counts": dict(variants), "byte_unique_query_variant_membership_counts": dict(Counter(label for q in execution_rows for label in q["variant_classes"])), "reclassification_after_retrieval": False, "CORE_RELATION_primary_diagnostic": True, "all_cases_have_CORE_RELATION": all(any(c["variant_class"] == "CORE_RELATION" for q in execution_rows if q["case_id"] == case for c in q["contributions"]) for case in expected_case_counts)})
    freeze("lexical_freeze_audit.json", {"artifact_schema_version": "LexicalFreezeAuditAlpha310V1", "query_text_changes": 0, "lexical_surface_changes": 0, "source_query_set_sha256": EXPECTED["query_set"], "new_aliases": 0, "new_synonyms": 0, "new_morphology_rules": 0, "ATM_policy_changes": 0, "unfielded_terms_added": 0, "relation_lexicon_changes": 0, "LLM_generated_wording": False, "manual_query_edits": False, "lexical_surface_undercoverage_resolved": False})
    freeze("downstream_policy_reuse_matrix.json", {"artifact_schema_version": "DownstreamPolicyReuseMatrixAlpha310V1", "source_alpha3_7_matrix": ref(A37 / "downstream_policy_reuse_matrix.json"), "rows": [{**row, "alpha3_10_compatibility": "REUSED_IDENTICALLY", "alpha3_10_material_change": False} for row in matrix], "material_downstream_policy_changes": 0})
    freeze("downstream_policy_compatibility_audit.json", {"artifact_schema_version": "DownstreamPolicyCompatibilityAuditAlpha310V1", "experimental_variable": "SEARCH_CONSTRAINT_ALLOCATION", "query_set_replacement_is_downstream_policy_change": False, "technical_continuation_is_post_abort_transport_epoch_only": True, "audited_dimension_count": len(matrix), "material_downstream_policy_changes": 0, "downstream_policy_compatible": True, "candidate_stack_component_drift": component_drift, "source_root_sha256": EXPECTED["alpha3_4"]})
    write_policy("query_execution_policy.json", {"query_count": 55, "case_order": qexec["case_order"], "logical_execution_count_per_byte_unique_query": 1, "execution_order": "frozen alpha3.9 query-set row order", "pubmed_sort": "relevance", "page_size": 30, "page_scheduling": "deterministic breadth-first round-robin across active queries within case", "pagination_is_transport_continuation_not_query_rerun": True, "all_queries_execute_unless_fail_closed": True, "family_variant_priority_cannot_skip_query": True, "hard_tail_count_only_behavior": tail["hard_tail_effect"]}, qexec_ref)
    write_policy("technical_retry_policy.json", {"maximum_total_attempts": 4, "timeout_seconds": 60, "backoff_seconds": [2, 4, 8], "automatic_retries_maximum": 3, "search_terminal_failure": retry["search_terminal_failure"], "metadata_terminal_failure": retry["metadata_terminal_failure"], "fulltext_terminal_failure": retry["fulltext_terminal_failure"], "technical_failure_is_scientific_zero": False}, retry_ref)
    freeze("technical_continuation_policy.json", {"artifact_schema_version": "TechnicalContinuationPolicyAlpha310V1", "preregistered_before_retrieval": True, "trigger": "first execution terminates solely from terminal transport failure after four-attempt policy", "failed_execution_freeze": "immutable", "incomplete_query_states": ["TERMINAL_TECHNICAL_FAILURE", "NOT_EXECUTED_AFTER_ABORT"], "continuation_epoch": "TECHNICAL_CONTINUATION_EPOCH", "continuation_set_derivation": "mechanical from frozen failed execution records", "successful_query_reruns": 0, "query_modifications": 0, "per_query_epoch_maximum_total_attempts": 4, "timeout_seconds": 60, "backoff_seconds": [2, 4, 8], "terminal_failure_in_continuation": "fail closed and stop", "combine_barrier": "all 55 byte-unique logical queries completed with successful transport result", "original_exhausted_attempts_relabelled": False, "source_precedent": ref(SURFACE / "technical_continuation_manifest.json"), "outcome_independent": True})
    freeze("runtime_adaptation_prohibition.json", {"artifact_schema_version": "RuntimeAdaptationProhibitionAlpha310V1", "runtime_adaptation_allowed": False, "forbidden_triggers": ["hit count", "CORE_RELATION result", "case difficulty", "variant class", "warnings", "candidate titles", "OA counts"], "forbidden_actions": ["drop/add context", "change relation constraints/proximity", "add lexical variant", "fallback to v2.3 or Surface V2", "skip frozen query"], "technical_pagination_and_preregistered_continuation_are_not_scientific_adaptation": True})
    write_policy("case_union_policy.json", {"union_scope": "WITHIN_CASE", "identity": "PMID", "cross_case_deduplication": False, "first_seen_order": "frozen query/page round-robin", "preserve_all_query_variant_intent_rank_page_relation_contributions": True, "hard_tail_after_within_case_deduplication": True}, union_ref)
    write_policy("tail_policy.json", {"soft_tail": 120, "soft_tail_reporting_only": True, "hard_tail": 180, "adaptive_tail_enabled": False, "application": "within-case PMID union after deduplication", "natural_exhaustion_retains_all": True, "count_only_requests_after_hard_tail": True}, tail_ref)
    write_policy("metadata_policy.json", {"fields": metadata["fields"], "source": metadata["source"], "batch_size": metadata["batch_size"], "query_execution_barrier_required": True, "missing_metadata_behavior": metadata["missing_metadata_behavior"], "outside_sources": False}, metadata_ref)
    write_policy("candidate_validation_policy.json", {"ordered_modules": scoring["ordered_modules"], "ranking_stack_sha256": scoring["stack_sha256"], "P0": "BiologicalUnitCompatibilityV1_1", "P1": "FunctionalRelationEvidenceV1_1", "P2": "EndpointSemanticsV1", "Policy_A": scoring["policy_a"], "tier_policy": scoring["tier_policy"], "search_does_not_assign_scientific_relevance": True, "validator_rejection_cannot_modify_query": True}, scoring_ref)
    freeze("search_vs_validation_diagnostic_metrics.json", {"artifact_schema_version": "SearchVsValidationDiagnosticMetricsAlpha310V1", "descriptive_only": True, "report_after_complete_query_barrier": ["candidates_entering_P0", "P0_incompatible", "P0_unresolved", "P0_retained", "candidates_entering_P1", "P1_blocking_relation_outcomes", "P1_unresolved", "P1_retained", "candidates_entering_P2", "P2_incompatible", "P2_unresolved", "P2_retained", "Policy_A_demotions"], "P0_P1_P2_policy_change": False, "observed_values": None})
    freeze("variant_attribution_metric_policy.json", {"artifact_schema_version": "VariantAttributionMetricPolicyAlpha310V1", "variant_classes": ["CORE_RELATION", "ENDPOINT_RELATION_FOCUSED", "CORE_RELATION_PLUS_CONTEXT"], "per_variant_metrics": ["query_count", "nonzero_query_count", "raw_hit_count", "unique_PMIDs_contributed", "PMIDs_uniquely_contributed", "hard_tail_PMIDs_contributed", "Tier_A_contributions", "Tier_B_contributions", "OA_contributions", "selected_contributions"], "multi_variant_PMIDs_count_for_every_contributing_variant": True, "PMID_metrics_censored_after_hard_tail_count_only_transition": True, "DIRECT_labels_prohibited": True, "observed_values": None})
    freeze("query_family_overlap_metric_policy.json", {"artifact_schema_version": "QueryFamilyOverlapMetricPolicyAlpha310V1", "scope": "within case, PMID identity, preserve all query contributions", "metrics": ["CORE_only_PMIDs", "context_only_additional_PMIDs", "PMIDs_shared_by_CORE_and_context_refined_variants", "endpoint_variant_overlap"], "descriptive_only": True, "observed_values": None})
    freeze("retrieval_viability_metrics.json", {"artifact_schema_version": "RetrievalViabilityMetricsAlpha310V1", "before_metadata_scientific_interpretation": True, "primary_metrics": ["nonzero_query_count", "zero_hit_query_count", "nonzero_case_count", "zero_hit_case_count", "CORE_RELATION_nonzero_query_count", "cases_with_nonzero_CORE_RELATION", "unique_PMIDs_before_tail_total"], "CORE_RELATION_additional_metrics": ["CORE_RELATION_queries_executed", "CORE_RELATION_nonzero_queries", "cases_with_nonzero_CORE_RELATION_retrieval", "unique_PMIDs_contributed_by_CORE_RELATION"], "hard_tail_censoring_flag_required": True, "before_tail_unique_PMIDs_meaning": "observed unique PMID union before hard-tail acceptance cap; not a complete universe when count-only transition occurs", "zero_hit_requires_successful_transport": True, "observed_values": None})
    write_policy("preacquisition_scoring_policy.json", {"ordered_modules": scoring["ordered_modules"], "stack_sha256": scoring["stack_sha256"], "component_hashes_verified": True, "policy_a": scoring["policy_a"], "tier_policy": scoring["tier_policy"], "within_tier_order": scoring["within_tier_order"], "historical_labels_used": False}, scoring_ref)
    write_policy("oa_eligibility_policy.json", {"required_identifier": "preserved PMCID", "source": "frozen PubMed metadata PMCID field", "permitted_fulltext_source": "NCBI PMC EFetch only", "DOI_title_journal_inference": False, "general_web_or_publisher_fallback": False}, oa_ref)
    write_policy("selection_fulltext_policy.json", {"selection_order": fulltext["selection_order"], "maximum_fulltexts_per_case": 10, "all_eight_ordered_manifests_frozen_before_first_fetch": True, "PMCID_required": True, "source": "NCBI PMC EFetch XML", "replacement": replacement, "no_replacement": True, "selection_cannot_use_fulltext_content": True}, fulltext_ref)
    write_policy("known_paper_blindness_policy.json", {"known_paper_queries": False, "known_PMID_recovery_before_acquisition_freeze": False, "manual_PMID_injection": False, "historical_direct_PMID_exposure_to_selection": False, "postfreeze_recovery_requires_separate_preregistration": True}, blind_ref)
    write_policy("historical_label_blinding_policy.json", {"historical_PASS_A_labels_visible": False, "historical_PASS_B_labels_visible": False, "DIRECT_relevance_labels_visible": False, "candidate_selection_label_blind": True, "neutral_review_corpus_freeze_separate": True, "future_adjudication_requires_separate_authorization": True}, labels_ref)
    freeze("four_architecture_comparison_plan.json", {"artifact_schema_version": "FourArchitectureComparisonPlanAlpha310V1", "architectures": ["v2.3 historical", "v2.4 exact-proposition serializer", "Retrieval Surface V2", "SearchConstraintAllocationV1"], "permitted_pre_relevance_metrics": ["query_count", "nonzero_query_count", "nonzero_case_count", "candidate_universe_size", "metadata_universe_size", "Tier_A_count", "Tier_B_count", "OA_count", "acquisition_count"], "prohibited_before_relevance_review": ["DIRECT_rate", "precision", "recall", "acceptability"], "historical_roots": {"exact_zero_hit": EXPECTED["exact_zero_hit"], "surface_execution": EXPECTED["surface_execution"]}, "no_historical_reexecution": True, "observed_values": None})
    freeze("scientific_state_safety_audit.json", {"artifact_schema_version": "ScientificStateSafetyAuditAlpha310V1", "scientific_targets_modified": False, "queries_modified": False, "lexical_surfaces_modified": False, "P0_P1_P2_Policy_A_modified": False, "known_pmid_checks": 0, "hit_counts_seen": 0, "candidate_records_seen": 0, "network_calls": 0, "retrieval_calls": 0, "provider_calls": 0, "llm_calls": 0})

    policy_hashes = {name: sha(A34 / name) for name in alpha34_manifest["downstream_policy_hashes"]}
    execution_manifest = {
        "artifact_schema_version": "SearchConstraintAllocationV1DevelopmentExecutionManifestAlpha310V1",
        "experimental_variable": "SEARCH_CONSTRAINT_ALLOCATION",
        "scientific_question": "Does search-versus-validation allocation restore a non-empty candidate universe while preserving relational retrieval?",
        "alpha3_9_root_sha256": EXPECTED["alpha3_9"],
        "query_set_sha256": EXPECTED["query_set"],
        "alpha3_4_downstream_root_sha256": EXPECTED["alpha3_4"],
        "query_count": 55, "relation_variant_contribution_count": 63,
        "exact_queries": execution_rows,
        "variant_labels": sorted(variants),
        "target_sha256_by_case": {case: next(iter(hashes)) for case, hashes in sorted(target_hashes.items())},
        "downstream_policy_hashes": policy_hashes,
        "downstream_reuse_matrix_sha256": sha(RUN / "downstream_policy_reuse_matrix.json"),
        "execution_policy_sha256": sha(RUN / "query_execution_policy.json"),
        "tail_policy_sha256": sha(RUN / "tail_policy.json"),
        "metadata_policy_sha256": sha(RUN / "metadata_policy.json"),
        "candidate_validation_policy_sha256": sha(RUN / "candidate_validation_policy.json"),
        "OA_policy_sha256": sha(RUN / "oa_eligibility_policy.json"),
        "fulltext_selection_policy_sha256": sha(RUN / "selection_fulltext_policy.json"),
        "retry_policy_sha256": sha(RUN / "technical_retry_policy.json"),
        "technical_continuation_policy_sha256": sha(RUN / "technical_continuation_policy.json"),
        "known_paper_blindness_policy_sha256": sha(RUN / "known_paper_blindness_policy.json"),
        "historical_label_blinding_policy_sha256": sha(RUN / "historical_label_blinding_policy.json"),
        "future_metrics_policy_sha256": {name: sha(RUN / name) for name in ["search_vs_validation_diagnostic_metrics.json", "variant_attribution_metric_policy.json", "query_family_overlap_metric_policy.json", "retrieval_viability_metrics.json", "four_architecture_comparison_plan.json"]},
        "soft_tail": 120, "hard_tail": 180, "adaptive_tail_enabled": False,
        "max_fulltexts_per_case": 10, "no_replacement": True,
        "runtime_adaptation_allowed": False, "known_paper_blindness": True, "historical_label_blinding": True,
        "execution_status": "NOT_EXECUTED_PREREGISTRATION", "observed_retrieval_values": None,
    }
    freeze("search_constraint_allocation_v1_development_execution_manifest.json", execution_manifest)
    manifest_sha = sha(RUN / "search_constraint_allocation_v1_development_execution_manifest.json")
    (RUN / "search_constraint_allocation_v1_development_execution_manifest_sha256").write_text(manifest_sha + "\n")
    after = {name: sha(path) for name, path in protected.items()}
    if before != after:
        raise RuntimeError("protected historical asset changed")
    summary = {"artifact_schema_version": "SearchPlanV24DevAlpha310SummaryV1", "status": "completed", "query_set_verified": True, "relation_contribution_count": 63, "byte_unique_query_count": 55, "query_text_changes": 0, "lexical_surface_changes": 0, "material_downstream_policy_changes": 0, "downstream_policy_compatible": True, "technical_continuation_policy_preregistered": True, "soft_tail": 120, "hard_tail": 180, "adaptive_tail_enabled": False, "max_fulltexts_per_case": 10, "known_paper_blindness_frozen": True, "historical_label_blinding_frozen": True, "runtime_adaptation_allowed": False, "execution_manifest_created": True, "search_constraint_allocation_v1_development_execution_manifest_sha256": manifest_sha, "production_case_specific_rules": 0, "next_stage_recommendation": "AUTHORIZE_SEARCH_CONSTRAINT_ALLOCATION_V1_FULL_DEVELOPMENT_RETRIEVAL", "provider_calls": 0, "llm_calls": 0, "network_calls": 0, "retrieval_calls": 0, "hit_counts_seen": 0, "candidate_records_seen": 0, "historical_assets_modified": False}
    freeze("summary.json", summary)
    actual_names = {p.name for p in RUN.iterdir() if p.is_file()}
    if actual_names | {"validation.json", "search_plan_v24_dev_alpha3_10_sha256"} != REQUIRED_OUTPUTS:
        raise RuntimeError("required output set mismatch")
    freeze("validation.json", {"artifact_schema_version": "SearchPlanV24DevAlpha310ValidationV1", "valid": True, "required_output_names": sorted(REQUIRED_OUTPUTS), "summary": summary, "runner_sha256": sha(ROOT / "scripts/search_plan_v24_alpha310_preregister_offline.py"), "upstream_roots_verified": True, "all_query_contributions_reconciled": True, "downstream_component_hashes_verified": True, "no_observed_retrieval_values": True})
    components = [[p.name, sha(p)] for p in sorted(RUN.iterdir()) if p.is_file() and p.name != "search_plan_v24_dev_alpha3_10_sha256"]
    root = digest(components)
    (RUN / "search_plan_v24_dev_alpha3_10_sha256").write_text(root + "\n")
    print(json.dumps({**summary, "search_plan_v24_dev_alpha3_10_sha256": root, "file_count": len(components) + 1}, sort_keys=True))


if __name__ == "__main__":
    main()
