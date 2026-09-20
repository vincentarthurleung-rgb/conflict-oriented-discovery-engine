"""Validated-plan-only compiler boundary for Search Plan v2.4 development."""

from __future__ import annotations

import hashlib
from typing import Any

from code_engine.search.planner_authority_contract_split_v1 import (
    USABLE_CLASSIFICATIONS,
    VALIDATED_PLAN_VERSION,
    AuthoritySplitContractError,
    validate_validated_plan,
)
from code_engine.search.proposition_aware_query_planner_v1 import sha256_value
from code_engine.search.query_compiler_v24_dev import (
    DEFAULT_DEVELOPMENT_BUDGETS,
    QueryBudgetConfigDev,
    QueryBudgetExceeded,
    QueryCompilerV24Error,
)
from code_engine.search.retrieval_intent_v1 import DIMENSION_ORDER, INTENT_ORDER
from code_engine.search.search_term_validator_v1 import normalize_term


COMPILER_VERSION = "DeterministicQueryCompilerV24DevValidatedPlanV1"
FIELD_QUALIFIER = "Title/Abstract"


def _qualified(value: str) -> str:
    escaped = str(value).replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"[{FIELD_QUALIFIER}]'


def _stable_terms(
    concept: dict[str, Any], receipts: dict[str, dict[str, Any]], budget: QueryBudgetConfigDev,
) -> list[dict[str, Any]]:
    enriched = [
        {**term, **{
            "deterministic_classification": receipts[term["term_id"]]["deterministic_classification"],
            "authority_reference": receipts[term["term_id"]]["authority_reference"],
            "receipt_sha256": receipts[term["term_id"]]["receipt_sha256"],
        }}
        for term in concept["proposed_terms"]
        if receipts[term["term_id"]]["deterministic_classification"] in USABLE_CLASSIFICATIONS
    ]
    search_only = sorted(
        (term for term in enriched if term["deterministic_classification"] == "SEARCH_ONLY_EXPANSION"),
        key=lambda term: (normalize_term(term["term"]), term["term"].encode("utf-8"), term["term_id"]),
    )
    allowed_search_ids = {term["term_id"] for term in search_only[:budget.max_search_only_terms_per_concept]}
    selected = [
        term for term in enriched
        if term["deterministic_classification"] == "AUTHORIZED_EQUIVALENT"
        or term["term_id"] in allowed_search_ids
    ]
    by_normalized: dict[str, dict[str, Any]] = {}
    for term in selected:
        normalized = normalize_term(term["term"])
        previous = by_normalized.get(normalized)
        if previous is None or (
            previous["deterministic_classification"] == "SEARCH_ONLY_EXPANSION"
            and term["deterministic_classification"] == "AUTHORIZED_EQUIVALENT"
        ):
            by_normalized[normalized] = term
    return [by_normalized[key] for key in sorted(by_normalized)]


