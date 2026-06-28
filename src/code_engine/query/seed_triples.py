"""Non-evidence seed triples derived from user research intent."""

from __future__ import annotations

import hashlib

from pydantic import Field, model_validator

from code_engine.query.intent import ResearchIntent
from code_engine.schemas.models import CODEBaseModel


class SeedResearchTriple(CODEBaseModel):
    triple_id: str
    subject: str
    relation: str
    object: str
    subject_type: str = "unknown"
    object_type: str = "unknown"
    purpose: str = "literature_search_planning"
    source: str = "user_intent_llm_parser"
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    is_evidence: bool = False
    warnings: list[str] = Field(default_factory=lambda: ["seed_triple_not_paper_evidence"])

    @model_validator(mode="after")
    def enforce_non_evidence(self):
        self.source = "user_intent_llm_parser"
        self.is_evidence = False
        if "seed_triple_not_paper_evidence" not in self.warnings:
            self.warnings.append("seed_triple_not_paper_evidence")
        return self


def build_seed_triples(intent: ResearchIntent) -> list[SeedResearchTriple]:
    subjects = intent.comparison_entities or intent.primary_entities
    objects = ([intent.disease_or_condition] if intent.disease_or_condition else []) + intent.mechanism_entities
    triples = []
    for subject in subjects:
        for obj in objects or intent.outcome_entities:
            stable = f"{intent.intent_id}|{subject}|mechanism_or_effect|{obj}"
            triples.append(SeedResearchTriple(
                triple_id=hashlib.sha256(stable.encode()).hexdigest()[:16],
                subject=subject,
                relation="mechanism_or_effect",
                object=obj,
                subject_type="compound",
                purpose="search_term_expansion",
                confidence=intent.confidence,
            ))
    return triples
