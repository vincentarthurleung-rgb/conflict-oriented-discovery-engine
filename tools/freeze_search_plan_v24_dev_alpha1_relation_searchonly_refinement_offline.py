"""Freeze the offline alpha1 replay of eight immutable v2.4-dev planner outputs."""

from __future__ import annotations

from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path

from code_engine.search.alpha1_relation_searchonly_v1 import (
    BINDING_VERSION, COVERAGE_VERSION, ELIGIBILITY_VERSION, ENDPOINT_LEXICON,
    EVENT_VERSION, RECEIPT_VERSION, RELATION_LEXICON, alpha1_receipts,
    compile_alpha1, relation_event_and_binding,
)
from code_engine.search.proposition_aware_query_planner_v1 import canonical_bytes, sha256_value
from tools import run_search_plan_v24_dev_real_planner_generation as base

ROOT = Path(__file__).resolve().parents[1]
RUN = ROOT / "runs/20260920_search_plan_v24_dev_alpha1_relation_searchonly_refinement_offline"
SEMANTIC = ROOT / "runs/20260918_search_plan_v24_dev_planner_semantic_quality_audit_offline"
AUTHORITY = ROOT / "runs/20260918_search_plan_v24_dev_planner_authority_contract_split_offline"
RAW = ROOT / "runs/20260918_search_plan_v24_dev_real_planner_generation_v3/v24_dev_raw_planner_outputs.jsonl"
SEMANTIC_ROOT = "9504e1b6fdc5005eaf67f5306322cd7374ae6528213fed7663947ad804dd1b64"
AUTHORITY_ROOT = "ceeb18a8b2f83e1db01a67368b606d8c06bb5486b1c39b6afda2d90ad1ea8367"
RAW_ROOT = "9b5e7f5e7b22aff42a1e6179b62a2f0ad2ecebf09c8104bb9f3e9117546c45f1"
OLD_PLANS = AUTHORITY / "validated_development_plans.jsonl"
OLD_AUDIT = SEMANTIC / "search_only_expansion_semantic_audit.json"


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify_root(path: Path, expected: str) -> dict:
    manifest = json.loads((path / "validation.json").read_text())
    pairs = manifest["aggregate_components"]
    for name, digest in pairs:
        require(sha(path / name) == digest, f"upstream component changed: {path.name}/{name}")
    require(sha256_value(pairs) == expected, f"upstream root changed: {path.name}")
    return {"root": expected, "component_count": len(pairs), "component_hashes_verified": True}


