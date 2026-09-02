"""Offline contracts for proposition-driven targeted corpus expansion."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class StrictPlanningModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class TargetedRetrievalSpecificationV1(StrictPlanningModel):
    schema_version: Literal["targeted_retrieval_specification_v1"] = "targeted_retrieval_specification_v1"
    target_id: str
    source_proposition_block_id: str
    entity_proposition: str
    relation_effect_family: str
    object_target: str
    measurement_targets: list[str]
    measurement_properties: list[str]
    intervention_targets: list[str] = Field(default_factory=list)
    causal_evidential_mode: str
    evidence_family: str
    result_semantic_families: list[str]
    contrast_semantics: str
    allowed_proposition_qualifiers: list[str]
    excluded_proposition_mismatches: list[str]
    publication_independence_requirements: list[str]
    fulltext_preference: str
    direction_hidden_during_primary_retrieval: Literal[True] = True
    scientific_gates_reused_without_relaxation: Literal[True] = True


class PlannedQueryComponentsV1(StrictPlanningModel):
    schema_version: Literal["planned_query_components_v1"] = "planned_query_components_v1"
    target_id: str
    entity_terms: list[str]
    relation_effect_terms: list[str]
    measurement_target_terms: list[str]
    measurement_property_terms: list[str]
    intervention_terms: list[str]
    prohibited_primary_terms: list[str]
    fuzzy_entity_expansion: Literal[False] = False
    external_ontology_expansion: Literal[False] = False
    executable_query_generated: Literal[False] = False

    @model_validator(mode="after")
    def primary_components_are_direction_neutral(self) -> "PlannedQueryComponentsV1":
        primary = self.entity_terms + self.relation_effect_terms + self.measurement_target_terms + self.measurement_property_terms + self.intervention_terms
        prohibited = {term.casefold() for term in self.prohibited_primary_terms}
        if any(term.casefold() in prohibited for term in primary):
            raise ValueError("contradiction-seeking term present in primary query components")
        return self


class BoundedTargetExpansionBudgetV1(StrictPlanningModel):
    schema_version: Literal["bounded_target_expansion_budget_v1"] = "bounded_target_expansion_budget_v1"
    target_id: str
    maximum_metadata_candidates: int = Field(gt=0)
    maximum_abstract_candidates: int = Field(gt=0)
    maximum_fulltexts: int = Field(gt=0)
    maximum_fulltext_extraction_calls: int = Field(gt=0)
    maximum_provider_calls: int = Field(gt=0)
    maximum_provider_attempts_per_source: Literal[1] = 1
    maximum_provider_retries_per_source: Literal[0] = 0
    cache_required_before_provider_call: Literal[True] = True

    @model_validator(mode="after")
    def bounds_are_monotone(self) -> "BoundedTargetExpansionBudgetV1":
        if not (self.maximum_metadata_candidates >= self.maximum_abstract_candidates >= self.maximum_fulltexts):
            raise ValueError("candidate budgets must narrow monotonically")
        if self.maximum_fulltext_extraction_calls > self.maximum_fulltexts:
            raise ValueError("extraction calls cannot exceed admitted fulltexts")
        if self.maximum_provider_calls > self.maximum_fulltext_extraction_calls:
            raise ValueError("provider calls cannot exceed extraction calls when retries are disabled")
        return self


EVALUATION_LEVELS_V1 = {
    0: "retrieved_publications",
    1: "fulltext_available_usable",
    2: "structurally_eligible_experimental_observations",
    3: "entity_eligible_observations",
    4: "minimum_sufficient_propositions",
    5: "cross_publication_proposition_peers",
    6: "source_independent_proposition_compatible_pairs",
    7: "opposing_result_candidates",
    8: "candidate_qualified_pairs",
}


def primary_contradiction_term_count_v1(rows: list[PlannedQueryComponentsV1]) -> int:
    """Count prohibited terms in only the primary, direction-neutral lane."""
    count = 0
    for row in rows:
        prohibited = {term.casefold() for term in row.prohibited_primary_terms}
        primary = row.entity_terms + row.relation_effect_terms + row.measurement_target_terms + row.measurement_property_terms + row.intervention_terms
        count += sum(term.casefold() in prohibited for term in primary)
    return count
