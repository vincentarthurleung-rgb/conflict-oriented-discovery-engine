"""Preregister alpha3.11 lexicalized retrieval without inspecting results."""

from __future__ import annotations

from collections import Counter
import hashlib
import json
from pathlib import Path
import shutil
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
A39 = ROOT / "runs/20260925_search_plan_v24_dev_alpha3_9_search_constraint_allocation_offline"
A310 = ROOT / "runs/20260925_search_plan_v24_dev_alpha3_10_search_constraint_allocation_retrieval_preregistration_offline"
A311 = ROOT / "runs/20260925_search_plan_v24_dev_alpha3_11_bounded_lexical_realization_v2_offline"
A34 = ROOT / "runs/20260923_search_plan_v24_dev_alpha3_4_retrieval_preregistration_offline"
RUN = ROOT / "runs/20260925_search_plan_v24_dev_alpha3_12_bounded_lexical_realization_v2_retrieval_preregistration_offline"
ROOTS = {
    A311 / "search_plan_v24_dev_alpha3_11_sha256": "2a006173d4bc4c512631303b5ab29142c465a0ece2ab64c9382a604652a5b2ad",
    A311 / "search_plan_v24_dev_bounded_lexical_realization_v2_query_set_sha256": "6edd5be9b9cdc6d1bf522585c214aa524e716ff27b1f244dfb7ca8b99ab99cb9",
    A310 / "search_plan_v24_dev_alpha3_10_sha256": "e6d05cfdb933e644d6da7fe0bb675e87deadf85108cc69149319887460c6eb10",
    A39 / "search_plan_v24_dev_search_constraint_allocation_v1_query_set_sha256": "717181a438d56735a5cfc030f648efb1e485509c1d0266d602e17e40ebf39560",
}
CANONICAL_CORPUS = "b918c60ea7efdf7ea10758b6e84199f8c5c06e3718589afb85468263af7d63a7"
OLD_MANIFEST_SHA = "f2935db4963b20438c057aea3c4c654e19a7668e6a581207ae8d02c231aa7930"
NEW_QUERY = A311 / "search_plan_v24_dev_bounded_lexical_realization_v2_query_set.jsonl"
OLD_QUERY = A39 / "search_plan_v24_dev_search_constraint_allocation_v1_query_set.jsonl"
OLD_MANIFEST = A310 / "search_constraint_allocation_v1_development_execution_manifest.json"
COPIED_POLICY_FILES = (
    "technical_retry_policy.json", "technical_continuation_policy.json",
    "runtime_adaptation_prohibition.json", "case_union_policy.json",
    "tail_policy.json", "metadata_policy.json", "candidate_validation_policy.json",
    "oa_eligibility_policy.json", "selection_fulltext_policy.json",
    "known_paper_blindness_policy.json", "historical_label_blinding_policy.json",
)
ALLOWED_CLASSES = {
    "CANONICAL_SURFACE", "AUTHORIZED_ALIAS", "VALIDATED_PLANNER_SURFACE",
    "DETERMINISTIC_MORPHOLOGICAL_VARIANT", "FROZEN_RELATION_LEXICON",
    "FROZEN_ENDPOINT_LEXICON",
}


def canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode()


