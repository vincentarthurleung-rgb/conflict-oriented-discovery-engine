"""Deterministic proposition-aware query compiler for Search Plan v2.4-dev.

The compiler accepts only a strict plan plus a matching deterministic term
validation receipt. It performs no retrieval, network access, or provider call.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
from typing import Any

from code_engine.search.proposition_aware_query_planner_v1 import (
    canonical_bytes,
    sha256_value,
    validate_plan,
)
from code_engine.search.retrieval_intent_v1 import DIMENSION_ORDER, INTENT_ORDER
from code_engine.search.retrieval_plan_coverage_v1 import validate_blueprint_coverage
from code_engine.search.search_term_validator_v1 import USABLE_CLASSES, normalize_term


COMPILER_VERSION = "DeterministicQueryCompilerV24Dev"
SEARCH_PLAN_VERSION = "v2.4-dev"
FIELD_QUALIFIER = "Title/Abstract"


class QueryCompilerV24Error(ValueError):
    """Base fail-closed compiler error."""


class QueryBudgetExceeded(QueryCompilerV24Error):
    """Raised when the frozen development budget is exceeded."""


@dataclass(frozen=True)
class QueryBudgetConfigDev:
    max_intents_per_target: int = 9
    max_blueprints_per_intent: int = 2
    max_queries_per_target: int = 12
    max_search_only_terms_per_concept: int = 2

    def __post_init__(self) -> None:
        for name, value in asdict(self).items():
            if not isinstance(value, int) or isinstance(value, bool) or value < 1:
                raise QueryCompilerV24Error(f"{name} must be a positive integer")

    def to_dict(self) -> dict[str, Any]:
        return {
            "artifact_schema_version": "QueryBudgetConfigDev",
            **asdict(self),
            "configuration_role": "DEVELOPMENT_DEFAULT_NOT_FROZEN_FOR_INDEPENDENT_VALIDATION",
            "optimized_against_retrieval_performance": False,
        }


DEFAULT_DEVELOPMENT_BUDGETS = QueryBudgetConfigDev()


def _escape(value: str) -> str:
    return str(value).replace("\\", "\\\\").replace('"', '\\"')


def _qualified(value: str) -> str:
    return f'"{_escape(value)}"[{FIELD_QUALIFIER}]'


def _stable_terms(concept: dict[str, Any], budget: QueryBudgetConfigDev) -> list[dict[str, Any]]:
    usable = [term for term in concept["proposed_terms"] if term["proposal_class"] in USABLE_CLASSES]
    search_only = sorted(
        (term for term in usable if term["proposal_class"] == "SEARCH_ONLY_EXPANSION"),
        key=lambda term: (normalize_term(term["term"]), term["term"].encode("utf-8"), term["term_id"]),
    )
    allowed_search_ids = {term["term_id"] for term in search_only[:budget.max_search_only_terms_per_concept]}
    selected = [
        term for term in usable
        if term["proposal_class"] == "AUTHORIZED_EQUIVALENT" or term["term_id"] in allowed_search_ids
    ]
    by_normalized: dict[str, dict[str, Any]] = {}
    for term in selected:
        normalized = normalize_term(term["term"])
        if not normalized:
            continue
        previous = by_normalized.get(normalized)
        if previous is None or (
            previous["proposal_class"] == "SEARCH_ONLY_EXPANSION"
            and term["proposal_class"] == "AUTHORIZED_EQUIVALENT"
        ):
            by_normalized[normalized] = term
    return [by_normalized[key] for key in sorted(by_normalized)]


def _verify_receipt(plan: dict[str, Any], receipt: dict[str, Any]) -> None:
    required = {
        "artifact_schema_version", "validator_version", "status", "validated_plan_sha256",
        "canonical_target_sha256", "canonical_identity_unchanged", "classification_counts",
        "classification_audit", "authority_manifest_sha256", "receipt_sha256",
    }
    if set(receipt) != required:
        raise QueryCompilerV24Error("term validation receipt shape mismatch")
    if receipt["status"] != "PASS" or receipt["canonical_identity_unchanged"] is not True:
        raise QueryCompilerV24Error("term validation did not pass")
    material = {key: value for key, value in receipt.items() if key != "receipt_sha256"}
    if hashlib.sha256(canonical_bytes(material)).hexdigest() != receipt["receipt_sha256"]:
        raise QueryCompilerV24Error("term validation receipt hash mismatch")
    if sha256_value(plan) != receipt["validated_plan_sha256"]:
        raise QueryCompilerV24Error("term validation receipt is not bound to this plan")
    if plan["canonical_proposition"]["target_sha256"] != receipt["canonical_target_sha256"]:
        raise QueryCompilerV24Error("term validation receipt target mismatch")


def compile_validated_plan(
    plan: dict[str, Any],
    validation_receipt: dict[str, Any],
    *,
    budgets: QueryBudgetConfigDev = DEFAULT_DEVELOPMENT_BUDGETS,
) -> dict[str, Any]:
    validate_plan(plan)
    _verify_receipt(plan, validation_receipt)
    applicable = [intent for intent in plan["retrieval_intents"] if intent["applicability"] == "APPLICABLE"]
    if len(applicable) > budgets.max_intents_per_target:
        raise QueryBudgetExceeded("max_intents_per_target exceeded")
    intent_position = {name: index for index, name in enumerate(INTENT_ORDER)}
    dimension_position = {name: index for index, name in enumerate(DIMENSION_ORDER)}
    compiled = []
    for intent in sorted(applicable, key=lambda row: (intent_position[row["intent_type"]], row["intent_id"])):
        blueprints = intent["candidate_query_blueprints"]
        if len(blueprints) > budgets.max_blueprints_per_intent:
            raise QueryBudgetExceeded(f"max_blueprints_per_intent exceeded for {intent['intent_id']}")
        concept_by_id = {concept["concept_id"]: concept for concept in intent["search_concepts"]}
        for blueprint in sorted(blueprints, key=lambda row: row["blueprint_id"]):
            validate_blueprint_coverage(blueprint, plan["canonical_proposition"]["target_payload"])
            groups = []
            selected_term_ids: set[str] = set()
            for concept_id in sorted(
                blueprint["concept_ids"],
                key=lambda value: (dimension_position[concept_by_id[value]["concept_type"]], value),
            ):
                concept = concept_by_id[concept_id]
                terms = _stable_terms(concept, budgets)
                if not terms:
                    continue
                selected_term_ids.update(term["term_id"] for term in terms)
                rendered = [_qualified(term["term"]) for term in terms]
                group = rendered[0] if len(rendered) == 1 else "(" + " OR ".join(rendered) + ")"
                groups.append({
                    "concept_id": concept_id,
                    "concept_type": concept["concept_type"],
                    "query_fragment": group,
                    "terms": [{
                        "term_id": term["term_id"], "term": term["term"],
                        "proposal_source": term["proposal_source"],
                        "proposal_class": term["proposal_class"],
                        "authority_reference": term["authority_reference"],
                    } for term in terms],
                })
            relation_row = blueprint["dimension_coverage"][DIMENSION_ORDER.index("relation")]
            relation_term_ids = set(relation_row["query_term_ids"]) & selected_term_ids
            relation_state = blueprint["relation_representation_state"]
            if relation_state == "REPRESENTED" and not relation_term_ids:
                raise QueryCompilerV24Error("represented relation has no executable validated term")
            if relation_row["coverage_state"] in {"OMITTED", "UNDERREPRESENTED"}:
                if relation_state != "RELATION_UNDERREPRESENTED":
                    raise QueryCompilerV24Error("relation omission is not explicit")
            if not groups:
                raise QueryCompilerV24Error("blueprint contains no executable validated terms")
            query_string = " AND ".join(group["query_fragment"] for group in groups)
            compiled.append({
                "artifact_schema_version": "CompiledPropositionAwareQueryV24Dev",
                "query_string": query_string,
                "target_id": plan["target_id"],
                "source_routes": [{
                    "intent_id": intent["intent_id"],
                    "intent_type": intent["intent_type"],
                    "blueprint_id": blueprint["blueprint_id"],
                    "relation_representation_state": relation_state,
                    "dimension_coverage": blueprint["dimension_coverage"],
                }],
                "ordered_term_groups": groups,
                "provenance": {
                    "request_provenance": plan["request_provenance"],
                    "canonical_target_sha256": plan["canonical_proposition"]["target_sha256"],
                    "planner_config_sha256": plan["planner_config_sha256"],
                    "planner_prompt_template_version": plan["planner_prompt_template_version"],
                    "planner_cache_key_sha256": plan["planner_cache_key_sha256"],
                    "term_validation_receipt_sha256": validation_receipt["receipt_sha256"],
                    "compiler_version": COMPILER_VERSION,
                    "budget_config_sha256": sha256_value(budgets.to_dict()),
                },
                "execution_status": "NOT_EXECUTED_DEVELOPMENT_IMPLEMENTATION",
            })
    by_query_string: dict[str, dict[str, Any]] = {}
    for query in compiled:
        existing = by_query_string.get(query["query_string"])
        if existing is None:
            by_query_string[query["query_string"]] = query
        else:
            existing["source_routes"].extend(query["source_routes"])
    output = []
    for query_string in sorted(by_query_string, key=lambda value: value.encode("utf-8")):
        query = by_query_string[query_string]
        routes = sorted(
            query["source_routes"],
            key=lambda route: (intent_position[route["intent_type"]], route["intent_id"], route["blueprint_id"]),
        )
        query["source_routes"] = routes
        query["source_intent_ids"] = sorted({route["intent_id"] for route in routes})
        query["source_blueprint_ids"] = sorted({route["blueprint_id"] for route in routes})
        query["relation_representation_states"] = sorted({route["relation_representation_state"] for route in routes})
        identity_material = {
            "target_sha256": plan["canonical_proposition"]["target_sha256"],
            "query_string": query_string,
            "ordered_term_groups": query["ordered_term_groups"],
            "source_routes": routes,
            "compiler_version": COMPILER_VERSION,
            "budget_configuration": budgets.to_dict(),
        }
        query_sha = sha256_value(identity_material)
        query["query_id"] = f"v24q:{query_sha}"
        query["query_sha256"] = query_sha
        query["query_text_sha256"] = hashlib.sha256(query_string.encode("utf-8")).hexdigest()
        output.append(query)
    if len(output) > budgets.max_queries_per_target:
        raise QueryBudgetExceeded("max_queries_per_target exceeded")
    return {
        "artifact_schema_version": "PropositionAwareQueryCompilationV24Dev",
        "search_plan_version": SEARCH_PLAN_VERSION,
        "compiler_version": COMPILER_VERSION,
        "target_id": plan["target_id"],
        "validated_plan_sha256": validation_receipt["validated_plan_sha256"],
        "budget_configuration": budgets.to_dict(),
        "compiled_query_count": len(output),
        "compiled_queries": output,
        "family_g_emitted": False,
        "hidden_fallback_used": False,
        "network_calls": 0,
        "retrieval_calls": 0,
    }


__all__ = [
    "COMPILER_VERSION",
    "DEFAULT_DEVELOPMENT_BUDGETS",
    "QueryBudgetConfigDev",
    "QueryBudgetExceeded",
    "QueryCompilerV24Error",
    "compile_validated_plan",
]
