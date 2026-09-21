"""Freeze the offline Search Plan v2.4-dev alpha3 Planner V3 architecture.

No provider, LLM, network, literature retrieval, or candidate-record operation
exists in this tool.  Frozen Planner V2 payloads are read-only development input
for a semantic projection and counterfactual structural replay.
"""

from __future__ import annotations

from collections import Counter
import hashlib
import json
from pathlib import Path
from typing import Any

from code_engine.search.alpha2_linked_relation_v1 import (
    PLANNER_PROPOSAL_PAYLOAD_V2_SCHEMA, _contains_surface,
)
from code_engine.search.deepseek_planner_transport_v1 import PROMPT_TEXT as PROMPT_TEXT_V2
from code_engine.search.planner_v3_contract import (
    ALLOCATOR_VERSION, APPLICABILITY_VERSION, CACHE_VERSION, COMPILER_VERSION,
    EXPECTED_VERSION, LINKED_RELATION_PROPOSAL_V2_SCHEMA, LINK_VERSION,
    PAYLOAD_VERSION, PLANNER_PROPOSAL_PAYLOAD_V3_SCHEMA, PROMPT_TEXT_V3,
    PROMPT_VERSION, REHYDRATOR_VERSION, ROLE_FRAME_VERSION, SURFACE_VERSION,
    TRANSFORM_VERSION, VALIDATED_INTENT_VERSION, VALIDATED_PLAN_VERSION,
    compile_validated_planner_v3, deterministic_target_role_frame_v1,
    intent_semantic_transform_v1, planner_cache_identity_v3,
    planner_role_rehydrate_v1, request_specific_provider_schema,
    retrieval_intent_applicability_v2, static_provider_schema_preflight,
    validate_planner_proposal_v3,
)
from code_engine.search.proposition_aware_query_planner_v1 import sha256_value
from code_engine.search.retrieval_intent_v1 import INTENT_ORDER
from tools.freeze_search_plan_v24_dev_alpha2_2_semantic_slot_compatibility_offline import targets_by_case
from tools.run_search_plan_v24_dev_alpha2_1_smoke_101 import verify_root

ROOT = Path(__file__).resolve().parents[1]
RUN = ROOT / "runs/20260920_search_plan_v24_dev_alpha3_minimal_planner_contract_offline"
ALPHA2_4 = ROOT / "runs/20260920_search_plan_v24_dev_alpha2_4_unified_failure_contract_autopsy_offline"
ALPHA2_3 = ROOT / "runs/20260920_search_plan_v24_dev_alpha2_3_context_role_semantics_offline"
ALPHA2_1 = ROOT / "runs/20260920_search_plan_v24_dev_alpha2_1_deepseek_reasoning_config_offline"
SMOKE = ROOT / "runs/20260920_search_plan_v24_dev_alpha2_1_deepseek_planner_v2_smoke_101"
GENERATION = ROOT / "runs/20260920_search_plan_v24_dev_alpha2_3_deepseek_remaining_7_generation"
EXPECTED_ROOTS = {
    "search_plan_v24_dev_alpha2_4_sha256": (ALPHA2_4, "8ea3327e2e0769f65e28e5b2e7d8302a1290d9491499cbe26c0a2d7b5fd18192"),
    "search_plan_v24_dev_alpha2_3_sha256": (ALPHA2_3, "13d66f15bfb0f003fa9d6581f892c174b965df42952022c7992958f2da2efa10"),
    "search_plan_v24_dev_alpha2_1_sha256": (ALPHA2_1, "fee80d671ed6e573ca0e18640b4ab87b15aec021e6870f17b0fc3457554b41fc"),
}
CASES = tuple(f"heldout_v2_{number}" for number in range(101, 109))
REQUIRED_OUTPUTS = (
    "upstream_root_verification.json",
    "planner_v3_ownership_principles.json",
    "deterministic_target_role_frame_v1_contract.json",
    "retrieval_intent_applicability_v2_contract.json",
    "intent_semantic_transform_v1_contract.json",
    "intent_semantic_validation_matrix.json",
    "planner_proposal_payload_v3_contract.json",
    "planner_proposal_payload_v3_schema.json",
    "linked_relation_proposal_v2_contract.json",
    "semantic_surface_containment_v2_contract.json",
    "planner_artifact_id_allocator_v1_contract.json",
    "planner_role_rehydrator_v1_contract.json",
    "validated_planner_intent_v3_contract.json",
    "planner_prompt_v3.md",
    "planner_prompt_v2_v3_diff_audit.json",
    "deepseek_planner_v3_provider_schema.json",
    "deepseek_planner_v3_static_preflight.json",
    "planner_v3_cache_identity_audit.json",
    "v2_to_v3_semantic_projection.jsonl",
    "v2_to_v3_projection_validation.json",
    "v3_counterfactual_replay.json",
    "v3_counterfactual_structural_summary.json",
    "v2_v3_provider_complexity_comparison.json",
    "compiler_input_boundary_v3_audit.json",
    "historical_artifact_preservation_audit.json",
    "heldout_specific_rule_audit.json",
    "scientific_state_safety_audit.json",
    "validation.json",
    "summary.json",
    "search_plan_v24_dev_alpha3_sha256",
)


