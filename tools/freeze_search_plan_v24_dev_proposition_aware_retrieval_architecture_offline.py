#!/usr/bin/env python3
"""Freeze the offline v2.4-dev proposition-aware retrieval architecture contracts."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools import analyze_search_plan_v24_dev_primary_failure_autopsy_offline as autopsy


RUN = ROOT / "runs/20260917_search_plan_v24_dev_proposition_aware_retrieval_architecture_offline"
AUTOPSY_RUN = autopsy.RUN
EXPECTED_AUTOPSY_ROOT = "4eddec80c4025e8d247cb28f89ed53c9c4b138e47b8e5e4bfe4e7cbe60b52d27"

DIMENSIONS = [
    "subject", "relation", "object_measurement_target", "endpoint_property",
    "biological_unit", "therapy", "disease", "genotype", "nested_treatment",
    "direction", "evidence_mode",
]
INTENT_TYPES = [
    "DIRECT_PERTURBATION", "INVERSE_PERTURBATION", "NECESSITY", "RESCUE",
    "FUNCTIONAL_CHAIN", "THERAPY_SENSITIZATION", "THERAPY_RESISTANCE",
    "ENDPOINT_SPECIFIC", "CONTEXT_SPECIFIC",
]
PROPOSAL_CLASSES = ["AUTHORIZED_EQUIVALENT", "SEARCH_ONLY_EXPANSION", "UNRESOLVED", "REJECTED"]

REQUIRED_OUTPUTS = {
    "v23_failure_to_v24_requirement_mapping.json",
    "proposition_aware_retrieval_architecture.json",
    "proposition_aware_retrieval_architecture.md",
    "retrieval_intent_v1_contract.json",
    "search_term_proposal_classification_contract.json",
    "retrieval_plan_coverage_v1_contract.json",
    "proposition_aware_search_plan_v1_schema.json",
    "query_planner_config_v1_contract.json",
    "deterministic_query_compiler_requirements.json",
    "llm_authority_boundary.json",
    "v23_components_preserved.json",
    "p0_p1_p2_future_role_audit.json",
    "future_validation_boundary.json",
    "scientific_state_safety_audit.json",
    "validation.json",
    "summary.json",
}


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def pretty(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n").encode("utf-8")


def digest(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def load_json(path: Path) -> Any:
    return json.loads(path.read_bytes())


def verify_autopsy_root() -> dict[str, Any]:
    validation = load_json(AUTOPSY_RUN / "validation.json")
    components = []
    for name, expected in validation["aggregate_components"]:
        actual = sha(AUTOPSY_RUN / name)
        require(actual == expected, f"autopsy component changed: {name}")
        components.append([name, actual])
    actual_root = digest(canonical(components))
    require(actual_root == validation["search_plan_v24_primary_failure_autopsy_sha256"],
            "autopsy validation root mismatch")
    require(actual_root == EXPECTED_AUTOPSY_ROOT, "authoritative autopsy root mismatch")
    summary = load_json(AUTOPSY_RUN / "summary.json")
    require(summary["search_plan_v24_primary_failure_autopsy_sha256"] == actual_root,
            "autopsy summary root mismatch")
    require(summary["v23_beta2_primary_evaluation_failed"] is True, "closed primary failure status changed")
    require(summary["v23_beta2_remains_frozen"] is True, "v2.3-beta.2 freeze status changed")
    require(summary["heldout_v2_primary_corpus_reclassified_for_v24_development"] is True,
            "development-corpus status changed")
    return {
        "status": "PASS",
        "search_plan_v24_primary_failure_autopsy_sha256": actual_root,
        "source_record_count": summary["record_count"],
        "source_direct_count": summary["direct_count"],
        "source_non_direct_count": summary["non_direct_count"],
    }


def protected_state() -> dict[str, str]:
    state = autopsy.protected_state()
    for path in AUTOPSY_RUN.iterdir():
        if path.is_file():
            state[str(path.resolve().relative_to(ROOT))] = sha(path)
    return dict(sorted(state.items()))


def proposal_classification_contract() -> dict[str, Any]:
    return {
        "artifact_schema_version": "SearchTermProposalClassificationContractV1",
        "classification_required_for": "EVERY_LLM_GENERATED_RETRIEVAL_TERM_OR_CONCEPT",
        "class_order_is_not_confidence_order": True,
        "classes": {
            "AUTHORIZED_EQUIVALENT": {
                "definition": "Supported by frozen deterministic authority and eligible for identity-sensitive matching.",
                "executable_query_use": True,
                "identity_sensitive_matching": True,
                "scientific_equivalence_granted": True,
                "authority_reference_required": True,
            },
            "SEARCH_ONLY_EXPANSION": {
                "definition": "Permitted only to improve retrieval recall; never scientific normalization or equivalence.",
                "executable_query_use": True,
                "identity_sensitive_matching": False,
                "scientific_equivalence_granted": False,
                "authority_reference_required": False,
            },
            "UNRESOLVED": {
                "definition": "Insufficient deterministic authority for executable query use.",
                "executable_query_use": False,
                "identity_sensitive_matching": False,
                "scientific_equivalence_granted": False,
                "authority_reference_required": False,
            },
            "REJECTED": {
                "definition": "Known incompatible, disallowed, or unsupported expansion.",
                "executable_query_use": False,
                "identity_sensitive_matching": False,
                "scientific_equivalence_granted": False,
                "authority_reference_required": False,
            },
        },
        "classification_owner": "DETERMINISTIC_TERM_VALIDATOR",
        "llm_self_classification_is_non_authoritative": True,
        "canonical_proposition_retained_downstream": True,
        "search_only_expansion_must_not_set": [
            "entity_identity_resolved", "therapy_equivalence", "biological_unit_compatibility",
            "endpoint_equivalence", "proposition_equivalence", "causal_truth",
        ],
        "fail_closed_rules": [
            "UNRESOLVED and REJECTED proposals cannot reach the deterministic compiler",
            "AUTHORIZED_EQUIVALENT without a verified frozen authority reference is invalid",
            "unknown proposal classes are invalid",
            "classification cannot be upgraded from retrieval yield or downstream labels",
        ],
    }


def retrieval_intent_contract() -> dict[str, Any]:
    definitions = {
        "DIRECT_PERTURBATION": ("Direct manipulation of the canonical subject linked to the target response.", ["subject", "relation", "object_measurement_target", "direction", "evidence_mode"]),
        "INVERSE_PERTURBATION": ("Loss, blockade, or opposing manipulation predicting an inverse response pattern.", ["subject", "relation", "object_measurement_target", "direction", "evidence_mode"]),
        "NECESSITY": ("Requirement or dependency evidence for the subject in producing the target response.", ["subject", "relation", "object_measurement_target", "evidence_mode"]),
        "RESCUE": ("Restoration or reversal structure that tests proposition dependence.", ["subject", "relation", "object_measurement_target", "direction", "evidence_mode"]),
        "FUNCTIONAL_CHAIN": ("A bounded mechanistic chain connecting perturbation to the measured endpoint.", ["subject", "relation", "object_measurement_target", "evidence_mode"]),
        "THERAPY_SENSITIZATION": ("Subject perturbation linked to increased response to the canonical therapy.", ["subject", "relation", "therapy", "direction", "evidence_mode"]),
        "THERAPY_RESISTANCE": ("Subject perturbation linked to resistance or reduced response to the canonical therapy.", ["subject", "relation", "therapy", "direction", "evidence_mode"]),
        "ENDPOINT_SPECIFIC": ("Search constrained to the required measurement target and endpoint property.", ["object_measurement_target", "endpoint_property", "evidence_mode"]),
        "CONTEXT_SPECIFIC": ("Search constrained to applicable biological, disease, genotype, or nested-treatment context.", ["evidence_mode"]),
    }
    applicability = {
        "DIRECT_PERTURBATION": "Applicable when the canonical proposition expresses a perturbation-response relation.",
        "INVERSE_PERTURBATION": "Applicable only when an inverse intervention and expected direction can be represented without asserting equivalence.",
        "NECESSITY": "Applicable only when necessity/dependency is compatible with the proposition semantics.",
        "RESCUE": "Applicable only when a rescue or reversal formulation is semantically meaningful.",
        "FUNCTIONAL_CHAIN": "Applicable when a bounded chain can seek current-study functional evidence without replacing the canonical relation.",
        "THERAPY_SENSITIZATION": "Applicable only when therapy identity and sensitization direction are explicit target dimensions.",
        "THERAPY_RESISTANCE": "Applicable only when therapy identity and resistance direction are explicit target dimensions.",
        "ENDPOINT_SPECIFIC": "Applicable when the proposition has a distinct measurement target or endpoint property.",
        "CONTEXT_SPECIFIC": "Applicable when at least one biological-unit, therapy, disease, genotype, or nested-treatment context is present.",
    }
    return {
        "artifact_schema_version": "RetrievalIntentV1Contract",
        "intent_types": {
            name: {"definition": definitions[name][0], "minimum_required_dimensions": definitions[name][1],
                   "applicability_rule": applicability[name]}
            for name in INTENT_TYPES
        },
        "intent_instantiation_rule": "SEMANTICS_DEPENDENT_NOT_ALL_INTENTS_REQUIRED",
        "fixed_legacy_family_start_forbidden": True,
        "biological_unit_context": {
            "carried_separately_from_subject_and_object_identity": True,
            "required_on_every_intent_record": True,
            "state_when_target_has_no_unit": "NOT_APPLICABLE",
            "lexical_forms_may_be_proposed_by_llm": True,
            "compatibility_decided_by_deterministic_authority": True,
            "v23_p0_not_a_substitute_for_query_context_planning": True,
        },
        "intent_is_retrieval_hypothesis_not_scientific_conclusion": True,
    }


def coverage_contract() -> dict[str, Any]:
    return {
        "artifact_schema_version": "RetrievalPlanCoverageV1Contract",
        "dimensions": DIMENSIONS,
        "all_dimensions_must_have_explicit_state_per_candidate_query": True,
        "dimension_states": ["REPRESENTED", "UNDERREPRESENTED", "OMITTED", "NOT_APPLICABLE"],
        "required_dimension_fields": [
            "dimension", "coverage_state", "source_concept_ids", "query_term_ids", "rationale",
        ],
        "relation_requirement": {
            "representation_attempt_mandatory_when_applicable": True,
            "states": ["REPRESENTED", "RELATION_UNDERREPRESENTED", "NOT_APPLICABLE"],
            "silent_relation_drop_forbidden": True,
            "underrepresented_provenance_marker": "RELATION_UNDERREPRESENTED",
        },
        "forbidden_summary_only_labels": ["high specificity", "broad query"],
        "coverage_is_not": ["scientific_truth", "proposition_equivalence", "expected_precision", "expected_recall"],
        "coverage_aggregation": "STRUCTURAL_TRACE_ONLY_NO_PERFORMANCE_SCORE",
    }


def planner_config_contract() -> dict[str, Any]:
    return {
        "artifact_schema_version": "QueryPlannerConfigV1Contract",
        "runtime_configuration_status": "NOT_INSTANTIATED_IN_ARCHITECTURE_ONLY_RUN",
        "required_frozen_fields": {
            "provider": "exact provider identifier",
            "model_identity": "exact provider model identifier",
            "reasoning_setting": "exact reasoning setting or explicit not_exposed",
            "temperature": "numeric value or null",
            "temperature_exposure": "EXPOSED or NOT_EXPOSED",
            "prompt_template_version": "immutable prompt/template version",
            "schema_version": "PropositionAwareSearchPlanV1 schema identity",
            "max_attempts": "positive integer fixed before planner execution",
            "repair_policy": "explicit fail/repair policy fixed before planner execution",
        },
        "architecture_default_constraints": {
            "no_automatic_retry_after_schema_failure": True,
            "no_outcome_informed_regeneration": True,
            "no_regeneration_after_retrieval_yield_seen": True,
            "invalid_schema_output_fails_closed": True,
        },
        "query_budget_fields_required_before_any_development_execution": [
            "maximum_retrieval_intents_per_target", "maximum_executable_queries_per_intent",
            "maximum_total_queries_per_target", "maximum_search_only_expansions_per_concept",
        ],
        "query_budget_values_in_this_run": "UNSET_PENDING_RETROSPECTIVE_DEVELOPMENT_ANALYSIS",
        "numerical_query_budgets_frozen_in_this_run": False,
        "budget_selection_constraints": [
            "may use only seen v2.3 development corpus and historical development cases",
            "must not use future held-out performance",
            "must be frozen before fresh-case selection or independent evaluation",
        ],
        "planner_cache_key": {
            "algorithm": "SHA-256",
            "canonical_input": [
                "canonical ScientificPropositionTarget", "complete QueryPlannerConfigV1",
                "planner prompt/template version",
            ],
            "formula": "SHA256(canonical_json([ScientificPropositionTarget, QueryPlannerConfigV1, planner_prompt_template_version]))",
        },
        "configuration_instance_must_be_frozen_before_first_planner_call": True,
    }


def search_plan_schema() -> dict[str, Any]:
    string = {"type": "string", "minLength": 1}
    dimension_enum = {"type": "string", "enum": DIMENSIONS}
    term = {
        "type": "object", "additionalProperties": False,
        "required": [
            "term_id", "term", "proposal_source", "proposal_class", "authority_reference",
            "confidence_not_used_for_scientific_truth",
        ],
        "properties": {
            "term_id": string, "term": string,
            "proposal_source": {"type": "string", "enum": ["CANONICAL_TARGET", "DETERMINISTIC_AUTHORITY", "LLM_PROPOSAL"]},
            "proposal_class": {"type": "string", "enum": PROPOSAL_CLASSES},
            "authority_reference": {"type": ["string", "null"]},
            "confidence_not_used_for_scientific_truth": {"const": True},
        },
        "allOf": [{
            "if": {"properties": {"proposal_class": {"const": "AUTHORIZED_EQUIVALENT"}}},
            "then": {"properties": {"authority_reference": {"type": "string", "minLength": 1}}},
        }],
    }
    concept = {
        "type": "object", "additionalProperties": False,
        "required": [
            "concept_id", "concept_type", "canonical_value", "proposal_source", "proposal_class",
            "authority_reference", "confidence_not_used_for_scientific_truth", "proposed_terms",
        ],
        "properties": {
            "concept_id": string,
            "concept_type": {"type": "string", "enum": DIMENSIONS},
            "canonical_value": {"type": ["string", "array", "null"], "items": string},
            "proposal_source": {"type": "string", "enum": ["CANONICAL_TARGET", "DETERMINISTIC_AUTHORITY", "LLM_PROPOSAL"]},
            "proposal_class": {"type": "string", "enum": PROPOSAL_CLASSES},
            "authority_reference": {"type": ["string", "null"]},
            "confidence_not_used_for_scientific_truth": {"const": True},
            "proposed_terms": {"type": "array", "items": term},
        },
        "allOf": [{
            "if": {"properties": {"proposal_class": {"const": "AUTHORIZED_EQUIVALENT"}}},
            "then": {"properties": {"authority_reference": {"type": "string", "minLength": 1}}},
        }],
    }
    coverage_item = {
        "type": "object", "additionalProperties": False,
        "required": ["dimension", "coverage_state", "source_concept_ids", "query_term_ids", "rationale"],
        "properties": {
            "dimension": dimension_enum,
            "coverage_state": {"type": "string", "enum": ["REPRESENTED", "UNDERREPRESENTED", "OMITTED", "NOT_APPLICABLE"]},
            "source_concept_ids": {"type": "array", "items": string, "uniqueItems": True},
            "query_term_ids": {"type": "array", "items": string, "uniqueItems": True},
            "rationale": string,
        },
    }
    blueprint = {
        "type": "object", "additionalProperties": False,
        "required": [
            "blueprint_id", "concept_ids", "dimension_coverage", "relation_representation_state",
            "compiler_input_only", "executable_query_absent",
        ],
        "properties": {
            "blueprint_id": string,
            "concept_ids": {"type": "array", "minItems": 1, "items": string, "uniqueItems": True},
            "dimension_coverage": {"type": "array", "minItems": 11, "maxItems": 11, "items": coverage_item},
            "relation_representation_state": {"type": "string", "enum": ["REPRESENTED", "RELATION_UNDERREPRESENTED", "NOT_APPLICABLE"]},
            "compiler_input_only": {"const": True},
            "executable_query_absent": {"const": True},
        },
    }
    intent = {
        "type": "object", "additionalProperties": False,
        "required": [
            "intent_id", "intent_type", "applicability", "applicability_rationale",
            "scientific_rationale", "required_dimensions", "optional_dimensions",
            "biological_unit_context", "search_concepts", "candidate_query_blueprints",
        ],
        "properties": {
            "intent_id": string,
            "intent_type": {"type": "string", "enum": INTENT_TYPES},
            "applicability": {"type": "string", "enum": ["APPLICABLE", "NOT_APPLICABLE"]},
            "applicability_rationale": string,
            "scientific_rationale": string,
            "required_dimensions": {"type": "array", "items": dimension_enum, "uniqueItems": True},
            "optional_dimensions": {"type": "array", "items": dimension_enum, "uniqueItems": True},
            "biological_unit_context": {
                "type": "object", "additionalProperties": False,
                "required": ["target_value", "planning_state", "separate_from_entity_identity"],
                "properties": {
                    "target_value": {"type": ["string", "array", "null"], "items": string},
                    "planning_state": {"type": "string", "enum": ["PRESENT", "ABSENT", "UNRESOLVED", "NOT_APPLICABLE"]},
                    "separate_from_entity_identity": {"const": True},
                },
            },
            "search_concepts": {"type": "array", "items": concept},
            "candidate_query_blueprints": {"type": "array", "items": blueprint},
        },
    }
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": "urn:conflict-oriented-discovery-engine:PropositionAwareSearchPlanV1",
        "title": "PropositionAwareSearchPlanV1",
        "type": "object", "additionalProperties": False,
        "required": [
            "artifact_schema_version", "request_provenance", "target_id", "canonical_proposition", "planner_config_sha256",
            "planner_prompt_template_version", "planner_cache_key_sha256", "retrieval_intents",
            "planner_output_frozen_before_retrieval",
        ],
        "properties": {
            "artifact_schema_version": {"const": "PropositionAwareSearchPlanV1"},
            "request_provenance": {
                "type": "object", "additionalProperties": False,
                "required": ["request_sha256", "preserved_request_reference"],
                "properties": {
                    "request_sha256": {"type": "string", "pattern": "^[0-9a-f]{64}$"},
                    "preserved_request_reference": string,
                },
            },
            "target_id": string,
            "canonical_proposition": {
                "type": "object", "additionalProperties": False,
                "required": ["schema_version", "target_sha256", "target_payload"],
                "properties": {
                    "schema_version": {"const": "ScientificPropositionTargetV1"},
                    "target_sha256": {"type": "string", "pattern": "^[0-9a-f]{64}$"},
                    "target_payload": {"type": "object"},
                },
            },
            "planner_config_sha256": {"type": "string", "pattern": "^[0-9a-f]{64}$"},
            "planner_prompt_template_version": string,
            "planner_cache_key_sha256": {"type": "string", "pattern": "^[0-9a-f]{64}$"},
            "retrieval_intents": {"type": "array", "minItems": 1, "items": intent},
            "planner_output_frozen_before_retrieval": {"const": True},
        },
        "x-deterministic-semantic-validations": [
            "intent IDs, concept IDs, term IDs, and blueprint IDs are unique within target",
            "every blueprint has exactly one coverage entry for each of the 11 dimensions",
            "UNRESOLVED and REJECTED terms never occur in compiler-eligible concept selections",
            "AUTHORIZED_EQUIVALENT always has verified authority_reference",
            "relation omissions carry RELATION_UNDERREPRESENTED when relation is applicable",
            "planner_cache_key_sha256 matches the frozen cache-key formula",
        ],
    }


def compiler_requirements() -> dict[str, Any]:
    return {
        "artifact_schema_version": "DeterministicQueryCompilerRequirementsV1",
        "implementation_status": "NOT_IMPLEMENTED",
        "input_contracts": [
            "schema-valid PropositionAwareSearchPlanV1",
            "deterministically validated proposal classifications",
            "semantically validated RetrievalIntentV1 applicability",
            "frozen QueryPlannerConfigV1 instance including query budgets",
        ],
        "pipeline_position": "AFTER_LLM_PLAN_AND_ALL_DETERMINISTIC_VALIDATION",
        "compiler_owns": [
            "Boolean syntax", "escaping", "PubMed field qualifiers", "parentheses",
            "stable ordering", "deduplication", "query identity", "query hashing",
            "budget enforcement", "frozen executable-query serialization",
        ],
        "compiler_must_not": [
            "infer scientific equivalence", "promote SEARCH_ONLY_EXPANSION to authority",
            "accept arbitrary prose as query syntax", "compile UNRESOLVED or REJECTED terms",
            "silently drop an applicable relation", "adapt after observing retrieval yield",
        ],
        "stable_ordering": {
            "intent_order": INTENT_TYPES,
            "dimension_order": DIMENSIONS,
            "term_order": "canonical normalized UTF-8 byte order after provenance-preserving deduplication",
            "boolean_rendering": "fixed grammar and fixed parenthesization owned by the future compiler contract",
        },
        "query_identity": {
            "algorithm": "SHA-256",
            "inputs": [
                "target_sha256", "intent_id", "blueprint_id", "ordered validated term records",
                "coverage record", "compiler version", "frozen budget configuration",
            ],
        },
        "output_requirements": [
            "executable query string", "query_id", "query_sha256", "compiler_version",
            "complete term provenance", "RetrievalPlanCoverageV1", "relation representation state",
            "budget position", "frozen-before-retrieval marker",
        ],
        "network_access": "FORBIDDEN_TO_COMPILER",
        "llm_access": "FORBIDDEN_TO_COMPILER",
    }


def llm_boundary() -> dict[str, Any]:
    return {
        "artifact_schema_version": "PropositionAwareQueryPlannerAuthorityBoundaryV1",
        "llm_role": "PROPOSITION_AWARE_QUERY_PLANNER",
        "scientific_authority": False,
        "may_propose": [
            "entity aliases", "gene/protein symbol alternatives", "drug names and target names",
            "relation paraphrases", "endpoint paraphrases", "inverse perturbation formulations",
            "necessity formulations", "rescue formulations", "therapy-response formulations",
            "biological-unit expressions", "disease/context expressions", "genotype expressions",
            "nested-treatment formulations",
        ],
        "must_not_establish": [
            "entity equivalence", "therapy equivalence", "biological-unit compatibility",
            "endpoint equivalence", "proposition equivalence", "contradiction", "causal truth",
        ],
        "must_not_emit": ["final executable PubMed query", "unproven authority reference", "scientific relevance label"],
        "output_is": "STRUCTURED_RETRIEVAL_HYPOTHESIS",
        "deterministic_checks_required": [
            "strict schema validation", "term proposal classification", "intent applicability validation",
            "coverage completeness validation", "budget validation", "compiler input validation",
        ],
        "evaluation_blinding": {
            "planner_output_persisted_before_retrieval": True,
            "retrieval_yield_unavailable_during_planning": True,
            "PASS_A_and_PASS_B_labels_unavailable_during_planning": True,
            "outcome_informed_rerun_forbidden": True,
        },
    }


def failure_mapping() -> dict[str, Any]:
    return {
        "artifact_schema_version": "V23FailureToV24RequirementMappingV1",
        "source_autopsy_sha256": EXPECTED_AUTOPSY_ROOT,
        "mappings": [
            {
                "failure": "TOPIC_INTERSECTION_WITHOUT_RELATION",
                "observed_evidence": {"family_A_any_contributing_N": 36, "family_A_direct_N": 0},
                "v24_requirements": ["retrieval-intent-first planning", "mandatory relation representation attempt", "RELATION_UNDERREPRESENTED provenance"],
            },
            {
                "failure": "BIOLOGICAL_UNIT_MISMATCH",
                "observed_evidence": {"affected_non_direct_N": 49, "rank": 1},
                "v24_requirements": ["biological unit separate from identity", "unit expressions classified by deterministic authority", "P0 cannot substitute for context planning"],
            },
            {
                "failure": "SUBJECT_OR_RELATION_PROPOSITION_MISALIGNMENT",
                "observed_evidence": {"subject_identity_N": 29, "relation_semantics_N": 22, "evidence_mode_N": 20},
                "v24_requirements": ["dimension-complete coverage trace", "intent-specific perturbation formulations", "evidence-mode coverage"],
            },
            {
                "failure": "ENDPOINT_OR_MEASUREMENT_SEMANTIC_MISMATCH",
                "observed_evidence": {"endpoint_property_N": 19, "measurement_target_N": 8},
                "v24_requirements": ["object/measurement target separated from endpoint property", "ENDPOINT_SPECIFIC intent", "search-only expansion cannot grant endpoint equivalence"],
            },
            {
                "failure": "THERAPY_OR_CONTEXT_OMISSION",
                "observed_evidence": {"therapy_identity_N": 5, "disease_context_N": 10, "nested_treatment_context_N": 7, "genotype_context_N": 0},
                "v24_requirements": ["explicit therapy/disease/genotype/nested-treatment coverage", "semantics-dependent therapy intents", "CONTEXT_SPECIFIC intent"],
            },
            {
                "failure": "TIER_A_ELIGIBILITY_NOT_PROPOSITION_COMPATIBILITY",
                "observed_evidence": {"tier_A_direct_N": 1, "tier_A_total_N": 18, "tier_B_direct_N": 1, "tier_B_total_N": 42},
                "v24_requirements": ["do not equate lexical gate eligibility with proposition evidence", "retain per-dimension trace", "freeze future gating logic before evaluation"],
            },
            {
                "failure": "P0_P1_FALSE_NEGATIVE_OR_UNRESOLVED_ON_DIRECT_PAPERS",
                "observed_evidence": {"P0_INCOMPATIBLE_direct_N": 1, "P0_UNRESOLVED_direct_N": 1, "P1_UNRESOLVED_direct_N": 2, "P2_EXACT_direct_N": 2},
                "v24_requirements": ["P0/P1/P2 become secondary audit modules", "existing blocking semantics not presumed", "module outputs retain reason codes and surfaces"],
            },
            {
                "failure": "NO_CLEAN_RAW_PREACQUISITION_SEPARATOR",
                "observed_evidence": {"direct_N": 2, "non_direct_N": 58, "clean_raw_feature_separator_found": False},
                "v24_requirements": ["no post-hoc classifier", "no threshold optimization", "development-only retrospective evaluation"],
            },
        ],
        "mapping_is_architecture_rationale_not_new_scientific_adjudication": True,
    }


def preserved_components() -> dict[str, Any]:
    components = {
        "deterministic_query_hashing": "Extend hash inputs to intent, coverage, validated terms, compiler version, and budgets.",
        "network_snapshot_freeze": "Persist exact requests/responses and retrieval state after executable-query freeze.",
        "soft_hard_metadata_tail_framework": "Retain bounded tail accounting; configure independently from planner semantics.",
        "candidate_identity_and_deduplication": "Retain deterministic candidate identity and cross-query provenance.",
        "pre_acquisition_evidence_freeze": "Freeze evidence surfaces before PASS A and PASS B.",
        "PASS_A_PASS_B_isolation": "Retain acquisition/relevance role separation and blinded workspaces.",
        "metrics_preregistration": "Freeze metrics before fresh-case retrieval and adjudication.",
        "provenance_chain": "Extend backward through target, intent, proposal, validation, compiler, and query.",
        "Atlas_review_boundary": "Retain bounded review boundary; search-only terms grant no scientific authority.",
    }
    return {
        "artifact_schema_version": "V23ComponentsPreservedForV24V1",
        "components": {name: {"status": "CONCEPTUALLY_PRESERVED", "v24_note": note} for name, note in components.items()},
        "preservation_does_not_activate_v24_production": True,
    }


def module_future_role() -> dict[str, Any]:
    return {
        "artifact_schema_version": "P0P1P2FutureRoleAuditV1",
        "source_autopsy_sha256": EXPECTED_AUTOPSY_ROOT,
        "reframed_role": "SECONDARY_PREACQUISITION_EVIDENCE_AUDIT_MODULES",
        "not_primary_retrieval_generators": True,
        "existing_blocking_semantics_preserved_by_default": False,
        "permitted_future_uses_to_evaluate": [
            "annotation", "priority support", "reviewability", "explicit incompatibility",
        ],
        "direct_paper_constraints": [
            {"candidate_id": "heldout_v2_102:pmid:28565847", "P0": "INCOMPATIBLE", "P1": "UNRESOLVED", "P2": "EXACT"},
            {"candidate_id": "heldout_v2_105:pmid:27023784", "P0": "UNRESOLVED", "P1": "UNRESOLVED", "P2": "EXACT"},
        ],
        "future_design_requirements": [
            "preserve module reason codes and evidence surfaces",
            "distinguish semantic error, parser failure, and unavailable evidence",
            "do not let unresolved state silently erase a compiler-valid retrieval intent",
            "validate any future blocking role on development data before protocol freeze",
            "freeze final gating semantics before fresh-case selection",
        ],
        "module_changes_in_this_run": False,
    }


def future_validation_boundary() -> dict[str, Any]:
    return {
        "artifact_schema_version": "SearchPlanV24FutureValidationBoundaryV1",
        "development_only_corpora": [
            "heldout-v1", "retired initial heldout-v2", "primary heldout-v2 cases 101-108",
        ],
        "primary_v2_corpus_status": "seen_primary_failure_development_corpus_for_v24",
        "allowed_descriptions_for_reuse": ["development replay", "retrospective development evaluation", "regression testing"],
        "forbidden_descriptions_for_reuse": ["held-out", "prospective", "independent validation"],
        "must_freeze_before_independent_evaluation": [
            "planner config", "planner prompt", "PropositionAwareSearchPlanV1 schema",
            "authority rules", "query budgets", "deterministic compiler", "retrieval intents",
            "gating logic", "metrics",
        ],
        "fresh_case_requirements": [
            "completely new case identities", "selected only after all listed components are frozen",
            "no overlap with heldout-v1, retired initial heldout-v2, or primary heldout-v2 101-108",
        ],
        "fresh_cases_selected_in_this_run": False,
        "future_independent_validation_requires_fresh_cases": True,
    }


def architecture() -> dict[str, Any]:
    return {
        "artifact_schema_version": "PropositionAwareRetrievalArchitectureV1",
        "architecture_status": "CONTRACT_FROZEN_IMPLEMENTATION_ABSENT",
        "authoritative_development_evidence_sha256": EXPECTED_AUTOPSY_ROOT,
        "core_conclusion": "Lexical/topic intersection is insufficient for proposition-level evidence retrieval.",
        "pipeline": [
            {"stage": 1, "name": "Scientific Proposition", "owner": "FROZEN_SCIENTIFIC_TARGET_AUTHORITY", "output": "ScientificPropositionTargetV1"},
            {"stage": 2, "name": "Retrieval Intent", "owner": "PROPOSITION_AWARE_QUERY_PLANNER_PROPOSAL_PLUS_DETERMINISTIC_VALIDATION", "output": "RetrievalIntentV1"},
            {"stage": 3, "name": "Search Concepts", "owner": "LLM_PROPOSAL_WITH_DETERMINISTIC_CLASSIFICATION", "output": "classified search concepts and terms"},
            {"stage": 4, "name": "Candidate Query Plan", "owner": "STRUCTURED_PLANNER_SCHEMA", "output": "PropositionAwareSearchPlanV1"},
            {"stage": 5, "name": "Deterministic Validation", "owner": "NON_LLM_VALIDATORS", "output": "validated intents, terms, coverage, and budgets"},
            {"stage": 6, "name": "Frozen Executable Queries", "owner": "DETERMINISTIC_PUBMED_COMPILER", "output": "hashed immutable executable queries"},
        ],
        "non_sufficiency_rule": "subject plus endpoint co-occurrence is not sufficient proposition retrieval",
        "contracts": [
            "RetrievalIntentV1", "SearchTermProposalClassificationContractV1",
            "RetrievalPlanCoverageV1", "PropositionAwareSearchPlanV1",
            "QueryPlannerConfigV1", "DeterministicQueryCompilerRequirementsV1",
        ],
        "complete_query_trace_required": [
            "user natural-language request", "ScientificPropositionTarget", "RetrievalIntent",
            "LLM proposal", "proposal classification", "deterministic validator",
            "deterministic compiler", "executable query",
        ],
        "unprovenance_query_terms_allowed": False,
        "relation_representation_attempt_mandatory": True,
        "search_only_expansion_supported": True,
        "canonical_proposition_retained": True,
        "v24_query_planner_implemented": False,
        "v24_query_compiler_implemented": False,
        "v24_retrieval_started": False,
    }


def architecture_markdown() -> bytes:
    text = """# Search Plan v2.4-dev proposition-aware retrieval architecture

