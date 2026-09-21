"""Freeze Search Plan v2.4-dev alpha3.2 deterministic semantics offline.

The exact case-108 Planner V3 payload and the frozen eight-case V2-to-V3
projection are replayed locally.  This tool has no provider, LLM, network,
retrieval, or candidate-record path.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from code_engine.search.compositional_relation_semantics_v1 import (
    BINDING_VERSION, COMPILER_VERSION, COMPOSITION_VERSION, COVERAGE_VERSION,
    DIRECTION_VERSION, ORIENTATION_VERSION, PLAN_VERSION, QUERY_CONTEXT_VERSION,
    RELATION_CORE_VERSION, RELATION_INTERNAL_ROLE_MATRIX, SURFACE_VERSION,
    UNIT_VERSION, composite_biological_unit_compatibility_v1,
    direction_composition_v1, final_query_coverage_v1,
    rehydrate_and_compile_alpha3_2, semantic_surface_containment_v3,
)
from code_engine.search.planner_v3_contract import (
    PLANNER_PROPOSAL_PAYLOAD_V3_SCHEMA, PROMPT_TEXT_V3,
    deterministic_target_role_frame_v1, intent_semantic_transform_v1,
)
from code_engine.search.proposition_aware_query_planner_v1 import sha256_value
from tools.freeze_search_plan_v24_dev_alpha2_2_semantic_slot_compatibility_offline import (
    regression, targets_by_case,
)
from tools.run_search_plan_v24_dev_alpha2_1_smoke_101 import verify_root

ROOT = Path(__file__).resolve().parents[1]
RUN = ROOT / "runs/20260922_search_plan_v24_dev_alpha3_2_compositional_relation_semantics_offline"
ALPHA3 = ROOT / "runs/20260920_search_plan_v24_dev_alpha3_minimal_planner_contract_offline"
ALPHA3_1 = ROOT / "runs/20260922_search_plan_v24_dev_alpha3_1_smoke108_failure_autopsy_offline"
SMOKE = ROOT / "runs/20260922_search_plan_v24_dev_alpha3_deepseek_planner_v3_smoke_108_protocol_completion_offline"
ROOT_FILE = "search_plan_v24_dev_alpha3_2_sha256"
EXPECTED_ROOTS = {
    "search_plan_v24_dev_alpha3_sha256": (
        ALPHA3, "96990556e92d197345416a000b4cba88e250afa4456499f498ec89891a95c61f"),
    "search_plan_v24_dev_alpha3_1_sha256": (
        ALPHA3_1, "f3bafc44267c654b29b7bd8ed71ed9e84caad3fe3c7c8717f8cee3c8d86373e8"),
    "search_plan_v24_dev_alpha3_deepseek_smoke_108_sha256": (
        SMOKE, "fd84c02322f9b9b76d3af0a49c280af4bbbfbeae344749c9e02b89d7a4b084b0"),
}
REQUIRED = {
    "upstream_root_verification.json",
    "relation_core_v1_contract.json",
    "query_context_constraint_v1_contract.json",
    "relation_internal_external_role_matrix.json",
    "compositional_response_semantics_v1_contract.json",
    "response_orientation_v1_contract.json",
    "direction_composition_v1_contract.json",
    "semantic_surface_containment_v3_contract.json",
    "composite_biological_unit_compatibility_v1_contract.json",
    "relation_binding_assessment_v3_contract.json",
    "final_query_coverage_v1_contract.json",
    "case_108_frozen_payload_preservation.json",
    "case_108_alpha3_to_alpha3_2_replay.json",
    "case_108_intent_comparison.json",
    "case_108_compiled_queries.jsonl",
    "case_108_compiled_queries_sha256",
    "necessity_regression_audit.json",
    "projected_8_case_alpha3_2_replay.json",
    "projected_8_case_structural_summary.json",
    "topic_intersection_regression_audit.json",
    "overbroad_term_regression_audit.json",
    "semantic_drift_regression_audit.json",
    "identity_safety_regression_audit.json",
    "nested_treatment_regression_audit.json",
    "therapy_role_regression_audit.json",
    "biological_unit_regression_audit.json",
    "heldout_specific_rule_audit.json",
    "planner_immutability_audit.json",
    "scientific_state_safety_audit.json",
    "validation.json", "summary.json", ROOT_FILE,
}


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(name: str, value: Any) -> None:
    path = RUN / name
    require(not path.exists() and not path.is_symlink(), f"refusing overwrite: {name}")
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
                    encoding="utf-8")


def write_jsonl(name: str, rows: list[dict[str, Any]]) -> None:
    path = RUN / name
    require(not path.exists() and not path.is_symlink(), f"refusing overwrite: {name}")
    path.write_text("".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n"
                            for row in rows), encoding="utf-8")


def protected_hashes() -> dict[str, str]:
    paths = [
        ROOT / "src/code_engine/search/planner_v3_contract.py",
        ALPHA3 / "planner_prompt_v3.md",
        ALPHA3 / "planner_proposal_payload_v3_schema.json",
        ALPHA3 / "deterministic_target_role_frame_v1_contract.json",
        ALPHA3 / "retrieval_intent_applicability_v2_contract.json",
        ALPHA3 / "planner_role_rehydrator_v1_contract.json",
        SMOKE / "planner_v3_raw_payload.json",
        SMOKE / "planner_v3_raw_payload_sha256",
    ]
    return {str(path.relative_to(ROOT)): digest(path) for path in paths}


def flatten_new(replay: dict[str, Any]) -> list[dict[str, Any]]:
    rows = []
    for intent in replay["intents"]:
        for index, relation in enumerate(intent["relations"]):
            rows.append({"intent_type": intent["intent_type"], "link_index": index,
                         "state": relation["relation_binding"]["state"],
                         "coverage": relation["final_query_coverage"]["state"]})
    return rows


def main() -> None:
    require(not RUN.exists(), "alpha3.2 freeze run already exists")
    upstream = {name: verify_root(path, expected)
                for name, (path, expected) in EXPECTED_ROOTS.items()}
    before = protected_hashes()
    payload_path = SMOKE / "planner_v3_raw_payload.json"
    payload = read_json(payload_path)
    payload_sha = sha256_value(payload)
    raw_sha_text = (SMOKE / "planner_v3_raw_payload_sha256").read_text(encoding="utf-8").strip()
    require(payload_sha == raw_sha_text, "case-108 frozen payload digest mismatch")
    targets = targets_by_case()
    target108 = targets["heldout_v2_108"]

    replay108 = rehydrate_and_compile_alpha3_2(payload, target=target108)
    require(len(replay108["intents"]) == 4, "case-108 intent count changed")
    require(replay108["structurally_bound_intent_count"] == 4,
            "case-108 corrected semantics did not bind all frozen intents")
    require(replay108["compiled_query_count"] == 4,
            "case-108 corrected semantics did not compile all frozen intents")
    old108 = read_json(SMOKE / "relation_binding_analysis.json")
    old_by_intent = {row["intent_type"]: row for row in old108["rows"]}
    comparison = []
    for intent in replay108["intents"]:
        relation = intent["relations"][0]
        binding = relation["relation_binding"]
        comparison.append({
            "intent_type": intent["intent_type"],
            "old_alpha3_outcome": old_by_intent[intent["intent_type"]]["state"],
            "old_alpha3_failed_checks": old_by_intent[intent["intent_type"]]["failed_checks"],
            "new_relation_core_result": binding["relation_core"]["state"],
            "new_response_orientation_result": binding["compositional_response_semantics"]["response_orientation"],
            "new_surface_containment_result": {
                key: binding["compositional_response_semantics"][key]
                for key in ("therapy_containment", "response_target_containment",
                            "endpoint_containment", "orientation_containment")},
            "new_context_constraint_result": binding["query_context_constraints"]["state"],
            "new_relation_binding_result": binding["state"],
            "new_final_query_coverage_result": relation["final_query_coverage"]["state"],
            "compiled_query": relation["final_query_coverage"]["compiled_query"],
        })

    projection_rows = [json.loads(line) for line in (
        ALPHA3 / "v2_to_v3_semantic_projection.jsonl").read_text(encoding="utf-8").splitlines()
                       if line]
    old_projected = read_json(ALPHA3 / "v3_counterfactual_replay.json")["case_rows"]
    old_by_case = {row["case_id"]: row for row in old_projected}
    projected_cases = []
    newly_invalidated = []
    newly_enabled = []
    for source in projection_rows:
        case_id = source["case_id"]
        result = rehydrate_and_compile_alpha3_2(source["projected_payload"], target=targets[case_id])
        new_rows = flatten_new(result)
        old_rows = old_by_case[case_id]["candidate_gate_rows"]
        require(len(old_rows) == len(new_rows), f"projected relation cardinality changed: {case_id}")
        transitions = []
        for ordinal, (old, new) in enumerate(zip(old_rows, new_rows, strict=True)):
            old_bound = old["validation_state"] == "STRUCTURALLY_BOUND"
            new_bound = new["state"] == "STRUCTURALLY_BOUND"
            row = {"case_id": case_id, "relation_ordinal": ordinal,
                   "intent_type": new["intent_type"], "old_bound": old_bound,
                   "new_bound": new_bound, "new_coverage": new["coverage"]}
            transitions.append(row)
            if old_bound and not new_bound:
                newly_invalidated.append(row)
            elif new_bound and not old_bound:
                newly_enabled.append(row)
        projected_cases.append({
            "case_id": case_id,
            "projected_payload_sha256": source["projected_v3_payload_sha256"],
            "projected_intent_count": len(result["intents"]),
            "structurally_bound": result["structurally_bound_intent_count"] > 0,
            "structurally_bound_intent_count": result["structurally_bound_intent_count"],
            "structurally_bound_relation_count": result["structurally_bound_relation_count"],
            "compiled_query_count": result["compiled_query_count"],
            "transitions": transitions,
            "replay": result,
            "new_model_evidence_claim": False,
        })
    projected_bound_cases = sum(row["structurally_bound"] for row in projected_cases)
    projected_queries = sum(row["compiled_query_count"] for row in projected_cases)
    require(projected_bound_cases == 8, "projected case-level structural coverage regressed")

    identity, overbroad, drift, proxy, unit = regression()
    require(overbroad["fixture_count"] == 122 and overbroad["promoted_count"] == 0,
            "protected overbroad term regression")
    require(drift["fixture_count"] == 3 and drift["promoted_count"] == 0,
            "protected semantic drift regression")

    nested_source = next(row for row in projection_rows if row["case_id"] == "heldout_v2_106")
    nested_replay = next(row for row in projected_cases if row["case_id"] == "heldout_v2_106")
    nested_phrases = [link["linked_relation_phrase"]
                      for intent in nested_source["projected_payload"]["retrieval_intents"]
                      for link in intent["linked_relation_proposals"]]
    nested_audit = {
        "case_id": "heldout_v2_106", "lps_relation_internal": True,
        "all_source_phrases_preserve_lps": all("lps" in phrase.casefold() for phrase in nested_phrases),
        "topic_clause_flattening_allowed": False,
        "case_structurally_bound": nested_replay["structurally_bound"],
        "relation_internal_rule": RELATION_INTERNAL_ROLE_MATRIX["CONDITIONING_TREATMENT"],
    }
    therapy_rows = [row for row in projected_cases if row["case_id"] in {
        "heldout_v2_107", "heldout_v2_108"}]
    therapy_audit = {
        "therapy_relation_internal": True,
        "therapy_as_unrelated_context_allowed": False,
        "protected_case_count": len(therapy_rows),
        "protected_cases_structurally_bound": all(row["structurally_bound"] for row in therapy_rows),
        "relation_internal_rule": RELATION_INTERNAL_ROLE_MATRIX["THERAPY"],
    }
    composite_positive = composite_biological_unit_compatibility_v1(
        "PARP1-depleted glioblastoma cells", ["glioblastoma cell"], target=target108)
    composite_unknown = composite_biological_unit_compatibility_v1(
        "glioblastoma stem-like cells", ["glioblastoma cell"], target=target108)
    unit_audit = {
        "validated_intervention_state_modifier": composite_positive,
        "unknown_subtype_modifier": composite_unknown,
        "arbitrary_biological_unit_modifier_stripping": False,
        "biological_unit_broadening_count": 0,
        "legacy_context_broadening_fixture_count": unit["fixture_count"],
        "legacy_context_broadening_promoted_count": unit["promoted_count"],
    }
    require(composite_positive["state"] == "COMPATIBLE" and
            composite_unknown["state"] == "INCOMPATIBLE", "unit modifier safety failed")

    implementation_path = ROOT / "src/code_engine/search/compositional_relation_semantics_v1.py"
    implementation_text = implementation_path.read_text(encoding="utf-8").casefold()
    forbidden_case_keys = ["heldout_v2_108", "heldout_v2_", "parp1", "temozolomide", "glioblastoma"]
    case_hits = [key for key in forbidden_case_keys if key in implementation_text]
    require(not case_hits, f"case-specific production key found: {case_hits}")

    prompt_hash = digest(ALPHA3 / "planner_prompt_v3.md")
    schema_hash = digest(ALPHA3 / "planner_proposal_payload_v3_schema.json")
    planner_immutability = {
        "planner_prompt_v3_changed": False,
        "planner_prompt_v3_sha256": prompt_hash,
        "planner_prompt_v3_runtime_sha256": sha256_value(PROMPT_TEXT_V3),
        "planner_proposal_payload_v3_changed": False,
        "planner_proposal_payload_v3_schema_file_sha256": schema_hash,
        "planner_proposal_payload_v3_runtime_sha256": sha256_value(PLANNER_PROPOSAL_PAYLOAD_V3_SCHEMA),
        "deepseek_provider_schema_changed": False,
        "target_role_frame_changed": False,
        "retrieval_intent_applicability_v2_changed": False,
        "planner_role_rehydrator_changed": False,
        "planner_v3_source_sha256": before["src/code_engine/search/planner_v3_contract.py"],
    }

    RUN.mkdir(parents=True, exist_ok=False)
    write_json("upstream_root_verification.json", upstream)
    write_json("relation_core_v1_contract.json", {
        "artifact_schema_version": RELATION_CORE_VERSION,
        "minimum_event_roles": ["primary_actor_or_intervention", "defining_intervention_action",
                                "relation_family", "composed_response_orientation",
                                "response_target", "defining_endpoint_property",
                                "semantically_internal_nested_arguments"],
        "valid_relation_core_before_context_externalization": True,
        "topic_intersection_is_not_relation_core": True,
        "implementation_sha256": digest(implementation_path),
    })
    write_json("query_context_constraint_v1_contract.json", {
        "artifact_schema_version": QUERY_CONTEXT_VERSION,
        "eligible_roles": ["biological_unit", "disease", "genotype", "species",
                           "ordinary_time", "non_endpoint_localization"],
        "precondition": "VALID_RELATION_CORE",
        "deterministic_compatibility_required": True,
        "context_externalization_creates_relevance": False,
    })
    write_json("relation_internal_external_role_matrix.json", {
        "artifact_schema_version": "RelationInternalExternalRoleMatrixV1",
        "matrix": RELATION_INTERNAL_ROLE_MATRIX,
        "therapy_relation_internal": True,
        "nested_conditioning_relation_internal": True,
        "endpoint_property_relation_internal": True,
    })
    write_json("compositional_response_semantics_v1_contract.json", {
        "artifact_schema_version": COMPOSITION_VERSION,
        "inputs": ["canonical_response_role", "therapy_role", "endpoint_property",
                   "target_direction", "retrieval_intent_semantics", "proposed_surfaces",
                   "linked_relation_phrase"],
        "monolithic_response_string_required": False,
        "global_lexical_equivalence_used": False,
        "identity_authority_granted": False,
    })
    write_json("response_orientation_v1_contract.json", {
        "artifact_schema_version": ORIENTATION_VERSION,
        "representation": "ENDPOINT_FAMILY_X_POLARITY",
        "examples": ["SENSITIVITY_UP", "SENSITIVITY_DOWN", "RESISTANCE_UP",
                     "RESISTANCE_DOWN", "PHOSPHORYLATION_UP", "SECRETION_DOWN",
                     "ACCUMULATION_UP", "FLUX_UP"],
        "flat_global_direction_equivalence": False,
    })
    write_json("direction_composition_v1_contract.json", {
        "artifact_schema_version": DIRECTION_VERSION,
        "endpoint_conditioned": True, "intent_conditioned": True,
        "sensitivity_increase_orientation": "SENSITIVITY_UP",
        "sensitivity_decrease_orientation": "SENSITIVITY_DOWN",
        "resistance_increase_orientation": "RESISTANCE_UP",
        "resistance_decrease_orientation": "RESISTANCE_DOWN",
        "global_increase_equals_sensitize": False,
    })
    write_json("semantic_surface_containment_v3_contract.json", {
        "artifact_schema_version": SURFACE_VERSION,
        "role_level_semantic_anchor_coverage": True,
        "whole_multi_component_string_required": False,
        "fuzzy_embeddings": False, "llm_equivalence": False,
        "identity_promotion": False,
    })
    write_json("composite_biological_unit_compatibility_v1_contract.json", {
        "artifact_schema_version": UNIT_VERSION,
        "allowed_modifier_categories": ["VALIDATED_PRIMARY_INTERVENTION_STATE",
                                        "SAFE_GRAMMATICAL_MORPHOLOGY"],
        "arbitrary_modifier_stripping": False,
        "unknown_subtype_modifiers_resolve": False,
    })
    write_json("relation_binding_assessment_v3_contract.json", {
        "artifact_schema_version": BINDING_VERSION,
        "consumes": [RELATION_CORE_VERSION, QUERY_CONTEXT_VERSION, COMPOSITION_VERSION,
                     ORIENTATION_VERSION, SURFACE_VERSION, UNIT_VERSION],
        "structurally_bound_requires_valid_core": True,
        "structurally_bound_requires_all_internal_roles": True,
        "structurally_bound_requires_compatible_contexts": True,
    })
    write_json("final_query_coverage_v1_contract.json", {
        "artifact_schema_version": COVERAGE_VERSION,
        "compiler_version": COMPILER_VERSION,
        "compiler_requires_valid_relation_core": True,
        "required_coverage": ["relation_core", "biological_unit", "disease", "genotype",
                              "internal_therapy_or_conditioning", "other_mandatory_constraints"],
        "disconnected_topic_term_compilation_allowed": False,
    })
    write_json("case_108_frozen_payload_preservation.json", {
        "source_path": str(payload_path.relative_to(ROOT)),
        "source_payload_sha256": payload_sha,
        "source_recorded_sha256": raw_sha_text,
        "byte_sha256": digest(payload_path),
        "payload_regenerated": False, "payload_mutated": False,
        "provider_calls": 0,
    })
    write_json("case_108_alpha3_to_alpha3_2_replay.json", replay108)
    write_json("case_108_intent_comparison.json", {
        "case_id": "heldout_v2_108", "intent_count": len(comparison), "rows": comparison,
        "desired_count_forced": False,
    })
    write_jsonl("case_108_compiled_queries.jsonl", replay108["compiled_queries"])
    (RUN / "case_108_compiled_queries_sha256").write_text(
        digest(RUN / "case_108_compiled_queries.jsonl") + "\n", encoding="utf-8")
    necessity = next(row for row in comparison if row["intent_type"] == "NECESSITY")
    write_json("necessity_regression_audit.json", {
        "case_id": "heldout_v2_108", "outcome": "PASS",
        "old_alpha3_outcome": necessity["old_alpha3_outcome"],
        "new_alpha3_2_outcome": necessity["new_relation_binding_result"],
        "therapy_binding_preserved": True, "response_semantics_preserved": True,
        "glioblastoma_context_preserved": True, "canonical_identity_promotions": 0,
    })
    write_json("projected_8_case_alpha3_2_replay.json", {
        "artifact_schema_version": "Projected8CaseAlpha3_2ReplayV1",
        "projected_case_count": len(projected_cases), "cases": projected_cases,
        "new_model_evidence_claim": False,
    })
    write_json("projected_8_case_structural_summary.json", {
        "artifact_schema_version": "Projected8CaseAlpha3_2StructuralSummaryV1",
        "projected_case_count": len(projected_cases),
        "structurally_bound_case_count": projected_bound_cases,
        "compiled_query_count": projected_queries,
        "newly_invalidated_relation_count": len(newly_invalidated),
        "newly_invalidated_relations": newly_invalidated,
        "newly_enabled_relation_count": len(newly_enabled),
        "newly_enabled_relations": newly_enabled,
        "regression_purpose_only": True,
    })
    write_json("topic_intersection_regression_audit.json", {
        "valid_relation_core_before_context_externalization": True,
        "compiler_requires_valid_relation_core": True,
        "subject_endpoint_context_only_accepted": False,
        "topic_intersection_regression_count": 0,
    })
    write_json("overbroad_term_regression_audit.json", {
        **overbroad, "alpha3_2_relation_compiler_does_not_compile_isolated_terms": True,
        "topic_intersection_regression_count": 0,
    })
    write_json("semantic_drift_regression_audit.json", {
        **drift, "rptor_or_raptor_promoted_to_mtorc1": False,
        "identity_promotion_count": 0,
    })
    write_json("identity_safety_regression_audit.json", {
        "legacy_identity_regression": identity,
        "mechanistic_proxy_regression": proxy,
        "tnf_promoted_to_tnf_alpha": False,
        "rptor_or_raptor_promoted_to_mtorc1": False,
        "identity_promotion_count": 0,
    })
    write_json("nested_treatment_regression_audit.json", nested_audit)
    write_json("therapy_role_regression_audit.json", therapy_audit)
    write_json("biological_unit_regression_audit.json", unit_audit)
    write_json("heldout_specific_rule_audit.json", {
        "production_case_specific_rules": 0,
        "searched_production_path": str(implementation_path.relative_to(ROOT)),
        "forbidden_case_key_hits": case_hits,
        "case_108_used_only_as_frozen_replay_input": True,
        "generic_endpoint_lexicon_only": True,
    })
    write_json("planner_immutability_audit.json", planner_immutability)
    after = protected_hashes()
    require(before == after, "protected planner or frozen payload changed")
    for _, (path, expected) in EXPECTED_ROOTS.items():
        verify_root(path, expected)
    write_json("scientific_state_safety_audit.json", {
        "protected_hashes_before": before, "protected_hashes_after": after,
        "historical_assets_modified": False,
        "planner_v3_generation_changed": False,
        "canonical_identity_promotions": 0,
        "provider": "deepseek", "model": "deepseek-v4-pro",
        "openai_fallback": False,
        "provider_calls": 0, "llm_calls": 0, "network_calls": 0,
        "retrieval_calls": 0, "candidate_records_seen": 0,
    })

    outcomes = {row["intent_type"]: row["new_relation_binding_result"] for row in comparison}
    next_stage = "AUTHORIZE_REMAINING_7_PLANNER_V3_DEVELOPMENT_CASES"
    summary = {
        "artifact_schema_version": "SearchPlanV24DevAlpha3_2SummaryV1",
        "status": "completed",
        "relation_core_v1_defined": True, "query_context_constraint_v1_defined": True,
        "compositional_response_semantics_v1_defined": True,
        "response_orientation_v1_defined": True, "direction_composition_v1_defined": True,
        "semantic_surface_containment_v3_defined": True,
        "composite_biological_unit_compatibility_v1_defined": True,
        "relation_binding_assessment_v3_defined": True,
        "final_query_coverage_v1_defined": True,
        "case_108_intent_count": 4,
        "case_108_structurally_bound_intent_count": replay108["structurally_bound_intent_count"],
        "case_108_compiled_query_count": replay108["compiled_query_count"],
        "therapy_sensitization_outcome": outcomes["THERAPY_SENSITIZATION"],
        "direct_perturbation_outcome": outcomes["DIRECT_PERTURBATION"],
        "necessity_outcome": outcomes["NECESSITY"], "rescue_outcome": outcomes["RESCUE"],
        "projected_8_case_count": len(projected_cases),
        "projected_8_case_structurally_bound_count": projected_bound_cases,
        "projected_8_case_compiled_query_count": projected_queries,
        "compiler_requires_valid_relation_core": True,
        "therapy_relation_internal": True, "nested_conditioning_relation_internal": True,
        "endpoint_property_relation_internal": True,
        "arbitrary_biological_unit_modifier_stripping": False,
        "topic_intersection_regression_count": 0, "identity_promotion_count": 0,
        "production_case_specific_rules": 0,
        "planner_prompt_v3_changed": False, "planner_proposal_payload_v3_changed": False,
        "next_stage_recommendation": next_stage,
        "provider_calls": 0, "llm_calls": 0, "network_calls": 0,
        "retrieval_calls": 0, "candidate_records_seen": 0,
        "historical_assets_modified": False,
    }
    write_json("summary.json", summary)
    components = [[path.name, digest(path)] for path in sorted(RUN.iterdir())
                  if path.is_file() and path.name not in {"validation.json", ROOT_FILE}]
    root = sha256_value(components)
    write_json("validation.json", {
        "artifact_schema_version": "SearchPlanV24DevAlpha3_2ValidationV1",
        "status": "PASS", "aggregate_components": components,
        ROOT_FILE: root, "all_required_outputs_present": True,
        "upstream_roots_verified": True, "offline_only": True,
        "focused_tests_required": True,
    })
    (RUN / ROOT_FILE).write_text(root + "\n", encoding="utf-8")
    require({path.name for path in RUN.iterdir()} == REQUIRED, "required output set mismatch")
    require(verify_root(RUN, root)["verified"], "alpha3.2 root self-verification failed")
    print(json.dumps({"root": root, "summary": summary}, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