def compile_validated_proposition_aware_plan(
    plan: dict[str, Any],
    *,
    budgets: QueryBudgetConfigDev = DEFAULT_DEVELOPMENT_BUDGETS,
) -> dict[str, Any]:
    """Compile only a hash-bound ValidatedPropositionAwareSearchPlanV1."""
    if not isinstance(plan, dict) or plan.get("artifact_schema_version") != VALIDATED_PLAN_VERSION:
        raise QueryCompilerV24Error(
            "compiler requires ValidatedPropositionAwareSearchPlanV1; raw planner proposals are forbidden"
        )
    try:
        validate_validated_plan(plan)
    except AuthoritySplitContractError as exc:
        raise QueryCompilerV24Error(f"validated-plan boundary rejected input: {exc}") from exc
    proposal = plan["planner_proposal_payload"]
    receipts = {row["term_id"]: row for row in plan["term_validation_receipts"]}
    coverage = {row["blueprint_id"]: row for row in plan["retrieval_plan_coverage"]}
    applicable = [row for row in proposal["retrieval_intents"] if row["applicability"] == "APPLICABLE"]
    if len(applicable) > budgets.max_intents_per_target:
        raise QueryBudgetExceeded("max_intents_per_target exceeded")
    intent_position = {name: index for index, name in enumerate(INTENT_ORDER)}
    dimension_position = {name: index for index, name in enumerate(DIMENSION_ORDER)}
    compiled = []
    for intent in sorted(applicable, key=lambda row: (intent_position[row["intent_type"]], row["intent_id"])):
        if len(intent["candidate_query_blueprints"]) > budgets.max_blueprints_per_intent:
            raise QueryBudgetExceeded(f"max_blueprints_per_intent exceeded for {intent['intent_id']}")
        concepts = {row["concept_id"]: row for row in intent["search_concepts"]}
        for blueprint in sorted(intent["candidate_query_blueprints"], key=lambda row: row["blueprint_id"]):
            coverage_record = coverage[blueprint["blueprint_id"]]
            groups = []
            selected_ids: set[str] = set()
            for concept_id in sorted(
                blueprint["concept_ids"],
                key=lambda value: (dimension_position[concepts[value]["concept_type"]], value),
            ):
                concept = concepts[concept_id]
                terms = _stable_terms(concept, receipts, budgets)
                if not terms:
                    continue
                selected_ids.update(term["term_id"] for term in terms)
                rendered = [_qualified(term["term"]) for term in terms]
                groups.append({
                    "concept_id": concept_id, "concept_type": concept["concept_type"],
                    "query_fragment": rendered[0] if len(rendered) == 1 else "(" + " OR ".join(rendered) + ")",
                    "terms": [{
                        "term_id": term["term_id"], "term": term["term"],
                        "deterministic_classification": term["deterministic_classification"],
                        "authority_reference": term["authority_reference"],
                        "validation_receipt_sha256": term["receipt_sha256"],
                    } for term in terms],
                })
            relation = coverage_record["dimension_coverage"][DIMENSION_ORDER.index("relation")]
            relation_ids = set(relation["query_term_ids"]) & selected_ids
            relation_state = coverage_record["relation_representation_state"]
            if relation_state == "REPRESENTED" and not relation_ids:
                raise QueryCompilerV24Error("represented relation has no executable validated term")
            if relation["coverage_state"] in {"OMITTED", "UNDERREPRESENTED"} \
                    and relation_state != "RELATION_UNDERREPRESENTED":
                raise QueryCompilerV24Error("relation omission is not explicit")
            if not groups:
                raise QueryCompilerV24Error("blueprint contains no executable validated terms")
            compiled.append({
                "artifact_schema_version": "CompiledPropositionAwareQueryV24DevValidatedPlanV1",
                "query_string": " AND ".join(group["query_fragment"] for group in groups),
                "target_id": plan["target_id"],
                "source_routes": [{
                    "intent_id": intent["intent_id"], "intent_type": intent["intent_type"],
                    "blueprint_id": blueprint["blueprint_id"],
                    "relation_representation_state": relation_state,
                    "dimension_coverage": coverage_record["dimension_coverage"],
                }],
                "ordered_term_groups": groups,
                "provenance": {
                    "request_provenance": plan["request_provenance"],
                    "canonical_target_sha256": plan["canonical_proposition"]["target_sha256"],
                    "planner_config_sha256": plan["planner_config_sha256"],
                    "planner_prompt_template_version": plan["planner_prompt_template_version"],
                    "planner_cache_key_sha256": plan["planner_cache_key_sha256"],
                    "planner_proposal_sha256": plan["planner_proposal_sha256"],
                    "term_validation_receipts_sha256": plan["term_validation_receipts_sha256"],
                    "retrieval_plan_coverage_sha256": plan["retrieval_plan_coverage_sha256"],
                    "compiler_version": COMPILER_VERSION,
                    "budget_config_sha256": sha256_value(budgets.to_dict()),
                },
                "execution_status": "NOT_EXECUTED_DEVELOPMENT_IMPLEMENTATION",
            })
    by_query: dict[str, dict[str, Any]] = {}
    for query in compiled:
        existing = by_query.get(query["query_string"])
        if existing is None:
            by_query[query["query_string"]] = query
        else:
            existing["source_routes"].extend(query["source_routes"])
    output_rows = []
    for query_string in sorted(by_query, key=lambda value: value.encode("utf-8")):
        query = by_query[query_string]
        routes = sorted(query["source_routes"], key=lambda row: (
            intent_position[row["intent_type"]], row["intent_id"], row["blueprint_id"],
        ))
        query["source_routes"] = routes
        query["source_intent_ids"] = sorted({row["intent_id"] for row in routes})
        query["source_blueprint_ids"] = sorted({row["blueprint_id"] for row in routes})
        query["relation_representation_states"] = sorted({
            row["relation_representation_state"] for row in routes
        })
        identity = {
            "target_sha256": plan["canonical_proposition"]["target_sha256"],
            "query_string": query_string, "ordered_term_groups": query["ordered_term_groups"],
            "source_routes": routes, "compiler_version": COMPILER_VERSION,
            "budget_configuration": budgets.to_dict(),
        }
        query_sha = sha256_value(identity)
        query["query_id"] = f"v24q:{query_sha}"
        query["query_sha256"] = query_sha
        query["query_text_sha256"] = hashlib.sha256(query_string.encode("utf-8")).hexdigest()
        output_rows.append(query)
    if len(output_rows) > budgets.max_queries_per_target:
        raise QueryBudgetExceeded("max_queries_per_target exceeded")
    return {
        "artifact_schema_version": "PropositionAwareQueryCompilationV24DevValidatedPlanV1",
        "search_plan_version": "v2.4-dev", "compiler_version": COMPILER_VERSION,
        "input_artifact_schema_version": VALIDATED_PLAN_VERSION,
        "target_id": plan["target_id"], "validated_plan_sha256": sha256_value(plan),
        "budget_configuration": budgets.to_dict(),
        "compiled_query_count": len(output_rows), "compiled_queries": output_rows,
        "compiler_can_read_unvalidated_llm_output": False,
        "compiler_can_read_model_authority_claim": False,
        "validated_authority_receipts_sha256": plan["term_validation_receipts_sha256"],
        "validated_coverage_sha256": plan["retrieval_plan_coverage_sha256"],
        "family_g_emitted": False, "hidden_fallback_used": False,
        "network_calls": 0, "retrieval_calls": 0,
    }


__all__ = ["COMPILER_VERSION", "compile_validated_proposition_aware_plan"]