## A. Failure → Requirement Mapping

The closed v2.3-beta.2 primary run showed that subject/endpoint topic intersection did not reliably retrieve proposition-level evidence. Family A contributed 36 acquired papers and zero direct papers. Biological-unit mismatch affected 49 of 58 non-direct papers. The architecture therefore requires explicit intent, relation, endpoint-property, context, direction, and evidence-mode coverage rather than a topical query label.

## B. New Retrieval Architecture

The frozen design is: Scientific Proposition → Retrieval Intent → classified Search Concepts → Candidate Query Plan → Deterministic Validation → Frozen Executable Queries. Every term remains traceable to the user request, frozen target, intent, proposal, classification, validation, and compiler output.

## C. LLM Role

The LLM role is `PROPOSITION_AWARE_QUERY_PLANNER`. It may propose retrieval vocabulary and evidence-pattern formulations. Its output is a structured retrieval hypothesis, never scientific authority, a relevance judgment, or an executable PubMed query. No model or runtime configuration is selected in this offline architecture-only run; a complete `QueryPlannerConfigV1` instance must be frozen before the first future planner call.

## D. Deterministic Authority Boundary

Every LLM-generated term is classified as `AUTHORIZED_EQUIVALENT`, `SEARCH_ONLY_EXPANSION`, `UNRESOLVED`, or `REJECTED`. Only deterministic frozen authority can grant equivalence. Search-only expansions may retrieve candidates but cannot resolve identity, endpoint equivalence, biological-unit compatibility, proposition equivalence, or causal truth.

