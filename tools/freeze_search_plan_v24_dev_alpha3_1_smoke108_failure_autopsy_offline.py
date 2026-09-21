"""Freeze the offline alpha3.1 proposal-level autopsy for case 108.

This is diagnostic instrumentation only.  It reuses the exact frozen DeepSeek
Planner V3 payload and does not modify or execute any planner, validator,
compiler, provider, network, or retrieval component.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from code_engine.search.proposition_aware_query_planner_v1 import sha256_value
from tools.run_search_plan_v24_dev_alpha2_1_smoke_101 import verify_root

ROOT = Path(__file__).resolve().parents[1]
RUN = ROOT / "runs/20260922_search_plan_v24_dev_alpha3_1_smoke108_failure_autopsy_offline"
ALPHA3 = ROOT / "runs/20260920_search_plan_v24_dev_alpha3_minimal_planner_contract_offline"
SMOKE = ROOT / "runs/20260922_search_plan_v24_dev_alpha3_deepseek_planner_v3_smoke_108_protocol_completion_offline"
SOURCE = ROOT / "runs/20260922_search_plan_v24_dev_alpha3_deepseek_planner_v3_smoke_108"
ROOTS = {
    "alpha3": (ALPHA3, "96990556e92d197345416a000b4cba88e250afa4456499f498ec89891a95c61f"),
    "protocol_complete_smoke_108": (SMOKE, "fd84c02322f9b9b76d3af0a49c280af4bbbfbeae344749c9e02b89d7a4b084b0"),
    "original_one_call_source": (SOURCE, "519de1d347c105c9b1cf7c64723674ac8b9478edf750f213b2865ec2a4706075"),
}
ROOT_FILE = "search_plan_v24_dev_alpha3_1_sha256"
REQUIRED = {
    "upstream_root_verification.json", "smoke108_payload_preservation_audit.json",
    "smoke108_all_proposals.json", "relation_core_v1_architecture_audit.json",
    "query_context_constraint_v1_architecture_audit.json",
    "relation_internal_external_context_matrix.json",
    "therapy_sensitization_failure_autopsy.json",
    "compositional_response_semantics_architecture_audit.json",
    "direct_perturbation_direction_autopsy.json",
    "direction_composition_architecture_audit.json",
    "rescue_biological_unit_autopsy.json",
    "relation_phrase_vs_query_coverage_audit.json",
    "topic_intersection_safety_audit.json", "therapy_relation_safety_audit.json",
    "nested_treatment_safety_audit.json", "endpoint_property_safety_audit.json",
    "necessity_success_reaudit.json", "smoke_success_classification.json",
    "next_component_recommendation.json", "remaining7_authorization_recommendation.json",
    "heldout_specific_rule_audit.json", "scientific_state_safety_audit.json",
    "validation.json", "summary.json", ROOT_FILE,
}


def require(ok: bool, message: str) -> None:
    if not ok:
        raise ValueError(message)


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def protected_hashes() -> dict[str, str]:
    paths = [
        ALPHA3 / "planner_prompt_v3.md",
        ALPHA3 / "planner_proposal_payload_v3_schema.json",
        ALPHA3 / "deterministic_target_role_frame_v1_contract.json",
        ALPHA3 / "intent_semantic_transform_v1_contract.json",
        ALPHA3 / "semantic_surface_containment_v2_contract.json",
        ALPHA3 / "planner_role_rehydrator_v1_contract.json",
        ALPHA3 / "validated_planner_intent_v3_contract.json",
        ALPHA3 / "compiler_input_boundary_v3_audit.json",
        SMOKE / "planner_v3_raw_payload.json",
        SMOKE / "planner_v3_raw_payload_sha256",
        SMOKE / "relation_binding_analysis.json",
        SMOKE / "compiled_queries.jsonl",
        ROOT / "src/code_engine/search/planner_v3_contract.py",
        ROOT / "src/code_engine/search/semantic_slot_compatibility_v1.py",
        ROOT / "src/code_engine/search/context_role_ontology_v1.py",
    ]
    return {str(path.relative_to(ROOT)): digest(path) for path in paths}


def main() -> None:
    require(not RUN.exists(), "alpha3.1 autopsy run already exists")
    upstream = {name: verify_root(path, expected)
                for name, (path, expected) in ROOTS.items()}
    before = protected_hashes()
    payload = read_json(SMOKE / "planner_v3_raw_payload.json")
    payload_sha = (SMOKE / "planner_v3_raw_payload_sha256").read_text(encoding="utf-8").strip()
    require(sha256_value(payload) == payload_sha ==
            "eca4a6a3d03185477a4ecbda1c5d08ebd515fd792d4b3e8679855dbc47036309",
            "frozen Planner V3 payload changed")
    frame = read_json(SMOKE / "target_role_frame_108.json")
    intents = read_json(SMOKE / "intent_selection_analysis.json")["intent_rows"]
    relations = read_json(SMOKE / "linked_relation_proposal_analysis.json")["proposals"]
    role_bindings = read_json(SMOKE / "role_rehydration_analysis.json")["role_bindings"]
    binding = read_json(SMOKE / "relation_binding_analysis.json")
    semantic = read_json(SMOKE / "semantic_slot_compatibility.json")["rows"]
    containment = read_json(SMOKE / "semantic_surface_containment.json")["rows"]
    compiled = [json.loads(line) for line in (SMOKE / "compiled_queries.jsonl").read_text(
        encoding="utf-8").splitlines() if line]
    require(len(intents) == len(relations) == len(role_bindings) == 4,
            "frozen four-intent census changed")
    by_type = {row["intent_type"]: row for row in relations}
    binding_by_type = {row["intent_type"]: row for row in binding["rows"]}
    roles_by_type = {row["intent_type"]: row for row in role_bindings}
    semantic_by_type = {row["intent_type"]: row for row in semantic}
    containment_by_type = {row["intent_type"]: row for row in containment}
    require(set(by_type) == {"THERAPY_SENSITIZATION", "DIRECT_PERTURBATION", "NECESSITY", "RESCUE"},
            "selected intent set changed")

    proposal_fields = (
        "intent_type", "subject_surface", "subject_action_surface", "relation_surface",
        "direction", "response_surface", "endpoint_property_surface", "linked_relation_phrase",
        "therapy_surface", "biological_unit_surface", "disease_surface", "genotype_surface",
        "conditioning_treatment_surface", "evidence_mode_surface", "planner_rationale",
    )
    raw_intents = {row["intent_type"]: row for row in payload["retrieval_intents"]}
    verbatim = []
    for intent_type in raw_intents:
        intent = raw_intents[intent_type]
        for proposal in intent["linked_relation_proposals"]:
            verbatim.append({"intent_type": intent_type,
                             **{field: proposal[field] for field in proposal_fields if field != "intent_type"},
                             "retrieval_rationale": intent["retrieval_rationale"],
                             "source_payload_sha256": payload_sha})
    require(len(verbatim) == 4, "proposal dump count changed")

    internal_external_matrix = [
        {"role": "PRIMARY_INTERVENTION", "default_location": "RELATION_CORE", "externalizable": False,
         "reason": "actor identity is an argument of the causal/retrieval event"},
        {"role": "PRIMARY_INTERVENTION_ACTION", "default_location": "RELATION_CORE", "externalizable": False,
         "reason": "perturbation distinguishes intervention from topic mention"},
        {"role": "RELATION_AND_DIRECTION", "default_location": "RELATION_CORE", "externalizable": False,
         "reason": "the actor-response linkage cannot be reconstructed from independent conjuncts"},
        {"role": "RESPONSE_TARGET", "default_location": "RELATION_CORE", "externalizable": False,
         "reason": "the measured response is an event argument"},
        {"role": "ENDPOINT_PROPERTY", "default_location": "RELATION_CORE", "externalizable": False,
         "reason": "scientifically defining properties such as phosphorylation, secretion, localization, flux, or therapy response must remain linked"},
        {"role": "THERAPY", "default_location": "RELATION_CORE_FOR_THERAPY_RESPONSE", "externalizable": False,
         "reason": "therapy is part of the response semantics, not generic context"},
        {"role": "CONDITIONING_TREATMENT", "default_location": "RELATION_CORE_FOR_NESTED_RESPONSE", "externalizable": False,
         "reason": "conditioning defines the nested response event"},
        {"role": "LOCALIZATION", "default_location": "RELATION_CORE_WHEN_ENDPOINT_PROPERTY",
         "externalizable": "ONLY_WHEN_NOT_ENDPOINT_DEFINING",
         "reason": "nuclear accumulation cannot be reduced to a generic context conjunct"},
        {"role": "BIOLOGICAL_UNIT", "default_location": "QUERY_CONTEXT_CONSTRAINT",
         "externalizable": True, "reason": "usually scopes the experiment after a valid relation core exists"},
        {"role": "DISEASE", "default_location": "QUERY_CONTEXT_CONSTRAINT",
         "externalizable": True, "reason": "usually scopes the experimental or clinical population"},
        {"role": "GENOTYPE", "default_location": "QUERY_CONTEXT_CONSTRAINT",
         "externalizable": True, "reason": "usually scopes the population unless itself an intervention/response argument"},
        {"role": "SPECIES", "default_location": "QUERY_CONTEXT_CONSTRAINT",
         "externalizable": True, "reason": "normally scopes the biological unit"},
        {"role": "TIME", "default_location": "QUERY_CONTEXT_CONSTRAINT",
         "externalizable": "ONLY_WHEN_NOT_DEFINING_EVENT_ORDER",
         "reason": "ordinary time scope may be conjunctive; causal ordering may not"},
    ]

    therapy = by_type["THERAPY_SENSITIZATION"]
    therapy_autopsy = {
        "intent_type": "THERAPY_SENSITIZATION",
        "canonical_response_target": frame["role_surfaces"]["RESPONSE_TARGET"],
        "canonical_therapy": frame["role_surfaces"]["THERAPY"],
        "canonical_endpoint_property": frame["role_surfaces"]["RESPONSE_PROPERTY"],
        "proposed_response_surface": therapy["response_surface"],
        "proposed_endpoint_property_surface": therapy["endpoint_property_surface"],
        "linked_relation_phrase": therapy["linked_relation_phrase"],
        "direction": therapy["direction"],
        "frozen_response_in_phrase": containment_by_type["THERAPY_SENSITIZATION"]["response_in_phrase"],
        "frozen_endpoint_in_phrase": containment_by_type["THERAPY_SENSITIZATION"]["endpoint_in_phrase"],
        "therapy_anchor_compatible": roles_by_type["THERAPY_SENSITIZATION"]["bound_role_state"]["THERAPY"]["bound"],
        "endpoint_semantics_compatible": semantic_by_type["THERAPY_SENSITIZATION"]["endpoint_semantics"],
        "direction_compatible": semantic_by_type["THERAPY_SENSITIZATION"]["intent_conditioned_direction"],
        "composition_observation": "sensitizes + to temozolomide compositionally expresses increased temozolomide sensitivity",
        "genuine_required_semantic_content_missing": False,
        "primary_cause": "COMPOSITIONAL_RESPONSE_CONTAINMENT_FALSE_NEGATIVE",
        "repair_implemented": False,
    }
    direct = by_type["DIRECT_PERTURBATION"]
    direct_autopsy = {
        "intent_type": "DIRECT_PERTURBATION",
        "target_direction": frame["target_direction"],
        "target_endpoint_property": frame["role_surfaces"]["RESPONSE_PROPERTY"],
        "expected_allowed_directions": semantic_by_type["DIRECT_PERTURBATION"]["expected_allowed_directions"],
        "actual_direction": direct["direction"],
        "actual_endpoint_property_surface": direct["endpoint_property_surface"],
        "linked_relation_phrase": direct["linked_relation_phrase"],
        "endpoint_semantics_compatible": semantic_by_type["DIRECT_PERTURBATION"]["endpoint_semantics"],
        "literal_direction_enum_compatible": semantic_by_type["DIRECT_PERTURBATION"]["intent_conditioned_direction"],
        "composition_hypothesis": "INCREASE plus SENSITIVITY is sensitization-compatible only because the endpoint family is sensitivity",
        "arbitrary_increase_equated_with_sensitize": False,
        "genuine_required_semantic_content_missing": False,
        "primary_cause": "ENDPOINT_CONDITIONED_DIRECTION_COMPOSITION_FALSE_NEGATIVE",
        "repair_implemented": False,
    }
    rescue = by_type["RESCUE"]
    rescue_roles = roles_by_type["RESCUE"]["bound_role_state"]["BIOLOGICAL_UNIT_CONTEXT"]
    rescue_autopsy = {
        "intent_type": "RESCUE",
        "target_biological_unit_surfaces": frame["role_surfaces"]["BIOLOGICAL_UNIT_CONTEXT"],
        "proposal_biological_unit_surface": rescue["biological_unit_surface"],
        "linked_relation_phrase": rescue["linked_relation_phrase"],
        "rehydrated_role_state": rescue_roles,
        "frozen_search_anchor_compatible": False,
        "canonical_unit_lexically_present_with_safe_plural_and_state_modifier": True,
        "modifier_semantics": "PARP1-depleted is a perturbation-state qualifier; it does not replace glioblastoma-cell identity",
        "biological_unit_omitted_from_phrase": False,
        "binder_relation_internal_requirement_was_immediate_cause": False,
        "genuine_incompatible_biological_unit": False,
        "primary_cause": "COMPOSITE_BIOLOGICAL_UNIT_SURFACE_FALSE_NEGATIVE",
        "repair_implemented": False,
    }
    necessity = by_type["NECESSITY"]
    necessity_audit = {
        "intent_type": "NECESSITY",
        "linked_relation_phrase": necessity["linked_relation_phrase"],
        "expected_allowed_directions": semantic_by_type["NECESSITY"]["expected_allowed_directions"],
        "actual_direction": necessity["direction"],
        "direction_compatible": semantic_by_type["NECESSITY"]["intent_conditioned_direction"],
        "therapy_response_semantics_preserved": True,
        "therapy_is_relation_internal": True,
        "glioblastoma_context_present_at_final_query_level": "glioblastoma cells" in compiled[0]["query_string"],
        "canonical_identity_boundary_preserved": True,
        "topic_only_fallback": False,
        "structural_reaudit": "PASS",
        "retrieval_or_relevance_claim": False,
    }

    relation_core_audit = {
        "component_hypothesis": "RelationCoreV1",
        "needed": True, "implemented": False,
        "relation_core_required_roles": ["actor_or_intervention", "intervention_action",
            "relation_family", "direction_or_composed_orientation", "response_target",
            "scientifically_defining_endpoint_property"],
        "therapy_is_core_for_therapy_response": True,
        "conditioning_treatment_is_core_for_nested_response": True,
        "endpoint_localization_is_core_when_measured_property": True,
        "core_must_be_structurally_bound_before_context_externalization": True,
        "independent_keyword_intersection_is_not_relation_core": True,
        "case_108_core_observations": {
            "therapy_sensitization_core_semantically_expressed": True,
            "direct_core_semantically_expressed": True,
            "necessity_core_structurally_bound": True,
            "rescue_core_semantically_expressed": True,
        },
    }
    context_audit = {
        "component_hypothesis": "QueryContextConstraintV1",
        "needed": True, "implemented": False,
        "potentially_external_roles": ["biological_unit", "disease", "genotype", "species",
                                       "time_when_not_event_order", "localization_when_not_endpoint"],
        "precondition": "STRUCTURALLY_BOUND_RELATION_CORE",
        "deterministic_target_authority_required": True,
        "final_query_must_cover_all_required_contexts": True,
        "external_context_cannot_repair_underbound_core": True,
        "not_decided_from_case_108_only": True,
    }
    response_architecture = {
        "component_hypothesis": "CompositionalResponseSemanticsV1",
        "needed": True, "implemented": False,
        "inputs": ["therapy_role", "response_target", "endpoint_property", "direction", "relation_family"],
        "output": "expected_response_semantics_for_validation",
        "generic_supported_composition_hypothesis": {
            "therapy": "T", "endpoint_property": "sensitivity", "direction": "increase_or_sensitize",
            "expected_semantics": "increased sensitivity to T / sensitization to T"},
        "must_not_grant_therapy_identity": True,
        "must_not_use_fuzzy_equivalence": True,
        "case_108_evidence": therapy_autopsy,
    }
    direction_architecture = {
        "component_hypothesis": "DirectionCompositionV1",
        "needed": True, "implemented": False,
        "inputs": ["direction", "endpoint_property", "intent_type"],
        "generic_hypotheses_for_future_freeze": [
            {"direction": "INCREASE", "endpoint_family": "SENSITIVITY", "orientation": "SENSITIZE"},
            {"direction": "DECREASE", "endpoint_family": "SENSITIVITY", "orientation": "RESIST_OR_REDUCED_SENSITIVITY"},
            {"direction": "INCREASE", "endpoint_family": "RESISTANCE", "orientation": "RESIST"},
            {"direction": "DECREASE", "endpoint_family": "RESISTANCE", "orientation": "SENSITIZE"},
            {"direction": "INCREASE", "endpoint_family": "PHOSPHORYLATION", "orientation": "INCREASE"},
        ],
        "mapping_is_endpoint_conditioned_not_global_enum_equivalence": True,
        "case_108_evidence": direct_autopsy,
    }
    coverage_audit = {
        "current_relation_binding_conflates_phrase_and_final_query_coverage": True,
        "evidence": "required biological unit, disease, genotype, and therapy checks are applied inside each linked phrase before compiler context composition",
        "recommended_two_stage_boundary": ["validate_relation_core", "attach_and_validate_deterministic_query_context_constraints"],
        "final_query_coverage_requires_core_plus_required_contexts": True,
        "context_clause_cannot_convert_keyword_bag_to_bound_relation": True,
        "implemented": False,
    }
    smoke_classification = {
        "v3_architecture_smoke_success": True,
        "architecture_reason": "one valid V3 intent was deterministically bound and compiled without provider IDs or authority violations",
        "v3_core_intent_coverage_success": False,
        "core_coverage_reason": "the most direct therapy-sensitization and direct perturbation formulations were blocked by likely deterministic false negatives",
        "compiled_necessity_query_count": 1,
        "direct_or_therapy_sensitization_compiled_query_count": 0,
        "no_retrieval_claim": True,
    }
    recommendation = {
        "next_component_recommendation": "MULTIPLE_DETERMINISTIC_REFINEMENTS_NEEDED",
        "supported_future_components": ["CompositionalResponseSemanticsV1", "DirectionCompositionV1",
                                        "RelationCoreV1", "QueryContextConstraintV1",
                                        "composite role-surface anchor handling"],
        "planner_v3_refinement_supported": False,
        "why": "all three failed proposals contain the required scientific content; frozen deterministic gates reject compositional or scoped surfaces",
        "implementation_performed": False,
    }
    authorization = {
        "recommendation": "REFINE_FIRST",
        "systemic_deterministic_false_negative_risk": "HIGH",
        "reason": "composition and relation-core/context issues are generic and can affect therapy response, nested treatment, defining endpoints, and scoped biological units across development cases",
        "remaining_case_calls_authorized_by_this_audit": 0,
        "fresh_cases_seen": 0,
    }

    RUN.mkdir(parents=True, exist_ok=False)
    write_json(RUN / "upstream_root_verification.json", upstream)
    write_json(RUN / "smoke108_payload_preservation_audit.json", {
        "raw_v3_payload_sha256": payload_sha,
        "parsed_payload_sha256": sha256_value(payload),
        "prompt_v3_sha256": digest(ALPHA3 / "planner_prompt_v3.md"),
        "planner_payload_schema_sha256": digest(ALPHA3 / "planner_proposal_payload_v3_schema.json"),
        "protected_hashes_before": before,
        "payload_regenerated": False, "payload_mutated": False,
    })
    write_json(RUN / "smoke108_all_proposals.json", {
        "source_payload_sha256": payload_sha, "proposal_count": len(verbatim),
        "proposals_verbatim_structured_fields": verbatim,
    })
    write_json(RUN / "relation_core_v1_architecture_audit.json", relation_core_audit)
    write_json(RUN / "query_context_constraint_v1_architecture_audit.json", context_audit)
    write_json(RUN / "relation_internal_external_context_matrix.json", {
        "matrix": internal_external_matrix,
        "role_count": len(internal_external_matrix),
        "generic_role_semantics_not_case_specific": True,
    })
    write_json(RUN / "therapy_sensitization_failure_autopsy.json", therapy_autopsy)
    write_json(RUN / "compositional_response_semantics_architecture_audit.json", response_architecture)
    write_json(RUN / "direct_perturbation_direction_autopsy.json", direct_autopsy)
    write_json(RUN / "direction_composition_architecture_audit.json", direction_architecture)
    write_json(RUN / "rescue_biological_unit_autopsy.json", rescue_autopsy)
    write_json(RUN / "relation_phrase_vs_query_coverage_audit.json", coverage_audit)
    write_json(RUN / "topic_intersection_safety_audit.json", {
        "subject_endpoint_context_intersection_sufficient": False,
        "structurally_bound_relation_core_required": True,
        "context_externalization_allowed_only_after_bound_core": True,
        "topic_only_fallback_allowed": False,
    })
    write_json(RUN / "therapy_relation_safety_audit.json", {
        "therapy_response_intents": ["THERAPY_SENSITIZATION", "THERAPY_RESISTANCE"],
        "therapy_must_remain_relation_core_response_semantics": True,
        "therapy_as_unrelated_external_context_allowed": False,
        "therapy_identity_requires_deterministic_authority": True,
    })
    write_json(RUN / "nested_treatment_safety_audit.json", {
        "conditioning_treatment_must_remain_attached_to_nested_response": True,
        "generic_example": "IL-10 suppresses LPS-induced TNF secretion",
        "conditioning_as_unrelated_context_allowed": False,
        "case_specific_rule": False,
    })
    write_json(RUN / "endpoint_property_safety_audit.json", {
        "defining_endpoint_must_remain_relation_core": True,
        "endpoint_families": ["phosphorylation", "secretion", "nuclear accumulation",
                              "autophagic flux", "therapy sensitivity"],
        "response_entity_without_defining_property_is_underrepresented": True,
    })
    write_json(RUN / "necessity_success_reaudit.json", necessity_audit)
    write_json(RUN / "smoke_success_classification.json", smoke_classification)
    write_json(RUN / "next_component_recommendation.json", recommendation)
    write_json(RUN / "remaining7_authorization_recommendation.json", authorization)
    write_json(RUN / "heldout_specific_rule_audit.json", {
        "production_case_specific_rules": 0,
        "case_108_used_only_as_frozen_diagnostic_evidence": True,
        "generic_role_matrix_applies_without_case_identifier": True,
        "new_target_specific_exception_proposed": False,
    })
    after = protected_hashes()
    require(before == after, "protected artifacts changed during diagnostic phase")
    for _, (path, expected) in ROOTS.items():
        verify_root(path, expected)
    write_json(RUN / "scientific_state_safety_audit.json", {
        "protected_hashes_before": before, "protected_hashes_after": after,
        "historical_assets_modified": False,
        "production_implementation_changes": 0,
        "prompt_v3_changes": 0, "schema_changes": 0, "validator_changes": 0,
        "compiler_changes": 0, "fresh_cases_seen": 0,
        "provider_calls": 0, "llm_calls": 0, "network_calls": 0,
        "retrieval_calls": 0, "candidate_records_seen": 0,
    })
    summary = {
        "artifact_schema_version": "SearchPlanV24DevAlpha3_1Smoke108FailureAutopsySummaryV1",
        "status": "completed",
        "v3_architecture_smoke_success": True,
        "v3_core_intent_coverage_success": False,
        "therapy_sensitization_primary_cause": therapy_autopsy["primary_cause"],
        "direct_perturbation_primary_cause": direct_autopsy["primary_cause"],
        "rescue_primary_cause": rescue_autopsy["primary_cause"],
        "necessity_structural_reaudit": necessity_audit["structural_reaudit"],
        "relation_core_context_split_needed": True,
        "compositional_response_semantics_needed": True,
        "direction_composition_needed": True,
        "systemic_deterministic_false_negative_risk": "HIGH",
        "next_component_recommendation": recommendation["next_component_recommendation"],
        "remaining7_authorization_recommendation": authorization["recommendation"],
        "production_case_specific_rules": 0,
        "provider_calls": 0, "llm_calls": 0, "network_calls": 0,
        "retrieval_calls": 0, "historical_assets_modified": False,
    }
    write_json(RUN / "summary.json", summary)
    components = [[path.name, digest(path)] for path in sorted(RUN.iterdir())
                  if path.is_file() and path.name not in {"validation.json", ROOT_FILE}]
    root = sha256_value(components)
    write_json(RUN / "validation.json", {
        "artifact_schema_version": "SearchPlanV24DevAlpha3_1Smoke108FailureAutopsyValidationV1",
        "status": "PASS", "aggregate_components": components,
        ROOT_FILE: root, "all_required_outputs_present": True,
        "upstream_roots_verified": True, "offline_only": True,
        "diagnostic_only_no_rule_changes": True,
    })
    (RUN / ROOT_FILE).write_text(root + "\n", encoding="utf-8")
    require({path.name for path in RUN.iterdir()} == REQUIRED, "required output set mismatch")
    require(verify_root(RUN, root)["verified"], "alpha3.1 root failed self-verification")
    print(json.dumps({"root": root, "summary": summary}, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
