"""Complete the alpha3 case-108 smoke protocol from its frozen one-call output.

The provider call run is immutable input.  This tool performs only deterministic
offline projection, audit, and compilation through the already-frozen alpha3
stack.  It makes no provider, network, retrieval, or literature calls.
"""

from __future__ import annotations

from collections import Counter
import hashlib
import json
from pathlib import Path
from typing import Any

from code_engine.search.alpha2_linked_relation_v1 import (
    SUFFICIENT_ANCHORS, search_anchor_compatibility,
)
from code_engine.search.planner_v3_contract import (
    ALLOCATOR_VERSION, APPLICABILITY_VERSION, CACHE_VERSION, COMPILER_VERSION,
    EXPECTED_VERSION, LINK_VERSION, PAYLOAD_VERSION, PROMPT_VERSION,
    REHYDRATOR_VERSION, ROLE_FRAME_VERSION, SURFACE_VERSION, TRANSFORM_VERSION,
    VALIDATED_INTENT_VERSION, VALIDATED_PLAN_VERSION,
    PLANNER_PROPOSAL_PAYLOAD_V3_SCHEMA, PROMPT_TEXT_V3,
    compile_validated_planner_v3, deterministic_target_role_frame_v1,
    intent_semantic_transform_v1, planner_cache_identity_v3,
    planner_role_rehydrate_v1, request_specific_provider_schema,
    retrieval_intent_applicability_v2, semantic_surface_containment_v2,
    static_provider_schema_preflight, validate_planner_proposal_v3,
)
from code_engine.search.proposition_aware_query_planner_v1 import sha256_value
from tools.freeze_search_plan_v24_dev_alpha2_2_semantic_slot_compatibility_offline import targets_by_case
from tools.run_search_plan_v24_dev_alpha2_1_smoke_101 import verify_root

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "runs/20260922_search_plan_v24_dev_alpha3_deepseek_planner_v3_smoke_108"
RUN = ROOT / "runs/20260922_search_plan_v24_dev_alpha3_deepseek_planner_v3_smoke_108_protocol_completion_offline"
ALPHA3 = ROOT / "runs/20260920_search_plan_v24_dev_alpha3_minimal_planner_contract_offline"
ALPHA3_ROOT = "96990556e92d197345416a000b4cba88e250afa4456499f498ec89891a95c61f"
SOURCE_ROOT = "519de1d347c105c9b1cf7c64723674ac8b9478edf750f213b2865ec2a4706075"
CASE_ID = "heldout_v2_108"
ROOT_FILE = "search_plan_v24_dev_alpha3_deepseek_smoke_108_sha256"


def require(ok: bool, message: str) -> None:
    if not ok:
        raise ValueError(message)


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.write_text("".join(json.dumps(row, ensure_ascii=False, sort_keys=True,
                                       separators=(",", ":")) + "\n" for row in rows), encoding="utf-8")


def source_snapshot() -> dict[str, str]:
    return {path.name: digest(path) for path in sorted(SOURCE.iterdir()) if path.is_file()}