## E. Retrieval Intent Model

`RetrievalIntentV1` defines nine generic intent types: direct and inverse perturbation, necessity, rescue, functional chain, therapy sensitization, therapy resistance, endpoint-specific, and context-specific. Applicability follows proposition semantics; no target is required to instantiate all intents, and planning does not begin with fixed A/B/C/D/E families.

## F. Proposition Coverage Model

`RetrievalPlanCoverageV1` records all eleven dimensions for every candidate query: subject, relation, object/measurement target, endpoint property, biological unit, therapy, disease, genotype, nested treatment, direction, and evidence mode. Coverage is structural provenance, not a precision, recall, or scientific-truth score.

## G. Biological Unit Strategy

Every intent carries a biological-unit context record separately from subject/object identity. The planner may propose lexical variants; deterministic authority classifies them. The v2.3 P0 classifier is not a substitute for query context planning.

## H. Relation Strategy

When applicable, the planner must attempt relation representation using perturbation, response, loss/gain, sensitization/resistance, necessity, or rescue formulations. If search-system constraints prevent adequate representation, provenance must say `RELATION_UNDERREPRESENTED`; silent omission is invalid.

## I. Query Compiler Boundary

The future deterministic compiler—not the LLM—owns Boolean syntax, escaping, PubMed field qualifiers, parentheses, stable ordering, deduplication, query identity, hashing, and budget enforcement. It accepts only schema-valid and deterministically validated inputs and cannot compile unresolved or rejected terms.

