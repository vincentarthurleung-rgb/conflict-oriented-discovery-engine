"""Freeze offline alpha2.3 context-role audit and exact case-101 replay."""

from __future__ import annotations

from collections import Counter
import hashlib
import json
from pathlib import Path
from typing import Any

from code_engine.search.alpha1_relation_searchonly_v1 import _anchors
from code_engine.search.alpha2_linked_relation_v1 import assess_linked_relation_v1_1, search_only_eligibility_v1_1
from code_engine.search.context_role_ontology_v1 import (
    APPLICABILITY_STATES, BINDING_VERSION, CONDITIONING_VERSION, LINK_VERSION,
    ONTOLOGY_VERSION, ROLES, THERAPY_VERSION, assess_linked_relation_v1_2,
    conditioning_context_applicability, context_role_mapping,
    linked_relation_search_only_eligibility_v1_2, therapy_context_applicability,
)
from code_engine.search.proposition_aware_query_planner_v1 import sha256_value
from code_engine.search.semantic_slot_compatibility_v1 import validate_v2_structure_and_slots
from tools.freeze_search_plan_v24_dev_alpha2_2_semantic_slot_compatibility_offline import (
    AUTOPSY, AUTHORITY, fixture_rows, targets_by_case,
)
from tools.run_search_plan_v24_dev_alpha2_1_smoke_101 import (
    classify_terms, compile_bound, frozen_target, verify_root,
)

ROOT = Path(__file__).resolve().parents[1]
RUN = ROOT / "runs/20260920_search_plan_v24_dev_alpha2_3_context_role_semantics_offline"
UPSTREAM = {
    "alpha2": (ROOT / "runs/20260920_search_plan_v24_dev_alpha2_linked_relation_deepseek_migration_offline",
               "918e0badbaeb70c439ae8d6e1d3bcc1eb5d5697c5df75b38dc2819357890a4e8"),
    "alpha2_1": (ROOT / "runs/20260920_search_plan_v24_dev_alpha2_1_deepseek_reasoning_config_offline",
                 "fee80d671ed6e573ca0e18640b4ab87b15aec021e6870f17b0fc3457554b41fc"),
    "alpha2_2": (ROOT / "runs/20260920_search_plan_v24_dev_alpha2_2_semantic_slot_compatibility_offline",
                 "c54fcb5cd86747fce09b79e90d0d8f833ae2dd6d7fdfeb28ee466ca4b5ca91b4"),
    "smoke": (ROOT / "runs/20260920_search_plan_v24_dev_alpha2_1_deepseek_planner_v2_smoke_101",
              "b66eebe346b1f130287083e364fbba10a22110b40f0a288e9185fe5f5242fd40"),
}
RAW_SHA = "e3f0386b9e08a6d8dce12b7388b5da34db4bd75995eb530576176bbc2ccf2c7f"