def flatten_terms(payload: dict[str, Any], frame: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    semantic_roles = {"PRIMARY_INTERVENTION_ACTION", "RESPONSE_PROPERTY", "EVIDENCE_MODE"}
    for intent_index, intent in enumerate(payload["retrieval_intents"]):
        for concept_index, concept in enumerate(intent["search_concept_proposals"]):
            role = concept["semantic_role"]
            anchors = frame["role_surfaces"].get(role, [])
            for term_index, term in enumerate(concept["proposed_terms"]):
                state = search_anchor_compatibility(term, anchors) if anchors else "NOT_IDENTITY_ROLE"
                if state in SUFFICIENT_ANCHORS:
                    classification = "CANONICAL_TARGET_SURFACE"
                    authority = f"DeterministicTargetRoleFrameV1#{role}"
                elif role in semantic_roles:
                    classification = "SEMANTIC_LEXICAL_PROPOSAL_NON_AUTHORITY"
                    authority = None
                else:
                    classification = "UNRESOLVED"
                    authority = None
                material = {
                    "case_id": CASE_ID, "intent_type": intent["intent_type"],
                    "intent_index": intent_index, "concept_index": concept_index,
                    "term_index": term_index, "semantic_role": role, "term": term,
                    "deterministic_classification": classification,
                    "anchor_compatibility": state, "authority_reference": authority,
                    "model_self_authorized": False, "canonical_identity_promoted": False,
                }
                rows.append({**material, "receipt_sha256": sha256_value(material)})
    return rows


def main() -> None:
    require(not RUN.exists(), "protocol-completion run already exists")
    alpha3 = verify_root(ALPHA3, ALPHA3_ROOT)
    source = verify_root(SOURCE, SOURCE_ROOT)
    before = source_snapshot()
    source_summary = json.loads((SOURCE / "summary.json").read_text(encoding="utf-8"))
    require(source_summary["provider_requests_attempted"] == 1
            and source_summary["inference_attempts"] == 1
            and source_summary["retry_count"] == 0
            and source_summary["repair_calls"] == 0
            and source_summary["openai_calls"] == 0,
            "frozen source call budget differs")

    target = targets_by_case()[CASE_ID]
    frame = deterministic_target_role_frame_v1(target)
    applicability = retrieval_intent_applicability_v2(target)
    provider_schema = request_specific_provider_schema(target)
    provider_preflight = static_provider_schema_preflight(provider_schema)
    require(provider_preflight["passed"], "frozen provider schema no longer preflights")
    request_preflight = json.loads((SOURCE / "frozen_request_preflight.json").read_text(encoding="utf-8"))
    require(request_preflight["provider_schema_sha256"] == sha256_value(provider_schema),
            "provider schema differs from executed request")
    require(request_preflight["target_sha256"] == frame["target_sha256"],
            "target differs from executed request")
    require(request_preflight["prompt_sha256"] == sha256_value(PROMPT_TEXT_V3),
            "prompt differs from executed request")
    require(request_preflight["proposal_schema_sha256"] == sha256_value(
        PLANNER_PROPOSAL_PAYLOAD_V3_SCHEMA), "payload schema differs from executed request")

    raw_text = (SOURCE / "raw_model_content.txt").read_text(encoding="utf-8")
    payload = json.loads((SOURCE / "parsed_provider_payload.json").read_text(encoding="utf-8"))
    require(json.loads(raw_text) == payload, "raw content and parsed payload differ")
    validate_planner_proposal_v3(payload, allowed_intent_types=applicability["applicable_intent_types"])
    validated = planner_role_rehydrate_v1(payload, target=target)
    require(validated == json.loads((SOURCE / "validated_planner_v3.json").read_text(encoding="utf-8")),
            "deterministic rehydration replay differs from frozen call run")
    replayed = planner_role_rehydrate_v1(payload, target=target)
    require(replayed == validated, "ID allocation or role rehydration is not replay-stable")
    compilation = compile_validated_planner_v3(validated)
    require(compilation["compiled_query_count"] == 1, "protocol success-path compiler count changed")

    selected = [intent["intent_type"] for intent in payload["retrieval_intents"]]
    require(len(selected) == len(set(selected)) == 4, "selected intent set changed")
    validated_by_type = {intent["intent_type"]: intent for intent in validated["intents"]}
    relation_rows: list[dict[str, Any]] = []
    role_rows: list[dict[str, Any]] = []
    intent_rows: list[dict[str, Any]] = []
    anchor_rows: list[dict[str, Any]] = []
    semantic_rows: list[dict[str, Any]] = []
    containment_rows: list[dict[str, Any]] = []
    binding_rows: list[dict[str, Any]] = []
    all_ids: list[str] = []
    for raw_intent, validated_intent in zip(payload["retrieval_intents"], validated["intents"], strict=True):
        expected = intent_semantic_transform_v1(target, raw_intent["intent_type"])
        all_ids.append(validated_intent["intent_id"])
        actual_semantics = []
        for proposal, relation in zip(raw_intent["linked_relation_proposals"],
                                      validated_intent["linked_relations"], strict=True):
            all_ids.append(relation["blueprint_id"])
            all_ids.extend(relation["deterministic_canonical_role_refs"].values())
            actual = {
                "subject_surface": proposal["subject_surface"],
                "subject_action_surface": proposal["subject_action_surface"],
                "relation_surface": proposal["relation_surface"],
                "direction": proposal["direction"],
                "response_surface": proposal["response_surface"],
                "endpoint_property_surface": proposal["endpoint_property_surface"],
                "therapy_surface": proposal["therapy_surface"],
                "biological_unit_surface": proposal["biological_unit_surface"],
                "linked_relation_phrase": proposal["linked_relation_phrase"],
                "planner_rationale": proposal["planner_rationale"],
            }
            actual_semantics.append(actual)
            relation_rows.append({
                "intent_type": raw_intent["intent_type"], **actual,
                "validation_state": relation["validation_state"],
            })
            role_rows.append({
                "intent_type": raw_intent["intent_type"],
                "blueprint_id": relation["blueprint_id"],
                "deterministic_canonical_role_refs": relation["deterministic_canonical_role_refs"],
                "bound_role_state": relation["bound_role_state"],
                "canonical_identity_promoted": relation["canonical_identity_promoted"],
            })
            checks = relation["checks"]
            anchor_rows.append({
                "intent_type": raw_intent["intent_type"],
                "subject_anchor": checks["subject_anchor"],
                "response_anchor": checks["response_anchor"],
                "biological_unit_context_compatible": checks["biological_unit_context_compatible"],
                "therapy_compatible": checks["therapy_compatible"],
                "disease_context_compatible": checks["disease_context_compatible"],
                "canonical_identity_promoted": False,
            })
            semantic_rows.append({
                "intent_type": raw_intent["intent_type"],
                "endpoint_semantics": checks["endpoint_semantics"],
                "intent_conditioned_direction": checks["intent_conditioned_direction"],
                "expected_allowed_directions": expected["allowed_directions"],
                "actual_direction": proposal["direction"],
            })
            containment_rows.append({
                "intent_type": raw_intent["intent_type"],
                "subject_in_phrase": checks["subject_in_phrase"],
                "response_in_phrase": checks["response_in_phrase"],
                "endpoint_in_phrase": checks["endpoint_in_phrase"],
                "semantic_surface_containment_version": SURFACE_VERSION,
                "fuzzy_equivalence_used": False,
            })
            binding_rows.append({
                "intent_type": raw_intent["intent_type"],
                "intent_id": validated_intent["intent_id"],
                "blueprint_id": relation["blueprint_id"],
                "state": "STRUCTURALLY_BOUND" if relation["validation_state"] == "STRUCTURALLY_BOUND"
                         else "UNDERREPRESENTED",
                "repository_internal_state": relation["validation_state"],
                "failed_checks": [name for name, passed in checks.items() if not passed],
                "topic_only_fallback": False,
            })
        intent_rows.append({
            "intent_type": raw_intent["intent_type"],
            "planner_rationale": raw_intent["retrieval_rationale"],
            "expected_retrieval_semantics": expected,
            "actual_proposal_semantics": actual_semantics,
            "compatibility": validated_intent["validation_state"],
        })

    collision_count = sum(count - 1 for count in Counter(all_ids).values() if count > 1)
    require(collision_count == 0, "deterministic allocator collision")
    term_receipts = flatten_terms(payload, frame)
    bound = [row for row in binding_rows if row["state"] == "STRUCTURALLY_BOUND"]
    underrepresented = [row for row in binding_rows if row["state"] == "UNDERREPRESENTED"]
    require(len(bound) == 1 and len(underrepresented) == 3, "binding census changed")

    compiled_rows = []
    receipts_by_intent = {}
    for receipt in term_receipts:
        receipts_by_intent.setdefault(receipt["intent_type"], []).append(receipt)
    for query in compilation["compiled_queries"]:
        binding = next(row for row in binding_rows if row["blueprint_id"] == query["blueprint_id"])
        role_binding = next(row for row in role_rows if row["blueprint_id"] == query["blueprint_id"])
        usable_terms = [row for row in receipts_by_intent[query["intent_type"]]
                        if row["deterministic_classification"] in {
                            "CANONICAL_TARGET_SURFACE", "SEMANTIC_LEXICAL_PROPOSAL_NON_AUTHORITY"}]
        compiled_rows.append({
            **query,
            "linked_semantic_relation": next(row for row in relation_rows
                                               if row["intent_type"] == query["intent_type"]),
            "deterministically_bound_roles": role_binding,
            "authorized_or_search_only_terms": usable_terms,
            "complete_provenance": {
                "alpha3_root": ALPHA3_ROOT, "source_call_root": SOURCE_ROOT,
                "target_sha256": frame["target_sha256"],
                "raw_payload_sha256": sha256_value(payload),
                "validated_plan_sha256": sha256_value(validated),
                "planner_cache_identity": planner_cache_identity_v3(target, provider_schema=provider_schema),
                "compiler_version": COMPILER_VERSION,
            },
            "relation_binding_state": binding["state"],
        })

    provider_metadata = json.loads((SOURCE / "provider_response_metadata.json").read_text(encoding="utf-8"))
    payload_keys = set()
    def keys(value: Any) -> None:
        if isinstance(value, dict):
            payload_keys.update(value)
            for child in value.values(): keys(child)
        elif isinstance(value, list):
            for child in value: keys(child)
    keys(payload)
    forbidden = {"intent_id", "blueprint_id", "concept_id", "term_id", "subject_concept_ref",
                 "response_concept_ref", "conditioning_context_refs", "therapy_context_refs",
                 "applicability", "authority", "authority_reference"}
    schema_validation = {
        "provider_payload_schema_valid": True,
        "semantic_lexical_fields_structurally_valid": True,
        "intent_types_within_precomputed_applicable_set": set(selected) <= set(
            applicability["applicable_intent_types"]),
        "model_generated_opaque_id_count": 0,
        "model_generated_canonical_ref_count": 0,
        "model_generated_applicability_decision_count": 0,
        "model_generated_authority_decision_count": 0,
        "forbidden_provider_fields_present": sorted(payload_keys & forbidden),
    }
    require(all(value is True for key, value in schema_validation.items()
                if key.endswith("valid") or key.endswith("set")), "schema validation audit failed")
    require(not schema_validation["forbidden_provider_fields_present"], "provider emitted forbidden field")

    # The smoke protocol declares success on at least one fully bound relation,
    # intent, and compiled query; underrepresented peers remain explicit.
    therapy_preserved = all(row["checks"]["therapy_compatible"] for row in
        [json.loads(line) for line in (SOURCE / "relation_binding_receipts.jsonl").read_text().splitlines()])
    biological_preserved = any(row["biological_unit_context_compatible"] for row in anchor_rows)
    success = (len(bound) >= 1 and len(compiled_rows) >= 1 and therapy_preserved
               and biological_preserved and collision_count == 0)
    require(success, "protocol smoke success criteria not met")

    component_files = {
        "planner_prompt_v3.md": ALPHA3 / "planner_prompt_v3.md",
        "planner_proposal_payload_v3_schema.json": ALPHA3 / "planner_proposal_payload_v3_schema.json",
        "linked_relation_proposal_v2_contract.json": ALPHA3 / "linked_relation_proposal_v2_contract.json",
        "deterministic_target_role_frame_v1_contract.json": ALPHA3 / "deterministic_target_role_frame_v1_contract.json",
        "retrieval_intent_applicability_v2_contract.json": ALPHA3 / "retrieval_intent_applicability_v2_contract.json",
        "intent_semantic_transform_v1_contract.json": ALPHA3 / "intent_semantic_transform_v1_contract.json",
        "planner_artifact_id_allocator_v1_contract.json": ALPHA3 / "planner_artifact_id_allocator_v1_contract.json",
        "planner_role_rehydrator_v1_contract.json": ALPHA3 / "planner_role_rehydrator_v1_contract.json",
        "semantic_surface_containment_v2_contract.json": ALPHA3 / "semantic_surface_containment_v2_contract.json",
        "deepseek_planner_v3_provider_schema.json": ALPHA3 / "deepseek_planner_v3_provider_schema.json",
    }
    config_verification = {
        "status": "PASS", "alpha3_root": ALPHA3_ROOT,
        "component_file_sha256": {name: digest(path) for name, path in component_files.items()},
        "runtime_versions": {
            "planner_payload": PAYLOAD_VERSION, "linked_relation": LINK_VERSION,
            "target_role_frame": ROLE_FRAME_VERSION, "intent_applicability": APPLICABILITY_VERSION,
            "intent_semantic_transform": TRANSFORM_VERSION, "expected_semantics": EXPECTED_VERSION,
            "id_allocator": ALLOCATOR_VERSION, "role_rehydrator": REHYDRATOR_VERSION,
            "semantic_surface_containment": SURFACE_VERSION,
            "validated_intent": VALIDATED_INTENT_VERSION, "validated_plan": VALIDATED_PLAN_VERSION,
            "prompt": PROMPT_VERSION, "cache": CACHE_VERSION, "compiler": COMPILER_VERSION,
        },
        "prompt_sha256": request_preflight["prompt_sha256"],
        "payload_schema_sha256": request_preflight["proposal_schema_sha256"],
        "provider_schema_sha256": request_preflight["provider_schema_sha256"],
        "transport_identity": {
            "provider": "deepseek", "model": "deepseek-v4-pro", "thinking": "enabled",
            "reasoning_effort": "high", "temperature_omitted": True, "top_p_omitted": True,
            "request_body_sha256": request_preflight["request_body_sha256"],
        },
    }

    RUN.mkdir(parents=True, exist_ok=False)
    write_json(RUN / "upstream_root_verification.json", {
        "alpha3": alpha3, "source_one_call_run": source,
        "source_one_call_root_sha256": SOURCE_ROOT,
        "source_run_mutated": False,
    })
    write_json(RUN / "planner_v3_config_verification.json", config_verification)
    write_json(RUN / "target_role_frame_108.json", frame)
    write_json(RUN / "retrieval_intent_applicability_108.json", applicability)
    write_json(RUN / "provider_call_manifest.json", {
        "provider": "deepseek", "model": "deepseek-v4-pro",
        "provider_requests_attempted": 1, "model_inference_calls": 1,
        "thinking": "enabled", "reasoning_effort": "high",
        "temperature_omitted": True, "top_p_omitted": True,
        "retry_count": 0, "repair_calls": 0, "openai_calls": 0,
        "request_body_sha256": request_preflight["request_body_sha256"],
        "source_call_root_sha256": SOURCE_ROOT,
        "new_provider_calls_during_protocol_completion": 0,
    })
    write_json(RUN / "raw_provider_response.json", {
        "provider": "deepseek", "model": "deepseek-v4-pro",
        "raw_response_content": raw_text,
        "raw_response_content_sha256": hashlib.sha256(raw_text.encode("utf-8")).hexdigest(),
        "provider_response_metadata": provider_metadata,
        "content_frozen_before_deterministic_processing": True,
    })
    write_json(RUN / "planner_v3_raw_payload.json", payload)
    (RUN / "planner_v3_raw_payload_sha256").write_text(sha256_value(payload) + "\n", encoding="utf-8")
    write_json(RUN / "planner_v3_schema_validation.json", schema_validation)
    write_json(RUN / "intent_selection_analysis.json", {
        "precomputed_applicable_intents": applicability["applicable_intent_types"],
        "selected_intents": selected, "selected_intent_count": len(selected),
        "all_applicable_intents_required": False, "intent_rows": intent_rows,
    })
    write_json(RUN / "linked_relation_proposal_analysis.json", {
        "artifact_schema_version": LINK_VERSION,
        "linked_relation_proposal_count": len(relation_rows), "proposals": relation_rows,
        "identity_judged_directly_from_model_text": False,
    })
    write_json(RUN / "artifact_id_allocation.json", {
        "artifact_schema_version": ALLOCATOR_VERSION,
        "allocated_id_count": len(all_ids), "unique_id_count": len(set(all_ids)),
        "allocator_collision_count": collision_count,
        "same_input_replay_identical": replayed == validated,
        "model_generated_opaque_id_count": 0,
        "deterministic_id_allocation_success": True,
    })
    write_json(RUN / "role_rehydration_analysis.json", {
        "artifact_schema_version": REHYDRATOR_VERSION,
        "role_bindings": role_rows,
        "role_rehydration_success": True,
        "canonical_identity_promotions": 0,
        "novel_therapy_identity_inferred": False,
    })
    write_json(RUN / "intent_semantic_transform_analysis.json", {
        "artifact_schema_version": TRANSFORM_VERSION,
        "intent_rows": intent_rows, "semantic_validation_rows": semantic_rows,
        "new_transform_invented_during_run": False,
    })
    write_json(RUN / "search_anchor_compatibility.json", {
        "rows": anchor_rows, "authority_boundary_violations": 0,
        "canonical_identity_promotions": 0,
    })
    write_json(RUN / "semantic_slot_compatibility.json", {
        "rows": semantic_rows, "intent_conditioned_validation": True,
    })
    write_json(RUN / "semantic_surface_containment.json", {
        "artifact_schema_version": SURFACE_VERSION, "rows": containment_rows,
        "fuzzy_semantic_equivalence_used": False,
    })
    write_jsonl(RUN / "term_validation_receipts.jsonl", term_receipts)
    write_json(RUN / "relation_binding_analysis.json", {
        "proposal_count": len(binding_rows), "structurally_bound_count": len(bound),
        "underrepresented_count": len(underrepresented), "rows": binding_rows,
        "topic_only_fallback_used": False,
    })
    write_jsonl(RUN / "compiled_queries.jsonl", compiled_rows)
    (RUN / "compiled_queries_sha256").write_text(digest(RUN / "compiled_queries.jsonl") + "\n", encoding="utf-8")
    write_json(RUN / "v2_v3_structural_smoke_comparison.json", {
        "comparison_scope": "STRUCTURAL_ONLY_NO_RETRIEVAL_PERFORMANCE",
        "v2_model_generated_context_refs": True,
        "v2_first_loss_involved_context_ref_bookkeeping": True,
        "v3_model_generated_opaque_refs": 0,
        "v3_deterministic_role_rehydration_state": "PARTIAL_WITH_ONE_STRUCTURALLY_BOUND_RELATION",
        "v3_is_better_claimed": False,
    })
    write_json(RUN / "first_loss_analysis.json", {
        "smoke_success_under_frozen_success_criteria": True,
        "first_loss_stage": "NONE",
        "proposal_level_underrepresentation": underrepresented,
        "proposal_level_diagnostics_do_not_change_smoke_first_loss": True,
        "repair_performed": False,
    })
    write_json(RUN / "scientific_state_safety_audit.json", {
        "source_call_run_mutated": False, "alpha3_assets_modified": False,
        "prompt_modified": False, "schema_modified": False, "target_role_frame_modified": False,
        "intent_applicability_modified": False, "intent_transform_modified": False,
        "id_allocator_modified": False, "role_rehydrator_modified": False,
        "validators_modified": False, "compiler_modified": False,
        "provider_configuration_modified": False,
        "provider_calls_total_for_smoke": 1,
        "new_provider_calls_during_protocol_completion": 0,
        "literature_network_calls": 0, "retrieval_calls": 0,
        "candidate_records_seen": 0, "hit_count_checks": 0, "known_pmid_checks": 0,
        "authority_boundary_violations": 0, "search_only_identity_promotions": 0,
        "historical_assets_modified": False,
    })
    summary = {
        "artifact_schema_version": "SearchPlanV24DevAlpha3DeepSeekSmoke108ProtocolSummaryV1",
        "status": "completed", "case_id": CASE_ID,
        "provider": "deepseek", "model": "deepseek-v4-pro",
        "provider_requests_attempted": 1, "model_inference_calls": 1,
        "planner_v3_payload_valid": True,
        "model_generated_opaque_id_count": 0, "model_generated_canonical_ref_count": 0,
        "selected_intent_count": len(selected),
        "linked_relation_proposal_count": len(relation_rows),
        "valid_linked_relation_count": len(bound),
        "deterministic_id_allocation_success": True,
        "role_rehydration_success": True,
        "structurally_bound_intent_count": len({row["intent_type"] for row in bound}),
        "compiled_query_count": len(compiled_rows),
        "therapy_requirement_preserved": therapy_preserved,
        "biological_unit_requirement_preserved": biological_preserved,
        "authority_boundary_violations": 0, "search_only_identity_promotions": 0,
        "first_loss_stage": "NONE",
        "next_stage_recommendation": "AUTHORIZE_REMAINING_7_PLANNER_V3_DEVELOPMENT_CASES",
        "literature_network_calls": 0, "retrieval_calls": 0, "candidate_records_seen": 0,
        "historical_assets_modified": False,
        "source_call_root_sha256": SOURCE_ROOT,
    }
    write_json(RUN / "summary.json", summary)
    require(source_snapshot() == before, "frozen source call run changed during completion")
    verify_root(ALPHA3, ALPHA3_ROOT)
    components = [[path.name, digest(path)] for path in sorted(RUN.iterdir())
                  if path.is_file() and path.name not in {"validation.json", ROOT_FILE}]
    root = sha256_value(components)
    write_json(RUN / "validation.json", {
        "artifact_schema_version": "SearchPlanV24DevAlpha3DeepSeekSmoke108ProtocolValidationV1",
        "status": "PASS", "aggregate_components": components,
        ROOT_FILE: root, "all_required_outputs_present": True,
        "source_call_root_verified": True, "alpha3_root_verified": True,
        "offline_protocol_completion": True,
    })
    (RUN / ROOT_FILE).write_text(root + "\n", encoding="utf-8")
    require(verify_root(RUN, root)["verified"], "protocol completion root failed self-verification")
    print(json.dumps({"root": root, "summary": summary}, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