## J. v2.3 Components Preserved

Deterministic query hashing, network snapshot freeze, metadata-tail accounting, candidate identity/deduplication, pre-acquisition evidence freeze, PASS A/PASS B isolation, metrics preregistration, provenance, and the Atlas review boundary remain conceptually preserved.

## K. P0/P1/P2 Future Role

P0/P1/P2 are reframed as secondary pre-acquisition evidence-audit modules. Existing blocking semantics are not presumed: one direct paper was P0 incompatible, the other P0 unresolved, and both were P1 unresolved while both were P2 exact. Future roles may include annotation, priority support, reviewability, and explicit incompatibility after separate development validation.

## L. Future Validation Boundary

The 60-paper primary corpus is permanently development-seen. Heldout-v1, retired initial heldout-v2, and primary heldout-v2 cases 101–108 cannot be reused as independent validation. Planner configuration, prompt, schema, authority rules, query budgets, compiler, intents, gates, and metrics must be frozen before selecting a completely fresh case set.

This run defines architecture and contracts only. It implements no query planner or compiler, performs no retrieval, and selects no held-out cases.
"""
    return text.encode("utf-8")


def build_outputs(authority: dict[str, Any], protected_before: dict[str, str]) -> dict[str, bytes]:
    mapping = failure_mapping()
    architecture_value = architecture()
    intent = retrieval_intent_contract()
    proposal = proposal_classification_contract()
    coverage = coverage_contract()
    schema = search_plan_schema()
    config = planner_config_contract()
    compiler = compiler_requirements()
    boundary = llm_boundary()
    preserved = preserved_components()
    modules = module_future_role()
    validation_boundary = future_validation_boundary()

    protected_after = protected_state()
    require(protected_before == protected_after, "historical or authoritative state changed")
    safety = {
        "artifact_schema_version": "V24ArchitectureScientificStateSafetyAuditV1",
        "offline_only": True,
        "network_calls": 0, "provider_calls": 0, "llm_calls": 0,
        "retrieval_calls": 0, "new_scientific_adjudication_calls": 0,
        "new_heldout_cases_selected": False,
        "production_query_execution": False,
        "v24_query_planner_implemented": False,
        "v24_query_compiler_implemented": False,
        "historical_assets_modified": False,
        "protected_state_before_sha256": digest(canonical(protected_before)),
        "protected_state_after_sha256": digest(canonical(protected_after)),
        "authoritative_autopsy_root_verified": authority["status"] == "PASS",
    }

    outputs = {
        "v23_failure_to_v24_requirement_mapping.json": pretty(mapping),
        "proposition_aware_retrieval_architecture.json": pretty(architecture_value),
        "proposition_aware_retrieval_architecture.md": architecture_markdown(),
        "retrieval_intent_v1_contract.json": pretty(intent),
        "search_term_proposal_classification_contract.json": pretty(proposal),
        "retrieval_plan_coverage_v1_contract.json": pretty(coverage),
        "proposition_aware_search_plan_v1_schema.json": pretty(schema),
        "query_planner_config_v1_contract.json": pretty(config),
        "deterministic_query_compiler_requirements.json": pretty(compiler),
        "llm_authority_boundary.json": pretty(boundary),
        "v23_components_preserved.json": pretty(preserved),
        "p0_p1_p2_future_role_audit.json": pretty(modules),
        "future_validation_boundary.json": pretty(validation_boundary),
        "scientific_state_safety_audit.json": pretty(safety),
    }

    component_names = sorted(REQUIRED_OUTPUTS - {"validation.json", "summary.json"})
    components = [[name, digest(outputs[name])] for name in component_names]
    root = digest(canonical(components))
    checks = {
        "authoritative_autopsy_root_verified": authority["status"] == "PASS",
        "architecture_pipeline_defined": len(architecture_value["pipeline"]) == 6,
        "llm_is_not_scientific_authority": boundary["scientific_authority"] is False,
        "all_four_proposal_classes_defined": set(proposal["classes"]) == set(PROPOSAL_CLASSES),
        "search_only_expansion_non_authoritative": not proposal["classes"]["SEARCH_ONLY_EXPANSION"]["scientific_equivalence_granted"],
        "all_nine_intent_types_defined": set(intent["intent_types"]) == set(INTENT_TYPES),
        "all_eleven_coverage_dimensions_defined": coverage["dimensions"] == DIMENSIONS,
        "relation_underrepresentation_explicit": coverage["relation_requirement"]["underrepresented_provenance_marker"] == "RELATION_UNDERREPRESENTED",
        "strict_search_plan_schema": schema["additionalProperties"] is False,
        "planner_runtime_config_not_instantiated": config["runtime_configuration_status"] == "NOT_INSTANTIATED_IN_ARCHITECTURE_ONLY_RUN",
        "numerical_query_budgets_not_prematurely_frozen": config["numerical_query_budgets_frozen_in_this_run"] is False,
        "compiler_required_but_not_implemented": compiler["implementation_status"] == "NOT_IMPLEMENTED",
        "v23_components_conceptually_preserved": len(preserved["components"]) == 9,
        "p0_p1_p2_reframed_as_secondary": modules["not_primary_retrieval_generators"] is True,
        "future_validation_requires_fresh_cases": validation_boundary["future_independent_validation_requires_fresh_cases"] is True,
        "no_runtime_or_network_activity": all(safety[key] == 0 for key in ("network_calls", "provider_calls", "llm_calls", "retrieval_calls")),
        "historical_state_unchanged": protected_before == protected_after,
    }
    failed = [name for name, passed in checks.items() if not passed]
    require(not failed, f"architecture validation failed: {failed}")
    validation = {
        "artifact_schema_version": "V24PropositionAwareArchitectureValidationV1",
        "status": "PASS",
        "checks": checks,
        "aggregate_components": components,
        "search_plan_v24_proposition_aware_architecture_sha256": root,
    }
    summary = {
        "artifact_schema_version": "V24PropositionAwareArchitectureSummaryV1",
        "status": "COMPLETED",
        "source_autopsy_sha256": EXPECTED_AUTOPSY_ROOT,
        "search_plan_v24_proposition_aware_architecture_sha256": root,
        "llm_role": "query_planner_not_scientific_authority",
        "search_only_expansion_supported": True,
        "retrieval_intent_model_defined": True,
        "proposition_coverage_model_defined": True,
        "deterministic_query_compiler_required": True,
        "v23_primary_corpus_used_as_development_only": True,
        "future_independent_validation_requires_fresh_cases": True,
        "v24_query_planner_implemented": False,
        "v24_query_compiler_implemented": False,
        "v24_retrieval_started": False,
        "new_heldout_cases_selected": False,
        "network_calls": 0, "provider_calls": 0, "llm_calls": 0,
        "historical_assets_modified": False,
    }
    outputs["validation.json"] = pretty(validation)
    outputs["summary.json"] = pretty(summary)
    require(set(outputs) == REQUIRED_OUTPUTS, "required output membership mismatch")
    return outputs


def run() -> None:
    authority = verify_autopsy_root()
    protected = protected_state()
    first = build_outputs(authority, protected)
    second = build_outputs(authority, protected)
    require(first == second, "architecture freeze replay is not byte-identical")
    RUN.mkdir(parents=True, exist_ok=True)
    require(not any(RUN.iterdir()), "architecture output run already contains files")
    for name in sorted(first):
        with (RUN / name).open("xb") as stream:
            stream.write(first[name])
    require({path.name for path in RUN.iterdir()} == REQUIRED_OUTPUTS, "written output membership mismatch")
    require(protected_state() == protected, "historical state changed after architecture write")
    print((RUN / "summary.json").read_text(encoding="utf-8"), end="")


if __name__ == "__main__":
    run()