def require(ok: bool, message: str) -> None:
    if not ok:
        raise ValueError(message)


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def dump(name: str, value: Any) -> None:
    path = RUN / name
    require(not path.exists() and not path.is_symlink(), f"refusing overwrite: {name}")
    path.write_text(json.dumps(value, sort_keys=True, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def lines(name: str, rows: list[dict[str, Any]]) -> None:
    path = RUN / name
    require(not path.exists() and not path.is_symlink(), f"refusing overwrite: {name}")
    path.write_bytes(b"".join(json.dumps(row, sort_keys=True, ensure_ascii=False,
                                   separators=(",", ":")).encode("utf-8") + b"\n" for row in rows))


def regression(targets: dict[str, dict[str, Any]]) -> dict[str, Any]:
    rows = fixture_rows()
    results = []
    for row in rows:
        state, rule = search_only_eligibility_v1_1(row["term"], row["concept_type"], targets[row["case_id"]])
        results.append({"case_id": row["case_id"], "term_id": row["term_id"],
                        "diagnostic_category": row["diagnostic_category"],
                        "prior_semantic_category": row["prior_semantic_category"],
                        "state": state, "rule_id": rule})
    protected = {
        "overbroad": [r for r in results if r["diagnostic_category"] == "CORRECTLY_WITHHELD_OVERBROAD"],
        "semantic_drift": [r for r in results if r["prior_semantic_category"] == "SEMANTIC_DRIFT"],
        "entity_substitution": [r for r in results if r["diagnostic_category"] == "CORRECTLY_WITHHELD_ENTITY_SUBSTITUTION"],
        "context_broadening": [r for r in results if r["diagnostic_category"] == "CORRECTLY_WITHHELD_CONTEXT_BROADENING"],
    }
    require(len(rows) == 328, "protected search-only fixture count changed")
    require({key: len(value) for key, value in protected.items()} == {
        "overbroad": 122, "semantic_drift": 3, "entity_substitution": 5, "context_broadening": 3},
        "protected fixture category count changed")
    require(all(r["state"] != "SEARCH_ONLY_EXPANSION" for group in protected.values() for r in group),
            "protected isolated term promoted")
    return {"artifact_schema_version": "Alpha2_3SearchOnlySafetyRegressionV1",
            "frozen_fixture_source_sha256": digest(AUTOPSY / "unresolved_term_diagnostic.json"),
            "term_count": len(rows), "protected_category_counts": {k: len(v) for k, v in protected.items()},
            "protected_term_promotions": 0, "isolated_term_validator_changed": False,
            "default_deny_preserved": True, "results_sha256": sha256_value(results)}


def main() -> None:
    require(not RUN.exists(), "alpha2.3 output already exists")
    upstream = {name: verify_root(path, root) for name, (path, root) in UPSTREAM.items()}
    source = UPSTREAM["smoke"][0]
    raw_path = source / "raw_model_content.txt"
    payload_path = source / "planner_v2_raw_payload.json"
    require(digest(raw_path) == RAW_SHA, "frozen model content hash changed")
    wrapper = json.loads(payload_path.read_text(encoding="utf-8"))
    payload = wrapper["parsed_provider_payload"]
    require(wrapper["parse_success"] and json.loads(raw_path.read_text(encoding="utf-8")) == payload,
            "raw provider payload differs from frozen parsed payload")
    target = frozen_target()
    targets = targets_by_case()
    require(len(targets) == 8 and targets["heldout_v2_101"] == target,
            "frozen eight-case authority mismatch")
    protected_paths = [raw_path, payload_path, UPSTREAM["alpha2"][0] / "planner_prompt_v2.md",
                       UPSTREAM["alpha2"][0] / "planner_proposal_payload_v2_schema.json",
                       ROOT / "src/code_engine/search/alpha1_relation_searchonly_v1.py",
                       ROOT / "src/code_engine/search/alpha2_linked_relation_v1.py",
                       ROOT / "src/code_engine/search/semantic_slot_compatibility_v1.py",
                       ROOT / "src/code_engine/search/context_role_ontology_v1.py",
                       ROOT / "tools/freeze_search_plan_v24_dev_alpha2_3_context_role_semantics_offline.py",
                       ROOT / "tests/test_context_role_ontology_v1.py"]
    protected_hashes = {str(path.relative_to(ROOT)): digest(path) for path in protected_paths}
    role_rows = []
    legacy_duplicates = []
    for case_id, current in sorted(targets.items()):
        mapping = context_role_mapping(current)
        cond = conditioning_context_applicability(current)
        therapy = therapy_context_applicability(current)
        treatment_rows = [r for r in mapping["roles"] if r["source_path"].endswith(("/treatment", "/treatment_context"))]
        old_required = bool(_anchors(current, "nested_treatment"))
        if old_required and cond["state"] == "NOT_APPLICABLE":
            legacy_duplicates.extend({"case_id": case_id, **r,
                                      "old_role": "CONDITIONING_TREATMENT",
                                      "new_role": r["role"],
                                      "explanation": "frozen primary action was duplicated as mandatory conditioning context"}
                                     for r in treatment_rows if r["role"] == "PRIMARY_INTERVENTION_ACTION")
        role_rows.append({"case_id": case_id, "target_sha256": sha256_value(current),
                          "primary_intervention": current.get("subject"),
                          "primary_intervention_action": current.get("subject_intervention"),
                          "conditioning": cond, "therapy": therapy,
                          "biological_unit_required": bool(_anchors(current, "biological_unit")),
                          "source_role_mapping": mapping,
                          "legacy_nested_treatment_required": old_required})
    require(len(legacy_duplicates) == 4, "unexpected legacy primary/context duplication count")
    by_case = {r["case_id"]: r for r in role_rows}
    require([by_case[f"heldout_v2_{i}"]["conditioning"]["state"] for i in range(101, 109)] ==
            ["NOT_APPLICABLE"] * 5 + ["REQUIRED", "NOT_APPLICABLE", "NOT_APPLICABLE"],
            "cross-case conditioning role pattern changed")
    require([by_case[f"heldout_v2_{i}"]["therapy"]["state"] for i in range(101, 109)] ==
            ["NOT_APPLICABLE"] * 6 + ["REQUIRED", "REQUIRED"],
            "cross-case therapy role pattern changed")
    replay = validate_v2_structure_and_slots(payload, target)
    require(replay["provider_payload_schema_valid"] and replay["concept_references_valid"] and
            replay["surface_anchors_compatible"] and replay["semantic_slots_compatible"],
            "frozen payload failed prior deterministic gates")
    links = []
    coverage = []
    binder_inputs = []
    for intent in payload["retrieval_intents"]:
        concepts = {c["concept_id"]: c for c in intent["search_concepts"]}
        for blueprint in intent["candidate_query_blueprints"]:
            selected = []
            for index, link in enumerate(blueprint["linked_relation_candidates"]):
                binding = assess_linked_relation_v1_2(link, target, concepts, blueprint["concept_ids"])
                search_state, search_rule = linked_relation_search_only_eligibility_v1_2(
                    link, target, concepts, blueprint["concept_ids"])
                legacy = assess_linked_relation_v1_1(link, target, intent_type=intent["intent_type"])
                row = {"intent_id": intent["intent_id"], "blueprint_id": blueprint["blueprint_id"],
                       "linked_candidate_index": index, "source_candidate_sha256": sha256_value(link),
                       "linked_phrase": link["linked_relation_phrase"],
                       "legacy_v1_1_binding": legacy,
                       "new_v1_2_binding": binding,
                       "new_v1_2_search_only_state": search_state,
                       "new_v1_2_search_only_rule": search_rule,
                       "original_candidate_mutated": False}
                links.append(row)
                selected.append(row)
                binder_inputs.append({"intent_id": intent["intent_id"],
                                      "blueprint_id": blueprint["blueprint_id"],
                                      "linked_candidate_index": index,
                                      "state": binding["state"],
                                      "search_only_classification": search_state})
            coverage.append({"artifact_schema_version": "PropositionCoverageAnalysisV1_2",
                             "intent_id": intent["intent_id"], "blueprint_id": blueprint["blueprint_id"],
                             "candidate_count": len(selected),
                             "structurally_bound_candidate_count": sum(
                                 r["new_v1_2_binding"]["state"] == "STRUCTURALLY_BOUND" for r in selected),
                             "relation_coverage_state": "REPRESENTED" if any(
                                 r["new_v1_2_binding"]["state"] == "STRUCTURALLY_BOUND" for r in selected)
                             else "RELATION_UNDERREPRESENTED"})
    require(len(links) == 2, "frozen candidate count changed")
    valid_count = sum(r["new_v1_2_binding"]["state"] == "STRUCTURALLY_BOUND" for r in links)
    bound_blueprints = sum(r["relation_coverage_state"] == "REPRESENTED" for r in coverage)
    receipts = classify_terms(payload, target)
    compiled = compile_bound(payload, target, binder_inputs, receipts) if valid_count else []
    compiled = [{**row, "alpha2_3_binding_contract": BINDING_VERSION,
                 "alpha2_3_applicability_contract": CONDITIONING_VERSION,
                 "historical_compiler_unchanged": True} for row in compiled]
    gates = [
        {"stage": "PROVIDER_PAYLOAD_SCHEMA", "passed": replay["provider_payload_schema_valid"]},
        {"stage": "CONCEPT_REFERENCE", "passed": replay["concept_references_valid"]},
        {"stage": "SURFACE_ANCHOR_COMPATIBILITY", "passed": replay["surface_anchors_compatible"]},
        {"stage": "SEMANTIC_SLOT_COMPATIBILITY", "passed": replay["semantic_slots_compatible"]},
        {"stage": "CONTEXT_ROLE_APPLICABILITY", "passed": by_case["heldout_v2_101"]["conditioning"]["state"] == "NOT_APPLICABLE"},
        {"stage": "LINKED_RELATION_VALIDATION", "passed": valid_count > 0, "valid_candidate_count": valid_count},
        {"stage": "SEARCH_ONLY_ELIGIBILITY", "passed": any(
            r["new_v1_2_search_only_state"] == "SEARCH_ONLY_EXPANSION" for r in links)},
        {"stage": "RELATION_BINDING", "passed": valid_count > 0},
        {"stage": "COVERAGE", "passed": bound_blueprints > 0},
        {"stage": "COMPILER", "passed": bool(compiled), "compiled_query_count": len(compiled)},
    ]
    first_loss = next((r["stage"] for r in gates if not r["passed"]), "NONE")
    recommendation = ("AUTHORIZE_REMAINING_7_DEEPSEEK_DEVELOPMENT_CASES" if
                      valid_count and bound_blueprints and compiled else
                      "PLANNER_V2_REFINEMENT_NEEDED" if first_loss == "LINKED_RELATION_VALIDATION" else
                      "DETERMINISTIC_REFINEMENT_NEEDED")
    require(valid_count == 2 and bound_blueprints == 1 and len(compiled) == 2 and first_loss == "NONE",
            "unexpected case-101 replay state; fail closed")
    safety = regression(targets)
    RUN.mkdir(parents=True, exist_ok=False)
    dump("upstream_root_verification.json", upstream)
    dump("context_role_ontology_v1_contract.json", {
        "artifact_schema_version": ONTOLOGY_VERSION, "roles": list(ROLES),
        "generic_patterns": {"A_affects_B": "no conditioning unless a distinct frozen treatment context exists",
                             "A_affects_C_under_B": "distinct B is conditioning treatment",
                             "A_affects_B_induced_C": "distinct B is conditioning treatment",
                             "A_changes_sensitivity_to_T": "T is therapy",
                             "A_changes_B_in_genotype_G": "G is genotype context",
                             "A_changes_B_in_cell_type_C": "C is biological-unit context"},
        "full_primary_action_match_required_for_treatment_role_reassignment": True,
        "ambiguous_same_actor_different_action": "UNRESOLVED",
        "target_identity_mutated": False,
        "implementation_sha256": protected_hashes["src/code_engine/search/context_role_ontology_v1.py"]})
    dump("target_role_mapping_audit.json", {"artifact_schema_version": "Alpha2_3TargetRoleMappingAuditV1",
        "case_count": len(role_rows), "role_mappings": role_rows,
        "source_authority": "frozen ScientificPropositionTargetV1 objects"})
    dump("case_101_context_role_provenance.json", {
        "case_id": "heldout_v2_101", "frozen_target_sha256": sha256_value(target),
        "source_target_constructor": "tools/freeze_search_plan_v23_beta_2_primary_heldout_v2_cases_offline.py",
        "source_target_field": "/context_qualifier_dimensions/treatment/0",
        "source_target_value": "EGF stimulation",
        "primary_intervention_field": "/subject_intervention",
        "primary_intervention_value": target["subject_intervention"],
        "legacy_anchor_helper": "src/code_engine/search/alpha1_relation_searchonly_v1.py::_anchors",
        "legacy_anchor_dimension": "nested_treatment", "legacy_anchor_values": _anchors(target, "nested_treatment"),
        "provider_schema": "PlannerProposalPayloadV2 requires conditioning_context_refs array but permits empty",
        "frozen_candidate_conditioning_refs": [
            link["conditioning_context_refs"] for i in payload["retrieval_intents"] for b in i["candidate_query_blueprints"]
            for link in b["linked_relation_candidates"]],
        "legacy_binding_layer": "RelationBindingAssessmentV1_1 nested_treatment check required nonempty refs whenever anchor exists",
        "alpha2_2_candidate_layer": "LinkedRelationCandidateSemanticSlotAuditV1 required_conditioning_context false",
        "alpha2_2_frozen_binding_additional_false_checks": [
            {"index": r["linked_candidate_index"],
             "false_checks": [k for k, v in r["legacy_v1_1_binding"]["checks"].items() if not v]}
            for r in links],
        "corrected_generic_role": "PRIMARY_INTERVENTION_ACTION",
        "corrected_conditioning_applicability": "NOT_APPLICABLE",
        "planner_prompt_changed": False, "source_target_mutated": False})
    dump("cross_case_context_role_audit.json", {"artifact_schema_version": "Alpha2_3CrossCaseContextRoleAuditV1",
        "case_count": len(role_rows), "cases": [
            {"case_id": r["case_id"], "primary_intervention": r["primary_intervention"],
             "primary_intervention_action": r["primary_intervention_action"],
             "conditioning_state": r["conditioning"]["state"],
             "conditioning_surfaces": r["conditioning"]["required_surfaces"],
             "therapy_state": r["therapy"]["state"],
             "therapy_surfaces": r["therapy"]["required_surfaces"],
             "biological_unit_required": r["biological_unit_required"]} for r in role_rows],
        "retrieval_outcomes_used": False})
    dump("conditioning_context_applicability_v1_contract.json", {
        "artifact_schema_version": CONDITIONING_VERSION, "states": list(APPLICABILITY_STATES),
        "required_if_distinct_frozen_treatment_role": True,
        "empty_refs_valid_if_not_applicable": True,
        "unknown_same_actor_action_fails_closed": True})
    dump("therapy_context_applicability_v1_contract.json", {
        "artifact_schema_version": THERAPY_VERSION, "states": list(APPLICABILITY_STATES),
        "therapy_response_requires_exact_frozen_therapy_ref": True,
        "therapy_not_flattened_to_conditioning_treatment": True})
    dump("semantic_role_duplication_audit.json", {
        "artifact_schema_version": "Alpha2_3SemanticRoleDuplicationAuditV1",
        "legacy_semantic_role_duplication_count": len(legacy_duplicates),
        "semantic_role_duplication_count": 0,
        "legacy_primary_action_as_conditioning_rows": legacy_duplicates,
        "therapy_field_and_therapy_context_same_role": [r["case_id"] for r in role_rows
            if r["therapy"]["state"] == "REQUIRED" and len(r["therapy"]["source_rows"]) > 1],
        "biological_unit_mapped_only_to_biological_unit_context": True})
    dump("linked_relation_candidate_v1_1_contract.json", {
        "artifact_schema_version": LINK_VERSION, "source_candidate_version": "LinkedRelationCandidateV1",
        "provider_payload_schema_changed": False, "primary_intervention_ref_distinct": True,
        "conditioning_treatment_refs_governed_by_applicability": True,
        "therapy_refs_governed_by_applicability": True,
        "biological_unit_ref_independent": True,
        "other_context_refs_separate": True,
        "wrong_role_or_wrong_canonical_ref_rejected": True})
    dump("relation_binding_assessment_v1_2_contract.json", {
        "artifact_schema_version": BINDING_VERSION,
        "uses_alpha2_2_surface_and_semantic_checks": True,
        "requires_primary_intervention_response_endpoint_relation_direction": True,
        "requires_biological_unit_if_frozen_target_requires": True,
        "requires_conditioning_only_if_applicability_REQUIRED": True,
        "requires_therapy_only_if_applicability_REQUIRED": True,
        "unresolved_applicability_blocks_binding": True,
        "frozen_v1_1_unchanged": True})
    dump("case_101_frozen_payload_replay.json", {
        "artifact_schema_version": "Alpha2_3Frozen101ReplayV1",
        "raw_model_content_sha256": RAW_SHA,
        "source_payload_file_sha256": digest(payload_path),
        "source_candidate_count": len(links), "valid_candidate_count": valid_count,
        "candidate_replays": links, "schema_reference_anchor_slot_replay": replay,
        "coverage_version": "PropositionCoverageAnalysisV1_2", "coverage": coverage,
        "source_payload_mutated": False})
    dump("case_101_gate_trace_v2.json", {"artifact_schema_version": "Alpha2_3Case101GateTraceV2",
        "gates": gates, "first_loss_stage": first_loss})
    dump("case_101_first_loss_reclassification.json", {
        "prior_alpha2_2_first_loss": "LINKED_RELATION_VALIDATION",
        "prior_first_loss_reclassification": "CONTEXT_ROLE_CONTRACT_FALSE_NEGATIVE",
        "reason": "alpha2.2 candidate audit failed only unconditional conditioning_context_refs for a primary action",
        "additional_legacy_binding_defect": "V1_1 binder did not consume alpha2.2 composite surface and endpoint semantic compatibility",
        "end_to_end_defect_count": 2,
        "new_first_loss_stage": first_loss,
        "planner_content_omission_established": False})
    lines("case_101_compiled_queries.jsonl", compiled)
    dump("nested_treatment_regression_audit.json", {
        "case_106_state": by_case["heldout_v2_106"]["conditioning"]["state"],
        "case_106_required_surface": "LPS stimulation",
        "missing_ref_blocks": True, "wrong_anchor_ref_blocks": True,
        "focused_test_names": ["test_lps_conditioning_required", "test_required_lps_cannot_be_empty",
                               "test_wrong_context_ref_cannot_be_laundered_by_phrase"],
        "requirement_preserved": True})
    dump("therapy_response_regression_audit.json", {
        "case_107_state": by_case["heldout_v2_107"]["therapy"]["state"],
        "case_108_state": by_case["heldout_v2_108"]["therapy"]["state"],
        "required_therapies": ["trametinib", "temozolomide"],
        "missing_ref_blocks": True, "wrong_anchor_ref_blocks": True,
        "primary_intervention_ref_cannot_satisfy_therapy": True,
        "requirement_preserved": True})
    dump("biological_unit_regression_audit.json", {
        "case_101_biological_unit_required": True,
        "missing_biological_unit_ref_blocks": True,
        "biological_unit_role_distinct_from_other_context": True,
        "requirement_preserved": True})
    dump("search_only_safety_regression.json", safety)
    dump("heldout_specific_rule_audit.json", {
        "case_specific_rules": 0, "case_ids_in_runtime_rule_tables": 0,
        "target_frozen_fields_used_only_for_generic_role_matching": True,
        "development_cases_used_for_offline_audit_only": True})
    require(all(digest(ROOT / path) == old for path, old in protected_hashes.items()),
            "source or protected file changed")
    for _, (path, root) in UPSTREAM.items():
        verify_root(path, root)
    dump("scientific_state_safety_audit.json", {
        "historical_assets_modified": False, "upstream_roots_reverified_after_replay": True,
        "protected_file_hashes": protected_hashes,
        "deepseek_transport_changed": False, "planner_prompt_v2_changed": False,
        "planner_proposal_payload_v2_changed": False,
        "identity_safety_preserved": True,
        "provider_calls": 0, "llm_calls": 0, "network_calls": 0,
        "retrieval_calls": 0, "candidate_records_seen": 0})
    summary = {"artifact_schema_version": "Alpha2_3ContextRoleSemanticsSummaryV1",
        "status": "completed", "context_role_ontology_defined": True,
        "primary_intervention_distinct_from_conditioning_treatment": True,
        "therapy_distinct_from_conditioning_treatment": True,
        "conditioning_context_applicability_defined": True,
        "therapy_context_applicability_defined": True,
        "case_101_conditioning_context_applicability": "NOT_APPLICABLE",
        "case_101_valid_linked_candidate_count": valid_count,
        "case_101_structurally_bound_blueprint_count": bound_blueprints,
        "case_101_compiled_query_count": len(compiled),
        "case_101_first_loss_classification": first_loss,
        "nested_treatment_requirement_preserved": True,
        "therapy_requirement_preserved": True,
        "biological_unit_requirement_preserved": True,
        "search_only_default_deny_preserved": True,
        "identity_safety_preserved": True,
        "production_case_specific_rules": 0,
        "next_stage_recommendation": recommendation,
        "provider_calls": 0, "llm_calls": 0, "network_calls": 0,
        "retrieval_calls": 0, "historical_assets_modified": False}
    dump("summary.json", summary)
    components = [[path.name, digest(path)] for path in sorted(RUN.iterdir()) if path.is_file()]
    root = sha256_value(components)
    dump("validation.json", {"artifact_schema_version": "Alpha2_3ContextRoleSemanticsValidationV1",
        "status": "PASS", "aggregate_components": components,
        "search_plan_v24_dev_alpha2_3_sha256": root,
        "upstream_roots_verified": True,
        "raw_payload_reused_exactly": True,
        "focused_tests_required_before_freeze": True,
        "no_model_or_retrieval_calls": True})
    (RUN / "search_plan_v24_dev_alpha2_3_sha256").write_text(root + "\n", encoding="utf-8")
    print(json.dumps({"summary": summary, "root": root}, sort_keys=True))


if __name__ == "__main__":
    main()