def digest(value: Any) -> str:
    return hashlib.sha256(canonical(value)).hexdigest()


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def rows(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def write(name: str, value: Any, *, json_lines: bool = False) -> None:
    path = RUN / name
    if path.exists():
        raise RuntimeError(f"refusing existing artifact: {name}")
    path.parent.mkdir(parents=True, exist_ok=True)
    if json_lines:
        path.write_bytes(b"".join(canonical(row) + b"\n" for row in value))
    else:
        path.write_text(json.dumps(value, sort_keys=True, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def copy_policy(name: str) -> str:
    source = A310 / name
    target = RUN / name
    if target.exists():
        raise RuntimeError(f"refusing existing policy: {name}")
    shutil.copy2(source, target)
    if sha(source) != sha(target):
        raise RuntimeError(f"policy copy mismatch: {name}")
    return sha(target)


def verify_upstream() -> tuple[dict[str, Any], dict[str, Any]]:
    for path, expected in ROOTS.items():
        if path.read_text(encoding="utf-8").strip() != expected:
            raise RuntimeError(f"upstream root file drift: {path}")
    a311_validation = load(A311 / "validation.json")
    pairs = a311_validation["aggregate_components"]
    if any(sha(A311 / name) != value for name, value in pairs) or digest(pairs) != ROOTS[A311 / "search_plan_v24_dev_alpha3_11_sha256"]:
        raise RuntimeError("alpha3.11 component drift")
    a310_files = sorted(p for p in A310.iterdir() if p.is_file() and p.name != "search_plan_v24_dev_alpha3_10_sha256")
    if digest([[p.name, sha(p)] for p in a310_files]) != ROOTS[A310 / "search_plan_v24_dev_alpha3_10_sha256"]:
        raise RuntimeError("alpha3.10 component drift")
    if sha(NEW_QUERY) != ROOTS[A311 / "search_plan_v24_dev_bounded_lexical_realization_v2_query_set_sha256"] or sha(OLD_QUERY) != ROOTS[A39 / "search_plan_v24_dev_search_constraint_allocation_v1_query_set_sha256"]:
        raise RuntimeError("query-set bytes drift")
    binding = load(A311 / "canonical_scientific_corpus_binding.json")
    if not binding["scientific_payload_equivalent"] or digest(binding["canonical_components"]) != CANONICAL_CORPUS or binding["canonical_search_constraint_allocation_v1_scientific_corpus_sha256"] != CANONICAL_CORPUS:
        raise RuntimeError("canonical scientific corpus binding drift")
    if sha(OLD_MANIFEST) != OLD_MANIFEST_SHA or (A310 / "search_constraint_allocation_v1_development_execution_manifest_sha256").read_text().strip() != OLD_MANIFEST_SHA:
        raise RuntimeError("alpha3.10 execution manifest drift")
    refs = {str(path.relative_to(ROOT)): {"expected_sha256": expected, "observed_sha256": path.read_text().strip(), "verified": True} for path, expected in ROOTS.items()}
    refs[str(OLD_MANIFEST.relative_to(ROOT))] = {"expected_sha256": OLD_MANIFEST_SHA, "observed_sha256": sha(OLD_MANIFEST), "verified": True}
    return refs, binding


def contribution_mapping() -> tuple[list[dict[str, Any]], dict[str, Any], list[dict[str, Any]], list[dict[str, Any]]]:
    old = rows(A39 / "empirical_serialized_queries.jsonl")
    old_ast = rows(A39 / "empirical_query_family_ast.jsonl")
    old_certs = rows(A39 / "empirical_query_certificates.jsonl")
    new = rows(A311 / "empirical_serialized_queries.jsonl")
    unique = rows(NEW_QUERY)
    if not (len(old) == len(old_ast) == len(old_certs) == len(new) == 63 and len(unique) == 55):
        raise RuntimeError("query/contribution cardinality drift")
    key = lambda r: (r["case_id"], r["surface_plan_id"], r["intent_type"], r["variant_class"])
    old_by = {key(r): (r, ast, cert) for r, ast, cert in zip(old, old_ast, old_certs)}
    new_by = {key(r): r for r in new}
    if len(old_by) != 63 or len(new_by) != 63 or old_by.keys() != new_by.keys():
        raise RuntimeError("structurally unmappable query contribution")
    pairs = []
    for k in old_by:
        prior, ast_row, cert_row = old_by[k]
        current = new_by[k]
        if ast_row["ast"]["source_surface_plan_id"] != k[1] or ast_row["ast"]["source_relation_core_sha256"] != current["relation_core_sha256"] or cert_row["allocation_certificate"] != current["search_constraint_allocation_certificate"]:
            raise RuntimeError("RelationCore or allocation provenance changed")
        previous_cert = {x: y for x, y in cert_row["certificate"].items() if x != "query_ast_sha256"}
        current_cert = {x: y for x, y in current["minimum_relational_retrieval_evidence_certificate"].items() if x != "query_ast_sha256"}
        if previous_cert != current_cert:
            raise RuntimeError("minimum relational evidence semantics changed")
        state = "BYTE_IDENTICAL" if prior["query"].encode() == current["query"].encode() else "LEXICALLY_CHANGED_ONLY"
        pairs.append({"artifact_schema_version": "Alpha39ToAlpha311QueryContributionPairV1", "case_id": k[0], "surface_plan_id": k[1], "intent_type": k[2], "variant_class": k[3], "relation_core_sha256": current["relation_core_sha256"], "alpha39_query_id": prior["query_id"], "alpha39_query_sha256": hashlib.sha256(prior["query"].encode()).hexdigest(), "alpha311_query_id": current["query_id"], "alpha311_query_sha256": current["query_sha256"], "allocation_certificate_sha256": digest(cert_row["allocation_certificate"]), "minimum_relational_evidence_semantics_sha256": digest(previous_cert), "lexical_alternative_set_ids": current["lexical_coverage_certificate"]["role_alternatives"], "source_plan_all_role_set_ids": current["lexical_alternative_set_ids"], "mapping_state": state})
    for row in unique:
        if hashlib.sha256(row["query"].encode()).hexdigest() != row["query_sha256"] or len(row["contributions"]) < 1:
            raise RuntimeError("new frozen query row drift")
    counts = Counter(row["mapping_state"] for row in pairs)
    if counts.get("STRUCTURALLY_UNMAPPABLE", 0):
        raise RuntimeError("unmappable query contribution")
    old_unique = rows(OLD_QUERY)
    old_texts = {(r["case_id"], r["query"].encode()) for r in old_unique}
    identical_query_count = sum((r["case_id"], r["query"].encode()) in old_texts for r in unique)
    summary = {"artifact_schema_version": "Alpha311LexicalChangeSummaryV1", "contribution_counts": dict(counts), "alpha39_byte_identical_query_contribution_count": counts.get("BYTE_IDENTICAL", 0), "alpha39_lexically_changed_only_query_contribution_count": counts.get("LEXICALLY_CHANGED_ONLY", 0), "structurally_unmappable_query_contributions": 0, "alpha39_identical_byte_unique_query_count": identical_query_count, "lexically_changed_byte_unique_query_count": len(unique) - identical_query_count, "alpha39_same_family_single_surface_roles": [307, 333], "alpha311_same_family_single_surface_roles": [209, 333], "query_text_changes_after_alpha3_11": 0, "additional_lexical_surface_changes": 0, "no_retrieval_outcomes_used": True}
    return pairs, summary, new, unique


def lexical_authority(new: list[dict[str, Any]]) -> dict[str, Any]:
    sets = rows(A311 / "lexical_alternative_sets.jsonl")
    certs = rows(A311 / "lexical_coverage_certificates.jsonl")
    by_id = {s["lexical_alternative_set_id"]: s for s in sets}
    if len(by_id) != len(sets) or len(certs) != 63:
        raise RuntimeError("lexical authority artifact cardinality mismatch")
    used_ids = {identifier for r in new for identifier in r["lexical_coverage_certificate"]["role_alternatives"].values()}
    bad = []
    for identifier in used_ids:
        if identifier not in by_id:
            bad.append({"lexical_alternative_set_id": identifier, "reason": "MISSING_SET"})
            continue
        for item in by_id[identifier]["alternatives"]:
            if item["authority_class"] not in ALLOWED_CLASSES or item["safety_status"] not in {"AUTHORIZED_EXACT_SURFACE", "WHITELISTED_GRAMMATICAL_REALIZATION"} or item["canonical_target_link"] != by_id[identifier]["canonical_target_link"]:
                bad.append({"lexical_alternative_set_id": identifier, "surface": item["surface"], "reason": "UNATTRIBUTED_OR_UNSAFE"})
    cert_by = {(c["case_id"], c["source_plan_id"] if "source_plan_id" in c else c["surface_plan_id"], c["variant_class"]): c for c in certs}
    for r in new:
        c = cert_by.get((r["case_id"], r["surface_plan_id"], r["variant_class"]))
        if c is None or c["query_id"] != r["query_id"] or c["query_ast_sha256"] != r["ast_sha256"] or c["identity_safety_result"] != "PASS" or c["semantic_broadening_result"] != "PASS":
            bad.append({"query_id": r["query_id"], "reason": "LEXICAL_CERTIFICATE_MISMATCH"})
    if bad:
        raise RuntimeError(f"unattributed executable surface or certificate: {bad[:3]}")
    return {"artifact_schema_version": "Alpha312LexicalAuthorityVerificationV1", "set_count": len(sets), "used_set_count": len(used_ids), "certificate_count": len(certs), "allowed_executable_classes": sorted(ALLOWED_CLASSES), "unattributed_executable_surface_count": 0, "unresolved_executable_surface_count": 0, "all_lexical_coverage_certificates_match": True, "lexical_alternative_sets_sha256": sha(A311 / "lexical_alternative_sets.jsonl"), "lexical_coverage_certificates_sha256": sha(A311 / "lexical_coverage_certificates.jsonl")}


def main() -> None:
    if RUN.exists():
        raise RuntimeError(f"refusing existing preregistration run: {RUN}")
    roots, binding = verify_upstream()
    mapping, lexical_summary, contributions, queries = contribution_mapping()
    lexical_check = lexical_authority(contributions)
    old_manifest = load(OLD_MANIFEST)
    matrix = load(A310 / "downstream_policy_reuse_matrix.json")
    if old_manifest["query_set_sha256"] != ROOTS[A39 / "search_plan_v24_dev_search_constraint_allocation_v1_query_set_sha256"] or any(row["compatibility"] != "REUSED_IDENTICALLY" or row["material_downstream_change"] for row in matrix["rows"]):
        raise RuntimeError("alpha3.10 downstream policy incompatible")
    for name, value in old_manifest["downstream_policy_hashes"].items():
        if sha(A34 / name) != value:
            raise RuntimeError(f"frozen downstream policy drift: {name}")
    protected_paths = list(ROOTS) + [NEW_QUERY, OLD_QUERY, OLD_MANIFEST, A311 / "lexical_alternative_sets.jsonl", A311 / "lexical_coverage_certificates.jsonl", A311 / "canonical_scientific_corpus_binding.json"] + [A310 / n for n in COPIED_POLICY_FILES]
    before = {str(p.relative_to(ROOT)): sha(p) for p in protected_paths}
    RUN.mkdir(parents=True)
    write("upstream_root_verification.json", {"artifact_schema_version": "Alpha312UpstreamRootVerificationV1", "verified": True, "roots": roots, "old_execution_manifest_sha256": OLD_MANIFEST_SHA})
    write("canonical_scientific_corpus_binding_verification.json", {"artifact_schema_version": "Alpha312CanonicalCorpusBindingVerificationV1", "canonical_scientific_corpus_bound": True, "canonical_search_constraint_allocation_v1_scientific_corpus_sha256": CANONICAL_CORPUS, "source_binding_sha256": sha(A311 / "canonical_scientific_corpus_binding.json"), "historical_source_and_projection_roots_preserved": True, "no_candidate_content_inspected": True})
    write("alpha3_11_query_set_verification.json", {"artifact_schema_version": "Alpha311QuerySetVerificationForAlpha312V1", "query_set_verified": True, "expected_sha256": ROOTS[A311 / "search_plan_v24_dev_bounded_lexical_realization_v2_query_set_sha256"], "observed_sha256": sha(NEW_QUERY), "relation_contribution_count": len(contributions), "byte_unique_query_count": len(queries), "query_text_changes_after_alpha3_11": 0, "additional_lexical_surface_changes": 0})
    write("query_pair_mapping.jsonl", mapping, json_lines=True)
    write("lexical_change_summary.json", lexical_summary)
    write("lexical_authority_verification.json", lexical_check)
    budget = load(A311 / "lexical_budget_policy.json")
    if budget["max_alternatives_per_semantic_role"] != 4 or budget["max_morphology_variants_per_base"] != 3 or budget["max_queries_per_target"] != 12:
        raise RuntimeError("lexical budget drift")
    write("lexical_budget_freeze.json", {"artifact_schema_version": "Alpha312LexicalBudgetFreezeV1", "source_policy_sha256": sha(A311 / "lexical_budget_policy.json"), "max_alternatives_per_semantic_role": 4, "max_morphology_variants_per_base": 3, "max_queries_per_target": 12, "case_level_byte_deduplication": True, "post_result_tuning": False})
    write("structural_immutability_audit.json", {"artifact_schema_version": "Alpha312StructuralImmutabilityAuditV1", "SearchConstraintAllocation_changed": False, "query_family_semantics_changed": False, "RelationCore_changed": False, "minimum_relational_evidence_semantics_changed": False, "therapy_internality_changed": False, "conditioning_internality_changed": False, "endpoint_internality_changed": False, "structurally_unmappable_query_contributions": 0, "mapped_contribution_count": len(mapping), "source_alpha3_11_audit_sha256": {n: sha(A311 / n) for n in ("search_constraint_allocation_immutability_audit.json", "query_family_immutability_audit.json", "identity_safety_audit.json", "semantic_broadening_audit.json")}})
    matrix_rows = [{**row, "alpha3_12_compatibility": "REUSED_IDENTICALLY", "alpha3_12_material_change": False} for row in matrix["rows"]]
    write("downstream_policy_reuse_matrix.json", {"artifact_schema_version": "DownstreamPolicyReuseMatrixAlpha312V1", "source_alpha3_10_matrix_sha256": sha(A310 / "downstream_policy_reuse_matrix.json"), "rows": matrix_rows, "material_downstream_policy_changes": 0, "query_set_input_identity_changed_only": True})
    write("downstream_policy_compatibility_audit.json", {"artifact_schema_version": "Alpha312DownstreamPolicyCompatibilityAuditV1", "downstream_policy_compatible": True, "material_downstream_policy_changes": 0, "audited_dimension_count": len(matrix_rows), "all_dimensions": "REUSED_IDENTICALLY", "alpha3_10_root_sha256": ROOTS[A310 / "search_plan_v24_dev_alpha3_10_sha256"], "alpha3_4_policy_hashes_verified": True, "only_query_set_input_binding_changes": True})
    for name in COPIED_POLICY_FILES:
        copy_policy(name)
    query_policy = load(A310 / "query_execution_policy.json")
    if query_policy["execution_order"] != "frozen alpha3.9 query-set row order" or query_policy["query_count"] != 55:
        raise RuntimeError("alpha3.10 execution input assumption changed")
    write("query_execution_policy.json", {**query_policy, "artifact_schema_version": "BoundedLexicalRealizationV2QueryExecutionPolicyAlpha312V1", "execution_order": "frozen alpha3.11 query-set row order", "query_set_input_sha256": sha(NEW_QUERY), "source_alpha3_10_policy_sha256": sha(A310 / "query_execution_policy.json"), "input_identity_change_only": True, "material_execution_semantics_changed": False})
    write("retrieval_viability_metrics.json", {"artifact_schema_version": "Alpha312RetrievalViabilityMetricPlanV1", "primary_metrics": ["nonzero_query_count", "zero_hit_query_count", "nonzero_case_count", "zero_hit_case_count", "unique_pmids_before_tail_total", "CORE_RELATION_nonzero_query_count", "cases_with_nonzero_CORE_RELATION"], "technical_failure_not_zero_hit": True, "observed_values": None})
    write("lexical_attribution_metric_policy.json", {"artifact_schema_version": "Alpha312LexicalAttributionMetricPolicyV1", "per_nonzero_query_fields": ["lexical_alternative_set_ids", "authority_classes_present", "text_differs_from_alpha3_9_counterpart", "associated_with_nonzero_retrieval_after_lexical_change"], "set_presence_source": "LexicalCoverageCertificateV2.role_alternatives", "source_plan_only_sets_not_counted_as_query_present": True, "aggregate_fields": ["alpha3_9_identical_query_count", "lexically_changed_query_count", "nonzero_alpha3_9_identical_queries", "nonzero_lexically_changed_queries"], "specific_alternative_causation_claims_allowed": False, "observed_values": None})
    write("variant_attribution_metric_policy.json", {"artifact_schema_version": "Alpha312VariantAttributionMetricPolicyV1", "variants": ["CORE_RELATION", "ENDPOINT_RELATION_FOCUSED", "CORE_RELATION_PLUS_CONTEXT"], "metrics_per_variant": ["query_count", "nonzero_count", "raw_hits", "unique_pmids", "uniquely_contributed_pmids", "shared_pmids"], "many_to_many_attribution": True, "observed_values": None})
    write("five_architecture_comparison_plan.json", {"artifact_schema_version": "Alpha312FiveArchitectureComparisonPlanV1", "architectures": ["v2.3", "exact-proposition serializer", "Surface V2", "SearchConstraintAllocationV1", "SearchConstraintAllocationV1 + BoundedLexicalRealizationV2"], "primary_comparison": ["SearchConstraintAllocationV1", "SearchConstraintAllocationV1 + BoundedLexicalRealizationV2"], "allowed_descriptive_fields": ["query count", "nonzero queries", "nonzero cases", "candidate universe", "metadata count", "Tier A/B counts", "OA count", "selected count", "acquired count"], "prohibited_fields": ["precision", "recall", "DIRECT rate", "acceptability"], "historical_baseline_user_supplied_not_read_from_candidate_records": {"query_count": 55, "nonzero_query_count": 3, "nonzero_case_count": 2, "unique_pmids": 2, "core_relation_query_count": 25, "core_relation_nonzero_query_count": 3, "metadata_records": 2, "tier_a": 0, "tier_b": 1, "abstain": 1, "oa_eligible": 1, "fulltexts_acquired": 1}, "new_observed_values": None})
    metadata = load(RUN / "metadata_policy.json")
    tail = load(RUN / "tail_policy.json")
    selection = load(RUN / "selection_fulltext_policy.json")
    retry = load(RUN / "technical_retry_policy.json")
    continuation = load(RUN / "technical_continuation_policy.json")
    if metadata["fields"] != ["PMID", "PMCID", "DOI", "title", "abstract text/availability", "publication date/year", "journal", "publication types"] or tail["soft_tail"] != 120 or tail["hard_tail"] != 180 or tail["adaptive_tail_enabled"] or selection["maximum_fulltexts_per_case"] != 10 or retry["maximum_total_attempts"] != 4 or retry["timeout_seconds"] != 60 or retry["backoff_seconds"] != [2, 4, 8] or not continuation["preregistered_before_retrieval"]:
        raise RuntimeError("downstream policy detail mismatch")
    write("scientific_state_safety_audit.json", {"artifact_schema_version": "Alpha312ScientificStateSafetyAuditV1", "known_pmid_checks": 0, "historical_label_reads": 0, "candidate_content_driven_query_design": 0, "manual_candidate_injections": 0, "scientific_relevance_adjudications": 0, "query_changes_after_alpha3_11": 0, "network_calls": 0, "retrieval_calls": 0, "provider_calls": 0, "llm_calls": 0, "hit_counts_seen": 0, "candidate_records_seen": 0})
    protected_after = {str(p.relative_to(ROOT)): sha(p) for p in protected_paths}
    if before != protected_after:
        raise RuntimeError("protected frozen input modified")
    # The execution manifest binds immutable inputs and policies, not observed outcomes.
    target_hashes = old_manifest["target_sha256_by_case"]
    if len(target_hashes) != 8 or any(r["search_constraint_allocation_certificate"]["source_target_sha256"] != target_hashes[r["case_id"]] for r in contributions):
        raise RuntimeError("target hash provenance changed")
    execution_manifest = {"artifact_schema_version": "BoundedLexicalRealizationV2DevelopmentExecutionManifestAlpha312V1", "alpha3_11_root_sha256": ROOTS[A311 / "search_plan_v24_dev_alpha3_11_sha256"], "new_query_set_sha256": sha(NEW_QUERY), "previous_alpha3_9_query_set_sha256": sha(OLD_QUERY), "canonical_scientific_corpus_sha256": CANONICAL_CORPUS, "alpha3_10_downstream_protocol_sha256": ROOTS[A310 / "search_plan_v24_dev_alpha3_10_sha256"], "previous_execution_manifest_sha256": OLD_MANIFEST_SHA, "target_sha256_by_case": target_hashes, "relation_contribution_count": len(contributions), "byte_unique_query_count": len(queries), "lexical_alternative_sets_sha256": sha(A311 / "lexical_alternative_sets.jsonl"), "lexical_coverage_certificates_sha256": sha(A311 / "lexical_coverage_certificates.jsonl"), "lexical_budget_policy_sha256": sha(A311 / "lexical_budget_policy.json"), "query_pair_mapping_sha256": sha(RUN / "query_pair_mapping.jsonl"), "exact_queries": queries, "per_contribution_provenance": [{"case_id": r["case_id"], "surface_plan_id": r["surface_plan_id"], "intent_type": r["intent_type"], "variant_class": r["variant_class"], "relation_core_sha256": r["relation_core_sha256"], "query_sha256": r["query_sha256"], "allocation_certificate_sha256": digest(r["search_constraint_allocation_certificate"]), "minimum_relational_evidence_certificate_sha256": digest(r["minimum_relational_retrieval_evidence_certificate"]), "lexical_coverage_certificate_sha256": digest(r["lexical_coverage_certificate"]), "lexical_alternative_set_ids": r["lexical_alternative_set_ids"]} for r in contributions], "material_downstream_policy_changes": 0, "downstream_policy_hashes_alpha3_4": old_manifest["downstream_policy_hashes"], "alpha3_12_policy_file_sha256": {n: sha(RUN / n) for n in ("query_execution_policy.json",) + COPIED_POLICY_FILES}, "retry_policy_sha256": sha(RUN / "technical_retry_policy.json"), "continuation_policy_sha256": sha(RUN / "technical_continuation_policy.json"), "blinding_policy_sha256": {n: sha(RUN / n) for n in ("known_paper_blindness_policy.json", "historical_label_blinding_policy.json")}, "future_metric_plan_sha256": {n: sha(RUN / n) for n in ("retrieval_viability_metrics.json", "lexical_attribution_metric_policy.json", "variant_attribution_metric_policy.json")}, "runtime_adaptation_allowed": False, "execution_status": "NOT_EXECUTED_PREREGISTRATION", "observed_retrieval_values": None}
    for row, contribution in zip(execution_manifest["per_contribution_provenance"], contributions):
        row["source_plan_all_role_set_ids"] = row["lexical_alternative_set_ids"]
        row["lexical_alternative_set_ids"] = contribution["lexical_coverage_certificate"]["role_alternatives"]
    execution_manifest["query_present_set_source"] = "LexicalCoverageCertificateV2.role_alternatives"
    write("bounded_lexical_realization_v2_development_execution_manifest.json", execution_manifest)
    manifest_sha = sha(RUN / "bounded_lexical_realization_v2_development_execution_manifest.json")
    if manifest_sha == OLD_MANIFEST_SHA:
        raise RuntimeError("new execution manifest did not change")
    (RUN / "bounded_lexical_realization_v2_development_execution_manifest_sha256").write_text(manifest_sha + "\n")
    summary = {"artifact_schema_version": "SearchPlanV24DevAlpha312SummaryV1", "status": "completed", "canonical_scientific_corpus_bound": True, "query_set_verified": True, "relation_contribution_count": 63, "byte_unique_query_count": 55, "alpha39_byte_identical_query_contribution_count": lexical_summary["alpha39_byte_identical_query_contribution_count"], "alpha39_lexically_changed_only_query_contribution_count": lexical_summary["alpha39_lexically_changed_only_query_contribution_count"], "structurally_unmappable_query_contributions": 0, "search_constraint_allocation_changed": False, "query_family_semantics_changed": False, "additional_lexical_surface_changes": 0, "material_downstream_policy_changes": 0, "downstream_policy_compatible": True, "technical_continuation_policy_preregistered": True, "execution_manifest_created": True, "bounded_lexical_realization_v2_development_execution_manifest_sha256": manifest_sha, "soft_tail": 120, "hard_tail": 180, "adaptive_tail_enabled": False, "max_fulltexts_per_case": 10, "known_paper_blindness_frozen": True, "historical_label_blinding_frozen": True, "runtime_adaptation_allowed": False, "next_stage_recommendation": "AUTHORIZE_BOUNDED_LEXICAL_REALIZATION_V2_FULL_DEVELOPMENT_RETRIEVAL", "provider_calls": 0, "llm_calls": 0, "network_calls": 0, "retrieval_calls": 0, "hit_counts_seen": 0, "candidate_records_seen": 0, "historical_assets_modified": False}
    write("summary.json", summary)
    pairs = [[p.name, sha(p)] for p in sorted(RUN.iterdir()) if p.is_file() and p.name not in {"validation.json", "search_plan_v24_dev_alpha3_12_sha256"}]
    write("validation.json", {"artifact_schema_version": "SearchPlanV24DevAlpha312ValidationV1", "valid": True, "aggregate_components_excluding_validation": pairs, "checks": {"query_set": True, "mapping": True, "authority": True, "downstream": True, "blinding": True, "no_results_read": True, "protected_inputs_unchanged": True}})
    root_pairs = [[p.name, sha(p)] for p in sorted(RUN.iterdir()) if p.is_file() and p.name != "search_plan_v24_dev_alpha3_12_sha256"]
    root_hash = digest(root_pairs)
    (RUN / "search_plan_v24_dev_alpha3_12_sha256").write_text(root_hash + "\n")
    print(json.dumps({**summary, "search_plan_v24_dev_alpha3_12_sha256": root_hash}, sort_keys=True))


def bind_targets_in_known_draft() -> None:
    """Finish only the alpha3.12 draft produced before explicit target binding."""
    old_root = "30d7e9679f5f32f2237021bfd47d573517bccf14f0e9a6e710c9d259cfff3fc9"
    old_manifest_sha = "6564a3da2b1eadcf4d9060e98f0635c24b86fe7c943ff2d060bd4ed204bfd545"
    root_file = RUN / "search_plan_v24_dev_alpha3_12_sha256"
    manifest_file = RUN / "bounded_lexical_realization_v2_development_execution_manifest.json"
    manifest_hash_file = RUN / "bounded_lexical_realization_v2_development_execution_manifest_sha256"
    if not RUN.is_dir() or root_file.read_text().strip() != old_root or manifest_hash_file.read_text().strip() != old_manifest_sha or sha(manifest_file) != old_manifest_sha:
        raise RuntimeError("not the known alpha3.12 target-binding draft")
    root_pairs = [[p.name, sha(p)] for p in sorted(RUN.iterdir()) if p.is_file() and p.name != root_file.name]
    if digest(root_pairs) != old_root:
        raise RuntimeError("draft root drifted")
    _, _, contributions, _ = contribution_mapping()
    targets = load(OLD_MANIFEST)["target_sha256_by_case"]
    if len(targets) != 8 or any(r["search_constraint_allocation_certificate"]["source_target_sha256"] != targets[r["case_id"]] for r in contributions):
        raise RuntimeError("target binding mismatch")
    manifest = load(manifest_file)
    if "target_sha256_by_case" in manifest:
        raise RuntimeError("draft already has target hashes")
    manifest["target_sha256_by_case"] = targets
    manifest_file.write_text(json.dumps(manifest, sort_keys=True, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    new_manifest_sha = sha(manifest_file)
    manifest_hash_file.write_text(new_manifest_sha + "\n")
    summary_file = RUN / "summary.json"
    summary = load(summary_file)
    summary["bounded_lexical_realization_v2_development_execution_manifest_sha256"] = new_manifest_sha
    summary_file.write_text(json.dumps(summary, sort_keys=True, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    validation_file = RUN / "validation.json"
    validation = load(validation_file)
    validation["aggregate_components_excluding_validation"] = [[p.name, sha(p)] for p in sorted(RUN.iterdir()) if p.is_file() and p.name not in {validation_file.name, root_file.name}]
    validation_file.write_text(json.dumps(validation, sort_keys=True, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    new_root_pairs = [[p.name, sha(p)] for p in sorted(RUN.iterdir()) if p.is_file() and p.name != root_file.name]
    new_root = digest(new_root_pairs)
    root_file.write_text(new_root + "\n")
    print(json.dumps({"target_binding_added_to_known_draft": True, "manifest_sha256": new_manifest_sha, "search_plan_v24_dev_alpha3_12_sha256": new_root}, sort_keys=True))


def bind_query_present_sets_in_known_draft() -> None:
    """Correct only this turn's known plan-wide-set attribution draft."""
    old_root = "29f057b9ec18adc199a19d58ff81805da1880756399db7ecaadc4fe38788f016"
    old_manifest_sha = "2ff6b809de0bbaee8a8f1acd7558d3ad80aab959577e70ee5cf6d938d77b4483"
    root_file = RUN / "search_plan_v24_dev_alpha3_12_sha256"
    manifest_file = RUN / "bounded_lexical_realization_v2_development_execution_manifest.json"
    manifest_hash_file = RUN / "bounded_lexical_realization_v2_development_execution_manifest_sha256"
    if not RUN.is_dir() or root_file.read_text().strip() != old_root or manifest_hash_file.read_text().strip() != old_manifest_sha or sha(manifest_file) != old_manifest_sha:
        raise RuntimeError("not the known alpha3.12 set-attribution draft")
    root_pairs = [[p.name, sha(p)] for p in sorted(RUN.iterdir()) if p.is_file() and p.name != root_file.name]
    if digest(root_pairs) != old_root:
        raise RuntimeError("draft root drifted")
    new_mapping, _, contributions, _ = contribution_mapping()
    mapping_file = RUN / "query_pair_mapping.jsonl"
    old_mapping = rows(mapping_file)
    if len(old_mapping) != len(new_mapping) or any({k: v for k, v in old.items() if k != "lexical_alternative_set_ids"} != {k: v for k, v in new.items() if k not in {"lexical_alternative_set_ids", "source_plan_all_role_set_ids"}} for old, new in zip(old_mapping, new_mapping)):
        raise RuntimeError("draft mapping differs beyond set attribution")
    mapping_file.write_bytes(b"".join(canonical(row) + b"\n" for row in new_mapping))
    metric_file = RUN / "lexical_attribution_metric_policy.json"
    metric = load(metric_file)
    if "set_presence_source" in metric:
        raise RuntimeError("draft attribution policy already corrected")
    metric["set_presence_source"] = "LexicalCoverageCertificateV2.role_alternatives"
    metric["source_plan_only_sets_not_counted_as_query_present"] = True
    metric_file.write_text(json.dumps(metric, sort_keys=True, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    manifest = load(manifest_file)
    if "query_present_set_source" in manifest or len(manifest["per_contribution_provenance"]) != len(contributions):
        raise RuntimeError("draft manifest already corrected or wrong cardinality")
    for row, contribution in zip(manifest["per_contribution_provenance"], contributions):
        if row["case_id"] != contribution["case_id"] or row["query_sha256"] != contribution["query_sha256"]:
            raise RuntimeError("manifest contribution order mismatch")
        row["source_plan_all_role_set_ids"] = row["lexical_alternative_set_ids"]
        row["lexical_alternative_set_ids"] = contribution["lexical_coverage_certificate"]["role_alternatives"]
    manifest["query_present_set_source"] = "LexicalCoverageCertificateV2.role_alternatives"
    manifest["query_pair_mapping_sha256"] = sha(mapping_file)
    manifest["future_metric_plan_sha256"][metric_file.name] = sha(metric_file)
    manifest_file.write_text(json.dumps(manifest, sort_keys=True, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    manifest_sha = sha(manifest_file)
    manifest_hash_file.write_text(manifest_sha + "\n")
    summary_file = RUN / "summary.json"
    summary = load(summary_file)
    summary["bounded_lexical_realization_v2_development_execution_manifest_sha256"] = manifest_sha
    summary_file.write_text(json.dumps(summary, sort_keys=True, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    validation_file = RUN / "validation.json"
    validation = load(validation_file)
    validation["aggregate_components_excluding_validation"] = [[p.name, sha(p)] for p in sorted(RUN.iterdir()) if p.is_file() and p.name not in {validation_file.name, root_file.name}]
    validation_file.write_text(json.dumps(validation, sort_keys=True, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    new_root = digest([[p.name, sha(p)] for p in sorted(RUN.iterdir()) if p.is_file() and p.name != root_file.name])
    root_file.write_text(new_root + "\n")
    print(json.dumps({"query_present_set_binding_corrected": True, "manifest_sha256": manifest_sha, "search_plan_v24_dev_alpha3_12_sha256": new_root}, sort_keys=True))


if __name__ == "__main__":
    if len(sys.argv) == 1:
        main()
    elif sys.argv[1:] == ["--bind-targets-in-known-draft"]:
        bind_targets_in_known_draft()
    elif sys.argv[1:] == ["--bind-query-present-sets-in-known-draft"]:
        bind_query_present_sets_in_known_draft()
    else:
        raise SystemExit("unsupported argument")
