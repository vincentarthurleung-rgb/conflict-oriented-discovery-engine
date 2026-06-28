"""Offline agentic KG enrichment interfaces with deterministic adjudication."""

from __future__ import annotations

from typing import Any

from pydantic import Field

from code_engine.schemas.models import CODEBaseModel


class AgentSuggestion(CODEBaseModel):
    agent: str
    suggestion: dict[str, Any] = Field(default_factory=dict)
    confidence: float = 0.0
    requires_deterministic_validation: bool = True


class SuggestionAgent:
    role = "generic_suggestion"

    def suggest(self, payload: dict[str, Any]) -> AgentSuggestion:
        return AgentSuggestion(
            agent=self.__class__.__name__,
            suggestion={"action": self.role, "input_keys": sorted(payload)},
            confidence=0.5 if payload else 0.0,
            requires_deterministic_validation=True,
        )


class DomainRoutingAgent(SuggestionAgent):
    role = "propose_domain_route"


class EntityNormalizationAgent(SuggestionAgent):
    role = "propose_entity_normalization"


class RelationExtractionAgent(SuggestionAgent):
    role = "propose_relation_extraction"


class SchemaAlignmentAgent(SuggestionAgent):
    role = "propose_schema_alignment"


class ConflictReviewAgent(SuggestionAgent):
    role = "propose_conflict_review"


class CoveragePlanningAgent(SuggestionAgent):
    role = "propose_coverage_plan"


class HypothesisCriticAgent(SuggestionAgent):
    role = "propose_hypothesis_critique"


__all__ = [
    "AgentSuggestion", "DomainRoutingAgent", "EntityNormalizationAgent",
    "RelationExtractionAgent", "SchemaAlignmentAgent", "ConflictReviewAgent",
    "CoveragePlanningAgent", "HypothesisCriticAgent",
]