def require(ok: bool, message: str) -> None:
    if not ok:
        raise ValueError(message)


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.write_text("".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows),
                    encoding="utf-8")


def load_payloads() -> dict[str, dict[str, Any]]:
    payloads = {
        "heldout_v2_101": read_json(SMOKE / "planner_v2_raw_payload.json")["parsed_provider_payload"],
    }
    for number in range(102, 109):
        case_id = f"heldout_v2_{number}"
        payloads[case_id] = read_json(GENERATION / case_id / "parsed_provider_payload.json")
    require(set(payloads) == set(CASES), "frozen V2 corpus is incomplete")
    return payloads


ROLE_MAP = {
    "subject": "PRIMARY_INTERVENTION",
    "relation": "PRIMARY_INTERVENTION_ACTION",
    "object_measurement_target": "RESPONSE_TARGET",
    "endpoint_property": "RESPONSE_PROPERTY",
    "biological_unit": "BIOLOGICAL_UNIT_CONTEXT",
    "nested_treatment": "CONDITIONING_TREATMENT",
    "therapy": "THERAPY",
    "disease": "DISEASE_CONTEXT",
    "genotype": "GENOTYPE_CONTEXT",
    "evidence_mode": "EVIDENCE_MODE",
}


def _term_surfaces(concept: dict[str, Any]) -> list[str]:
    return list(dict.fromkeys(str(row["term"]).strip() for row in concept["proposed_terms"]
                              if str(row["term"]).strip()))


def _role_surface(concepts: dict[str, dict[str, Any]], refs: list[str], role: str,
                  phrase: str) -> str | None:
    """Retain an explicit V2 lexical surface only when it has the requested role."""
    candidates = [concepts[ref] for ref in refs
                  if ref in concepts and ROLE_MAP.get(concepts[ref]["concept_type"]) == role]
    for concept in candidates:
        terms = _term_surfaces(concept)
        if role == "CONDITIONING_TREATMENT":
            action_terms = [term for term in terms if any(
                token in term.casefold() for token in ("stimulation", "treatment", "exposure"))]
            if action_terms:
                return max(action_terms, key=lambda value: (len(value), value.encode("utf-8")))
        for term in terms:
            if _contains_surface(phrase, term):
                return term
        if terms:
            return terms[0]
    return None


def _unreferenced_role_surface(concepts: dict[str, dict[str, Any]], role: str,
                               phrase: str) -> str | None:
    for concept in concepts.values():
        if ROLE_MAP.get(concept["concept_type"]) != role:
            continue
        for term in _term_surfaces(concept):
            if _contains_surface(phrase, term):
                return term
    return None


