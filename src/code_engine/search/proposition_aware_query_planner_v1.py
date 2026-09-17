"""Strict structured planner boundary for Search Plan v2.4-dev.

This module prepares and validates planner requests. It performs no provider or
network access by itself; a caller must explicitly inject a provider callable.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json
from pathlib import Path
from typing import Any, Callable

from code_engine.search.retrieval_intent_v1 import (
    DIMENSION_ORDER,
    INTENT_ORDER,
    validate_intent,
)
from code_engine.search.retrieval_plan_coverage_v1 import validate_blueprint_coverage


PLANNER_VERSION = "PropositionAwareQueryPlannerV1"
PLAN_SCHEMA_VERSION = "PropositionAwareSearchPlanV1"
PROMPT_VERSION = "PropositionAwareQueryPlannerPromptV1"
PROPOSAL_CLASSES = frozenset({"AUTHORIZED_EQUIVALENT", "SEARCH_ONLY_EXPANSION", "UNRESOLVED", "REJECTED"})
PROPOSAL_SOURCES = frozenset({"CANONICAL_TARGET", "DETERMINISTIC_AUTHORITY", "LLM_PROPOSAL"})

PROMPT_TEXT = """You are the PROPOSITION_AWARE_QUERY_PLANNER.

Your only role is to propose retrieval language and structured retrieval hypotheses.
You are NOT scientific authority. Never claim that a proposed term is scientifically
equivalent, biologically compatible, causally true, contradictory, or relevant.

You may propose aliases, lexical variants, gene/protein names, drug/target expressions,
relation paraphrases, perturbation language, endpoint language, biological-unit
expressions, disease/genotype expressions, therapy-response expressions, and
inverse/necessity/rescue formulations.

