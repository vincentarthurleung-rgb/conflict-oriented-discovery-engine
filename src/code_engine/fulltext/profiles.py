"""Scientific profiles share infrastructure but never input assumptions."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class AdjudicationProfile:
    profile_id: str
    input_unit: str
    context_authority: str
    entity_decision_scope: str
    requires_reasoning_chain_for_intervention: bool
    version: str = "1.0.0"


ABSTRACT_L2_PROJECTION = AdjudicationProfile(
    "abstract_l2_projection", "claim_or_sentence", "lightweight_context",
    "candidate", False,
)
FULLTEXT_EVIDENCE_PROJECTION = AdjudicationProfile(
    "fulltext_evidence_projection", "experiment_linked_observation",
    "observation_level", "final_for_fulltext", True,
)


def profile_for(scope: str | None) -> AdjudicationProfile:
    return FULLTEXT_EVIDENCE_PROJECTION if str(scope or "").casefold() in {"fulltext", "full_text"} else ABSTRACT_L2_PROJECTION


__all__ = ["ABSTRACT_L2_PROJECTION", "FULLTEXT_EVIDENCE_PROJECTION", "AdjudicationProfile", "profile_for"]
