"""Deterministic opportunity envelopes for partial scientific propositions."""
from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


DimensionStateV1 = Literal["resolved", "unresolved", "not_applicable", "review_required"]
EnvelopeStateV1 = Literal[
    "cross_publication_match_already_supported",
    "potential_match_if_single_gap_resolved",
    "potential_match_if_multiple_gaps_resolved",
    "blocked_resolved_proposition_mismatch",
    "blocked_profile_or_causal_mode",
    "blocked_entity_identity",
    "blocked_same_publication",
    "blocked_duplicate_or_same_experiment",
    "insufficient_shared_authority",
]


class StrictCandidateModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class PartialDimensionV1(StrictCandidateModel):
    state: DimensionStateV1
    value: Any | None = None
    authority: str
    source_refs: list[str] = Field(default_factory=list)


class PartialScientificPropositionSignatureV1(StrictCandidateModel):
    schema_version: Literal[
        "partial_scientific_proposition_signature_v1"
    ] = "partial_scientific_proposition_signature_v1"
    observation_id: str
    publication_id: str | None
    experiment_id: str | None
    evidence_span_ids: list[str] = Field(default_factory=list)
    profile: str
    entity_integrity_permits_comparison: bool
    dimensions: dict[str, PartialDimensionV1]
    direction_excluded: Literal[True] = True
    candidate_only: Literal[True] = True


class CrossPublicationCompatibilityEnvelopeV1(StrictCandidateModel):
    schema_version: Literal[
        "cross_publication_compatibility_envelope_v1"
    ] = "cross_publication_compatibility_envelope_v1"
    left_observation_id: str
    right_observation_id: str
    envelope_state: EnvelopeStateV1
    resolved_compatible_dimensions: list[str] = Field(default_factory=list)
    unresolved_dimensions: list[str] = Field(default_factory=list)
    resolved_mismatches: list[str] = Field(default_factory=list)
    unresolved_gap_count: int = 0
    source_independent: bool
    candidate_created: Literal[False] = False
    contradiction_evaluated: Literal[False] = False


PROPOSITION_CRITICAL_DIMENSIONS = (
    "entity_proposition", "relation_family", "object_target",
    "measurement_target", "measurement_property", "result_semantic_level",
    "intervention_proposition", "causal_evidential_mode", "contrast_role",
)


def compare_cross_publication_envelope_v1(
    left: PartialScientificPropositionSignatureV1,
    right: PartialScientificPropositionSignatureV1,
) -> CrossPublicationCompatibilityEnvelopeV1:
    """Compare only exact resolved authority; unresolved is a gap, never a match."""
    base = dict(
        left_observation_id=left.observation_id,
        right_observation_id=right.observation_id,
        source_independent=False,
    )
    if not left.publication_id or not right.publication_id:
        return CrossPublicationCompatibilityEnvelopeV1(
            **base, envelope_state="insufficient_shared_authority"
        )
    if left.publication_id == right.publication_id:
        return CrossPublicationCompatibilityEnvelopeV1(
            **base, envelope_state="blocked_same_publication"
        )
    if (
        left.observation_id == right.observation_id
        or (left.experiment_id and left.experiment_id == right.experiment_id)
        or bool(set(left.evidence_span_ids) & set(right.evidence_span_ids))
    ):
        return CrossPublicationCompatibilityEnvelopeV1(
            **base, envelope_state="blocked_duplicate_or_same_experiment"
        )
    base["source_independent"] = True
    if not left.entity_integrity_permits_comparison or not right.entity_integrity_permits_comparison:
        return CrossPublicationCompatibilityEnvelopeV1(
            **base, envelope_state="blocked_entity_identity"
        )
    if left.profile != right.profile:
        return CrossPublicationCompatibilityEnvelopeV1(
            **base, envelope_state="blocked_profile_or_causal_mode",
            resolved_mismatches=["profile"],
        )
    compatible, unresolved, mismatches = [], [], []
    for name in PROPOSITION_CRITICAL_DIMENSIONS:
        a, b = left.dimensions[name], right.dimensions[name]
        if a.state == "not_applicable" and b.state == "not_applicable":
            compatible.append(name)
        elif a.state != "resolved" or b.state != "resolved":
            unresolved.append(name)
        elif a.value == b.value:
            compatible.append(name)
        else:
            mismatches.append(name)
    if "causal_evidential_mode" in mismatches:
        state: EnvelopeStateV1 = "blocked_profile_or_causal_mode"
    elif mismatches:
        state = "blocked_resolved_proposition_mismatch"
    elif len(unresolved) == 0:
        state = "cross_publication_match_already_supported"
    elif len(unresolved) == 1:
        state = "potential_match_if_single_gap_resolved"
    else:
        state = "potential_match_if_multiple_gaps_resolved"
    return CrossPublicationCompatibilityEnvelopeV1(
        **base, envelope_state=state,
        resolved_compatible_dimensions=compatible,
        unresolved_dimensions=unresolved,
        resolved_mismatches=mismatches,
        unresolved_gap_count=len(unresolved),
    )