Return only a PropositionAwareSearchPlanV1 object. Do not emit an executable PubMed
query. Every concept and term must retain proposal source and a provisional proposal
class. Deterministic validators—not you—decide usable authority. Represent all eleven
coverage dimensions explicitly for each blueprint. Never silently drop relation
semantics; use RELATION_UNDERREPRESENTED when adequate lexical representation is not
available. Keep biological unit separate from subject/object identity.
"""


class PlannerValidationError(ValueError):
    """Raised when structured planner output violates the frozen contract."""


class PlannerProviderAuthorizationRequired(RuntimeError):
    """Raised when uncached planning is requested without an injected provider call."""


@dataclass(frozen=True)
class QueryPlannerConfigV1:
    provider: str
    model: str
    reasoning_effort: str
    temperature: float | None
    temperature_exposed: bool
    service_tier: str
    prompt_version: str
    schema_version: str
    maximum_attempts: int
    repair_policy: str

    def __post_init__(self) -> None:
        for field in ("provider", "model", "reasoning_effort", "service_tier", "prompt_version", "schema_version", "repair_policy"):
            if not str(getattr(self, field)).strip():
                raise PlannerValidationError(f"planner config {field} is required")
        if self.maximum_attempts < 1:
            raise PlannerValidationError("maximum_attempts must be positive")
        if not self.temperature_exposed and self.temperature is not None:
            raise PlannerValidationError("temperature must be null when it is not exposed")

    def to_dict(self) -> dict[str, Any]:
        return {"artifact_schema_version": "QueryPlannerConfigV1", **asdict(self)}


DEFAULT_DEVELOPMENT_CONFIG = QueryPlannerConfigV1(
    provider="OpenAI",
    model="gpt-5.6-sol",
    reasoning_effort="high",
    temperature=None,
    temperature_exposed=False,
    service_tier="default",
    prompt_version=PROMPT_VERSION,
    schema_version=PLAN_SCHEMA_VERSION,
    maximum_attempts=1,
    repair_policy="FAIL_CLOSED_NO_AUTOMATIC_RETRY_OR_REPAIR",
)


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def sha256_value(value: Any) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def canonical_target_hash(target: dict[str, Any]) -> str:
    if target.get("artifact_schema_version") != "ScientificPropositionTargetV1":
        raise PlannerValidationError("target must be ScientificPropositionTargetV1")
    return sha256_value(target)


def planner_config_hash(config: QueryPlannerConfigV1 | dict[str, Any]) -> str:
    value = config.to_dict() if isinstance(config, QueryPlannerConfigV1) else config
    return sha256_value(value)


def planner_cache_key(
    target: dict[str, Any],
    config: QueryPlannerConfigV1 | dict[str, Any],
    *,
    prompt_version: str,
    schema_version: str,
) -> str:
    return sha256_value({
        "canonical_target_hash": canonical_target_hash(target),
        "planner_model_config_hash": planner_config_hash(config),
        "prompt_version": prompt_version,
        "schema_version": schema_version,
    })


def _exact_keys(value: dict[str, Any], expected: set[str], label: str) -> None:
    if not isinstance(value, dict):
        raise PlannerValidationError(f"{label} must be an object")
    extra = set(value) - expected
    missing = expected - set(value)
    if extra or missing:
        raise PlannerValidationError(f"{label} keys mismatch; missing={sorted(missing)}, extra={sorted(extra)}")


def _nonempty(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise PlannerValidationError(f"{label} must be a non-empty string")
    return value


def _hash(value: Any, label: str) -> str:
    result = _nonempty(value, label)
    if len(result) != 64 or any(char not in "0123456789abcdef" for char in result):
        raise PlannerValidationError(f"{label} must be a lowercase SHA-256")
    return result


def _validate_proposal(value: dict[str, Any], label: str) -> None:
    expected = {
        "term_id", "term", "proposal_source", "proposal_class",
        "authority_reference", "confidence_not_used_for_scientific_truth",
    }
    _exact_keys(value, expected, label)
    _nonempty(value["term_id"], f"{label}.term_id")
    _nonempty(value["term"], f"{label}.term")
    if value["proposal_source"] not in PROPOSAL_SOURCES:
        raise PlannerValidationError(f"{label} has invalid proposal source")
    if value["proposal_class"] not in PROPOSAL_CLASSES:
        raise PlannerValidationError(f"{label} has invalid proposal class")
    if value["authority_reference"] is not None and not isinstance(value["authority_reference"], str):
        raise PlannerValidationError(f"{label}.authority_reference must be string or null")
    if value["proposal_class"] == "AUTHORIZED_EQUIVALENT" and not str(value["authority_reference"] or "").strip():
        raise PlannerValidationError(f"{label} authorized equivalence lacks authority reference")
    if value["confidence_not_used_for_scientific_truth"] is not True:
        raise PlannerValidationError(f"{label} improperly uses confidence as scientific truth")


def validate_plan(plan: dict[str, Any], *, expected_target: dict[str, Any] | None = None) -> dict[str, Any]:
    """Validate the frozen strict schema plus deterministic semantic invariants."""
    root_keys = {
        "artifact_schema_version", "request_provenance", "target_id", "canonical_proposition",
        "planner_config_sha256", "planner_prompt_template_version", "planner_cache_key_sha256",
        "retrieval_intents", "planner_output_frozen_before_retrieval",
    }
    _exact_keys(plan, root_keys, "plan")
    if plan["artifact_schema_version"] != PLAN_SCHEMA_VERSION:
        raise PlannerValidationError("unsupported plan schema")
    _exact_keys(plan["request_provenance"], {"request_sha256", "preserved_request_reference"}, "request_provenance")
    _hash(plan["request_provenance"]["request_sha256"], "request_sha256")
    _nonempty(plan["request_provenance"]["preserved_request_reference"], "preserved_request_reference")
    _nonempty(plan["target_id"], "target_id")
    _exact_keys(plan["canonical_proposition"], {"schema_version", "target_sha256", "target_payload"}, "canonical_proposition")
    canonical = plan["canonical_proposition"]
    if canonical["schema_version"] != "ScientificPropositionTargetV1":
        raise PlannerValidationError("canonical target schema mismatch")
    _hash(canonical["target_sha256"], "target_sha256")
    if not isinstance(canonical["target_payload"], dict):
        raise PlannerValidationError("target payload must be an object")
    if canonical_target_hash(canonical["target_payload"]) != canonical["target_sha256"]:
        raise PlannerValidationError("canonical target hash mismatch")
    if expected_target is not None and canonical_bytes(canonical["target_payload"]) != canonical_bytes(expected_target):
        raise PlannerValidationError("planner output changed canonical scientific identity")
    _hash(plan["planner_config_sha256"], "planner_config_sha256")
    _hash(plan["planner_cache_key_sha256"], "planner_cache_key_sha256")
    _nonempty(plan["planner_prompt_template_version"], "planner_prompt_template_version")
    if plan["planner_output_frozen_before_retrieval"] is not True:
        raise PlannerValidationError("planner output must be frozen before retrieval")
    intents = plan["retrieval_intents"]
    if not isinstance(intents, list) or not intents:
        raise PlannerValidationError("at least one retrieval intent is required")
    intent_ids: set[str] = set()
    global_ids: set[str] = set()
    for intent_index, intent in enumerate(intents):
        label = f"retrieval_intents[{intent_index}]"
        intent_keys = {
            "intent_id", "intent_type", "applicability", "applicability_rationale", "scientific_rationale",
            "required_dimensions", "optional_dimensions", "biological_unit_context", "search_concepts",
            "candidate_query_blueprints",
        }
        _exact_keys(intent, intent_keys, label)
        intent_id = _nonempty(intent["intent_id"], f"{label}.intent_id")
        if intent_id in intent_ids:
            raise PlannerValidationError("duplicate intent id")
        intent_ids.add(intent_id)
        _nonempty(intent["applicability_rationale"], f"{label}.applicability_rationale")
        _nonempty(intent["scientific_rationale"], f"{label}.scientific_rationale")
        _exact_keys(intent["biological_unit_context"], {"target_value", "planning_state", "separate_from_entity_identity"}, f"{label}.biological_unit_context")
        unit = intent["biological_unit_context"]
        if unit["planning_state"] not in {"PRESENT", "ABSENT", "UNRESOLVED", "NOT_APPLICABLE"}:
            raise PlannerValidationError("invalid biological-unit planning state")
        validate_intent(intent, canonical["target_payload"])
        concepts = intent["search_concepts"]
        if not isinstance(concepts, list):
            raise PlannerValidationError("search concepts must be a list")
        concept_ids: set[str] = set()
        term_ids: set[str] = set()
        for concept_index, concept in enumerate(concepts):
            concept_label = f"{label}.search_concepts[{concept_index}]"
            concept_keys = {
                "concept_id", "concept_type", "canonical_value", "proposal_source", "proposal_class",
                "authority_reference", "confidence_not_used_for_scientific_truth", "proposed_terms",
            }
            _exact_keys(concept, concept_keys, concept_label)
            concept_id = _nonempty(concept["concept_id"], f"{concept_label}.concept_id")
            if concept_id in concept_ids or concept_id in global_ids:
                raise PlannerValidationError("duplicate concept id")
            concept_ids.add(concept_id)
            global_ids.add(concept_id)
            if concept["concept_type"] not in DIMENSION_ORDER:
                raise PlannerValidationError("invalid concept type")
            concept_proposal = {key: concept[key] for key in (
                "proposal_source", "proposal_class", "authority_reference", "confidence_not_used_for_scientific_truth"
            )}
            concept_proposal.update({"term_id": concept_id, "term": str(concept["canonical_value"] or concept_id)})
            _validate_proposal(concept_proposal, concept_label)
            if not isinstance(concept["proposed_terms"], list):
                raise PlannerValidationError("proposed terms must be a list")
            for term_index, term in enumerate(concept["proposed_terms"]):
                _validate_proposal(term, f"{concept_label}.proposed_terms[{term_index}]")
                if term["term_id"] in term_ids or term["term_id"] in global_ids:
                    raise PlannerValidationError("duplicate term id")
                term_ids.add(term["term_id"])
                global_ids.add(term["term_id"])
        blueprints = intent["candidate_query_blueprints"]
        if not isinstance(blueprints, list):
            raise PlannerValidationError("candidate query blueprints must be a list")
        for blueprint_index, blueprint in enumerate(blueprints):
            blueprint_label = f"{label}.candidate_query_blueprints[{blueprint_index}]"
            blueprint_keys = {
                "blueprint_id", "concept_ids", "dimension_coverage", "relation_representation_state",
                "compiler_input_only", "executable_query_absent",
            }
            _exact_keys(blueprint, blueprint_keys, blueprint_label)
            blueprint_id = _nonempty(blueprint["blueprint_id"], f"{blueprint_label}.blueprint_id")
            if blueprint_id in global_ids:
                raise PlannerValidationError("duplicate blueprint id")
            global_ids.add(blueprint_id)
            if blueprint["compiler_input_only"] is not True or blueprint["executable_query_absent"] is not True:
                raise PlannerValidationError("planner blueprint cannot contain an executable query")
            if not isinstance(blueprint["concept_ids"], list) or not blueprint["concept_ids"]:
                raise PlannerValidationError("blueprint concept ids are required")
            if not set(blueprint["concept_ids"]).issubset(concept_ids):
                raise PlannerValidationError("blueprint references an unknown concept")
            validate_blueprint_coverage(blueprint, canonical["target_payload"])
            for row in blueprint["dimension_coverage"]:
                if not set(row["source_concept_ids"]).issubset(concept_ids):
                    raise PlannerValidationError("coverage references unknown concept")
                if not set(row["query_term_ids"]).issubset(term_ids):
                    raise PlannerValidationError("coverage references unknown term")
    return plan


def immutable_cache_write(path: Path, cache_key: str, plan: dict[str, Any]) -> None:
    validate_plan(plan)
    if plan["planner_cache_key_sha256"] != cache_key:
        raise PlannerValidationError("cache path key does not match plan")
    payload = canonical_bytes(plan) + b"\n"
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        if path.read_bytes() != payload:
            raise PlannerValidationError("immutable planner cache collision")
        return
    with path.open("xb") as stream:
        stream.write(payload)


class PropositionAwareQueryPlannerV1:
    """Provider-neutral structured planner wrapper with an explicit call boundary."""

    def __init__(self, config: QueryPlannerConfigV1 = DEFAULT_DEVELOPMENT_CONFIG):
        self.config = config

    def expected_cache_key(self, target: dict[str, Any]) -> str:
        return planner_cache_key(
            target,
            self.config,
            prompt_version=self.config.prompt_version,
            schema_version=self.config.schema_version,
        )

    def render_prompt(self, target: dict[str, Any], request_reference: str) -> str:
        canonical_target_hash(target)
        return (
            PROMPT_TEXT
            + "\nPreserved request reference: " + str(request_reference)
            + "\nCanonical ScientificPropositionTargetV1:\n"
            + json.dumps(target, sort_keys=True, ensure_ascii=False)
        )

    def plan(
        self,
        target: dict[str, Any],
        *,
        request_reference: str,
        cached_plan: dict[str, Any] | None = None,
        provider_call: Callable[..., dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        expected_key = self.expected_cache_key(target)
        if cached_plan is not None:
            validate_plan(cached_plan, expected_target=target)
            if cached_plan["planner_cache_key_sha256"] != expected_key:
                raise PlannerValidationError("cached planner key mismatch")
            return cached_plan
        if provider_call is None:
            raise PlannerProviderAuthorizationRequired(
                "uncached planner generation requires an explicitly authorized injected provider call"
            )
        if self.config.maximum_attempts != 1 or self.config.repair_policy != "FAIL_CLOSED_NO_AUTOMATIC_RETRY_OR_REPAIR":
            raise PlannerValidationError("development planner must use one fail-closed attempt")
        raw = provider_call(
            self.render_prompt(target, request_reference),
            model=self.config.model,
            reasoning_effort=self.config.reasoning_effort,
            service_tier=self.config.service_tier,
            temperature=self.config.temperature,
            schema_version=self.config.schema_version,
        )
        validate_plan(raw, expected_target=target)
        if raw["planner_cache_key_sha256"] != expected_key:
            raise PlannerValidationError("provider planner key mismatch")
        return raw


__all__ = [
    "DEFAULT_DEVELOPMENT_CONFIG",
    "PLAN_SCHEMA_VERSION",
    "PLANNER_VERSION",
    "PROMPT_TEXT",
    "PROMPT_VERSION",
    "PlannerProviderAuthorizationRequired",
    "PlannerValidationError",
    "PropositionAwareQueryPlannerV1",
    "QueryPlannerConfigV1",
    "canonical_bytes",
    "canonical_target_hash",
    "immutable_cache_write",
    "planner_cache_key",
    "planner_config_hash",
    "sha256_value",
    "validate_plan",
]
