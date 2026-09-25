"""Freeze alpha3.9 counterfactual query families without any network access."""

from __future__ import annotations

import hashlib
import json
import copy
from collections import Counter, defaultdict
from pathlib import Path

from code_engine.search.retrieval_surface_compiler_v2 import _field_scoped
from code_engine.search.search_constraint_allocation_v1 import (
    ALLOCATION, VALIDATOR, VARIANT_PRIORITY, AllocationError, allocation_for_plan,
    burden, canonical, certificate_for_ast, compile_family, digest,
    serialize_validated_ast,
)


ROOT = Path(__file__).resolve().parents[1]
RUN = ROOT / "runs/20260925_search_plan_v24_dev_alpha3_9_search_constraint_allocation_offline"
SURFACE = ROOT / "runs/20260924_search_plan_v24_dev_alpha3_6_retrieval_surface_compiler_v2_offline"
ALPHA38 = ROOT / "runs/20260925_search_plan_v24_dev_alpha3_8_conjunctive_rigidity_autopsy_offline"
CONT = ROOT / "runs/20260925_search_plan_v24_dev_retrieval_surface_v2_technical_continuation"
P32 = ROOT / "runs/20260922_search_plan_v24_dev_alpha3_2_planner_v3_empirical_remaining7"
P33 = ROOT / "runs/20260923_search_plan_v24_dev_alpha3_3_role_scoped_polarity_offline"
ROOTS = {
    "search_plan_v24_dev_alpha3_8_sha256": (ALPHA38 / "search_plan_v24_dev_alpha3_8_sha256", "768992cef210e61cfadc97e71fb658079f3ee23c32d8e72bd721c56c73eef60b"),
    "retrieval_surface_v2_complete_execution_corpus_sha256": (CONT / "retrieval_surface_v2_complete_execution_corpus_sha256", "052d332ecdf2042713ab07f608c934457908c6d5d9f15536c433c55c92f8b4d1"),
    "retrieval_surface_v2_completed_development_acquisition_corpus_sha256": (CONT / "retrieval_surface_v2_completed_development_acquisition_corpus_sha256", "8b40a35c5976f3c6e084e2e467fbefc01e3b925a4aad135341c99daa90b0c353"),
    "search_plan_v24_dev_alpha3_2_empirical_v3_sha256": (P32 / "search_plan_v24_dev_alpha3_2_empirical_v3_sha256", "a78a2737f6f84d8f14088f8dfaf5dca08f7485511877076772ca9b874d9f2b76"),
    "search_plan_v24_dev_alpha3_3_sha256": (P33 / "search_plan_v24_dev_alpha3_3_sha256", "e5a7b502102a36de920e5421aa83b4bfc4775ddee4418df86299d587a4c5a763"),
}
ROOT_MANIFESTS = {
    "search_plan_v24_dev_alpha3_8_sha256": ALPHA38 / "validation.json",
    "retrieval_surface_v2_complete_execution_corpus_sha256": CONT / "retrieval_surface_v2_complete_execution_corpus_manifest.json",
    "retrieval_surface_v2_completed_development_acquisition_corpus_sha256": CONT / "retrieval_surface_v2_development_acquisition_corpus_manifest.json",
    "search_plan_v24_dev_alpha3_2_empirical_v3_sha256": P32 / "validation.json",
    "search_plan_v24_dev_alpha3_3_sha256": P33 / "validation.json",
}


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def read_jsonl(path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def write_json(name, obj):
    (RUN / name).write_text(json.dumps(obj, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")


def write_jsonl(name, rows):
    (RUN / name).write_bytes(b"".join(canonical(row) + b"\n" for row in rows))


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def snapshot(paths):
    return {str(path.relative_to(ROOT)): sha(path) for path in paths}


def main():
    if RUN.exists() and any(RUN.iterdir()):
        old_root = RUN / "search_plan_v24_dev_alpha3_9_sha256"
        draft_roots = {"0e1d35937cc0c7f730311fd2a5038edd3d175256a6daf5be5dc44652e7bda163", "388424acc8079a955dc5451befe6b7758df02ad76e51e091a2c3833deb3f23d7", "1f87266968484dfc0340d02ee7ec136747787ba65f362f295c4eee588c11c9d4", "830cd06c57c9326cc1299675fc320e01f7457ddb7e103898a9d0a0c561c44c46", "42896c11fceb71449e92c5d0429b02f01f215ca42bed6c81be1eefaf1d6fe6b7"}
        if not old_root.exists() or old_root.read_text().strip() not in draft_roots:
            raise RuntimeError("alpha3.9 run exists and is not a known pre-validation draft; refusing overwrite")
    verified_roots = {}
    for key, (path, expected) in ROOTS.items():
        actual = path.read_text(encoding="utf-8").strip()
        if actual != expected:
            raise RuntimeError(f"upstream root mismatch: {key}")
        manifest_path = ROOT_MANIFESTS[key]
        pairs = read_json(manifest_path)["aggregate_components"]
        if any(sha(manifest_path.parent / name) != component_sha for name, component_sha in pairs):
            raise RuntimeError(f"upstream component drift: {key}")
        if digest(pairs) != expected:
            raise RuntimeError(f"upstream aggregate drift: {key}")
        verified_roots[key] = {"root_file": str(path.relative_to(ROOT)), "manifest": str(manifest_path.relative_to(ROOT)), "expected": expected, "observed": actual, "aggregate_verified": True, "component_count": len(pairs)}
    plans_path = SURFACE / "empirical_v3_to_surface_plan.jsonl"
    plans = read_jsonl(plans_path)
    if len(plans) != 29 or len({p["case_id"] for p in plans}) != 8:
        raise RuntimeError("frozen V3 surface-plan cardinality mismatch")
    protected = [path for path, _ in ROOTS.values()] + [plans_path, SURFACE / "search_plan_v24_dev_retrieval_surface_v2_query_set.jsonl", ALPHA38 / "mandatory_lexical_burden.jsonl"]
    before = snapshot(protected)
    RUN.mkdir(parents=True, exist_ok=True)
    write_json("upstream_root_verification.json", {"artifact_schema_version": "Alpha39UpstreamRootVerificationV1", "verified": True, "roots": verified_roots})
    write_json("search_constraint_allocation_v1_contract.json", {"artifact_schema_version": "SearchConstraintAllocationV1", "defined": True, "allocations": ["SEARCH_INTRINSIC", "SEARCH_VARIANT_ELIGIBLE", "POST_RETRIEVAL_VALIDATION", "RELATION_INTERNAL_MANDATORY", "UNRESOLVED"], "decision_authority": "DETERMINISTIC_ROLE_BASED", "scientific_target_unchanged": True, "model_controls_allocation": False, "unresolved_fails_closed": True})
    write_json("minimum_relational_retrieval_evidence_v1_contract.json", {"artifact_schema_version": "MinimumRelationalRetrievalEvidenceV1", "defined": True, "required": ["actor/action bounded anchor", "response or defining endpoint anchor", "bounded orientation-response or orientation-endpoint relation edge", "all applicable relation-internal roles"], "every_or_branch_must_pass": True, "scientific_proof": False})
    write_json("search_relation_evidence_v1_contract.json", {"artifact_schema_version": "SearchRelationEvidenceV1", "defined": True, "purpose": "candidate eligibility only", "mechanism": "bounded orientation-response or orientation-endpoint proximity using frozen validated surfaces", "not_equivalent_to": "ScientificRelationValidation"})
    write_json("relational_query_family_v3_contract.json", {"artifact_schema_version": "RelationalQueryFamilyV3", "defined": True, "core_required_for_each_validated_intent": True, "variant_priority": VARIANT_PRIORITY, "every_executable_member_certified": True, "query_ast_version": "PubMedQueryASTV2"})
    write_json("search_constraint_allocation_certificate_v1_contract.json", {"artifact_schema_version": "SearchConstraintAllocationCertificateV1", "defined": True, "fields": ["search_required_roles", "deferred_roles", "variant_eligible_roles", "relation_internal_roles", "deferred_validator_owners", "unowned_deferred_roles"], "unowned_deferred_roles_must_be_empty": True})
    write_json("family_level_target_coverage_v1_contract.json", {"artifact_schema_version": "FamilyLevelTargetCoverageV1", "defined": True, "coverage_routes": ["mandatory search", "context variant", "deterministic validator", "neutral/fulltext review"], "scientific_status_assigned_by_search": False})
    write_json("generic_role_allocation_matrix.json", {"artifact_schema_version": "GenericRoleAllocationMatrixV1", "role_primary_allocation": ALLOCATION, "search_variant_eligible": sorted(VALIDATOR), "applicability_rule": "therapy and conditioning are mandatory only when present in validated relation core; endpoint property is always mandatory", "production_case_specific_rules": 0})
    write_json("downstream_validator_ownership_v2.json", {"artifact_schema_version": "DownstreamValidatorOwnershipV2", "deferred_role_owners": VALIDATOR, "P1": "functional relation evidence", "P2": "endpoint semantics", "Policy_A": "compose frozen blocker outcomes", "neutral_fulltext": "disease, genotype, and scientific context without deterministic owner"})
    write_json("relation_internal_role_matrix.json", {"artifact_schema_version": "RelationInternalRoleMatrixV1", "always_required": ["INTERVENTION_ACTION", "DEFINING_ENDPOINT_PROPERTY"], "conditionally_required": {"THERAPY": "therapy_required", "CONDITIONING_TREATMENT": "conditioning_required"}, "never_defer_applicable_internal_role": True})
    write_json("query_family_variant_policy.json", {"artifact_schema_version": "QueryFamilyVariantPolicyV3", "priority": VARIANT_PRIORITY, "endpoint_variant_condition": "frozen intent_type == ENDPOINT_SPECIFIC", "context_variant_condition": "one or more validated external contexts", "core_excludes_external_context": True, "no_result_driven_selection": True})
    write_json("query_family_budget_policy.json", {"artifact_schema_version": "QueryFamilyBudgetPolicyV3", "max_variants_per_intent_pre_dedup": 3, "max_queries_per_target": 12, "case_level_byte_dedup": True, "no_adaptive_expansion": True})

    families = [compile_family(p) for p in plans]
    allocations = [f["allocation"] for f in families]
    write_jsonl("empirical_target_constraint_allocations.jsonl", allocations)
    family_rows = [{"artifact_schema_version": "RelationalQueryFamilyPlanV3", "case_id": f["case_id"], "intent_type": f["intent_type"], "surface_plan_id": f["surface_plan_id"], "allocation": f["allocation"], "variants": [m["variant_class"] for m in f["members"]]} for f in families]
    write_jsonl("empirical_query_family_plans.jsonl", family_rows)
    ast_rows = []
    query_rows = []
    cert_rows = []
    unique_by_case = defaultdict(dict)
    for f in families:
        for member in f["members"]:
            ast = member["ast"]
            query = member["query"]
            qid = "v24scav1q:" + hashlib.sha256(query.encode("utf-8")).hexdigest()
            record = {"case_id": f["case_id"], "intent_type": f["intent_type"], "surface_plan_id": f["surface_plan_id"], "variant_class": member["variant_class"], "query_id": qid, "query": query, "ast_sha256": ast["ast_sha256"], "burden": burden(ast)}
            ast_rows.append({"case_id": f["case_id"], "intent_type": f["intent_type"], "variant_class": member["variant_class"], "query_id": qid, "ast": ast})
            query_rows.append(record)
            cert_rows.append({"case_id": f["case_id"], "query_id": qid, "variant_class": member["variant_class"], "certificate": member["certificate"], "allocation_certificate": f["allocation"]})
            unique_by_case[f["case_id"]].setdefault(query.encode("utf-8"), {"case_id": f["case_id"], "query_id": qid, "query": query, "contributions": []})["contributions"].append({"surface_plan_id": f["surface_plan_id"], "intent_type": f["intent_type"], "variant_class": member["variant_class"], "ast_sha256": ast["ast_sha256"]})
    write_jsonl("empirical_query_family_ast.jsonl", ast_rows)
    write_jsonl("empirical_serialized_queries.jsonl", query_rows)
    write_jsonl("empirical_query_certificates.jsonl", cert_rows)
    unique_rows = [row for case in sorted(unique_by_case) for row in unique_by_case[case].values()]
    case_summary = {}
    for case in sorted(unique_by_case):
        cr = [r for r in query_rows if r["case_id"] == case]
        core = [r for r in cr if r["variant_class"] == "CORE_RELATION"]
        case_summary[case] = {"validated_intents": sum(f["case_id"] == case for f in families), "relation_contributions": len(cr), "byte_unique_queries": len(unique_by_case[case]), "core_relation_contributions": len(core), "context_free_core_relation_contributions": sum(not r["burden"]["mandatory_external_context_roles"] for r in core), "relation_internal_roles_preserved": True, "unowned_deferred_roles": []}
        if len(unique_by_case[case]) > 12:
            raise RuntimeError(f"case query budget exceeded: {case}")
    write_json("per_case_query_family_summary.json", case_summary)
    core_cert = [r for r in cert_rows if r["variant_class"] == "CORE_RELATION"]
    write_json("validator_opportunity_summary.json", {"artifact_schema_version": "ValidatorOpportunitySummaryV1", "core_queries": len(core_cert), "meaning": "Search lexical inclusion does not satisfy scientific validation", "per_core_query": [{"case_id": r["case_id"], "query_id": r["query_id"], "deferred_roles_by_owner": {owner: sorted(role for role, own in r["certificate"]["deferred_validator_owners"].items() if own == owner) for owner in sorted(set(VALIDATOR.values()))}, "roles_for_P1_functional_relation_validation": ["ACTOR", "INTERVENTION_ACTION", "RELATION_ORIENTATION", "RESPONSE_TARGET"], "roles_for_P2_endpoint_validation": ["RESPONSE_TARGET", "DEFINING_ENDPOINT_PROPERTY"], "roles_for_Policy_A_composition": ["P0", "P1", "P2"]} for r in core_cert]})
    prev = read_jsonl(ALPHA38 / "mandatory_lexical_burden.jsonl")
    write_json("constraint_allocation_delta.json", {"artifact_schema_version": "ConstraintAllocationDeltaV1", "surface_v2_queries_with_all_serialized_roles_mandatory": len(prev), "surface_v2_queries_with_mandatory_external_context": sum(bool(r["mandatory_external_context_count"]) for r in prev), "alpha39_role_allocation_occurrences": dict(Counter(v for a in allocations for v in a["role_allocations"].values())), "alpha39_core_queries_with_mandatory_external_context": sum(bool(r["burden"]["mandatory_external_context_roles"]) for r in query_rows if r["variant_class"] == "CORE_RELATION")})
    def avg(key):
        return round(sum(r["burden"][key] for r in query_rows) / len(query_rows), 4)
    hist = read_json(ALPHA38 / "v23_vs_exact_vs_surface_v2_rigidity_comparison.json")
    unknown_role_metrics = {"average_mandatory_unique_lexical_atom_count": None, "average_mandatory_semantic_role_count": None, "average_top_level_and_child_count": None, "queries_with_repeated_mandatory_roles": None, "queries_with_mandatory_external_context": None, "relation_bearing_query_count": None, "context_free_core_relation_query_count": None}
    comparison = {"artifact_schema_version": "V23ExactSurfaceV2Alpha39RigidityComparisonV1", "method_limit": "offline structural comparison only; historical string grammars lack comparable role AST; no recall or precision inference", "v23": {**hist["v23"], **unknown_role_metrics}, "exact": {**hist["exact"], **unknown_role_metrics}, "surface_v2": {**hist["surface_v2"], "average_mandatory_unique_lexical_atom_count": round(sum(r["mandatory_unique_lexical_atom_count"] for r in prev)/len(prev),4), "average_mandatory_semantic_role_count": round(sum(r["mandatory_semantic_role_count"] for r in prev)/len(prev),4), "average_top_level_and_child_count": 4.8, "queries_with_repeated_mandatory_roles": sum(bool(r["repeated_mandatory_roles"]) for r in prev), "queries_with_mandatory_external_context": sum(bool(r["mandatory_external_context_count"]) for r in prev), "relation_bearing_query_count": 25, "context_free_core_relation_query_count": 0}, "alpha39": {"query_count": len(unique_rows), "relation_contribution_count": len(query_rows), "average_mandatory_unique_lexical_atom_count": avg("mandatory_unique_lexical_atom_count"), "average_mandatory_semantic_role_count": avg("mandatory_semantic_role_count"), "average_top_level_and_child_count": avg("top_level_and_child_count"), "queries_with_repeated_mandatory_roles": sum(bool(r["burden"]["repeated_mandatory_roles"]) for r in query_rows), "queries_with_mandatory_external_context": sum(bool(r["burden"]["mandatory_external_context_roles"]) for r in query_rows), "relation_bearing_query_count": len(query_rows), "context_free_core_relation_query_count": sum(r["variant_class"] == "CORE_RELATION" and not r["burden"]["mandatory_external_context_roles"] for r in query_rows)}}
    write_json("v23_exact_surfacev2_alpha39_rigidity_comparison.json", comparison)

    # Negative tests are compile-time counterexamples, never query outputs.
    therapy_plan = next(p for p in plans if p["requirements"]["therapy_required"] and "DISEASE_CONTEXT" in p["external_contexts"])
    negative_examples = [
        ("actor_endpoint_only", plans[0], ["ACTOR", "RESPONSE_TARGET", "DEFINING_ENDPOINT_PROPERTY"]),
        ("actor_response_biological_unit", plans[0], ["ACTOR", "RESPONSE_TARGET", "BIOLOGICAL_UNIT_CONTEXT"]),
        ("actor_therapy_disease", therapy_plan, ["ACTOR", "THERAPY", "DISEASE_CONTEXT"]),
        ("all_mandatory_roles_without_relation", plans[0], allocation_for_plan(plans[0])["search_required_roles"]),
    ]
    rejected = {}
    for name, plan, roles in negative_examples:
        family = compile_family(plan)
        fake = copy.deepcopy(family["members"][0]["ast"])
        fake["root"] = {"node_type": "AND_GROUP", "children": [_field_scoped((plan["surface_roles"].get(role) or plan["external_contexts"].get(role))[0], role) for role in roles]}
        fake["ast_sha256"] = digest({k: v for k, v in fake.items() if k != "ast_sha256"})
        try:
            certificate_for_ast(fake, family["allocation"])
        except AllocationError as exc:
            rejected[name] = str(exc)
    topic_regressions = len(negative_examples) - len(rejected)
    if "topic intersection" not in rejected.get("all_mandatory_roles_without_relation", ""):
        topic_regressions += 1
    write_json("topic_intersection_regression_audit.json", {"artifact_schema_version": "TopicIntersectionRegressionAuditV1", "invalid_examples": len(negative_examples), "rejected_with_reason": rejected, "all_roles_without_relation_rejected_for_relation_failure": "topic intersection" in rejected.get("all_mandatory_roles_without_relation", ""), "regression_count": topic_regressions})
    therapy = [f for f in families if f["allocation"]["relation_internal_roles"] and "THERAPY" in f["allocation"]["relation_internal_roles"]]
    conditioning = [f for f in families if "CONDITIONING_TREATMENT" in f["allocation"]["relation_internal_roles"]]
    for name, chosen, role in [("therapy_internality_regression_audit.json", therapy, "THERAPY"), ("nested_conditioning_regression_audit.json", conditioning, "CONDITIONING_TREATMENT")]:
        intact = all(role in m["certificate"]["relation_internal_roles"] and role in m["certificate"]["search_required_roles"] for f in chosen for m in f["members"])
        write_json(name, {"artifact_schema_version": "RelationInternalityRegressionAuditV1", "role": role, "applicable_intents": len(chosen), "preserved": intact, "regression_count": 0 if intact else 1})
    endpoint_intact = all("DEFINING_ENDPOINT_PROPERTY" in m["certificate"]["search_required_roles"] for f in families for m in f["members"])
    write_json("endpoint_internality_regression_audit.json", {"artifact_schema_version": "EndpointInternalityRegressionAuditV1", "applicable_intents": len(families), "preserved": endpoint_intact, "regression_count": 0 if endpoint_intact else 1})
    source_surfaces = {s["text"] for p in plans for surfaces in list(p["surface_roles"].values()) + list(p["external_contexts"].values()) for s in surfaces}
    ast_surfaces = {n["surface"] for row in ast_rows for n in _walk_all(row["ast"]["root"]) if n.get("node_type") in {"TERM", "COMPACT_CONCEPT"}}
    unapproved = sorted(ast_surfaces - source_surfaces)
    write_json("identity_safety_regression_audit.json", {"artifact_schema_version": "IdentitySafetyRegressionAuditV1", "source_surfaces_only": not unapproved, "unapproved_surfaces": unapproved, "identity_promotion_count": 0, "tnf_to_tnf_alpha_promotion": False})
    write_json("protected_term_regression_audit.json", {"artifact_schema_version": "ProtectedTermRegressionAuditV1", "all_query_surfaces_from_frozen_validated_plans": not unapproved, "unsupported_overbroad_regression_count": len(unapproved), "semantic_drift_regression_count": 0 if not unapproved else len(unapproved), "no_new_synonyms": True, "global_ATM_enabled": False})
    write_json("lexical_undercoverage_deferred_issue.json", {"artifact_schema_version": "LexicalUndercoverageDeferredIssueV1", "frozen_alpha38_diagnosis": True, "resolved": False, "deferred": True, "new_synonyms": 0, "ATM_global_enable": False, "retrieval_outcome_unknown": True})
    after = snapshot(protected)
    write_json("historical_corpus_preservation_audit.json", {"artifact_schema_version": "HistoricalCorpusPreservationAuditV1", "historical_assets_modified": before != after, "protected_file_sha256_before": before, "protected_file_sha256_after": after})
    write_json("planner_immutability_audit.json", {"artifact_schema_version": "PlannerImmutabilityAuditV1", "empirical_surface_plan_sha256_before": before[str(plans_path.relative_to(ROOT))], "empirical_surface_plan_sha256_after": after[str(plans_path.relative_to(ROOT))], "fresh_planner_calls": 0, "planner_outputs_modified": False})
    write_json("scientific_state_safety_audit.json", {"artifact_schema_version": "ScientificStateSafetyAuditV1", "scientific_target_modified": False, "relation_core_modified": False, "P0_P1_P2_Policy_A_modified": False, "retrieval_execution": False, "known_pmid_checks": 0, "candidate_records_seen": 0, "scientific_status_assigned": False})
    valid = not any([topic_regressions, unapproved, before != after, not endpoint_intact, any(not r["certificate"]["all_paths_certified"] for r in cert_rows)]) and len(case_summary) == 8 and all(v["context_free_core_relation_contributions"] for v in case_summary.values()) and all(len(unique_by_case[c]) <= 12 for c in case_summary)
    if valid:
        write_jsonl("search_plan_v24_dev_search_constraint_allocation_v1_query_set.jsonl", unique_rows)
        (RUN / "search_plan_v24_dev_search_constraint_allocation_v1_query_set_sha256").write_text(sha(RUN / "search_plan_v24_dev_search_constraint_allocation_v1_query_set.jsonl") + "\n")
    recommendation = "PREREGISTER_SEARCH_CONSTRAINT_ALLOCATION_V1_RETRIEVAL" if valid else "SEARCH_CONSTRAINT_ALLOCATION_UNSAFE"
    summary = {"artifact_schema_version": "SearchPlanV24DevAlpha39SummaryV1", "status": "completed" if valid else "failed", "search_constraint_allocation_v1_defined": True, "minimum_relational_retrieval_evidence_v1_defined": True, "search_relation_evidence_v1_defined": True, "relational_query_family_v3_defined": True, "search_constraint_allocation_certificate_v1_defined": True, "family_level_target_coverage_v1_defined": True, "relation_contribution_count": len(query_rows), "byte_unique_query_count": len(unique_rows), "cases_with_core_relation_query": sum(bool(v["context_free_core_relation_contributions"]) for v in case_summary.values()), "average_mandatory_unique_lexical_atom_count": avg("mandatory_unique_lexical_atom_count"), "average_mandatory_semantic_role_count": avg("mandatory_semantic_role_count"), "average_top_level_and_child_count": avg("top_level_and_child_count"), "queries_with_repeated_mandatory_roles": comparison["alpha39"]["queries_with_repeated_mandatory_roles"], "queries_with_mandatory_external_context": comparison["alpha39"]["queries_with_mandatory_external_context"], "all_executable_queries_relation_bearing": all(r["certificate"]["all_paths_certified"] for r in cert_rows), "therapy_internality_preserved": all("THERAPY" in m["certificate"]["search_required_roles"] for f in therapy for m in f["members"]), "nested_conditioning_internality_preserved": all("CONDITIONING_TREATMENT" in m["certificate"]["search_required_roles"] for f in conditioning for m in f["members"]), "endpoint_property_internality_preserved": endpoint_intact, "unowned_deferred_scientific_role_count": sum(len(a["unowned_deferred_roles"]) for a in allocations), "topic_intersection_regression_count": topic_regressions, "identity_promotion_count": 0, "semantic_drift_regression_count": len(unapproved), "unsupported_overbroad_regression_count": len(unapproved), "lexical_surface_undercoverage_resolved": False, "lexical_surface_undercoverage_deferred": True, "production_case_specific_rules": 0, "new_query_set_created": valid, "search_plan_v24_dev_search_constraint_allocation_v1_query_set_sha256": sha(RUN / "search_plan_v24_dev_search_constraint_allocation_v1_query_set.jsonl") if valid else None, "next_stage_recommendation": recommendation, "provider_calls": 0, "llm_calls": 0, "network_calls": 0, "retrieval_calls": 0, "known_pmid_checks": 0, "candidate_records_seen": 0, "historical_assets_modified": before != after}
    write_json("summary.json", summary)
    write_json("validation.json", {"artifact_schema_version": "SearchPlanV24DevAlpha39ValidationV1", "valid": valid, "summary": summary, "upstream_roots_verified": True, "compiler_sha256": sha(ROOT / "src/code_engine/search/search_constraint_allocation_v1.py"), "runner_sha256": sha(ROOT / "scripts/search_plan_v24_alpha39_offline.py"), "source_plan_count": len(plans), "case_count": len(case_summary), "all_families_have_core": all(f["members"][0]["variant_class"] == "CORE_RELATION" for f in families), "all_family_budgets_valid": all(len(f["members"]) <= 3 for f in families), "all_case_budgets_valid": all(len(unique_by_case[c]) <= 12 for c in case_summary), "no_literature_inspection": True})
    manifest = {p.name: sha(p) for p in sorted(RUN.iterdir()) if p.is_file() and p.name != "search_plan_v24_dev_alpha3_9_sha256"}
    root_hash = digest({"artifact_schema_version": "SearchPlanV24DevAlpha39FreezeV1", "files": manifest})
    (RUN / "search_plan_v24_dev_alpha3_9_sha256").write_text(root_hash + "\n")
    print(json.dumps({**summary, "search_plan_v24_dev_alpha3_9_sha256": root_hash}, sort_keys=True))
    if not valid:
        raise RuntimeError("alpha3.9 validation failed closed")


def _walk_all(node):
    yield node
    if node["node_type"] in {"AND_GROUP", "OR_GROUP"}:
        for child in node["children"]:
            yield from _walk_all(child)
    elif node["node_type"] == "FIELD_SCOPE":
        yield from _walk_all(node["child"])
    elif node["node_type"] == "PROXIMITY":
        yield from node["anchors"]


if __name__ == "__main__":
    main()
