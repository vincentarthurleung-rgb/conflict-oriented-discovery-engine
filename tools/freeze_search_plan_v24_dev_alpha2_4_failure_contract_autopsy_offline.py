"""Read-only alpha2.4 autopsy of the frozen eight-case DeepSeek corpus.

This tool diagnoses provider-schema/local-contract gaps and failed payloads.
It does not call a model, retrieve literature, or change any frozen rule.
"""

from __future__ import annotations

from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
from typing import Any

from code_engine.search.alpha2_linked_relation_v1 import (
    PLANNER_PROPOSAL_PAYLOAD_V2_SCHEMA, _validate_local_schema,
)
from code_engine.search.context_role_ontology_v1 import (
    assess_linked_relation_v1_2, conditioning_context_applicability,
    therapy_context_applicability,
)
from code_engine.search.deepseek_planner_transport_v1 import PROMPT_TEXT
from code_engine.search.proposition_aware_query_planner_v1 import sha256_value
from code_engine.search.retrieval_intent_v1 import INTENT_ORDER, MINIMUM_REQUIRED_DIMENSIONS
from code_engine.search.semantic_slot_compatibility_v1 import (
    SEMANTIC_DIMENSIONS, semantic_slot_compatibility,
    search_anchor_compatibility_v1_1,
)
from tools.freeze_search_plan_v24_dev_alpha2_2_semantic_slot_compatibility_offline import targets_by_case
from tools.run_search_plan_v24_dev_alpha2_1_smoke_101 import verify_root
from tools.run_search_plan_v24_dev_alpha2_3_deepseek_remaining_7 import digest, write_json, write_jsonl

ROOT = Path(__file__).resolve().parents[1]
RUN = ROOT / "runs/20260920_search_plan_v24_dev_alpha2_4_unified_failure_contract_autopsy_offline"
UNIFIED = ROOT / "runs/20260920_search_plan_v24_dev_alpha2_3_deepseek_planner_v2_remaining7"
GENERATION = ROOT / "runs/20260920_search_plan_v24_dev_alpha2_3_deepseek_remaining_7_generation"
SMOKE = ROOT / "runs/20260920_search_plan_v24_dev_alpha2_1_deepseek_planner_v2_smoke_101"
ROOTS = {
    "unified": (UNIFIED, "ecec5273efd2eec70b0a477a9750f9f113444791e78f89d301ccf4f2fb7c9a7b"),
    "alpha2_3": (ROOT / "runs/20260920_search_plan_v24_dev_alpha2_3_context_role_semantics_offline",
                 "13d66f15bfb0f003fa9d6581f892c174b965df42952022c7992958f2da2efa10"),
    "alpha2_2": (ROOT / "runs/20260920_search_plan_v24_dev_alpha2_2_semantic_slot_compatibility_offline",
                 "c54fcb5cd86747fce09b79e90d0d8f833ae2dd6d7fdfeb28ee466ca4b5ca91b4"),
    "alpha2_1": (ROOT / "runs/20260920_search_plan_v24_dev_alpha2_1_deepseek_reasoning_config_offline",
                 "fee80d671ed6e573ca0e18640b4ab87b15aec021e6870f17b0fc3457554b41fc"),
}
CASES = tuple(f"heldout_v2_{n}" for n in range(101, 109))
FAILED = CASES[1:]
TAXONOMY = (
    "MODEL_CONTENT_INSUFFICIENT", "MODEL_CONTENT_INCONSISTENT",
    "PROVIDER_SCHEMA_UNDERCONSTRAINED", "PROVIDER_SCHEMA_CROSS_FIELD_INVARIANT_MISSING",
    "CONCEPT_REF_NAMESPACE_DEFECT", "CONTEXT_REF_NAMESPACE_DEFECT",
    "CONTEXT_ROLE_APPLICABILITY_DEFECT", "LINKED_RELATION_CONTRACT_OVERCONSTRAINED",
    "LINKED_RELATION_CONTENT_MISSING", "SEMANTIC_SLOT_VALIDATOR_FALSE_NEGATIVE",
    "INTENT_AWARE_SEMANTIC_VALIDATION_MISSING", "SEARCH_ANCHOR_VALIDATION_FALSE_NEGATIVE",
    "SEARCH_ONLY_ELIGIBILITY_FALSE_NEGATIVE", "OTHER",
)
PRIMARY = {
    "heldout_v2_102": "PROVIDER_SCHEMA_CROSS_FIELD_INVARIANT_MISSING",
    "heldout_v2_103": "CONTEXT_ROLE_APPLICABILITY_DEFECT",
    "heldout_v2_104": "CONTEXT_ROLE_APPLICABILITY_DEFECT",
    "heldout_v2_105": "CONCEPT_REF_NAMESPACE_DEFECT",
    "heldout_v2_106": "INTENT_AWARE_SEMANTIC_VALIDATION_MISSING",
    "heldout_v2_107": "CONTEXT_REF_NAMESPACE_DEFECT",
    "heldout_v2_108": "CONTEXT_REF_NAMESPACE_DEFECT",
}
SECONDARY = {
    "heldout_v2_102": ["CONCEPT_REF_NAMESPACE_DEFECT", "MODEL_CONTENT_INCONSISTENT",
                       "PROVIDER_SCHEMA_UNDERCONSTRAINED"],
    "heldout_v2_103": ["LINKED_RELATION_CONTRACT_OVERCONSTRAINED",
                       "SEMANTIC_SLOT_VALIDATOR_FALSE_NEGATIVE",
                       "PROVIDER_SCHEMA_CROSS_FIELD_INVARIANT_MISSING"],
    "heldout_v2_104": ["LINKED_RELATION_CONTRACT_OVERCONSTRAINED",
                       "SEARCH_ANCHOR_VALIDATION_FALSE_NEGATIVE",
                       "PROVIDER_SCHEMA_CROSS_FIELD_INVARIANT_MISSING"],
    "heldout_v2_105": ["MODEL_CONTENT_INCONSISTENT", "CONTEXT_REF_NAMESPACE_DEFECT",
                       "PROVIDER_SCHEMA_UNDERCONSTRAINED"],
    "heldout_v2_106": ["MODEL_CONTENT_INSUFFICIENT", "SEMANTIC_SLOT_VALIDATOR_FALSE_NEGATIVE"],
    "heldout_v2_107": ["MODEL_CONTENT_INCONSISTENT", "PROVIDER_SCHEMA_UNDERCONSTRAINED"],
    "heldout_v2_108": ["MODEL_CONTENT_INCONSISTENT", "PROVIDER_SCHEMA_UNDERCONSTRAINED"],
}
GATES = (
    "RAW_DEEPSEEK_PAYLOAD", "PROVIDER_SCHEMA", "PLANNER_V2_PARSE",
    "LOCAL_PLANNER_STRUCTURE", "CONCEPT_REFS", "CONTEXT_REFS",
    "SEMANTIC_SLOTS", "ROLE_APPLICABILITY", "LINKED_RELATION_VALIDATION",
    "SEARCH_ANCHOR_COMPATIBILITY", "SEARCH_ONLY_ELIGIBILITY",
    "RELATION_BINDING", "COVERAGE", "COMPILER_ELIGIBILITY",
)


