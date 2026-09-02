"""Strict candidate contract for an unauthorized future extraction smoke."""
from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class ProviderExtractionCandidateV1(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["provider_extraction_candidate_v1"] = "provider_extraction_candidate_v1"
    candidate_id: str
    target_id: str
    publication_identity: dict[str, str | None]
    publication_independence_state: Literal["independent_publication"]
    fulltext_source: str
    fulltext_sha256: str
    plausibility_evidence: list[str] = Field(min_length=1)
    remaining_scientific_uncertainty: list[str] = Field(min_length=1)
    cache_state: Literal["miss_no_sufficient_matching_extraction"]
    duplicate_state: Literal["not_known_duplicate"]
    recommended_extraction_contract: dict[str, Any]
    estimated_provider_call_count: Literal[1] = 1
    retry_count: Literal[0] = 0
    execution_authorized: Literal[False] = False
    provider_executed: Literal[False] = False


def contains_all_groups_v1(text: str, groups: list[list[str]]) -> bool:
    """Exact case-insensitive surface check; each semantic group needs one term."""
    folded = text.casefold()
    return all(any(term.casefold() in folded for term in group) for group in groups)