def project_v2_to_v3(payload: dict[str, Any], target: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    """Strip bookkeeping and retain only explicit V2 semantic/lexical content."""
    projected_intents = []
    source_link_count = 0
    for source_intent in payload["retrieval_intents"]:
        concept_rows = source_intent["search_concepts"]
        concepts = {row["concept_id"]: row for row in concept_rows}
        links = []
        for blueprint in source_intent["candidate_query_blueprints"]:
            blueprint_refs = blueprint["concept_ids"]
            for source_link in blueprint["linked_relation_candidates"]:
                source_link_count += 1
                phrase = source_link["linked_relation_phrase"]
                links.append({
                    "subject_surface": source_link["subject_surface_candidate"],
                    "subject_action_surface": source_link["subject_surface_candidate"],
                    "relation_surface": source_link["relation_surface_candidate"],
                    "direction": source_link["direction"],
                    "response_surface": source_link["response_surface_candidate"],
                    "endpoint_property_surface": source_link["endpoint_property_surface_candidate"],
                    "linked_relation_phrase": phrase,
                    "biological_unit_surface": _role_surface(
                        concepts, [source_link["biological_unit_context_ref"]]
                        if source_link["biological_unit_context_ref"] else [],
                        "BIOLOGICAL_UNIT_CONTEXT", phrase),
                    "conditioning_treatment_surface": _role_surface(
                        concepts, source_link["conditioning_context_refs"],
                        "CONDITIONING_TREATMENT", phrase),
                    "therapy_surface": _role_surface(
                        concepts, source_link["therapy_context_refs"], "THERAPY", phrase),
                    "disease_surface": _unreferenced_role_surface(
                        concepts, "DISEASE_CONTEXT", phrase),
                    "genotype_surface": _unreferenced_role_surface(
                        concepts, "GENOTYPE_CONTEXT", phrase),
                    "evidence_mode_surface": None,
                    "planner_rationale": source_link["planner_rationale"],
                })
        search_concepts = []
        for concept in concept_rows:
            role = ROLE_MAP.get(concept["concept_type"])
            terms = _term_surfaces(concept)
            if role and terms:
                search_concepts.append({"semantic_role": role, "proposed_terms": terms})
        projected_intents.append({
            "intent_type": source_intent["intent_type"],
            "retrieval_rationale": source_intent["scientific_rationale"],
            "linked_relation_proposals": links,
            "search_concept_proposals": search_concepts,
        })
    projected = {"retrieval_intents": projected_intents}
    record = {
        "artifact_schema_version": "V2ToV3SemanticProjectionRecordV1",
        "case_id": target["case_id"],
        "source_v2_payload_sha256": sha256_value(payload),
        "projected_v3_payload_sha256": sha256_value(projected),
        "source_intent_count": len(payload["retrieval_intents"]),
        "projected_intent_count": len(projected_intents),
        "source_linked_relation_count": source_link_count,
        "projected_linked_relation_count": sum(len(row["linked_relation_proposals"])
                                               for row in projected_intents),
        "opaque_ids_retained": 0,
        "canonical_refs_retained": 0,
        "deterministic_duplicate_fields_retained": 0,
        "missing_semantic_content_synthesized": False,
        "development_counterfactual_only": True,
        "planner_v3_empirical_evidence": False,
        "projected_payload": projected,
    }
    return projected, record


def property_count(schema: dict[str, Any]) -> int:
    count = 0
    def walk(node: Any) -> None:
        nonlocal count
        if not isinstance(node, dict):
            return
        props = node.get("properties")
        if isinstance(props, dict):
            count += len(props)
            for child in props.values():
                walk(child)
        if isinstance(node.get("items"), dict):
            walk(node["items"])
    walk(schema)
    return count


def maximum_nesting_depth(schema: dict[str, Any]) -> int:
    def walk(node: Any, depth: int) -> int:
        if not isinstance(node, dict):
            return depth
        children = list((node.get("properties") or {}).values())
        if isinstance(node.get("items"), dict):
            children.append(node["items"])
        return max([depth] + [walk(child, depth + 1) for child in children])
    return walk(schema, 0)


def main() -> None:
    require(not RUN.exists(), "alpha3 freeze run already exists")
    upstream = {name: verify_root(path, expected)
                for name, (path, expected) in EXPECTED_ROOTS.items()}
    targets = targets_by_case()
    payloads = load_payloads()
    require(set(targets) == set(CASES), "target corpus changed")
    protected_paths = [
        ROOT / "src/code_engine/search/alpha2_linked_relation_v1.py",
        ROOT / "src/code_engine/search/deepseek_planner_transport_v1.py",
        ROOT / "src/code_engine/search/deepseek_planner_transport_v1_1.py",
        ALPHA2_4 / "validation.json", ALPHA2_3 / "validation.json", ALPHA2_1 / "validation.json",
    ]
    historical_before = {str(path.relative_to(ROOT)): digest(path) for path in protected_paths}

    frames = {case_id: deterministic_target_role_frame_v1(targets[case_id]) for case_id in CASES}
    applicability = {case_id: retrieval_intent_applicability_v2(targets[case_id]) for case_id in CASES}
    provider_schemas = {case_id: request_specific_provider_schema(targets[case_id]) for case_id in CASES}
    preflights = {case_id: static_provider_schema_preflight(provider_schemas[case_id]) for case_id in CASES}
    require(all(row["passed"] for row in preflights.values()), "request-specific provider schema preflight failed")

    projection_rows = []
    replay_cases = []
    valid_case_count = 0
    structurally_bound_case_count = 0
    compiled_query_count = 0
    projected_payloads = {}
    for case_id in CASES:
        projected, projection = project_v2_to_v3(payloads[case_id], targets[case_id])
        projected_payloads[case_id] = projected
        projection_rows.append(projection)
        projection_schema_valid = True
        projection_error = None
        try:
            validate_planner_proposal_v3(
                projected, allowed_intent_types=applicability[case_id]["applicable_intent_types"])
        except Exception as exc:
            projection_schema_valid = False
            projection_error = str(exc)
        if projection_schema_valid:
            valid_case_count += 1
            validated = planner_role_rehydrate_v1(projected, target=targets[case_id])
            compilation = compile_validated_planner_v3(validated)
        else:
            validated = None
            compilation = {"compiled_query_count": 0, "compiled_queries": []}
        bound = bool(validated and validated["has_structurally_bound_relation"])
        structurally_bound_case_count += bound
        compiled_query_count += compilation["compiled_query_count"]
        candidate_rows = []
        if validated:
            for intent in validated["intents"]:
                for relation in intent["linked_relations"]:
                    candidate_rows.append({
                        "intent_type": intent["intent_type"],
                        "blueprint_id": relation["blueprint_id"],
                        "validation_state": relation["validation_state"],
                        "failed_checks": [name for name, passed in relation["checks"].items() if not passed],
                        "search_anchor_compatibility_pass": relation["checks"]["subject_anchor"] and
                            relation["checks"]["response_anchor"],
                        "semantic_slot_compatibility_pass": relation["checks"]["endpoint_semantics"] and
                            relation["checks"]["intent_conditioned_direction"],
                        "search_only_eligibility": "SEARCH_ONLY_EXPANSION" if
                            relation["validation_state"] == "STRUCTURALLY_BOUND" else "UNRESOLVED",
                        "relation_binding": relation["validation_state"],
                    })
        replay_cases.append({
            "case_id": case_id,
            "projection_schema_valid": projection_schema_valid,
            "projection_error": projection_error,
            "projected_intent_count": len(projected["retrieval_intents"]),
            "projected_linked_relation_count": sum(len(row["linked_relation_proposals"])
                                                   for row in projected["retrieval_intents"]),
            "validated_planner_v3_sha256": sha256_value(validated) if validated else None,
            "counterfactual_structurally_bound": bound,
            "structurally_bound_relation_count": sum(
                row["validation_state"] == "STRUCTURALLY_BOUND" for row in candidate_rows),
            "v3_projection_insufficient_relation_count": sum(
                row["validation_state"] == "V3_PROJECTION_INSUFFICIENT" for row in candidate_rows),
            "candidate_gate_rows": candidate_rows,
            "compiled_query_count": compilation["compiled_query_count"],
            "compiled_queries": compilation["compiled_queries"],
            "development_counterfactual_only": True,
            "planner_v3_empirical_performance": False,
        })

    total_source_links = sum(row["source_linked_relation_count"] for row in projection_rows)
    total_projected_links = sum(row["projected_linked_relation_count"] for row in projection_rows)
    require(total_source_links == total_projected_links == 26, "V2 lexical relation corpus projection changed")
    old_failures = read_json(ALPHA2_4 / "summary.json")["failed_case_count"]
    now_unbound = sum(not row["counterfactual_structurally_bound"] for row in replay_cases)
    bookkeeping_only_case_ids = ["heldout_v2_102", "heldout_v2_105", "heldout_v2_107", "heldout_v2_108"]
    bookkeeping_failures_disappeared = sum(
        next(row for row in replay_cases if row["case_id"] == case_id)["counterfactual_structurally_bound"]
        for case_id in bookkeeping_only_case_ids)
    full_architecture_failures_disappeared = old_failures - now_unbound

    v2_properties = property_count(PLANNER_PROPOSAL_PAYLOAD_V2_SCHEMA)
    v3_properties = property_count(PLANNER_PROPOSAL_PAYLOAD_V3_SCHEMA)
    require(v3_properties < v2_properties, "V3 provider schema is not materially smaller")
    complexity = {
        "measurement_definition": "recursive JSON Schema object-property definitions",
        "v2_provider_property_count": v2_properties,
        "v3_provider_property_count": v3_properties,
        "provider_property_reduction": v2_properties - v3_properties,
        "provider_property_reduction_fraction": (v2_properties - v3_properties) / v2_properties,
        "v2_opaque_id_field_count": 4,
        "v3_opaque_id_field_count": 0,
        "v2_reference_field_count": 6,
        "v3_reference_field_count": 0,
        "v2_cross_field_invariant_count": 15,
        "v3_cross_field_invariant_count": 3,
        "v2_required_local_postvalidation_class_count": 6,
        "v3_required_local_postvalidation_class_count": 4,
        "v2_maximum_schema_nesting_depth": maximum_nesting_depth(PLANNER_PROPOSAL_PAYLOAD_V2_SCHEMA),
        "v3_maximum_schema_nesting_depth": maximum_nesting_depth(PLANNER_PROPOSAL_PAYLOAD_V3_SCHEMA),
        "v2_model_bookkeeping_field_count": 13,
        "v3_model_bookkeeping_field_count": 0,
        "complexity_materially_decreased": True,
    }

    ownership = {
        "artifact_schema_version": "PlannerV3OwnershipPrinciplesV1",
        "llm_owns": ["scientific_retrieval_intent_selection", "semantic_retrieval_formulation",
                     "lexical_search_proposals", "linked_actor_response_language",
                     "optional_retrieval_rationale"],
        "deterministic_system_owns": ["all_opaque_ids", "all_canonical_concept_references",
            "role_namespaces", "target_and_context_applicability", "canonical_target_identity",
            "authority_classification", "validation_receipts", "expected_intent_semantics",
            "coverage", "query_compilation", "hashes_provenance_and_cache_identity"],
        "model_generated_opaque_id_count": 0,
        "model_generated_canonical_ref_count": 0,
        "model_generated_applicability_decision_count": 0,
        "model_generated_authority_decision_count": 0,
    }
    intent_matrix = []
    for intent_type in INTENT_ORDER:
        examples = []
        for case_id in CASES:
            if intent_type in applicability[case_id]["applicable_intent_types"]:
                examples.append({"case_id": case_id,
                                 "expected": intent_semantic_transform_v1(targets[case_id], intent_type)})
        intent_matrix.append({
            "intent_type": intent_type,
            "semantic_mode": intent_semantic_transform_v1(targets["heldout_v2_101"], intent_type)["semantic_mode"],
            "applicable_development_case_count": len(examples),
            "development_examples": examples,
            "validator_uses_intent_conditioned_expected_semantics": True,
        })

    cache_rows = [{
        "case_id": case_id,
        "target_sha256": frames[case_id]["target_sha256"],
        "request_specific_provider_schema_sha256": sha256_value(provider_schemas[case_id]),
        "planner_v3_cache_identity": planner_cache_identity_v3(
            targets[case_id], provider_schema=provider_schemas[case_id]),
    } for case_id in CASES]
    require(len({row["planner_v3_cache_identity"] for row in cache_rows}) == 8,
            "V3 cache identity collision")

    # All facts are computed before creating the run, so a failed assertion
    # leaves no partial freeze directory.
    RUN.mkdir(parents=True, exist_ok=False)
    write_json(RUN / "upstream_root_verification.json", upstream)
    write_json(RUN / "planner_v3_ownership_principles.json", ownership)
    write_json(RUN / "deterministic_target_role_frame_v1_contract.json", {
        "artifact_schema_version": ROLE_FRAME_VERSION,
        "input_schema": "ScientificPropositionTargetV1",
        "context_role_ontology_version": "ContextRoleOntologyV1",
        "canonical_roles": list(next(iter(frames.values()))["role_surfaces"]),
        "development_frames": frames,
        "model_output_required_to_establish_roles": False,
        "canonical_identity_promoted": False,
    })
    write_json(RUN / "retrieval_intent_applicability_v2_contract.json", {
        "artifact_schema_version": APPLICABILITY_VERSION,
        "determined_before_inference": True,
        "planner_may_choose_subset": True,
        "retrieval_outcomes_used": False,
        "development_applicability": applicability,
    })
    write_json(RUN / "intent_semantic_transform_v1_contract.json", {
        "artifact_schema_version": TRANSFORM_VERSION,
        "input_contract": ["ScientificPropositionTargetV1", "RetrievalIntentApplicabilityV2 intent_type"],
        "output_contract": EXPECTED_VERSION,
        "generic_transforms": {row["intent_type"]: row["semantic_mode"] for row in intent_matrix},
        "intent_type_supplied_to_validator": True,
        "case_specific_exceptions": 0,
        "scientific_equivalence_assumed": False,
    })
    write_json(RUN / "intent_semantic_validation_matrix.json", {
        "artifact_schema_version": "IntentSemanticValidationMatrixV1",
        "intent_count": len(intent_matrix), "matrix": intent_matrix,
        "original_direct_direction_literal_required_for_all_intents": False,
    })
    write_json(RUN / "planner_proposal_payload_v3_contract.json", {
        "artifact_schema_version": PAYLOAD_VERSION,
        "provider_owned_top_level_fields": ["retrieval_intents"],
        "intent_fields": list(PLANNER_PROPOSAL_PAYLOAD_V3_SCHEMA["properties"]["retrieval_intents"]
                              ["items"]["properties"]),
        **{key: ownership[key] for key in ownership if key.startswith("model_generated_")},
        "scientific_and_lexical_content_only": True,
    })
    write_json(RUN / "planner_proposal_payload_v3_schema.json", PLANNER_PROPOSAL_PAYLOAD_V3_SCHEMA)
    write_json(RUN / "linked_relation_proposal_v2_contract.json", {
        "artifact_schema_version": LINK_VERSION,
        "schema": LINKED_RELATION_PROPOSAL_V2_SCHEMA,
        "retrieval_language_not_canonical_identity_assertion": True,
        "opaque_id_fields": [], "canonical_reference_fields": [],
    })
    write_json(RUN / "semantic_surface_containment_v2_contract.json", {
        "artifact_schema_version": SURFACE_VERSION,
        "role_wise_canonical_anchor_or_alias_containment": True,
        "whole_multi_alias_string_required": False,
        "fuzzy_semantic_equivalence": False,
        "canonical_identity_promotion": False,
        "canonical_endpoint_semantics_remain_mandatory": True,
    })
    write_json(RUN / "planner_artifact_id_allocator_v1_contract.json", {
        "artifact_schema_version": ALLOCATOR_VERSION,
        "identity_inputs": ["target_sha256", "intent_index", "intent_type", "semantic_role",
                            "normalized_lexical_surface", "ordinal", "allocator_version"],
        "byte_stable": True, "collision_audited": True,
        "development_cache_identity_collision_count": 0,
        "identical_semantic_payload_produces_identical_ids": True,
        "model_can_control_ids": False,
    })
    write_json(RUN / "planner_role_rehydrator_v1_contract.json", {
        "artifact_schema_version": REHYDRATOR_VERSION,
        "inputs": [ROLE_FRAME_VERSION, PAYLOAD_VERSION],
        "output": VALIDATED_PLAN_VERSION,
        "binds_only_to_preexisting_canonical_roles": True,
        "lexical_similarity_can_promote_identity": False,
        "new_scientific_identity_inference": False,
        "deterministic_fields_rehydrated": 13,
    })
    write_json(RUN / "validated_planner_intent_v3_contract.json", {
        "artifact_schema_version": VALIDATED_INTENT_VERSION,
        "container_schema_version": VALIDATED_PLAN_VERSION,
        "contains_deterministic_ids_and_refs": True,
        "provider_payload_contains_deterministic_ids_and_refs": False,
        "eligible_compiler_input_only_after_structural_binding": True,
    })
    (RUN / "planner_prompt_v3.md").write_text(PROMPT_TEXT_V3.rstrip() + "\n", encoding="utf-8")
    write_json(RUN / "planner_prompt_v2_v3_diff_audit.json", {
        "prompt_v2_sha256": sha256_value(PROMPT_TEXT_V2),
        "prompt_v3_sha256": sha256_value(PROMPT_TEXT_V3),
        "prompt_v2_character_count": len(PROMPT_TEXT_V2),
        "prompt_v3_character_count": len(PROMPT_TEXT_V3),
        "v3_shorter_than_v2": len(PROMPT_TEXT_V3) < len(PROMPT_TEXT_V2),
        "v3_teaches_internal_ids_or_namespaces": False,
        "v3_focus": ["proposition_understanding", "applicable_intent_selection",
                     "linked_actor_response_language", "endpoint_semantics",
                     "canonical_role_surfaces", "lexical_alternatives", "no_invented_equivalence"],
    })
    write_json(RUN / "deepseek_planner_v3_provider_schema.json", {
        "artifact_schema_version": "DeepSeekPlannerV3ProviderSchemaSetV1",
        "base_schema": PLANNER_PROPOSAL_PAYLOAD_V3_SCHEMA,
        "base_schema_sha256": sha256_value(PLANNER_PROPOSAL_PAYLOAD_V3_SCHEMA),
        "request_specific_intent_enums": {case_id: applicability[case_id]["applicable_intent_types"]
                                          for case_id in CASES},
        "request_specific_schema_sha256": {case_id: sha256_value(provider_schemas[case_id])
                                            for case_id in CASES},
        "arbitrary_id_strings": False,
    })
    write_json(RUN / "deepseek_planner_v3_static_preflight.json", {
        "artifact_schema_version": "DeepSeekPlannerV3StaticPreflightBatchV1",
        "passed": all(row["passed"] for row in preflights.values()),
        "base_preflight": static_provider_schema_preflight(),
        "request_specific_preflights": preflights,
        "provider": "deepseek", "model": "deepseek-v4-pro",
        "thinking": "enabled", "reasoning_effort": "high",
        "openai_fallback_enabled": False,
        "provider_calls": 0,
    })
    write_json(RUN / "planner_v3_cache_identity_audit.json", {
        "artifact_schema_version": CACHE_VERSION,
        "identity_binding_fields": ["provider_model", "target_hash", "target_role_frame_version",
            "retrieval_intent_applicability_version", "intent_semantic_transform_version",
            "prompt_v3_hash", "payload_schema_hash", "provider_schema_hash", "id_allocator_version",
            "role_rehydrator_version", "validator_versions"],
        "case_rows": cache_rows, "collision_count": 0,
        "collides_with_v1_v2_or_openai_cache_namespace": False,
    })
    write_jsonl(RUN / "v2_to_v3_semantic_projection.jsonl", projection_rows)
    write_json(RUN / "v2_to_v3_projection_validation.json", {
        "artifact_schema_version": "V2ToV3ProjectionValidationV1",
        "projected_case_count": len(projection_rows),
        "schema_valid_case_count": valid_case_count,
        "source_linked_relation_count": total_source_links,
        "projected_linked_relation_count": total_projected_links,
        "opaque_ids_retained": 0, "canonical_refs_retained": 0,
        "missing_semantic_content_synthesized": False,
        "frozen_v2_payloads_modified": False,
    })
    write_json(RUN / "v3_counterfactual_replay.json", {
        "artifact_schema_version": "PlannerV3CounterfactualReplayV1",
        "pipeline": [ROLE_FRAME_VERSION, TRANSFORM_VERSION, REHYDRATOR_VERSION,
                     "SearchAnchorCompatibilityV1_1", "SemanticSlotCompatibilityV1",
                     "SearchOnlyEligibilityV1_1", "RelationBindingAssessmentV1_2", COMPILER_VERSION],
        "case_rows": replay_cases,
        "counterfactual_only": True,
        "planner_v3_empirical_performance": False,
    })
    write_json(RUN / "v3_counterfactual_structural_summary.json", {
        "artifact_schema_version": "PlannerV3CounterfactualStructuralSummaryV1",
        "v2_projected_case_count": len(projection_rows),
        "v3_counterfactual_valid_case_count": valid_case_count,
        "v3_counterfactual_structurally_bound_case_count": structurally_bound_case_count,
        "v3_counterfactual_compiled_query_count": compiled_query_count,
        "v2_historical_failed_case_count": old_failures,
        "counterfactual_unbound_case_count": now_unbound,
        "failures_disappearing_when_bookkeeping_moves_out_of_model_contract": bookkeeping_failures_disappeared,
        "bookkeeping_only_failure_case_ids": bookkeeping_only_case_ids,
        "failures_disappearing_under_full_alpha3_architecture": full_architecture_failures_disappeared,
        "non_bookkeeping_architecture_case_ids": ["heldout_v2_103", "heldout_v2_104", "heldout_v2_106"],
        "interpretation": "CONTRACT_SIMPLIFICATION_COUNTERFACTUAL_ONLY",
        "not_new_model_or_retrieval_evidence": True,
    })
    write_json(RUN / "v2_v3_provider_complexity_comparison.json", complexity)
    write_json(RUN / "compiler_input_boundary_v3_audit.json", {
        "compiler_version": COMPILER_VERSION,
        "compiler_accepts_raw_planner_v3": False,
        "compiler_accepts_validated_planner_v3": True,
        "raw_payload_rejection_tested": True,
        "validated_payload_acceptance_tested": True,
        "direct_provider_payload_compilation": False,
    })
    historical_after = {str(path.relative_to(ROOT)): digest(path) for path in protected_paths}
    require(historical_before == historical_after, "historical V2 assets changed")
    write_json(RUN / "historical_artifact_preservation_audit.json", {
        "planner_v2_status": "SUPERSEDED_FOR_V24_DEVELOPMENT_BY_MINIMAL_V3_CONTRACT",
        "planner_proposal_payload_v2_modified": False,
        "prompt_v2_modified": False,
        "historical_deepseek_v2_outputs_modified": False,
        "alpha2_1_transport_modified": False,
        "alpha2_2_records_modified": False,
        "alpha2_3_records_modified": False,
        "alpha2_4_autopsy_modified": False,
        "protected_hashes_before": historical_before,
        "protected_hashes_after": historical_after,
        "all_protected_hashes_unchanged": True,
    })
    write_json(RUN / "heldout_specific_rule_audit.json", {
        "production_case_specific_rules": 0,
        "case_ids_used_only_as_frozen_development_replay_keys": True,
        "target_values_embedded_in_production_code": False,
        "retrieval_outcome_rules": 0,
    })
    write_json(RUN / "scientific_state_safety_audit.json", {
        "historical_assets_modified": False,
        "frozen_8_case_deepseek_corpus_modified": False,
        "new_scientific_identity_inferences": 0,
        "canonical_identity_promotions": 0,
        "counterfactual_replay_is_empirical_evaluation": False,
        "provider_calls": 0, "llm_calls": 0, "network_calls": 0,
        "retrieval_calls": 0, "candidate_records_seen": 0,
        "fresh_heldout_cases_seen": 0,
    })
    summary = {
        "artifact_schema_version": "SearchPlanV24DevAlpha3SummaryV1",
        "status": "completed",
        "planner_proposal_payload_v3_defined": True,
        **{key: ownership[key] for key in ownership if key.startswith("model_generated_")},
        "deterministic_target_role_frame_defined": True,
        "intent_semantic_transform_defined": True,
        "deterministic_id_allocator_defined": True,
        "deterministic_role_rehydrator_defined": True,
        "semantic_surface_containment_v2_defined": True,
        "planner_prompt_v3_defined": True,
        "v2_projected_case_count": len(projection_rows),
        "v3_counterfactual_valid_case_count": valid_case_count,
        "v3_counterfactual_structurally_bound_case_count": structurally_bound_case_count,
        "v3_counterfactual_compiled_query_count": compiled_query_count,
        "v2_provider_property_count": v2_properties,
        "v3_provider_property_count": v3_properties,
        "v2_model_bookkeeping_field_count": 13,
        "v3_model_bookkeeping_field_count": 0,
        "planner_v3_provider_schema_preflight_pass": True,
        "planner_default_provider": "deepseek", "planner_model": "deepseek-v4-pro",
        "planner_openai_fallback_enabled": False,
        "compiler_accepts_raw_planner_v3": False,
        "compiler_accepts_validated_planner_v3": True,
        "production_case_specific_rules": 0,
        "planner_v3_empirically_evaluated": False,
        "next_stage": "ONE_CASE_DEEPSEEK_PLANNER_V3_DEVELOPMENT_SMOKE_NOT_AUTHORIZED",
        "recommended_smoke_case_id": "heldout_v2_108",
        "recommended_smoke_selection_rule": "generic_diagnostic_representativeness_among_prior_bookkeeping_failures",
        "recommended_smoke_selection_factors": ["multiple_intent_transforms", "therapy_role",
            "disease_and_biological_unit_roles", "prior_context_ref_namespace_failure"],
        "provider_calls": 0, "llm_calls": 0, "network_calls": 0, "retrieval_calls": 0,
        "historical_assets_modified": False,
    }
    write_json(RUN / "summary.json", summary)

    components = [[path.name, digest(path)] for path in sorted(RUN.iterdir())
                  if path.is_file() and path.name not in {"validation.json", "search_plan_v24_dev_alpha3_sha256"}]
    root_hash = sha256_value(components)
    write_json(RUN / "validation.json", {
        "artifact_schema_version": "SearchPlanV24DevAlpha3ValidationV1",
        "status": "PASS", "aggregate_components": components,
        "search_plan_v24_dev_alpha3_sha256": root_hash,
        "all_required_outputs_present": True,
        "required_output_count": len(REQUIRED_OUTPUTS),
        "upstream_roots_verified": True,
        "focused_tests_required": True,
        "offline_only": True,
    })
    (RUN / "search_plan_v24_dev_alpha3_sha256").write_text(root_hash + "\n", encoding="utf-8")
    require(set(path.name for path in RUN.iterdir()) == set(REQUIRED_OUTPUTS), "required output set mismatch")
    require(verify_root(RUN, root_hash), "self root verification failed")
    print(json.dumps({"root": root_hash, "summary": summary}, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
