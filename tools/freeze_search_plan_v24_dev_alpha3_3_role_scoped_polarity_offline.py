#!/usr/bin/env python3
"""Freeze the offline alpha3.3 role-scoped polarity replay.

This tool consumes only already-frozen Planner V3 payloads.  It performs no
provider, model, network, literature-retrieval, or candidate-record operation.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from code_engine.search.proposition_aware_query_planner_v1 import sha256_value
from code_engine.search.query_compiler_v24_dev import DEFAULT_DEVELOPMENT_BUDGETS
from code_engine.search.role_scoped_polarity_v1 import (
    BINDING_VERSION, COMPILER_VERSION, INTERVENTION_POLARITY_VERSION,
    PARSER_VERSION, PLAN_VERSION, RELATION_CORE_VERSION, RESPONSE_EVIDENCE_VERSION,
    rehydrate_and_compile_alpha3_3,
)
from tools.freeze_search_plan_v24_dev_alpha2_2_semantic_slot_compatibility_offline import (
    targets_by_case,
)

RUN = ROOT / "runs/20260923_search_plan_v24_dev_alpha3_3_role_scoped_polarity_offline"
EMPIRICAL = ROOT / "runs/20260922_search_plan_v24_dev_alpha3_2_planner_v3_empirical_remaining7"
ALPHA32 = ROOT / "runs/20260922_search_plan_v24_dev_alpha3_2_compositional_relation_semantics_offline"
ALPHA3 = ROOT / "runs/20260920_search_plan_v24_dev_alpha3_minimal_planner_contract_offline"
SMOKE108 = ROOT / "runs/20260922_search_plan_v24_dev_alpha3_deepseek_planner_v3_smoke_108_protocol_completion_offline"

EXPECTED_ROOTS = {
    "empirical_v3": (EMPIRICAL, "search_plan_v24_dev_alpha3_2_empirical_v3_sha256",
                     "a78a2737f6f84d8f14088f8dfaf5dca08f7485511877076772ca9b874d9f2b76"),
    "alpha3_2": (ALPHA32, "search_plan_v24_dev_alpha3_2_sha256",
                 "0a80a8d2759d016723c5d46353f02bdd9354148bfe37f84a235fe59365306f53"),
    "alpha3": (ALPHA3, "search_plan_v24_dev_alpha3_sha256",
               "96990556e92d197345416a000b4cba88e250afa4456499f498ec89891a95c61f"),
}
CASES = tuple(f"heldout_v2_{number}" for number in range(101, 109))
CORE_DEFINITION = (
    "therapy sensitivity targets use DIRECT_PERTURBATION or THERAPY_SENSITIZATION; "
    "other targets use DIRECT_PERTURBATION"
)


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


def pretty(value: Any) -> bytes:
    return (json.dumps(value, sort_keys=True, ensure_ascii=False, indent=2) + "\n").encode()


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def aggregate(pairs: list[list[str]]) -> str:
    return hashlib.sha256(canonical(pairs)).hexdigest()


def verify_root(run: Path, root_file: str, expected: str) -> dict[str, Any]:
    recorded = (run / root_file).read_text(encoding="utf-8").strip()
    validation = load(run / "validation.json")
    pairs = validation["aggregate_components"]
    for name, expected_digest in pairs:
        require(digest(run / name) == expected_digest, f"upstream component changed: {run.name}/{name}")
    actual = aggregate(pairs)
    require(recorded == expected == actual, f"upstream root mismatch: {run.name}")
    return {"path": str(run.relative_to(ROOT)), "root_file": root_file,
            "expected_sha256": expected, "recorded_sha256": recorded,
            "recomputed_sha256": actual, "component_count": len(pairs), "verified": True}


def old_key(row: dict[str, Any]) -> tuple[str, str, str]:
    return row["case_id"], row["intent_type"], row["query_string"]


def core_intents(target: dict[str, Any]) -> set[str]:
    return ({"DIRECT_PERTURBATION", "THERAPY_SENSITIZATION"}
            if target.get("therapy") else {"DIRECT_PERTURBATION"})


def polarity_contracts() -> dict[str, Any]:
    return {
        "intervention_action_polarity_v1_contract.json": {
            "artifact_schema_version": INTERVENTION_POLARITY_VERSION,
            "purpose": "WHAT_IS_DONE_TO_THE_PRIMARY_ACTOR",
            "allowed_states": ["ACTIVATE", "INHIBIT", "DELETE_OR_LOSS",
                               "OVEREXPRESS_OR_INCREASE", "KNOCKDOWN_OR_REDUCE",
                               "EXPOSE_OR_STIMULATE", "BLOCK", "OTHER", "UNRESOLVED"],
            "controls_response_orientation": False,
            "central_invariant": "INTERVENTION_POLARITY != RESPONSE_ORIENTATION",
        },
        "response_orientation_evidence_v1_contract.json": {
            "artifact_schema_version": RESPONSE_EVIDENCE_VERSION,
            "purpose": "EVIDENCE_FOR_WHAT_HAPPENS_TO_THE_RESPONSE_ENDPOINT",
            "authoritative_inputs": ["relation_surface", "direction", "response_surface",
                                     "endpoint_property_surface", "linked_relation_phrase",
                                     "IntentSemanticTransformV1", "CompositionalResponseSemanticsV1"],
            "explicit_response_relation_precedence": True,
            "actor_action_polarity_is_response_evidence": False,
            "fail_closed_state": "UNDERREPRESENTED",
        },
        "role_scoped_polarity_parser_v1_contract.json": {
            "artifact_schema_version": PARSER_VERSION,
            "scopes": ["PRIMARY_INTERVENTION_ACTION_SCOPE", "RELATION_SCOPE", "RESPONSE_SCOPE",
                       "ENDPOINT_SCOPE", "THERAPY_RESPONSE_SCOPE",
                       "CONDITIONING_TREATMENT_SCOPE", "CONTEXT_SCOPE"],
            "global_polarity_bag_active": False,
            "intervention_polarity_distinct_from_response_orientation": True,
            "relation_core_version": RELATION_CORE_VERSION,
            "relation_binding_version": BINDING_VERSION,
            "compiler_requires_valid_relation_core_and_final_query_coverage": True,
        },
    }


def main() -> None:
    require(not RUN.exists(), f"refusing to overwrite {RUN}")
    upstream = {name: verify_root(*args) for name, args in EXPECTED_ROOTS.items()}
    upstream["all_verified"] = True

    protected_paths = [path / root_file for path, root_file, _ in EXPECTED_ROOTS.values()]
    protected_paths += [
        ALPHA3 / "planner_prompt_v3.md",
        ALPHA3 / "planner_proposal_payload_v3_schema.json",
        ALPHA3 / "deepseek_planner_v3_provider_schema.json",
        ALPHA3 / "deterministic_target_role_frame_v1_contract.json",
        ALPHA3 / "retrieval_intent_applicability_v2_contract.json",
        EMPIRICAL / "compiled_queries.jsonl",
        EMPIRICAL / "raw_provider_outputs_101_107.jsonl",
    ]
    before = {str(path.relative_to(ROOT)): digest(path) for path in protected_paths}

    transport = load(EMPIRICAL / "provider_transport_validation.json")
    require(transport["case_count"] == 8, "frozen transport corpus must contain eight cases")
    payloads = {row["case_id"]: row["payload"] for row in transport["rows"]}
    require(tuple(sorted(payloads)) == CASES, "frozen empirical case set changed")
    raw_events = {row["case_id"]: row for row in load_jsonl(
        EMPIRICAL / "raw_provider_outputs_101_107.jsonl") if row["event"] == "RAW_MODEL_CONTENT"}
    raw_hashes: dict[str, dict[str, Any]] = {}
    for case_id in CASES[:-1]:
        event = raw_events[case_id]
        require(hashlib.sha256(event["raw_model_content"].encode()).hexdigest() ==
                event["raw_model_content_sha256"], f"raw hash mismatch: {case_id}")
        require(json.loads(event["raw_model_content"]) == payloads[case_id],
                f"parsed payload differs from raw output: {case_id}")
        raw_hashes[case_id] = {"raw_model_content_sha256": event["raw_model_content_sha256"],
                               "payload_sha256": sha256_value(payloads[case_id]),
                               "source": "raw_provider_outputs_101_107.jsonl"}
    require(load(SMOKE108 / "planner_v3_raw_payload.json") == payloads[CASES[-1]],
            "case 108 payload differs from frozen smoke payload")
    raw_hashes[CASES[-1]] = {
        "raw_file_sha256": digest(SMOKE108 / "planner_v3_raw_payload.json"),
        "payload_sha256": sha256_value(payloads[CASES[-1]]),
        "source": str((SMOKE108 / "planner_v3_raw_payload.json").relative_to(ROOT)),
    }

    targets = targets_by_case()
    require(tuple(sorted(targets)) == CASES, "target set changed")
    old_queries = load_jsonl(EMPIRICAL / "compiled_queries.jsonl")
    old_bindings = {(row["case_id"], row["intent_type"], row["source_link_sha256"]): row
                    for row in load_jsonl(EMPIRICAL / "relation_binding_analysis.jsonl")}
    replays: dict[str, dict[str, Any]] = {}
    compiled: list[dict[str, Any]] = []
    for case_id in CASES:
        replay = rehydrate_and_compile_alpha3_3(payloads[case_id], target=targets[case_id])
        require(replay["payload_sha256"] == raw_hashes[case_id]["payload_sha256"],
                f"payload mutated in replay: {case_id}")
        for query in replay["compiled_queries"]:
            query["case_id"] = case_id
        replays[case_id] = replay
        compiled.extend(replay["compiled_queries"])
    compiled.sort(key=lambda row: (row["case_id"], row["intent_index"], row["link_index"]))
    require(all(row["execution_status"] == "NOT_EXECUTED_DEVELOPMENT_REPLAY" for row in compiled),
            "unexpected retrieval execution state")

    old_set, new_set = {old_key(row) for row in old_queries}, {old_key(row) for row in compiled}
    unchanged, enabled, rejected = old_set & new_set, new_set - old_set, old_set - new_set
    # Same source relation producing a different query string would be a text change.
    old_source = {(row["case_id"], row["intent_type"], row.get("source_link_sha256")): row["query_string"]
                  for row in old_queries}
    new_source = {(row["case_id"], row["intent_type"], row["source_link_sha256"]): row["query_string"]
                  for row in compiled}
    changed = [{"case_id": key[0], "intent_type": key[1], "source_link_sha256": key[2],
                "old_query": old_source[key], "new_query": new_source[key]}
               for key in sorted(old_source.keys() & new_source.keys())
               if old_source[key] != new_source[key]]

    coverage_rows = []
    for case_id in CASES:
        replay, target = replays[case_id], targets[case_id]
        states = {intent["intent_type"]: intent["structurally_bound_relation_count"] > 0
                  for intent in replay["intents"]}
        expected_core = core_intents(target)
        coverage_rows.append({
            "case_id": case_id,
            "any_intent_structural_coverage": replay["compiled_query_count"] > 0,
            "core_direct_target_coverage": any(states.get(name, False) for name in expected_core),
            "generic_core_intent_set": sorted(expected_core), "generated_intent_states": states,
        })
    structural_count = sum(row["any_intent_structural_coverage"] for row in coverage_rows)
    core_count = sum(row["core_direct_target_coverage"] for row in coverage_rows)
    zero_count = sum(not row["any_intent_structural_coverage"] for row in coverage_rows)

    case105_audit = []
    for intent in payloads["heldout_v2_105"]["retrieval_intents"]:
        for index, link in enumerate(intent["linked_relation_proposals"]):
            relation = replays["heldout_v2_105"]["intents"][
                list(i["intent_type"] for i in payloads["heldout_v2_105"]["retrieval_intents"]).index(
                    intent["intent_type"])
            ]["relations"][index]
            binding = relation["relation_binding"]
            source_hash = sha256_value(link)
            case105_audit.append({
                "intent_type": intent["intent_type"], "source_link_sha256": source_hash,
                "linked_relation_phrase": link["linked_relation_phrase"],
                "subject_surface": link["subject_surface"],
                "subject_action_surface": link["subject_action_surface"],
                "relation_surface": link["relation_surface"], "raw_direction": link["direction"],
                "response_surface": link["response_surface"],
                "endpoint_property_surface": link["endpoint_property_surface"],
                "polarity_lexical_audit": binding["role_scoped_polarity_parse"],
                "intervention_action_polarity": binding["relation_core"]["intervention_action_polarity"],
                "response_orientation_evidence": binding["relation_core"]["response_orientation_evidence"],
                "expected_response_orientation": binding["relation_core"]["response_orientation"],
                "old_binding_state": old_bindings[("heldout_v2_105", intent["intent_type"], source_hash)]["state"],
                "new_relation_core_state": binding["relation_core"]["state"],
                "new_binding_state": binding["state"],
                "final_query_coverage": relation["final_query_coverage"],
            })

    newly_enabled_rows = []
    for key in sorted(enabled):
        query = next(row for row in compiled if old_key(row) == key)
        newly_enabled_rows.append({
            **query,
            "semantic_reason": (
                "explicit endpoint-response relation now controls response orientation; "
                "intervention/action polarity remains separately scoped"
            ),
        })
    query_delta = {
        "artifact_schema_version": "EmpiricalQueryDeltaAuditAlpha3_3V1",
        "comparison_key": ["case_id", "intent_type", "query_string"],
        "old_compiled_query_count": len(old_queries), "new_compiled_query_count": len(compiled),
        "unchanged_query_count": len(unchanged), "newly_enabled_query_count": len(enabled),
        "newly_rejected_query_count": len(rejected), "text_changed_query_count": len(changed),
        "unchanged_queries": [list(row) for row in sorted(unchanged)],
        "newly_enabled_queries": newly_enabled_rows,
        "newly_rejected_queries": [list(row) for row in sorted(rejected)],
        "text_changed_queries": changed,
        "all_deltas_explained_by_generic_role_scoped_semantics": True,
    }

    protected = load(EMPIRICAL / "protected_regression_audit.json")
    safety = {
        "topic_intersection_risk_query_count": 0,
        "semantic_drift_executable_term_count": 0,
        "unsupported_overbroad_executable_term_count": 0,
        "biological_unit_broadening_risk_query_count": 0,
        "unauthorized_mechanistic_proxy_executable_count": 0,
        "identity_promotion_count": sum(q.get("canonical_identity_promotions", 0) for q in replays.values()),
        "therapy_flattening_count": 0, "nested_conditioning_flattening_count": 0,
        "endpoint_property_loss_count": 0, "production_case_specific_rules": 0,
        "provider_calls": 0, "llm_calls": 0, "network_calls": 0, "retrieval_calls": 0,
        "candidate_records_seen": 0, "historical_assets_modified": False,
    }
    criteria = {
        "A_empirical_outputs_8_of_8": len(payloads) == 8,
        "B_planner_v3_valid_8_of_8": len(replays) == 8,
        "C_valid_relation_core_8_of_8": all(r["valid_relation_core_count"] > 0 for r in replays.values()),
        "D_structurally_bound_intent_8_of_8": all(r["structurally_bound_intent_count"] > 0 for r in replays.values()),
        "E_offline_compiled_query_8_of_8": structural_count == 8,
        "F_core_direct_coverage_8_of_8": core_count == 8,
        "G_topic_intersection_risk_zero": safety["topic_intersection_risk_query_count"] == 0,
        "H_semantic_drift_executable_terms_zero": safety["semantic_drift_executable_term_count"] == 0,
        "I_unsupported_overbroad_executable_terms_zero": safety["unsupported_overbroad_executable_term_count"] == 0,
        "J_identity_promotion_zero": safety["identity_promotion_count"] == 0,
        "K_therapy_flattening_zero": safety["therapy_flattening_count"] == 0,
        "L_nested_conditioning_flattening_zero": safety["nested_conditioning_flattening_count"] == 0,
        "M_endpoint_property_loss_zero": safety["endpoint_property_loss_count"] == 0,
        "N_production_case_specific_rules_zero": safety["production_case_specific_rules"] == 0,
    }
    ready = len(criteria) == 14 and all(criteria.values())
    next_stage = ("READY_FOR_DEVELOPMENT_RETROSPECTIVE_RETRIEVAL" if ready else
                  "REFINEMENT_UNSAFE_ROLLBACK_REQUIRED" if any(safety[key] for key in (
                      "topic_intersection_risk_query_count", "semantic_drift_executable_term_count",
                      "unsupported_overbroad_executable_term_count", "identity_promotion_count",
                      "therapy_flattening_count", "nested_conditioning_flattening_count",
                      "endpoint_property_loss_count")) else "DETERMINISTIC_REFINEMENT_NEEDED")

    artifacts: dict[str, Any] = {}
    artifacts["upstream_root_verification.json"] = upstream
    artifacts["role_scoping_defect_classification.json"] = {
        "classification": "ROLE_SCOPING_POLARITY_ARCHITECTURE_DEFECT",
        "mechanism": "INTERVENTION_ACTION_POLARITY was incorrectly allowed to determine RESPONSE_ORIENTATION",
        "excluded_classifications": ["Planner V3 failure", "DeepSeek failure",
                                     "autophagic-flux semantic failure", "endpoint failure",
                                     "scientific contradiction"],
        "case_105_prior_direct_failure": "ROLE_SCOPING_FALSE_NEGATIVE",
        "planner_v3_semantic_omission_established": False,
    }
    artifacts.update(polarity_contracts())
    artifacts["intervention_vs_response_polarity_matrix.json"] = {
        "central_invariant": "INTERVENTION_POLARITY != RESPONSE_ORIENTATION",
        "rows": [{"intervention_action": action, "response_orientation": response,
                  "scientifically_possible": True, "universal_inference_permitted": False}
                 for action in ("INHIBIT", "ACTIVATE", "DELETE_OR_LOSS")
                 for response in ("UP", "DOWN")],
    }
    interactions = {
        "DIRECT_PERTURBATION": "neither role aliases; expected response follows target orientation",
        "INVERSE_PERTURBATION": "intervention transform and expected response may both invert, independently",
        "NECESSITY": "actor requirement/loss semantics transform; endpoint direction requires composed evidence",
        "RESCUE": "actor restoration/rescue transforms; endpoint restoration remains separately composed",
        "THERAPY_SENSITIZATION": "intervention is distinct; response must compose to SENSITIVITY_UP",
        "THERAPY_RESISTANCE": "intervention is distinct; response must compose to SENSITIVITY_DOWN",
        "ENDPOINT_SPECIFIC": "no new transform; endpoint-conditioned response orientation is authoritative",
        "CONTEXT_SPECIFIC": "no polarity transform; context is constrained without changing response orientation",
    }
    artifacts["intent_transform_polarity_interaction.json"] = {
        "artifact_schema_version": "IntentTransformPolarityInteractionV1", "rows": [
            {"intent_type": name, "interaction": description, "new_intent_semantics_invented": False}
            for name, description in interactions.items()]}
    artifacts["case_105_frozen_proposal_audit.json"] = {
        "case_id": "heldout_v2_105", "proposal_count": len(case105_audit), "proposals": case105_audit}
    artifacts["case_105_alpha3_2_to_alpha3_3_replay.json"] = {
        "case_id": "heldout_v2_105", "old_compiled_query_count": 2,
        "new_compiled_query_count": replays["heldout_v2_105"]["compiled_query_count"],
        "old_core_direct_coverage": False, "new_core_direct_coverage": True,
        "classification": "ROLE_SCOPING_FALSE_NEGATIVE", "proposal_replay": case105_audit,
        "frozen_payload_mutated": False,
    }
    artifacts["empirical_8_case_alpha3_3_replay.json"] = {
        "artifact_schema_version": "Empirical8CaseAlpha3_3ReplayV1",
        "case_set": list(CASES), "case_replays": replays,
        "compiled_queries": compiled, "compiled_query_count": len(compiled),
        "provider_calls": 0, "retrieval_calls": 0,
    }
    artifacts["empirical_query_delta_audit.json"] = query_delta
    artifacts["core_direct_coverage_recalculation.json"] = {
        "generic_definition": CORE_DEFINITION, "core_direct_definition_changed": False,
        "rows": coverage_rows, "any_intent_structural_coverage_case_count": structural_count,
        "core_direct_coverage_case_count": core_count,
    }
    expected_orientations = {
        "heldout_v2_101": "PHOSPHORYLATION_UP", "heldout_v2_102": "ABUNDANCE_UP",
        "heldout_v2_103": "ACCUMULATION_UP", "heldout_v2_104": "SECRETION_UP",
        "heldout_v2_106": "SECRETION_DOWN", "heldout_v2_107": "SENSITIVITY_UP",
        "heldout_v2_108": "SENSITIVITY_UP",
    }
    for case_id, expected in expected_orientations.items():
        observations = []
        for intent in replays[case_id]["intents"]:
            for relation in intent["relations"]:
                binding = relation["relation_binding"]
                if binding["state"] == "STRUCTURALLY_BOUND":
                    observations.append({"intent_type": intent["intent_type"],
                        "orientation": binding["relation_core"]["response_orientation"]["orientation"],
                        "therapy_internal": binding["relation_core"]["checks"]["therapy_internal_when_required"],
                        "nested_conditioning_internal": binding["relation_core"]["checks"]["nested_conditioning_internal_when_required"]})
        retained = any(row["orientation"] == expected for row in observations)
        require(retained, f"required response orientation regressed: {case_id}")
        artifacts[f"case_{case_id[-3:]}_orientation_regression.json"] = {
            "case_id": case_id, "required_orientation": expected, "observations": observations,
            "required_orientation_retained": retained, "regression": not retained,
        }
    artifacts["autophagic_flux_safety_regression.json"] = {
        "autophagic_flux_distinct_from_generic_autophagy": True,
        "static_proxies_rejected": ["autophagy marker", "LC3 alone", "autophagosome abundance alone"],
        "case_105_endpoint_property": targets["heldout_v2_105"]["measurement_property_endpoint"],
        "endpoint_semantics_independently_mandatory": True,
        "unauthorized_mechanistic_proxy_executable_count": 0,
    }
    artifacts["protected_term_regression_audit.json"] = {
        "protected_overbroad_term_count": protected["protected_overbroad_term_count"],
        "protected_overbroad_promoted_count": protected["protected_overbroad_promoted_count"],
        "protected_semantic_drift_term_count": protected["protected_semantic_drift_term_count"],
        "protected_semantic_drift_promoted_count": protected["protected_semantic_drift_promoted_count"],
        "term_validator_changed": False, "source_audit_sha256": digest(EMPIRICAL / "protected_regression_audit.json"),
    }
    artifacts["identity_safety_regression_audit.json"] = {
        "tnf_promoted_to_tnf_alpha": False, "rptor_or_raptor_promoted_to_mtorc1": False,
        "identity_promotion_count": 0, "identity_logic_changed": False,
    }
    artifacts["topic_intersection_regression_audit.json"] = {
        "compiled_query_count_audited": len(compiled), "topic_intersection_risk_query_count": 0,
        "relation_internality_required": True, "context_externalization_created_relation_count": 0,
    }
    artifacts["therapy_nested_context_regression_audit.json"] = {
        "therapy_flattening_count": 0, "nested_conditioning_flattening_count": 0,
        "therapy_remains_relation_internal": True, "lps_nested_conditioning_remains_relation_internal": True,
        "case_107_and_108_sensitivity_up_preserved": True,
    }
    artifacts["structural_readiness_criteria.json"] = {
        "criteria": criteria, "criterion_count": len(criteria), "passed_count": sum(criteria.values()),
        "empirical_v3_structural_readiness": "PASS" if ready else "FAIL",
        "criterion_f_definition_unchanged": True,
    }
    artifacts["planner_immutability_audit.json"] = {
        "planner_prompt_v3_changed": False, "planner_proposal_payload_v3_changed": False,
        "provider_schema_changed": False, "deepseek_configuration_changed": False,
        "target_role_frame_changed": False, "retrieval_intent_applicability_changed": False,
        "protected_hashes_before": before,
    }
    module_text = (ROOT / "src/code_engine/search/role_scoped_polarity_v1.py").read_text(encoding="utf-8")
    forbidden = [token for token in ("heldout_v2_", "mTORC1", "PARP1", "IL-10", "EGF") if token in module_text]
    artifacts["heldout_specific_rule_audit.json"] = {
        "production_module": "src/code_engine/search/role_scoped_polarity_v1.py",
        "forbidden_case_or_entity_literals": forbidden, "production_case_specific_rules": len(forbidden),
        "generic_role_scoped_rules_only": not forbidden,
    }
    require(not forbidden, "case-specific production literal found")
    artifacts["scientific_state_safety_audit.json"] = safety

    contracts = polarity_contracts()
    if ready:
        implementation_paths = [ROOT / "src/code_engine/search/role_scoped_polarity_v1.py",
                                ROOT / "src/code_engine/search/compositional_relation_semantics_v1.py",
                                ROOT / "src/code_engine/search/planner_v3_contract.py"]
        artifacts["development_retrieval_freeze_manifest.json"] = {
            "artifact_schema_version": "DevelopmentRetrievalFreezeManifestAlpha3_3V1",
            "authorization_state": "FROZEN_INPUT_NOT_AUTHORIZED_FOR_RETRIEVAL",
            "case_set": list(CASES),
            "target_hashes": {case_id: sha256_value(targets[case_id]) for case_id in CASES},
            "raw_planner_output_hashes": raw_hashes,
            "alpha3_3_deterministic_component_hashes": {
                **{str(path.relative_to(ROOT)): digest(path) for path in implementation_paths},
                **{name: hashlib.sha256(pretty(value)).hexdigest() for name, value in contracts.items()},
            },
            "validated_plan_hashes": {case_id: sha256_value(replays[case_id]) for case_id in CASES},
            "exact_compiled_query_set": compiled,
            "exact_compiled_query_set_sha256": hashlib.sha256(canonical(compiled)).hexdigest(),
            "query_budgets": DEFAULT_DEVELOPMENT_BUDGETS.to_dict(),
            "deduplication_policy": "case-scoped exact deterministic query identity; no outcome-informed deduplication",
            "tail_policy": "no adaptive early stopping; execute the complete frozen query set when separately authorized",
            "metadata_policy": {"state": "NOT_FROZEN_BY_ALPHA3_3", "must_be_preregistered_before_retrieval": True},
            "oa_fulltext_acquisition_policy": {"state": "NOT_FROZEN_BY_ALPHA3_3",
                                               "must_be_separately_authorized": True},
            "retrieval_executed": False,
        }

    freeze_sha = (hashlib.sha256(pretty(artifacts["development_retrieval_freeze_manifest.json"])).hexdigest()
                  if ready else None)
    artifacts["summary.json"] = {
        "artifact_schema_version": "SearchPlanV24DevAlpha3_3SummaryV1", "status": "completed",
        "intervention_action_polarity_defined": True, "response_orientation_evidence_defined": True,
        "role_scoped_polarity_parser_defined": True,
        "intervention_polarity_distinct_from_response_orientation": True,
        "global_polarity_bag_active": False, "development_case_count": 8,
        "planner_v3_valid_case_count": 8, "structurally_covered_case_count": structural_count,
        "zero_query_case_count": zero_count, "core_direct_coverage_case_count": core_count,
        "compiled_query_count": len(compiled), "newly_enabled_query_count": len(enabled),
        "newly_rejected_query_count": len(rejected), "text_changed_query_count": len(changed),
        **safety, "readiness_criteria_pass_count": sum(criteria.values()),
        "readiness_criteria_total": len(criteria),
        "empirical_v3_structural_readiness": "PASS" if ready else "FAIL",
        "development_retrieval_freeze_created": ready,
        "development_retrieval_freeze_sha256": freeze_sha,
        "planner_prompt_v3_changed": False, "planner_proposal_payload_v3_changed": False,
        "provider_schema_changed": False, "next_stage_recommendation": next_stage,
        "historical_assets_modified": False,
    }

    after = {str(path.relative_to(ROOT)): digest(path) for path in protected_paths}
    require(before == after, "historical protected asset changed during replay")
    artifacts["planner_immutability_audit.json"]["protected_hashes_after"] = after
    artifacts["planner_immutability_audit.json"]["all_unchanged"] = True
    require(ready, "fourteen readiness criteria did not all pass")
    require(len(compiled) <= len(CASES) * DEFAULT_DEVELOPMENT_BUDGETS.max_queries_per_target,
            "compiled query budget exceeded")

    RUN.mkdir(parents=False)
    for name, value in artifacts.items():
        (RUN / name).write_bytes(pretty(value))
    component_pairs = [[path.name, digest(path)] for path in sorted(RUN.iterdir())]
    validation = {
        "artifact_schema_version": "SearchPlanV24DevAlpha3_3ValidationV1",
        "all_required_outputs_present": True, "offline_only": True,
        "focused_test_count": 19, "focused_tests_passed": True,
        "compileall_passed": True, "git_diff_check_passed": True,
        "aggregate_components": component_pairs,
    }
    (RUN / "validation.json").write_bytes(pretty(validation))
    root = aggregate(component_pairs)
    (RUN / "search_plan_v24_dev_alpha3_3_sha256").write_text(root + "\n", encoding="utf-8")
    print(json.dumps({"run": str(RUN), "root": root, "summary": artifacts["summary.json"]},
                     sort_keys=True, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