def require(ok: bool, message: str) -> None:
    if not ok:
        raise ValueError(message)


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def sha_file(path: Path) -> str:
    return digest(path.read_bytes())


def source_payloads() -> tuple[dict[str, dict[str, Any]], dict[str, dict[str, Any]], dict[str, Any]]:
    targets = targets_by_case()
    require(set(targets) == set(CASES), "frozen target set changed")
    summary = read_json(UNIFIED / "unified_8_case_structural_summary.json")
    require(summary["case_count"] == 8, "unified case count changed")
    observations = {row["case_id"]: row for row in summary["cases"]}
    require(set(observations) == set(CASES), "unified observations changed")
    payloads = {"heldout_v2_101": read_json(SMOKE / "planner_v2_raw_payload.json")["parsed_provider_payload"]}
    for case_id in FAILED:
        payloads[case_id] = read_json(GENERATION / case_id / "parsed_provider_payload.json")
    for case_id in CASES:
        _validate_local_schema(payloads[case_id], PLANNER_PROPOSAL_PAYLOAD_V2_SCHEMA)
    return payloads, targets, observations


def concepts_by_intent(intent: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {row["concept_id"]: row for row in intent["search_concepts"]}


def structural_violations(payload: dict[str, Any]) -> list[dict[str, Any]]:
    """Collect independent local invariants without changing the V2 validator."""
    violations = []
    global_concepts: dict[str, list[str]] = defaultdict(list)
    global_terms: dict[str, list[str]] = defaultdict(list)
    global_blueprints: dict[str, list[str]] = defaultdict(list)
    for index, intent in enumerate(payload["retrieval_intents"]):
        intent_id = intent["intent_id"]
        required = intent["required_dimensions"]
        optional = intent["optional_dimensions"]
        minimum = set(MINIMUM_REQUIRED_DIMENSIONS[intent["intent_type"]])
        missing = sorted(minimum - set(required))
        if missing:
            violations.append({"path": f"retrieval_intents[{index}].required_dimensions",
                               "intent_id": intent_id, "kind": "MISSING_MINIMUM_REQUIRED_DIMENSIONS",
                               "detail": missing, "provider_schema_permits": True,
                               "locally_rejected": True})
        if len(required) != len(set(required)) or len(optional) != len(set(optional)) or set(required) & set(optional):
            violations.append({"path": f"retrieval_intents[{index}].required_dimensions/optional_dimensions",
                               "intent_id": intent_id, "kind": "DIMENSION_DUPLICATE_OR_OVERLAP",
                               "detail": sorted(set(required) & set(optional)),
                               "provider_schema_permits": True, "locally_rejected": True})
        concepts = concepts_by_intent(intent)
        for concept in intent["search_concepts"]:
            global_concepts[concept["concept_id"]].append(intent_id)
            for term in concept["proposed_terms"]:
                global_terms[term["term_id"]].append(intent_id)
        for blueprint in intent["candidate_query_blueprints"]:
            bid = blueprint["blueprint_id"]
            global_blueprints[bid].append(intent_id)
            refs = blueprint["concept_ids"]
            if len(refs) != len(set(refs)) or not set(refs) <= set(concepts):
                violations.append({"path": f"{intent_id}/{bid}.concept_ids",
                                   "kind": "BLUEPRINT_CONCEPT_REFS_INVALID",
                                   "detail": sorted(set(refs) - set(concepts)),
                                   "provider_schema_permits": True, "locally_rejected": True})
            if intent["applicability"] == "APPLICABLE" and "relation" in (
                    required + optional) and not blueprint["linked_relation_candidates"]:
                violations.append({"path": f"{intent_id}/{bid}.linked_relation_candidates",
                                   "kind": "MISSING_REQUIRED_LINKED_RELATION",
                                   "provider_schema_permits": True, "locally_rejected": True})
            for link_index, link in enumerate(blueprint["linked_relation_candidates"]):
                path = f"{intent_id}/{bid}/linked_relation_candidates[{link_index}]"
                roles = {
                    "subject_concept_ref": ("subject", [link["subject_concept_ref"]]),
                    "response_concept_ref": ("object_measurement_target", [link["response_concept_ref"]]),
                    "conditioning_context_refs": ("nested_treatment", link["conditioning_context_refs"]),
                    "therapy_context_refs": ("therapy", link["therapy_context_refs"]),
                    "biological_unit_context_ref": ("biological_unit", [link["biological_unit_context_ref"]]
                                                    if link["biological_unit_context_ref"] else []),
                }
                for field, (expected_type, values) in roles.items():
                    for ref in values:
                        actual_type = concepts.get(ref, {}).get("concept_type")
                        if ref not in refs or actual_type != expected_type:
                            violations.append({"path": path + "." + field,
                                               "kind": "INVALID_CONTEXT_REF" if "context" in field else "INVALID_CONCEPT_REF",
                                               "raw_ref": ref, "expected_concept_type": expected_type,
                                               "actual_concept_type": actual_type,
                                               "exists_in_intent": ref in concepts,
                                               "exists_in_blueprint": ref in refs,
                                               "provider_schema_permits": True,
                                               "locally_rejected": True})
    for kind, registry in (("DUPLICATE_CONCEPT_ID_ACROSS_INTENTS", global_concepts),
                           ("DUPLICATE_TERM_ID_ACROSS_INTENTS", global_terms),
                           ("DUPLICATE_BLUEPRINT_ID_ACROSS_INTENTS", global_blueprints)):
        for identifier, paths in registry.items():
            if len(paths) > 1:
                violations.append({"path": kind, "kind": kind, "raw_id": identifier,
                                   "intent_ids": paths, "provider_schema_permits": True,
                                   "locally_rejected": True})
    return violations


def provider_schema_inventory() -> list[dict[str, Any]]:
    """Explicit non-enforced invariants and safe future placement."""
    items = [
        ("minimum_required_dimensions_by_intent_type", "B_REQUEST_SPECIFIC_OR_GENERIC_CONDITIONAL", True),
        ("required_optional_dimensions_disjoint", "A_CROSS_ARRAY_NOT_PRACTICAL", True),
        ("concept_ids_unique_across_intents", "A_MODEL_GENERATED_KEY_UNIQUENESS", True),
        ("term_ids_unique_across_intents", "A_MODEL_GENERATED_KEY_UNIQUENESS", True),
        ("blueprint_concept_refs_exist_in_same_intent", "B_IF_DETERMINISTIC_IDS_PREALLOCATED", True),
        ("linked_subject_ref_has_subject_type", "B_IF_DETERMINISTIC_IDS_PREALLOCATED", True),
        ("linked_response_ref_has_response_type", "B_IF_DETERMINISTIC_IDS_PREALLOCATED", True),
        ("context_refs_have_correct_role_namespace", "B_IF_DETERMINISTIC_IDS_PREALLOCATED", True),
        ("required_linked_relation_nonempty_when_applicable", "B_GENERIC_CONDITIONAL", True),
        ("conditioning_ref_required_only_when_applicable", "C_LOCAL_TARGET_ROLE_AUTHORITY", True),
        ("therapy_ref_required_only_when_applicable", "C_LOCAL_TARGET_ROLE_AUTHORITY", True),
        ("biological_unit_ref_required_when_applicable", "C_LOCAL_TARGET_ROLE_AUTHORITY", True),
        ("semantic_slot_compatible_with_intent", "C_LOCAL_SCIENTIFIC_SEMANTICS", True),
        ("canonical_anchor_compatible_with_frozen_target", "C_LOCAL_IDENTITY_AUTHORITY", True),
        ("linked_phrase_covers_subject_response_endpoint", "C_LOCAL_SEMANTIC_BINDING", True),
    ]
    return [{"invariant": name, "placement_class": placement,
             "enforced_by_frozen_provider_schema": not gap,
             "provider_schema_gap": gap} for name, placement, gap in items]


def schema_leaf_paths() -> list[str]:
    paths = []
    def walk(node: dict[str, Any], path: str) -> None:
        if node.get("type") == "object":
            for field, child in node["properties"].items():
                walk(child, path + "." + field)
        elif node.get("type") == "array":
            walk(node["items"], path + "[]")
        else:
            paths.append(path)
    walk(PLANNER_PROPOSAL_PAYLOAD_V2_SCHEMA, "$")
    return paths


def field_ownership(path: str) -> tuple[str, str]:
    leaf = path.rsplit(".", 1)[-1].replace("[]", "")
    deterministic = {
        "intent_id", "required_dimensions", "target_value", "separate_from_entity_identity",
        "concept_id", "canonical_anchor", "term_id", "blueprint_id",
        "subject_concept_ref", "response_concept_ref", "conditioning_context_refs",
        "therapy_context_refs", "biological_unit_context_ref",
    }
    lexical = {"term", "subject_surface_candidate", "relation_surface_candidate",
               "response_surface_candidate", "endpoint_property_surface_candidate",
               "linked_relation_phrase"}
    duplicate = {"applicability_rationale", "scientific_rationale", "planner_rationale"}
    validation_only = {"separate_from_entity_identity"}
    if leaf in validation_only:
        return "DETERMINISTIC_VALIDATION_ONLY", "constant safety assertion; not model judgment"
    if leaf in deterministic:
        return "DETERMINISTIC_DERIVABLE", "target or post-proposal structure can supply this under stated preconditions"
    if leaf in lexical:
        return "MODEL_LEXICAL_GENERATION_REQUIRED", "retrieval wording is the planner's useful contribution"
    if leaf in duplicate:
        return "UNNECESSARY_DUPLICATE", "explanatory text is not an executable binding input"
    return "MODEL_SEMANTIC_GENERATION_REQUIRED", "retrieval-intent or relation choice requires model proposal"


def reference_feasibility(payloads: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    fields = {
        "subject_concept_ref": "subject",
        "response_concept_ref": "object_measurement_target",
        "biological_unit_context_ref": "biological_unit",
        "therapy_context_refs": "therapy",
        "conditioning_context_refs": "nested_treatment",
        "disease_context_refs_future": "disease",
        "genotype_context_refs_future": "genotype",
    }
    rows = []
    for case_id, payload in payloads.items():
        for intent in payload["retrieval_intents"]:
            concepts = concepts_by_intent(intent)
            for blueprint in intent["candidate_query_blueprints"]:
                for field, role in fields.items():
                    allowed = sorted(ref for ref in blueprint["concept_ids"] if
                                     concepts.get(ref, {}).get("concept_type") == role)
                    rows.append({"case_id": case_id, "intent_id": intent["intent_id"],
                                 "blueprint_id": blueprint["blueprint_id"],
                                 "ref_field": field, "required_role": role,
                                 "allowed_value_count_after_generation": len(allowed),
                                 "allowed_values_after_generation": allowed,
                                 "known_before_inference": False,
                                 "provider_schema_enum_feasible_current_v2": False,
                                 "provider_schema_enum_feasible_after_deterministic_id_allocation": True,
                                 "scientific_risk": "wrong role or fabricated reference can pass provider schema and fail locally"})
    return rows


def complexity(payloads: dict[str, dict[str, Any]], violations: dict[str, list[dict[str, Any]]]) -> list[dict[str, Any]]:
    def keys(value: Any) -> int:
        if isinstance(value, dict):
            return len(value) + sum(keys(v) for v in value.values())
        if isinstance(value, list):
            return sum(keys(v) for v in value)
        return 0
    rows = []
    for case_id, payload in payloads.items():
        intents = payload["retrieval_intents"]
        blueprints = [b for i in intents for b in i["candidate_query_blueprints"]]
        candidates = [l for b in blueprints for l in b["linked_relation_candidates"]]
        concepts = [c for i in intents for c in i["search_concepts"]]
        ref_count = sum(len(b["concept_ids"]) for b in blueprints) + sum(
            2 + len(l["conditioning_context_refs"]) + len(l["therapy_context_refs"]) +
            bool(l["biological_unit_context_ref"]) for l in candidates)
        # Fixed inventory of local cross-field invariant classes; this is not a
        # count of actual validation invocations or a performance metric.
        rows.append({"case_id": case_id, "provider_payload_property_occurrences": keys(payload),
                     "intent_count": len(intents), "blueprint_count": len(blueprints),
                     "linked_candidate_count": len(candidates), "concept_count": len(concepts),
                     "reference_occurrences": ref_count,
                     "cross_field_invariant_classes_required": 15,
                     "local_postvalidation_violation_count_diagnostic": len(violations[case_id]),
                     "local_postvalidation_check_occurrences_estimate":
                        2 * len(intents) + 2 * len(concepts) + 2 * len(blueprints) + 12 * len(candidates),
                     "model_bookkeeping_burden_high": len(intents) > 1 or ref_count > 20})
    return rows


def gate_trace(case_id: str, observation: dict[str, Any], replay: dict[str, Any],
               structural: list[dict[str, Any]]) -> dict[str, Any]:
    first = observation["first_loss_stage"]
    status = {stage: "NOT_REACHED" for stage in GATES}
    for stage in ("RAW_DEEPSEEK_PAYLOAD", "PROVIDER_SCHEMA", "PLANNER_V2_PARSE"):
        status[stage] = "PASS"
    if case_id == "heldout_v2_101":
        status = {stage: "PASS" for stage in GATES}
    elif first == "CONCEPT_REFERENCE_OR_PLANNER_STRUCTURE":
        historical_error = replay["validation"].get("error", "")
        status["LOCAL_PLANNER_STRUCTURE"] = "FAIL" if (
            "intent dimension contract" in historical_error or "duplicate concept ID" in historical_error
        ) else "PASS"
        if status["LOCAL_PLANNER_STRUCTURE"] == "PASS":
            status["CONCEPT_REFS"] = "PASS"
            status["CONTEXT_REFS"] = "FAIL"
    elif first == "SEMANTIC_SLOT_COMPATIBILITY":
        for stage in ("LOCAL_PLANNER_STRUCTURE", "CONCEPT_REFS", "CONTEXT_REFS"):
            status[stage] = "PASS"
        status["SEMANTIC_SLOTS"] = "FAIL"
    elif first == "LINKED_RELATION_VALIDATION":
        for stage in ("LOCAL_PLANNER_STRUCTURE", "CONCEPT_REFS", "CONTEXT_REFS",
                      "SEMANTIC_SLOTS", "ROLE_APPLICABILITY"):
            status[stage] = "PASS"
        status["LINKED_RELATION_VALIDATION"] = "FAIL"
    require(all(value in {"PASS", "FAIL", "NOT_REACHED"} for value in status.values()),
            "invalid gate trace state")
    return {"case_id": case_id, "frozen_first_loss": first,
            "gate_statuses": [{"gate": stage, "status": status[stage]} for stage in GATES],
            "later_static_diagnostics_not_promoted_into_executable_flow": True,
            "static_structural_violation_count": len(structural),
            "static_linked_candidate_diagnostics": [
                {"index": row["linked_candidate_index"],
                 "failed_checks": [name for name, passed in row["binding"]["checks"].items() if not passed]}
                for row in replay["linked_candidates"]]}


def candidate_static_diagnostics(case_id: str, payload: dict[str, Any],
                                 target: dict[str, Any]) -> list[dict[str, Any]]:
    rows = []
    conditioning = conditioning_context_applicability(target)
    therapy = therapy_context_applicability(target)
    for intent in payload["retrieval_intents"]:
        concepts = concepts_by_intent(intent)
        for blueprint in intent["candidate_query_blueprints"]:
            for index, link in enumerate(blueprint["linked_relation_candidates"]):
                try:
                    binding = assess_linked_relation_v1_2(link, target, concepts, blueprint["concept_ids"])
                    failed = [name for name, passed in binding["checks"].items() if not passed]
                    state = binding["state"]
                except (KeyError, TypeError, ValueError) as exc:
                    failed = ["STATIC_DIAGNOSTIC_ERROR:" + type(exc).__name__]
                    state = "UNRESOLVED_DIAGNOSTIC"
                rows.append({"case_id": case_id, "intent_id": intent["intent_id"],
                             "intent_type": intent["intent_type"],
                             "blueprint_id": blueprint["blueprint_id"], "candidate_index": index,
                             "subject_ref": link["subject_concept_ref"],
                             "response_ref": link["response_concept_ref"],
                             "relation_family": link["relation_family"],
                             "direction": link["direction"],
                             "endpoint_property": link["endpoint_property_surface_candidate"],
                             "linked_phrase": link["linked_relation_phrase"],
                             "biological_unit_ref": link["biological_unit_context_ref"],
                             "conditioning_refs": link["conditioning_context_refs"],
                             "therapy_refs": link["therapy_context_refs"],
                             "conditioning_applicability": conditioning["state"],
                             "therapy_applicability": therapy["state"],
                             "static_binding_state": state,
                             "static_failed_checks": failed,
                             "after_prior_failure_diagnostic_only": True})
    return rows


def intent_106_rows(payload: dict[str, Any], target: dict[str, Any]) -> list[dict[str, Any]]:
    expected = {
        "DIRECT_PERTURBATION": ("DECREASE", "decreases / suppresses", "ORIGINAL_TARGET_SEMANTICS"),
        "INVERSE_PERTURBATION": ("INCREASE", "increases", "INTENT_TRANSFORMED_EXPECTED_SEMANTICS"),
        "NECESSITY": ("REQUIRE", "required for", "INTENT_TRANSFORMED_EXPECTED_SEMANTICS"),
        "RESCUE": ("RESCUE", "rescues", "INTENT_TRANSFORMED_EXPECTED_SEMANTICS"),
    }
    rows = []
    for intent in payload["retrieval_intents"]:
        direction_concepts = [c for c in intent["search_concepts"] if c["concept_type"] == "direction"]
        relation_concepts = [c for c in intent["search_concepts"] if c["concept_type"] == "relation"]
        evidence_concepts = [c for c in intent["search_concepts"] if c["concept_type"] == "evidence_mode"]
        def first(concepts: list[dict[str, Any]]) -> str | None:
            if not concepts:
                return None
            value = concepts[0]["canonical_anchor"]
            return value[0] if isinstance(value, list) and value else value
        actual_direction, actual_relation, evidence = first(direction_concepts), first(relation_concepts), first(evidence_concepts)
        expected_direction, expected_relation, comparison = expected[intent["intent_type"]]
        rows.append({"intent_id": intent["intent_id"], "intent_type": intent["intent_type"],
                     "original_proposition_direction": "DECREASE",
                     "expected_retrieval_formulation_direction_hypothesis": expected_direction,
                     "actual_proposed_direction": actual_direction,
                     "original_relation_family": target["relation_family"],
                     "expected_intent_conditioned_relation_family_hypothesis": expected_relation,
                     "actual_relation_family": actual_relation,
                     "semantic_slot_validator_direction": semantic_slot_compatibility(
                         "direction", actual_direction, target),
                     "semantic_slot_validator_relation": semantic_slot_compatibility(
                         "relation", actual_relation, target),
                     "actual_evidence_mode": evidence,
                     "semantic_slot_validator_evidence_mode": semantic_slot_compatibility(
                         "evidence_mode", evidence, target),
                     "appropriate_comparison_hypothesis": comparison,
                     "intent_transformed_scientific_equivalence_proven": False})
    return rows


def context_ref_violations(case_id: str, payload: dict[str, Any],
                           target: dict[str, Any]) -> list[dict[str, Any]]:
    rows = []
    for intent in payload["retrieval_intents"]:
        concepts = concepts_by_intent(intent)
        for blueprint in intent["candidate_query_blueprints"]:
            for index, link in enumerate(blueprint["linked_relation_candidates"]):
                for ref in link["conditioning_context_refs"]:
                    actual = concepts.get(ref, {}).get("concept_type")
                    if actual == "nested_treatment":
                        continue
                    kind = "INVENTED_ID" if actual is None else (
                        "DISEASE_CONTEXT_CONFUSION" if actual == "disease" else
                        "GENOTYPE_CONTEXT_CONFUSION" if actual == "genotype" else
                        "THERAPY_CONTEXT_CONFUSION" if actual == "therapy" else "WRONG_ROLE")
                    rows.append({"case_id": case_id, "intent_id": intent["intent_id"],
                                 "blueprint_id": blueprint["blueprint_id"],
                                 "linked_candidate_index": index,
                                 "raw_emitted_ref": ref,
                                 "expected_ref_namespace": "nested_treatment concept ID in same blueprint",
                                 "actual_ref_namespace": actual or "MISSING",
                                 "model_intended_semantic_role_inferred_from_concept_type": actual,
                                 "referenced_concept_exists_under_other_role": actual is not None,
                                 "referenced_concept_in_blueprint": ref in blueprint["concept_ids"],
                                 "provider_schema_allowed_invalid_value": True,
                                 "prompt_exposed_exact_legal_ids": False,
                                 "error_class": kind,
                                 "therapy_applicability": therapy_context_applicability(target)["state"],
                                 "conditioning_applicability": conditioning_context_applicability(target)["state"]})
    return rows


def markdown(path: Path, title: str, paragraphs: list[str]) -> None:
    require(not path.exists(), f"refusing overwrite: {path.name}")
    path.write_text("# " + title + "\n\n" + "\n\n".join(paragraphs) + "\n", encoding="utf-8")


def fmt_violations(rows: list[dict[str, Any]]) -> str:
    if not rows:
        return "No additional static structural violation found."
    return "\n".join("- `" + str(row.get("kind")) + "` at `" + str(row.get("path")) + "`" +
                     (": " + str(row.get("detail")) if row.get("detail") else "") +
                     ("; ID=`" + str(row.get("raw_id")) + "`" if row.get("raw_id") else "") +
                     ("; ref=`" + str(row.get("raw_ref")) + "`" if row.get("raw_ref") else "")
                     for row in rows)


def main() -> None:
    require(not RUN.exists(), "alpha2.4 autopsy run already exists")
    upstream = {name: verify_root(path, expected) for name, (path, expected) in ROOTS.items()}
    payloads, targets, observations = source_payloads()
    source_hashes = {str(path.relative_to(ROOT)): sha_file(path) for path in (
        ROOT / "src/code_engine/search/alpha2_linked_relation_v1.py",
        ROOT / "src/code_engine/search/semantic_slot_compatibility_v1.py",
        ROOT / "src/code_engine/search/context_role_ontology_v1.py",
        ROOT / "src/code_engine/search/deepseek_planner_transport_v1_1.py",
        ROOT / "tools/freeze_search_plan_v24_dev_alpha2_4_failure_contract_autopsy_offline.py",
    )}
    violations = {case_id: structural_violations(payloads[case_id]) for case_id in CASES}
    replay = {case_id: read_json(UNIFIED / "unified_case_replays" / case_id / "deterministic_replay.json")
              for case_id in CASES}
    static_candidates = {case_id: candidate_static_diagnostics(case_id, payloads[case_id], targets[case_id])
                         for case_id in CASES}
    traces = [gate_trace(case_id, observations[case_id], replay[case_id], violations[case_id]) for case_id in CASES]
    require(len(traces) == 8 and all(len(row["gate_statuses"]) == len(GATES) for row in traces),
            "incomplete eight-case gate trace")
    expected_frozen = {
        "heldout_v2_101": "NONE",
        "heldout_v2_102": "CONCEPT_REFERENCE_OR_PLANNER_STRUCTURE",
        "heldout_v2_103": "LINKED_RELATION_VALIDATION",
        "heldout_v2_104": "LINKED_RELATION_VALIDATION",
        "heldout_v2_105": "CONCEPT_REFERENCE_OR_PLANNER_STRUCTURE",
        "heldout_v2_106": "SEMANTIC_SLOT_COMPATIBILITY",
        "heldout_v2_107": "CONCEPT_REFERENCE_OR_PLANNER_STRUCTURE",
        "heldout_v2_108": "CONCEPT_REFERENCE_OR_PLANNER_STRUCTURE",
    }
    require({row["case_id"]: row["frozen_first_loss"] for row in traces} == expected_frozen,
            "frozen first-loss observations changed")
    # Case-level attribution is one primary cause per historical first loss.
    attributions = []
    for case_id in FAILED:
        attributions.append({"case_id": case_id,
                             "frozen_first_loss": observations[case_id]["first_loss_stage"],
                             "first_loss_primary_cause": PRIMARY[case_id],
                             "secondary_causes": SECONDARY[case_id],
                             "taxonomy_version": "Alpha2_4FailureTaxonomyV1",
                             "scientific_correctness_or_retrieval_performance_inferred": False})
    blueprint_attributions = []
    candidate_attributions = []
    for case_id in FAILED:
        payload = payloads[case_id]
        historical_replay = replay[case_id]
        evaluated = {(x["intent_id"], x["blueprint_id"], x["linked_candidate_index"]): x
                     for x in historical_replay["linked_candidates"]}
        for intent in payload["retrieval_intents"]:
            for blueprint in intent["candidate_query_blueprints"]:
                blueprint_attributions.append({"case_id": case_id, "intent_id": intent["intent_id"],
                    "blueprint_id": blueprint["blueprint_id"],
                    "first_loss_primary_cause": PRIMARY[case_id],
                    "secondary_causes": SECONDARY[case_id],
                    "primary_cause_inherited_from_case_first_gate": True,
                    "blueprint_scientific_invalidity_not_inferred_from_unreached_gates": True})
                for index, link in enumerate(blueprint["linked_relation_candidates"]):
                    key = (intent["intent_id"], blueprint["blueprint_id"], index)
                    earlier = evaluated.get(key)
                    static = next(x for x in static_candidates[case_id] if x["intent_id"] == intent["intent_id"]
                                  and x["blueprint_id"] == blueprint["blueprint_id"] and x["candidate_index"] == index)
                    candidate_attributions.append({"case_id": case_id, "intent_id": intent["intent_id"],
                        "blueprint_id": blueprint["blueprint_id"], "candidate_index": index,
                        "candidate_sha256": sha256_value(link),
                        "first_loss_primary_cause": PRIMARY[case_id],
                        "secondary_causes": SECONDARY[case_id],
                        "reached_executable_candidate_gate": earlier is not None,
                        "static_failed_checks": static["static_failed_checks"],
                        "static_checks_are_diagnostic_not_repaired": True})
    require(len(attributions) == 7 and len(blueprint_attributions) == 19 and len(candidate_attributions) == 24,
            "failed blueprint/candidate census changed")
    intent106 = intent_106_rows(payloads["heldout_v2_106"], targets["heldout_v2_106"])
    require([r["intent_type"] for r in intent106] == [
        "DIRECT_PERTURBATION", "INVERSE_PERTURBATION", "NECESSITY", "RESCUE"],
        "case 106 intent set changed")
    refs107 = context_ref_violations("heldout_v2_107", payloads["heldout_v2_107"], targets["heldout_v2_107"])
    refs108 = context_ref_violations("heldout_v2_108", payloads["heldout_v2_108"], targets["heldout_v2_108"])
    require(len(refs107) == 4 and len(refs108) == 5,
            "invalid context-ref census changed")
    schema_inventory = provider_schema_inventory()
    ref_feasibility = reference_feasibility(payloads)
    complexity_rows = complexity(payloads, violations)
    leaves = schema_leaf_paths()
    ownership = [{"field_path": path, "ownership": field_ownership(path)[0],
                  "reason": field_ownership(path)[1]} for path in leaves]
    require(len(leaves) == 30, "PlannerProposalPayloadV2 field inventory changed")
    RUN.mkdir(parents=True, exist_ok=False)
    write_json(RUN / "upstream_root_verification.json", upstream)
    write_jsonl(RUN / "unified_8_case_gate_trace.jsonl", traces)
    write_json(RUN / "failure_primary_cause_decomposition.json", {
        "taxonomy": list(TAXONOMY), "failed_case_count": 7,
        "case_attributions": attributions,
        "failed_blueprint_count": len(blueprint_attributions),
        "failed_blueprint_attributions": blueprint_attributions,
        "failed_raw_candidate_count": len(candidate_attributions),
        "failed_candidate_attributions": candidate_attributions,
        "one_primary_cause_per_failed_case_blueprint_candidate": True,
        "no_payload_repaired": True})
    write_json(RUN / "provider_schema_adequacy_audit.json", {
        "provider_schema_sha256": sha256_value(PLANNER_PROPOSAL_PAYLOAD_V2_SCHEMA),
        "all_eight_provider_schema_valid": True,
        "local_full_structure_or_ref_valid_case_count": 4,
        "local_invariant_inventory": schema_inventory,
        "provider_schema_gap_count": sum(r["provider_schema_gap"] for r in schema_inventory),
        "direction_enum_enforced_by_provider_schema": True,
        "intent_type_enum_enforced_by_provider_schema": True,
        "concept_type_enum_enforced_by_provider_schema": True,
        "all_provider_schema_valid_but_locally_rejected_case_ids": [
            case_id for case_id in CASES if not observations[case_id]["planner_v2_payload_valid"]],
        "provider_json_object_mode_is_not_remote_cross_field_enforcement": True})
    write_json(RUN / "request_specific_ref_enum_feasibility.json", {
        "current_v2_model_generates_concept_ids": True,
        "valid_actual_ids_known_before_inference": False,
        "request_specific_ref_enums_feasible_current_v2": False,
        "feasible_only_after_deterministic_concept_id_allocation": True,
        "field_blueprint_examples": ref_feasibility,
        "exact_role_ref_enums_not_implemented": True})
    for case_id, number in (("heldout_v2_102", 102), ("heldout_v2_105", 105)):
        current = payloads[case_id]
        parts = [
            f"Frozen raw payload contains {len(current['retrieval_intents'])} intents and " +
            f"{sum(len(b['linked_relation_candidates']) for i in current['retrieval_intents'] for b in i['candidate_query_blueprints'])} linked candidates.",
            "Local post-validation violations (including latent violations after the historical first loss):\n" +
            fmt_violations(violations[case_id]),
            "Prompt V2 requires a linked actor-response phrase and distinct roles, but does not state the "
            "minimum required_dimensions for each intent type or global uniqueness of model-generated IDs. "
            "The provider schema requires the fields and their JSON types; it does not enforce these cross-field invariants.",
            "Thus a provider-schema-valid object can fail local validation. Frozen target information in other "
            "intents does not automatically supply a missing required dimension in this blueprint. No ID or field was repaired.",
        ]
        if number == 102:
            parts.append("The ENDPOINT_SPECIFIC and CONTEXT_SPECIFIC intents put evidence_mode in optional_dimensions "
                         "rather than required_dimensions. Their direct-intent peer does contain evidence_mode; "
                         "the first failure is representational, not proof that the proposition's evidence mode was unknown. "
                         "Shared concept IDs across intents are a latent namespace ambiguity.")
        else:
            null_refs = [{"intent": i["intent_id"], "concept_id": c["concept_id"],
                          "concept_type": c["concept_type"]} for i in current["retrieval_intents"]
                         for c in i["search_concepts"] if c["canonical_anchor"] is None]
            proxy_terms = [t["term"] for i in current["retrieval_intents"] for c in i["search_concepts"]
                           for t in c["proposed_terms"] if any(stem in t["term"].casefold()
                           for stem in ("rptor", "raptor"))]
            parts.append("Every frozen linked phrase retains dynamic autophagic-flux wording; no static LC3 marker "
                         "was accepted as flux. The raw proposal nevertheless contains null-anchor role concepts "
                         f"{null_refs} and RPTOR/Raptor search terms {proxy_terms}. The latter have no automatic "
                         "mTORC1 identity authority and produced no executable query. The necessity phrase uses "
                         "an essential-component proxy; its scientific equivalence remains unverified.")
            parts.append("The response ref in the direct blueprint points to an object_measurement_target concept "
                         "for autophagic flux; the first local failure is the repeated concept-ID namespace, "
                         "not a proven wrong response reference.")
        markdown(RUN / f"case_{number}_planner_structure_autopsy.md",
                 f"Case {number}: frozen planner-structure autopsy", parts)
    for case_id, number in (("heldout_v2_103", 103), ("heldout_v2_104", 104)):
        candidate_lines = []
        for row in static_candidates[case_id]:
            candidate_lines.append(
                f"Candidate {row['candidate_index']} ({row['intent_id']} / {row['blueprint_id']}): "
                f"subject_ref=`{row['subject_ref']}`; response_ref=`{row['response_ref']}`; "
                f"relation=`{row['relation_family']}`; direction=`{row['direction']}`; "
                f"endpoint=`{row['endpoint_property']}`; linked_phrase=`{row['linked_phrase']}`; "
                f"biological_unit_ref=`{row['biological_unit_ref']}`; "
                f"conditioning_applicability=`{row['conditioning_applicability']}`; "
                f"therapy_applicability=`{row['therapy_applicability']}`; "
                f"conditioning_refs={row['conditioning_refs']}; therapy_refs={row['therapy_refs']}; "
                f"failed_checks={row['static_failed_checks']}.")
        paragraphs = [
            "\n\n".join(candidate_lines),
            "The frozen target's stimulation is already the PRIMARY_INTERVENTION_ACTION, so conditioning "
            "applicability is NOT_APPLICABLE. Every candidate nevertheless fills conditioning_context_refs "
            "with the primary-action concept. That is a role/representation conflict at the frozen V1.2 gate, "
            "not proof that the actor-response phrase is merely a keyword bag.",
        ]
        if number == 103:
            paragraphs.append("Candidate 0 says 'nuclear β-catenin accumulation', but the endpoint lexical check "
                              "looks for a contiguous 'nuclear accumulation' variant and flags it. This is a "
                              "diagnostic lexical overconstraint; it does not rescue the independent context-ref "
                              "failure. Candidate 1 explicitly says nuclear localization; candidate 2 says "
                              "nuclear translocation. The target's nuclear endpoint and intestinal epithelial "
                              "unit must remain mandatory.")
        else:
            paragraphs.append("The candidate's response_surface_candidate contains the disjunction "
                              "'PGE2 / prostaglandin E2', while its linked phrase contains PGE2 and the explicit "
                              "secretion/release endpoint. Whole-surface phrase containment fails, although the "
                              "canonical PGE2 token is present. This is a representational/anchor-check "
                              "overconstraint hypothesis, independent of the redundant conditioning ref.")
        paragraphs.append("No linked candidate was modified or promoted; all findings after its frozen first loss are diagnostic.")
        markdown(RUN / f"case_{number}_linked_validation_autopsy.md",
                 f"Case {number}: linked-validation autopsy", paragraphs)
    intent_lines = []
    for row in intent106:
        intent_lines.append(
            f"- `{row['intent_type']}`: original direction `DECREASE`; expected intent-formulation "
            f"`{row['expected_retrieval_formulation_direction_hypothesis']}`; proposed "
            f"`{row['actual_proposed_direction']}`; original relation `{row['original_relation_family']}`; "
            f"expected `{row['expected_intent_conditioned_relation_family_hypothesis']}`; proposed "
            f"`{row['actual_relation_family']}`; frozen direction-state "
            f"`{row['semantic_slot_validator_direction']['state']}`; relation-state "
            f"`{row['semantic_slot_validator_relation']['state']}`; evidence-state "
            f"`{row['semantic_slot_validator_evidence_mode']['state']}`.")
    markdown(RUN / "case_106_intent_semantic_autopsy.md", "Case 106: intent-aware semantic autopsy", [
        "\n".join(intent_lines),
        "`SemanticSlotCompatibilityV1` receives only dimension, proposed value, and the original frozen target; "
        "it receives no intent type. The direct suppression formulation matches the original direction. "
        "Inverse, necessity, and rescue formulations are compared against that same original suppression "
        "direction, yielding an intent-aware validation gap. This does not prove those alternatives are "
        "scientifically valid: their actor/polarity and evidence-mode claims still need separate checks.",
        "LPS remains a REQUIRED conditioning treatment and macrophage remains the biological-unit context. "
        "The frozen proposal and validator were not repaired.",
    ])
    for number, ref_rows in ((107, refs107), (108, refs108)):
        ref_lines = [
            f"- `{row['intent_id']}` / `{row['blueprint_id']}` candidate {row['linked_candidate_index']}: "
            f"emitted `{row['raw_emitted_ref']}` in conditioning_context_refs; expected "
            f"`nested_treatment` namespace, actual `{row['actual_ref_namespace']}`; "
            f"in-blueprint={row['referenced_concept_in_blueprint']}; class `{row['error_class']}`."
            for row in ref_rows]
        markdown(RUN / f"case_{number}_context_ref_autopsy.md",
                 f"Case {number}: context-ref namespace autopsy", [
            "\n".join(ref_lines),
            "Every listed ID exists as a concept under another role, so these are wrong-namespace refs rather "
            "than invented IDs. Provider JSON Schema allows arbitrary strings in conditioning_context_refs; "
            "Prompt V2 does not enumerate legal IDs or say to copy role-typed IDs exactly.",
            "The frozen target requires therapy (trametinib for 107; temozolomide for 108), and the model "
            "also supplied therapy_context_refs. The disease/genotype context cannot be laundered through "
            "conditioning refs. No ref was moved or repaired.",
        ])
    write_json(RUN / "intent_semantic_transform_architecture_audit.json", {
        "component_hypothesis": "IntentSemanticTransformV1",
        "needed": True, "implemented": False,
        "input_contract": ["ScientificPropositionTargetV1", "RetrievalIntentV1"],
        "hypothesized_output": ["expected_actor_role", "intervention_polarity", "relation_family",
                               "direction", "response_orientation", "therapy_orientation",
                               "conditioning_treatment_orientation"],
        "case_106_intent_rows": intent106,
        "current_semantic_slot_validator_accepts_intent_type": False,
        "scientific_equivalence_of_alternate_intents_not_presumed": True})
    semantics_matrix = []
    transformed = {"INVERSE_PERTURBATION", "NECESSITY", "RESCUE", "THERAPY_RESISTANCE"}
    additional = {"FUNCTIONAL_CHAIN", "THERAPY_SENSITIZATION", "ENDPOINT_SPECIFIC", "CONTEXT_SPECIFIC"}
    present = {name: [case_id for case_id in CASES if any(i["intent_type"] == name
               for i in payloads[case_id]["retrieval_intents"])] for name in INTENT_ORDER}
    for name in INTENT_ORDER:
        comparison = ("INTENT_TRANSFORMED_EXPECTED_SEMANTICS" if name in transformed else
                      "ORIGINAL_SEMANTICS_PLUS_ADDITIONAL_CONSTRAINTS" if name in additional else
                      "ORIGINAL_TARGET_SEMANTICS")
        semantics_matrix.append({"intent_type": name, "frozen_cases_present": present[name],
                                 "comparison_hypothesis": comparison,
                                 "requires_future_intent_transform": name in transformed,
                                 "scientific_equivalence_assumed": False})
    write_json(RUN / "intent_validation_semantics_matrix.json", {
        "intent_type_count": len(INTENT_ORDER), "matrix": semantics_matrix,
        "classification_is_architecture_diagnosis_not_rule_change": True})
    write_json(RUN / "context_ref_schema_ergonomics.json", {
        "case_107_invalid_conditioning_ref_occurrences": len(refs107),
        "case_108_invalid_conditioning_ref_occurrences": len(refs108),
        "invalid_ref_details": refs107 + refs108,
        "provider_schema_conditioning_refs_item_type": "unconstrained string",
        "exact_enum_possible_before_current_v2_inference": False,
        "exact_enum_possible_after_deterministic_id_allocation": True,
        "role_typed_refs_should_not_be_conflated": True,
        "schema_unchanged": True})
    write_json(RUN / "prompt_reference_ergonomics_audit.json", {
        "prompt_sha256": sha256_value(PROMPT_TEXT),
        "prompt_requires_linked_actor_response_phrase": "single phrase" in PROMPT_TEXT,
        "prompt_mentions_distinct_conditioning_and_therapy_roles": "distinct roles" in PROMPT_TEXT,
        "prompt_lists_exact_legal_ref_ids": False,
        "prompt_explains_role_ref_namespace": False,
        "prompt_states_required_not_applicable_role_states": False,
        "prompt_requires_exact_id_copying": False,
        "frozen_prompt_plausibly_ambiguous_about_ref_bookkeeping": True,
        "prompt_modified": False})
    write_json(RUN / "cross_field_invariant_inventory.json", {
        "invariant_count": len(schema_inventory),
        "invariants": schema_inventory,
        "safe_future_provider_schema_candidates": [r["invariant"] for r in schema_inventory if
            r["placement_class"].startswith("B_")],
        "remain_local_deterministic": [r["invariant"] for r in schema_inventory if
            r["placement_class"].startswith("C_")],
        "cannot_reasonably_encode_under_current_generated_ids": [r["invariant"] for r in schema_inventory if
            r["placement_class"].startswith("A_")],
        "no_schema_change_implemented": True})
    write_json(RUN / "planner_v2_complexity_audit.json", {
        "measurement_definitions": {
            "provider_payload_property_occurrences": "recursive count of JSON object keys, not unique schema fields",
            "reference_occurrences": "blueprint concept_ids plus linked role references",
            "local_postvalidation_check_occurrences_estimate": "2 per intent, concept, blueprint and 12 per linked candidate; complexity proxy only",
        },
        "case_rows": complexity_rows,
        "high_burden_case_count": sum(row["model_bookkeeping_burden_high"] for row in complexity_rows),
        "model_bookkeeping_burden_high": True,
        "no_performance_score": True})
    rehydration = [
        ("intent_id", "assign after model chooses intent type/position"),
        ("required_dimensions", "derive minimum and frozen required contexts from intent/target"),
        ("biological_unit_context.target_value", "echo frozen target biological unit"),
        ("biological_unit_context.separate_from_entity_identity", "constant true safety invariant"),
        ("concept_id", "assign after semantic concept set is selected"),
        ("canonical_anchor", "echo frozen target authority for chosen concept type"),
        ("proposed_terms.term_id", "assign after lexical terms are selected"),
        ("blueprint_id", "assign after blueprint set is selected"),
        ("subject_concept_ref", "derive only if unique subject concept in blueprint"),
        ("response_concept_ref", "derive only if unique response concept in blueprint"),
        ("biological_unit_context_ref", "derive only if unique required unit concept"),
        ("therapy_context_refs", "derive only if therapy REQUIRED and unique typed therapy concept"),
        ("conditioning_context_refs", "derive only if conditioning REQUIRED and unique typed context concept"),
    ]
    write_json(RUN / "deterministic_rehydration_candidate_audit.json", {
        "candidate_count": len(rehydration),
        "candidates": [{"field": name, "precondition": condition,
                        "classification": "DETERMINISTIC_REHYDRATION_CANDIDATE",
                        "model_semantic_freedom_preserved_if_precondition_holds": True}
                       for name, condition in rehydration],
        "unambiguous_role_concept_uniqueness_required_for_ref_derivation": True,
        "no_field_migrated_in_this_run": True})
    write_json(RUN / "planner_field_ownership_v2_audit.json", {
        "provider_payload_leaf_field_count": len(leaves),
        "ownership_rows": ownership,
        "ownership_class_counts": dict(Counter(row["ownership"] for row in ownership)),
        "model_semantic_and_lexical_content_kept_distinct_from_bookkeeping": True,
        "no_v3_schema_or_prompt_created": True})
    # Counts are case-incidence diagnostics, not disjoint failure labels or a
    # scientific-accuracy score. Unverified proxy risk is not called omission.
    incidences = {
        "genuine_model_semantic_omission": [],
        "model_structural_inconsistency": ["heldout_v2_102", "heldout_v2_103", "heldout_v2_104",
                                           "heldout_v2_105", "heldout_v2_107", "heldout_v2_108"],
        "provider_schema_underconstraint": ["heldout_v2_102", "heldout_v2_103", "heldout_v2_104",
                                           "heldout_v2_105", "heldout_v2_107", "heldout_v2_108"],
        "deterministic_ref_generation_failure": ["heldout_v2_102", "heldout_v2_105",
                                                 "heldout_v2_107", "heldout_v2_108"],
        "deterministic_validator_false_negative": ["heldout_v2_103", "heldout_v2_104", "heldout_v2_106"],
        "intent_semantic_validation_gap": ["heldout_v2_106"],
        "contract_overconstraint": ["heldout_v2_103", "heldout_v2_104"],
        "ambiguous_ownership_or_duplicated_field": ["heldout_v2_102", "heldout_v2_103", "heldout_v2_104",
                                                    "heldout_v2_105", "heldout_v2_107", "heldout_v2_108"],
    }
    counts = {
        "counting_unit": "failed_case_incidence_nonexclusive_except_primary_cause",
        "failed_case_count": 7,
        "primary_cause_counts": dict(Counter(PRIMARY.values())),
        "incidence_case_ids": incidences,
        **{name + "_count": len(case_ids) for name, case_ids in incidences.items()},
        "no_confirmed_whole_case_scientific_semantic_omission": True,
        "nonexecutable_proxy_terms_not_mistaken_for_confirmed_equivalence": True,
    }
    write_json(RUN / "unified_failure_counts.json", counts)
    recommendation = "FULL_CONTRACT_SIMPLIFICATION_NEEDED"
    write_json(RUN / "next_architecture_recommendation.json", {
        "recommendation": recommendation,
        "why_not_planner_v3_only": "frozen post-validation has intent-unaware and phrase-binding overconstraints",
        "why_not_deterministic_alpha2_5_only": "model carries excessive global IDs and context refs",
        "why_not_provider_schema_only": "actual ref IDs are generated by the model, so exact enums are unavailable before inference",
        "priority": ["freeze field ownership", "separate model semantics/lexicon from deterministic IDs",
                     "design intent-conditioned expected semantics", "then assess smaller provider schema/prompt"],
        "no_planner_v3_or_alpha2_5_implemented": True,
        "no_additional_model_or_retrieval_calls_authorized": True})
    write_json(RUN / "heldout_specific_rule_audit.json", {
        "production_case_specific_rules": 0,
        "case_ids_used_only_as_frozen_audit_keys": True,
        "no_target_specific_validator_exception_added": True})
    for _, (path, expected) in ROOTS.items():
        verify_root(path, expected)
    require(all(sha_file(ROOT / name) == value for name, value in source_hashes.items()),
            "source changed during offline autopsy")
    write_json(RUN / "scientific_state_safety_audit.json", {
        "historical_assets_modified": False,
        "upstream_roots_reverified_after_audit": True,
        "protected_source_hashes": source_hashes,
        "provider_calls": 0, "llm_calls": 0, "network_calls": 0,
        "retrieval_calls": 0, "candidate_records_seen": 0,
        "prompt_modified": False, "provider_schema_modified": False,
        "validator_modified": False, "ontology_modified": False,
        "binding_modified": False, "compiler_modified": False,
        "budgets_modified": False,
        "scientific_or_retrieval_performance_claims": False})
    summary = {"artifact_schema_version": "Alpha2_4UnifiedFailureContractAutopsySummaryV1",
        "status": "completed", "development_case_count": 8, "failed_case_count": 7,
        "all_8_case_gate_traces_complete": True,
        "all_7_failed_cases_have_primary_cause": True,
        "planner_structure_first_loss_count": 2,
        "linked_validation_first_loss_count": 2,
        "semantic_slot_first_loss_count": 1,
        "invalid_context_ref_first_loss_count": 2,
        "genuine_model_semantic_omission_count": counts["genuine_model_semantic_omission_count"],
        "model_structural_inconsistency_count": counts["model_structural_inconsistency_count"],
        "provider_schema_underconstraint_count": counts["provider_schema_underconstraint_count"],
        "deterministic_ref_generation_failure_count": counts["deterministic_ref_generation_failure_count"],
        "deterministic_validator_false_negative_count": counts["deterministic_validator_false_negative_count"],
        "intent_semantic_validation_gap_count": counts["intent_semantic_validation_gap_count"],
        "contract_overconstraint_count": counts["contract_overconstraint_count"],
        "request_specific_ref_enums_feasible": False,
        "intent_semantic_transform_needed": True,
        "planner_bookkeeping_burden_high": True,
        "deterministic_rehydration_candidate_count": len(rehydration),
        "provider_schema_vs_local_validation_gap_quantified": True,
        "next_architecture_recommendation": recommendation,
        "production_case_specific_rules": 0,
        "provider_calls": 0, "llm_calls": 0, "network_calls": 0,
        "retrieval_calls": 0, "historical_assets_modified": False}
    write_json(RUN / "summary.json", summary)
    components = [[path.name, sha_file(path)] for path in sorted(RUN.iterdir()) if path.is_file()
                  and path.name not in {"validation.json", "search_plan_v24_dev_alpha2_4_sha256"}]
    root = sha256_value(components)
    write_json(RUN / "validation.json", {
        "artifact_schema_version": "Alpha2_4UnifiedFailureContractAutopsyValidationV1",
        "status": "PASS", "aggregate_components": components,
        "search_plan_v24_dev_alpha2_4_sha256": root,
        "all_required_outputs_present": True,
        "upstream_roots_verified": True,
        "offline_only": True})
    (RUN / "search_plan_v24_dev_alpha2_4_sha256").write_text(root + "\n", encoding="utf-8")
    print(json.dumps({"root": root, "summary": summary}, sort_keys=True))


if __name__ == "__main__":
    main()