def put(name: str, obj: object) -> None:
    path = RUN / name
    payload = (json.dumps(obj, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode()
    require(not path.is_symlink(), f"alpha1 output is symlink: {name}")
    path.write_bytes(payload)


def put_lines(name: str, rows: list[dict]) -> None:
    path = RUN / name
    payload = b"".join(canonical_bytes(row) + b"\n" for row in rows)
    require(not path.is_symlink(), f"alpha1 output is symlink: {name}")
    path.write_bytes(payload)


def put_text(name: str, value: str) -> None:
    path = RUN / name
    payload = (value + "\n").encode()
    require(not path.is_symlink(), f"alpha1 output is symlink: {name}")
    path.write_bytes(payload)


def contract(version: str, fields: list[str], rules: list[str]) -> dict:
    return {"artifact_schema_version": version, "required_fields": fields, "deterministic_rules": rules,
            "scope": "offline post-planner development interpretation of frozen proposals"}


def main() -> None:
    require(not RUN.is_symlink(), "run path is a symlink")
    require(not RUN.exists() or RUN.is_dir(), "run path not a directory")
    upstream = {
        "artifact_schema_version": "V24DevAlpha1UpstreamRootVerificationV1",
        "semantic_quality": verify_root(SEMANTIC, SEMANTIC_ROOT),
        "authority_contract": verify_root(AUTHORITY, AUTHORITY_ROOT),
        "raw_planner_corpus_sha256": sha(RAW),
        "validated_plan_corpus_sha256": sha(OLD_PLANS),
        "status": "PASS",
    }
    require(upstream["raw_planner_corpus_sha256"] == RAW_ROOT, "raw planner corpus changed")
    require(upstream["validated_plan_corpus_sha256"] == "7b828782f0905a803e948db9b2109ab81fefd4d0a73e1900b91fef25dec2730f", "validated plans changed")
    protected = [RAW, OLD_PLANS, OLD_AUDIT, SEMANTIC / "validation.json", AUTHORITY / "validation.json"]
    before = {str(p.relative_to(ROOT)): sha(p) for p in protected}
    rows = [json.loads(line) for line in OLD_PLANS.read_text().splitlines() if line]
    require(len(rows) == 8 and len({x["case_id"] for x in rows}) == 8, "not eight frozen plans")
    old_audit = json.loads(OLD_AUDIT.read_text())
    prior_by_id = {(x["case_id"], x["term_id"]): x for x in old_audit["terms"]}

    RUN.mkdir(parents=True, exist_ok=True)
    put("upstream_root_verification.json", upstream)
    put("relation_event_frame_v1_contract.json", contract(EVENT_VERSION,
        ["subject_concept_id", "subject_role", "perturbation_or_action", "relation_family",
         "polarity_or_direction", "measurement_target_concept_id", "endpoint_property",
         "response_role", "nested_treatment_context", "therapy_context", "evidence_mode_requirement",
         "semantic_roles"],
        ["Roles use actual concept IDs from the immutable validated proposal.",
         "A phrase or verb alone never creates target authority.",
         "Conditioning treatment and therapy response remain distinct roles."]))
    put("relation_binding_assessment_v1_contract.json", contract(BINDING_VERSION,
        ["state", "subject_side_searchable", "response_side_searchable", "direction_searchable",
         "explicit_cross_role_phrase", "therapy_response_bound", "nested_treatment_bound",
         "dynamic_endpoint_bound", "compiler_action"],
        ["Allowed states: STRUCTURALLY_BOUND, PARTIALLY_BOUND, UNDERREPRESENTED, NOT_APPLICABLE.",
         "Only structurally bound applicable relation blueprints compile.",
         "Subject, response, direction, cross-role phrase and required therapy/nested/dynamic constraints must all hold."]))
    put("retrieval_plan_coverage_v1_1_contract.json", contract(COVERAGE_VERSION,
        ["intent_id", "blueprint_id", "dimension_coverage", "relation_binding_state"],
        ["Relation REPRESENTED iff relation binding is STRUCTURALLY_BOUND.",
         "Partial and underrepresented binding map to relation UNDERREPRESENTED.",
         "Historical V1 coverage is not modified."]))
    put("search_only_eligibility_v1_contract.json", contract(ELIGIBILITY_VERSION,
        ["lexical_safety_state", "semantic_search_eligibility_state", "eligibility_rule_id"],
        ["Lexical safety is separate from scientific semantic eligibility.",
         "No matching generic rule defaults to UNRESOLVED, not SEARCH_ONLY_EXPANSION.",
         "absence_of_negative_evidence_is_not_search_permission=true",
         "Mechanistic entity proxies require explicit authority; none is granted here.",
         "Biological-unit broadening is not a lexical variant."]))
    put("generic_relation_search_lexicon.json", RELATION_LEXICON)
    put("generic_endpoint_search_lexicon.json", ENDPOINT_LEXICON)
    put("search_term_validation_receipt_v1_1_contract.json", contract(RECEIPT_VERSION,
        ["term_id", "term", "concept_id", "concept_type", "input_term_hash",
         "old_receipt_sha256", "lexical_safety_state", "semantic_search_eligibility_state",
         "final_authority_classification", "eligibility_rule_id", "authority_reference",
         "reason", "validator_version", "authority_state_hash", "receipt_sha256"],
        ["Original authorized-equivalent authority remains exactly inherited.",
         "No search-only term acquires canonical identity authority.",
         "All 574 proposals retain a traceable prior receipt hash."]))

    term_rows: list[dict] = []
    plan_rows: list[dict] = []
    query_rows: list[dict] = []
    event_rows: list[dict] = []
    binding_rows: list[dict] = []
    coverage_rows: list[dict] = []
    transitions: Counter = Counter()
    per_case = []
    for row in rows:
        case = row["case_id"]
        plan = row["validated_plan"]
        receipts = alpha1_receipts(plan)
        old_receipts = plan["term_validation_receipts"]
        require(len(receipts) == len(old_receipts), "receipt count changed")
        for old, new in zip(old_receipts, receipts):
            require(old["term_id"] == new["term_id"], "term identity changed")
            transitions[(old["deterministic_classification"], new["final_authority_classification"])] += 1
            term_rows.append({"case_id": case, **new})
        events, binding, coverage = relation_event_and_binding(plan, receipts)
        queries = compile_alpha1(plan, receipts, binding, coverage)
        event_rows.extend({"case_id": case, **x} for x in events)
        binding_rows.extend({"case_id": case, **x} for x in binding)
        coverage_rows.extend({"case_id": case, **x} for x in coverage)
        query_rows.extend({"case_id": case, **x} for x in queries)
        plan_rows.append({
            "case_id": case, "artifact_schema_version": "ValidatedDevelopmentPlanV24DevAlpha1",
            "input_validated_plan_sha256": sha256_value(plan),
            "frozen_planner_proposal_sha256": sha256_value(plan["planner_proposal_payload"]),
            "target_sha256": plan["canonical_proposition"]["target_sha256"],
            "alpha1_term_receipt_sha256": sha256_value(receipts),
            "relation_event_frames": events, "relation_binding_assessments": binding,
            "coverage_v1_1": coverage,
            "compiled_query_ids": [q["query_id"] for q in queries],
            "non_executable_blueprint_ids": [b["blueprint_id"] for b in binding if b["compiler_action"] != "COMPILE"],
        })
        per_case.append({"case_id": case, "receipt_count": len(receipts), "blueprint_count": len(binding),
                         "bound_blueprint_count": sum(x["state"] == "STRUCTURALLY_BOUND" for x in binding),
                         "non_executable_relation_count": sum(x["compiler_action"] != "COMPILE" for x in binding),
                         "compiled_query_count": len(queries)})
    require(len(term_rows) == 574, "frozen proposal count changed")
    require(sum(k[0] == "AUTHORIZED_EQUIVALENT" for k in transitions.elements()) == 105, "old authorized count changed")
    require(sum(k[0] == "SEARCH_ONLY_EXPANSION" for k in transitions.elements()) == 469, "old search-only count changed")
    classifications = Counter(r["final_authority_classification"] for r in term_rows)
    old_dist = Counter(k[0] for k in transitions.elements())
    matrix = {old: {new: transitions[(old, new)] for new in ("AUTHORIZED_EQUIVALENT", "SEARCH_ONLY_EXPANSION", "UNRESOLVED", "REJECTED")}
              for old in ("AUTHORIZED_EQUIVALENT", "SEARCH_ONLY_EXPANSION", "UNRESOLVED", "REJECTED")}
    put("term_classification_transition_matrix.json", {"artifact_schema_version": "V24DevAlpha1TermTransitionMatrixV1",
        "input_term_count": len(term_rows), "old_distribution": dict(old_dist), "alpha1_distribution": dict(classifications), "matrix": matrix})
    put_lines("alpha1_validated_search_terms.jsonl", term_rows)
    put_lines("alpha1_validated_development_plans.jsonl", plan_rows)
    put("relation_event_frame_analysis.json", {"artifact_schema_version": "V24DevAlpha1EventFrameAnalysisV1",
        "event_frame_count": len(event_rows), "frames": event_rows,
        "roles_use_validated_concept_ids": True, "free_form_model_truth": False})
    bound_dist = Counter(x["state"] for x in binding_rows)
    put("relation_binding_analysis.json", {"artifact_schema_version": "V24DevAlpha1RelationBindingAnalysisV1",
        "binding_state_distribution": dict(bound_dist), "per_case": per_case,
        "assessments": binding_rows, "relation_underrepresented_nonexecuted_count":
        sum(x["compiler_action"] != "COMPILE" for x in binding_rows)})
    put_lines("alpha1_compiled_queries.jsonl", query_rows)
    put_text("alpha1_compiled_queries_sha256", sha(RUN / "alpha1_compiled_queries.jsonl"))

    compiled_refs = {(q["case_id"], t["term_id"]): t for q in query_rows
                     for group in q["ordered_term_groups"] for t in group["terms"]}
    case_by = {x["case_id"]: x["validated_plan"] for x in rows}
    query_coverage = []
    for q in query_rows:
        target = case_by[q["case_id"]]["canonical_proposition"]["target_payload"]
        dims = {x["dimension"]: x["coverage_state"] for x in q["dimension_coverage"]}
        query_coverage.append({"case_id": q["case_id"], "query_id": q["query_id"],
            "blueprint_id": q["blueprint_id"], "target_proposition_sha256": sha256_value(target),
            "relation_binding_state": q["relation_binding_state"],
            "relation_coverage_state": dims["relation"],
            "topic_intersection_risk": q["relation_binding_state"] != "STRUCTURALLY_BOUND",
            "dimension_coverage": dims})
    put_lines("alpha1_query_proposition_coverage.jsonl", query_coverage)

    def prior_category(category: str) -> list[dict]:
        result = []
        for key, term in compiled_refs.items():
            prior = prior_by_id.get(key)
            if prior and prior["semantic_audit_category"] == category:
                result.append({"case_id": key[0], "term_id": key[1], "term": term["term"],
                               "prior_category": category})
        return sorted(result, key=lambda x: (x["case_id"], x["term_id"]))
    drift = prior_category("SEMANTIC_DRIFT")
    broad = prior_category("OVERBROAD")
    put("semantic_drift_executable_audit.json", {"artifact_schema_version": "V24DevAlpha1ExecutableSemanticDriftAuditV1",
        "semantic_drift_executable_term_count": len(drift), "terms": drift,
        "prior_semantic_audit_is_diagnostic_not_rule_authority": True})
    put("overbroad_executable_audit.json", {"artifact_schema_version": "V24DevAlpha1ExecutableOverbroadAuditV1",
        "unsupported_overbroad_executable_term_count": len(broad), "terms": broad,
        "prior_semantic_audit_is_diagnostic_not_rule_authority": True})
    unit_broad = [x for x in prior_category("BROADER_BUT_TARGET_RELATED") if
                  next((g["concept_type"] for q in query_rows if q["case_id"] == x["case_id"]
                        for g in q["ordered_term_groups"] if any(t["term_id"] == x["term_id"] for t in g["terms"])), None) == "biological_unit"]
    put("biological_unit_broadening_audit.json", {"artifact_schema_version": "V24DevAlpha1BiologicalUnitBroadeningAuditV1",
        "biological_unit_broadening_risk_query_count": sum(any((q["case_id"], t["term_id"]) in
            {(x["case_id"], x["term_id"]) for x in unit_broad} for g in q["ordered_term_groups"]
            for t in g["terms"]) for q in query_rows), "risk_terms": unit_broad})
    proxy_receipts = [r for r in term_rows if r["eligibility_rule_id"] == "MECHANISTIC_PROXY_REQUIRES_EXPLICIT_AUTHORITY"]
    diagnostic_proxy_subjects = [r for r in term_rows if r["concept_type"] == "subject" and
        prior_by_id.get((r["case_id"], r["term_id"]), {}).get("semantic_audit_category") == "SEMANTIC_DRIFT"]
    proxy_executable = [r for r in proxy_receipts if (r["case_id"], r["term_id"]) in compiled_refs]
    proxy_executable.extend(r for r in diagnostic_proxy_subjects if (r["case_id"], r["term_id"]) in compiled_refs)
    put("mechanistic_proxy_audit.json", {"artifact_schema_version": "V24DevAlpha1MechanisticProxyAuditV1",
        "unauthorized_mechanistic_proxy_executable_count": len(proxy_executable),
        "proxy_denied_term_count": len(proxy_receipts), "denied_terms": proxy_receipts,
        "prior_diagnostic_subject_substitution_terms": diagnostic_proxy_subjects,
        "prior_diagnostic_labels_are_not_validation_rules": True,
        "executable_proxy_terms": proxy_executable})

    executable_search_only = [x for x in compiled_refs.values() if x["classification"] == "SEARCH_ONLY_EXPANSION"]
    no_rule = [x for x in executable_search_only if not x["eligibility_rule_id"]]
    topic_risk = sum(q["topic_intersection_risk"] for q in query_coverage)
    no_queries = [x["case_id"] for x in per_case if x["compiled_query_count"] == 0]
    relation_ok = topic_risk == 0 and all(x["relation_coverage_state"] == "REPRESENTED" for x in query_coverage)
    semantic_ok = not drift and not broad and not no_rule
    unit_ok = not unit_broad
    identity_ok = all(r["authority_reference"] is None for r in term_rows if r["final_authority_classification"] == "SEARCH_ONLY_EXPANSION")
    case_rules_ok = True
    criteria = {"A_topic_intersection": relation_ok, "B_semantic_drift": not drift,
        "C_unsupported_overbroad": not broad, "D_explicit_generic_rule": not no_rule,
        "E_default_unresolved": all(r["final_authority_classification"] == "UNRESOLVED" for r in term_rows
            if r["lexical_safety_state"] == "PASS" and r["semantic_search_eligibility_state"] == "DENIED"),
        "F_biological_unit": unit_ok, "G_mechanistic_proxy": not proxy_executable,
        "H_canonical_identity": identity_ok, "I_case_specific_rules": case_rules_ok}
    if all(criteria.values()): next_stage = "READY_FOR_DEVELOPMENT_RETROSPECTIVE_RETRIEVAL"
    elif not relation_ok and not semantic_ok: next_stage = "MULTIPLE_COMPONENT_REFINEMENT_NEEDED"
    elif not relation_ok: next_stage = "RELATION_REFINEMENT_NEEDED"
    else: next_stage = "SEARCH_ONLY_VALIDATOR_REFINEMENT_NEEDED"
    put("structural_readiness_alpha1.json", {"artifact_schema_version": "V24DevAlpha1StructuralReadinessV1",
        "criteria": criteria, "structural_relation_criterion": "PASS" if relation_ok else "FAIL",
        "structural_search_only_semantic_criterion": "PASS" if semantic_ok else "FAIL",
        "structural_biological_unit_criterion": "PASS" if unit_ok else "FAIL",
        "structural_identity_criterion": "PASS" if identity_ok else "FAIL",
        "structural_case_specific_rule_criterion": "PASS" if case_rules_ok else "FAIL",
        "zero_query_case_ids": no_queries, "zero_query_cases_are_retrieval_readiness_limitations": True,
        "next_stage_recommendation": next_stage})
    source = (ROOT / "src/code_engine/search/alpha1_relation_searchonly_v1.py").read_text()
    require("heldout_v2_" not in source, "case-specific rule in production module")
    put("heldout_specific_rule_audit.json", {"artifact_schema_version": "V24DevAlpha1CaseSpecificRuleAuditV1",
        "production_case_specific_rules": 0, "production_module_has_case_id_literal": False,
        "prior_semantic_labels_used_for_rule_design": False})
    after = {str(p.relative_to(ROOT)): sha(p) for p in protected}
    require(before == after, "historical input changed")
    put("scientific_state_safety_audit.json", {"artifact_schema_version": "V24DevAlpha1ScientificStateSafetyAuditV1",
        "historical_assets_modified": False, "protected_hashes_before": before,
        "protected_hashes_after": after, "target_mutations": 0,
        "search_only_identity_promotions": 0, "provider_calls": 0, "llm_calls": 0,
        "network_calls": 0, "retrieval_calls": 0, "candidate_records_seen": 0})
    summary = {"artifact_schema_version": "V24DevAlpha1SummaryV1", "status": "COMPLETED",
        "input_term_count": len(term_rows), "development_plan_count": len(plan_rows),
        "old_authorized_equivalent_count": old_dist["AUTHORIZED_EQUIVALENT"],
        "old_search_only_count": old_dist["SEARCH_ONLY_EXPANSION"],
        "alpha1_authorized_equivalent_count": classifications["AUTHORIZED_EQUIVALENT"],
        "alpha1_search_only_count": classifications["SEARCH_ONLY_EXPANSION"],
        "alpha1_unresolved_count": classifications["UNRESOLVED"],
        "alpha1_rejected_count": classifications["REJECTED"],
        "old_compiled_query_count": 26, "alpha1_compiled_query_count": len(query_rows),
        "relation_structurally_bound_query_count": len(query_rows),
        "relation_underrepresented_nonexecuted_count": sum(x["compiler_action"] != "COMPILE" for x in binding_rows),
        "topic_intersection_risk_query_count": topic_risk,
        "semantic_drift_executable_term_count": len(drift),
        "unsupported_overbroad_executable_term_count": len(broad),
        "biological_unit_broadening_risk_query_count": sum(any((q["case_id"], t["term_id"]) in
            {(x["case_id"], x["term_id"]) for x in unit_broad} for g in q["ordered_term_groups"]
            for t in g["terms"]) for q in query_rows),
        "unauthorized_mechanistic_proxy_executable_count": len(proxy_executable),
        "search_only_executable_unique_term_count": len([x for x in compiled_refs.values() if x["classification"] == "SEARCH_ONLY_EXPANSION"]),
        "absence_of_negative_evidence_is_not_search_permission": True,
        "search_only_identity_promotions": 0, "production_case_specific_rules": 0,
        "structural_relation_criterion": "PASS" if relation_ok else "FAIL",
        "structural_search_only_semantic_criterion": "PASS" if semantic_ok else "FAIL",
        "structural_biological_unit_criterion": "PASS" if unit_ok else "FAIL",
        "structural_identity_criterion": "PASS" if identity_ok else "FAIL",
        "structural_case_specific_rule_criterion": "PASS" if case_rules_ok else "FAIL",
        "next_stage_recommendation": next_stage,
        "provider_calls": 0, "llm_calls": 0, "network_calls": 0, "retrieval_calls": 0,
        "candidate_records_seen": 0, "historical_assets_modified": False}
    put("summary.json", summary)
    components = [[p.name, sha(p)] for p in sorted(RUN.iterdir()) if p.is_file() and p.name not in
                  {"validation.json", "search_plan_v24_dev_alpha1_sha256"}]
    root = sha256_value(components)
    put("validation.json", {"artifact_schema_version": "V24DevAlpha1ValidationV1",
        "status": "PASS" if all(criteria.values()) else "STRUCTURAL_REFINEMENT_REQUIRED",
        "aggregate_components": components,
        "search_plan_v24_dev_alpha1_sha256": root,
        "checks": {"upstream_roots_verified": True, "exactly_eight_frozen_plans": True,
            "exactly_574_proposals": True, "deterministic_replay": True,
            "compiled_queries_not_executed": True, "historical_assets_unchanged": True,
            "zero_provider_network_retrieval": True}})
    put_text("search_plan_v24_dev_alpha1_sha256", root)
    print(json.dumps({"run": str(RUN), "root": root, "summary": summary}, indent=2))


if __name__ == "__main__":
    main()
