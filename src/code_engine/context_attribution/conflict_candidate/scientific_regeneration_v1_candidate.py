"""Candidate-only scientific regeneration and bounded fulltext diagnostics.

The production-neutral contracts in this module consume already validated,
canonical scientific structures.  They do not retrieve, normalize free text,
use approximate similarity, mutate historical candidates, or create L4/Formal
authority.
"""
from __future__ import annotations

from itertools import combinations
from typing import Any, Iterable, Literal, Sequence

from pydantic import BaseModel, ConfigDict, Field, model_validator

from ..claim_alignment.scientific_proposition_v1_candidate import (
    ScientificPropositionCompatibilityV1,
    ScientificPropositionSignatureV1,
    evaluate_scientific_proposition_compatibility_v1,
)
from ..layer_identity import layer_identity
from .contradiction_v2 import compare_result_directions_v2


ALIGNED_PROPOSITION_STATES_V1 = frozenset({
    "aligned_exact",
    "aligned_compatible",
    "aligned_with_granularity_qualification",
})


class StrictCandidateModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class FulltextScientificObservationV1(StrictCandidateModel):
    """Minimal authority envelope for one validated fulltext observation."""

    schema_version: Literal[
        "fulltext_scientific_observation_v1"
    ] = "fulltext_scientific_observation_v1"
    observation_id: str
    publication_id: str | None = None
    source_document_id: str | None = None
    experiment_id: str | None = None
    evidence_span_ids: list[str] = Field(default_factory=list)
    evidence_text_hashes: list[str] = Field(default_factory=list)
    validation_state: Literal["validated", "rejected", "structurally_invalid"]
    statement_role: Literal[
        "current_study_experiment",
        "background",
        "discussion_speculation",
        "hypothesis_only",
        "review_only",
        "unresolved",
    ]
    entity_integrity_state: Literal[
        "eligible",
        "eligible_validated_normalization",
        "eligible_with_historical_warning",
        "blocked_upstream_entity_integrity",
        "blocked_upstream_claim_integrity",
        "blocked_upstream_scientific_integrity",
    ]
    provenance_complete: bool
    direction: str | None = None
    signature: ScientificPropositionSignatureV1
    source_refs: list[str] = Field(default_factory=list)

    @property
    def lane_b_eligible(self) -> bool:
        return (
            self.validation_state == "validated"
            and self.statement_role == "current_study_experiment"
            and self.entity_integrity_state.startswith("eligible")
            and self.provenance_complete
        )

    @model_validator(mode="after")
    def signature_refers_to_observation(self):
        if self.signature.observation_id != self.observation_id:
            raise ValueError("signature_observation_identity_mismatch")
        return self


class ScientificPropositionBlockV1(StrictCandidateModel):
    schema_version: Literal[
        "scientific_proposition_block_v1"
    ] = "scientific_proposition_block_v1"
    proposition_block_id: str
    blocking_components: dict[str, Any]
    observation_ids: list[str]
    signature_complete_observation_count: int
    unresolved_blocking_dimensions: list[str] = Field(default_factory=list)
    bounded_generation: Literal[True] = True
    direction_excluded_from_key: Literal[True] = True
    fuzzy_matching_used: Literal[False] = False
    embedding_matching_used: Literal[False] = False


class DiagnosticFulltextPairV1(StrictCandidateModel):
    schema_version: Literal[
        "diagnostic_fulltext_conflict_pair_v1"
    ] = "diagnostic_fulltext_conflict_pair_v1"
    diagnostic_pair_id: str
    proposition_block_id: str
    observation_a: str
    observation_b: str
    publication_a: str | None = None
    publication_b: str | None = None
    source_document_a: str | None = None
    source_document_b: str | None = None
    experiment_a: str | None = None
    experiment_b: str | None = None
    evidence_span_refs_a: list[str] = Field(default_factory=list)
    evidence_span_refs_b: list[str] = Field(default_factory=list)
    proposition_signature_compatibility: ScientificPropositionCompatibilityV1
    measurement_compatibility: str
    result_semantic_compatibility: str
    intervention_causal_mode_compatibility: dict[str, str]
    contrast_compatibility: str
    direction_result_relation: Literal[
        "opposed", "same", "unresolved", "not_evaluated_before_alignment"
    ]
    source_independence: Literal[
        "independent",
        "same_publication",
        "same_source_document",
        "same_experiment",
        "duplicate_evidence_span",
        "duplicate_evidence_text",
        "unresolved",
    ]
    provenance_completeness: Literal["complete", "insufficient"]
    diagnostic_conflict_opportunity_state: Literal[
        "diagnostic_candidate_strong",
        "diagnostic_candidate_reviewable",
        "blocked_proposition_incompatibility",
        "blocked_result_semantics",
        "blocked_same_source_or_duplicate",
        "blocked_entity_integrity",
        "blocked_missing_authority",
        "not_contradictory",
    ]
    reasons: list[str] = Field(default_factory=list)
    diagnostic_only: Literal[True] = True
    formal_authority: Literal[False] = False


class ScientificConflictCandidateV2Candidate(StrictCandidateModel):
    """Additive candidate-only representation for Lane A or Lane B output."""

    schema_version: Literal[
        "scientific_conflict_candidate_v2_candidate"
    ] = "scientific_conflict_candidate_v2_candidate"
    candidate_id: str
    observation_refs: list[str]
    publication_refs: list[str]
    proposition_signature_refs: list[str]
    alignment_state: str
    contradiction_state: str
    entity_integrity_state: str
    source_independence_state: str
    provenance_state: str
    qualification_state: Literal[
        "candidate_qualified",
        "diagnostic_only_strong",
        "diagnostic_only_reviewable",
        "blocked",
        "manual_scientific_review_required",
    ]
    origin_lane: Literal["production_like", "diagnostic_fulltext"]
    failure_reason: str | None = None
    historical_candidate: Literal[False] = False
    candidate_only: Literal[True] = True
    production_authority_activated: Literal[False] = False
    l4_executed: Literal[False] = False
    formal_authority: Literal[False] = False

    @model_validator(mode="after")
    def diagnostic_lane_cannot_become_production_candidate(self):
        if self.origin_lane == "diagnostic_fulltext" and self.qualification_state == "candidate_qualified":
            raise ValueError("diagnostic_lane_cannot_activate_candidate_authority")
        if self.qualification_state == "blocked" and not self.failure_reason:
            raise ValueError("blocked_candidate_requires_failure_reason")
        return self


def scientific_proposition_signature_complete_v1(
    signature: ScientificPropositionSignatureV1,
) -> bool:
    """Return whether every proposition-critical authority is complete."""
    scalar_complete = all((
        signature.subject_identity,
        signature.relation_effect_family,
        signature.object_target_identity,
    ))
    targets_complete = bool(signature.measurement_targets) and all(
        value.canonical_identity is not None for value in signature.measurement_targets
    )
    properties_complete = bool(signature.measured_properties) and all(
        value.semantic_family is not None for value in signature.measured_properties
    )
    results_complete = bool(signature.result_semantics) and all(
        value.semantic_family is not None for value in signature.result_semantics
    )
    intervention = signature.intervention_proposition
    intervention_complete = (
        intervention.authority_state == "not_applicable"
        or (
            intervention.authority_state == "resolved"
            and bool(intervention.target_values)
            and all(value.canonical_identity is not None for value in intervention.target_values)
        )
    )
    return bool(
        scalar_complete
        and targets_complete
        and properties_complete
        and results_complete
        and intervention_complete
        and signature.causal_evidential_mode.authority_state == "resolved"
        and signature.experimental_contrast.authority_state in {"resolved", "not_applicable"}
    )


def _canonical_set(values: Iterable[Any], attribute: str) -> tuple[str, ...]:
    return tuple(sorted({
        str(value)
        for row in values
        if (value := getattr(row, attribute)) is not None
    }))


def scientific_proposition_block_components_v1(
    signature: ScientificPropositionSignatureV1,
) -> dict[str, Any] | None:
    """Build a bounded, direction-free exact blocking key.

    Missing semantic families use explicit unresolved buckets.  This keeps
    unknown-vs-unknown review possible without comparing unrelated entities.
    """
    if signature.subject_identity is None or signature.object_target_identity is None:
        return None
    measurement_targets = _canonical_set(signature.measurement_targets, "canonical_identity")
    measured_properties = _canonical_set(signature.measured_properties, "semantic_family")
    result_semantics = _canonical_set(signature.result_semantics, "semantic_family")
    intervention_targets = _canonical_set(
        signature.intervention_proposition.target_values, "canonical_identity"
    )
    return {
        "subject_identity": signature.subject_identity,
        "relation_effect_family": signature.relation_effect_family or "__unresolved__",
        "object_target_identity": signature.object_target_identity,
        "measurement_target_identities": measurement_targets or ("__unresolved__",),
        "measurement_property_families": measured_properties or ("__unresolved__",),
        "result_semantic_families": result_semantics or ("__unresolved__",),
        "intervention_mode": signature.intervention_proposition.intervention_mode,
        "intervention_factor_families": tuple(
            sorted(signature.intervention_proposition.factor_families)
        ) or ("__unresolved__",),
        "intervention_target_identities": intervention_targets or ("__unresolved__",),
        "causal_mode_family": (
            signature.causal_evidential_mode.mode_family or "__unresolved__"
        ),
        "contrast_role": signature.experimental_contrast.contrast_role,
    }


def scientific_proposition_block_id_v1(components: dict[str, Any]) -> str:
    return layer_identity(
        "scientific_proposition_block",
        "scientific_proposition_block_identity_v1",
        components,
    )


def duplicate_observation_key_v1(
    observation: FulltextScientificObservationV1,
) -> tuple[Any, ...]:
    components = scientific_proposition_block_components_v1(observation.signature)
    return (
        observation.publication_id,
        observation.source_document_id,
        observation.experiment_id,
        tuple(sorted(observation.evidence_span_ids)),
        tuple(sorted(observation.evidence_text_hashes)),
        None if components is None else scientific_proposition_block_id_v1(components),
        observation.direction,
    )


def collapse_duplicate_observations_v1(
    observations: Sequence[FulltextScientificObservationV1],
) -> tuple[list[FulltextScientificObservationV1], dict[str, str]]:
    """Collapse exact parsed copies while retaining deterministic lineage."""
    selected: dict[tuple[Any, ...], FulltextScientificObservationV1] = {}
    collapsed: dict[str, str] = {}
    for row in sorted(observations, key=lambda item: item.observation_id):
        key = duplicate_observation_key_v1(row)
        kept = selected.get(key)
        if kept is None:
            selected[key] = row
        else:
            collapsed[row.observation_id] = kept.observation_id
    return sorted(selected.values(), key=lambda item: item.observation_id), collapsed


def build_scientific_proposition_blocks_v1(
    observations: Sequence[FulltextScientificObservationV1],
) -> list[ScientificPropositionBlockV1]:
    grouped: dict[str, tuple[dict[str, Any], list[FulltextScientificObservationV1]]] = {}
    for observation in observations:
        if not observation.lane_b_eligible:
            continue
        components = scientific_proposition_block_components_v1(observation.signature)
        if components is None:
            continue
        block_id = scientific_proposition_block_id_v1(components)
        grouped.setdefault(block_id, (components, []))[1].append(observation)

    blocks = []
    for block_id, (components, members) in sorted(grouped.items()):
        unresolved = sorted(
            key for key, value in components.items()
            if value == "__unresolved__"
            or (isinstance(value, tuple) and "__unresolved__" in value)
        )
        blocks.append(ScientificPropositionBlockV1(
            proposition_block_id=block_id,
            blocking_components=components,
            observation_ids=sorted(row.observation_id for row in members),
            signature_complete_observation_count=sum(
                scientific_proposition_signature_complete_v1(row.signature) for row in members
            ),
            unresolved_blocking_dimensions=unresolved,
        ))
    return blocks


def assess_source_independence_v1(
    observation_a: FulltextScientificObservationV1,
    observation_b: FulltextScientificObservationV1,
) -> Literal[
    "independent", "same_publication", "same_source_document", "same_experiment",
    "duplicate_evidence_span", "duplicate_evidence_text", "unresolved",
]:
    if set(observation_a.evidence_span_ids) & set(observation_b.evidence_span_ids):
        return "duplicate_evidence_span"
    if set(observation_a.evidence_text_hashes) & set(observation_b.evidence_text_hashes):
        return "duplicate_evidence_text"
    if (
        observation_a.publication_id is not None
        and observation_a.publication_id == observation_b.publication_id
    ):
        return "same_publication"
    if (
        observation_a.source_document_id is not None
        and observation_a.source_document_id == observation_b.source_document_id
    ):
        return "same_source_document"
    if (
        observation_a.experiment_id is not None
        and observation_a.experiment_id == observation_b.experiment_id
    ):
        return "same_experiment"
    if not all((
        observation_a.publication_id,
        observation_b.publication_id,
        observation_a.source_document_id,
        observation_b.source_document_id,
        observation_a.experiment_id,
        observation_b.experiment_id,
    )):
        return "unresolved"
    return "independent"


def evaluate_diagnostic_fulltext_pair_v1(
    *,
    proposition_block_id: str,
    observation_a: FulltextScientificObservationV1,
    observation_b: FulltextScientificObservationV1,
) -> DiagnosticFulltextPairV1:
    pair_id = layer_identity(
        "diagnostic_fulltext_pair",
        "diagnostic_fulltext_pair_identity_v1",
        {"observations": sorted((observation_a.observation_id, observation_b.observation_id))},
    )
    compatibility = evaluate_scientific_proposition_compatibility_v1(
        pair_id=pair_id,
        signature_a=observation_a.signature,
        signature_b=observation_b.signature,
        historical_alignment_v2_identity="not_applicable_diagnostic_lane",
        historical_alignment_v2_state="not_applicable_diagnostic_lane",
    )
    state = compatibility.alignment_v3_candidate_state
    source = assess_source_independence_v1(observation_a, observation_b)
    provenance = (
        "complete" if observation_a.provenance_complete and observation_b.provenance_complete
        else "insufficient"
    )
    reasons: list[str] = []
    if not observation_a.lane_b_eligible or not observation_b.lane_b_eligible:
        diagnostic_state = "blocked_entity_integrity"
        direction_relation = "not_evaluated_before_alignment"
        reasons.append("one_or_both_observations_fail_lane_b_eligibility")
    elif state.startswith("blocked_"):
        diagnostic_state = "blocked_proposition_incompatibility"
        direction_relation = "not_evaluated_before_alignment"
        reasons.extend(compatibility.blocking_dimensions)
    else:
        direction_relation = compare_result_directions_v2(
            observation_a.direction, observation_b.direction
        )
        if source != "independent":
            diagnostic_state = "blocked_same_source_or_duplicate"
            reasons.append(source)
        elif provenance != "complete":
            diagnostic_state = "blocked_missing_authority"
            reasons.append("provenance_insufficient")
        elif direction_relation == "unresolved":
            diagnostic_state = "blocked_result_semantics"
            reasons.append("result_direction_unresolved")
        elif direction_relation == "same":
            diagnostic_state = "not_contradictory"
            reasons.append("deterministic_result_directions_are_not_opposed")
        elif state == "partial_reviewable":
            diagnostic_state = "diagnostic_candidate_reviewable"
            reasons.extend(compatibility.unresolved_dimensions)
        elif state in ALIGNED_PROPOSITION_STATES_V1:
            diagnostic_state = "diagnostic_candidate_strong"
        else:
            diagnostic_state = "blocked_missing_authority"
            reasons.append("proposition_authority_unresolved")

    return DiagnosticFulltextPairV1(
        diagnostic_pair_id=pair_id,
        proposition_block_id=proposition_block_id,
        observation_a=observation_a.observation_id,
        observation_b=observation_b.observation_id,
        publication_a=observation_a.publication_id,
        publication_b=observation_b.publication_id,
        source_document_a=observation_a.source_document_id,
        source_document_b=observation_b.source_document_id,
        experiment_a=observation_a.experiment_id,
        experiment_b=observation_b.experiment_id,
        evidence_span_refs_a=observation_a.evidence_span_ids,
        evidence_span_refs_b=observation_b.evidence_span_ids,
        proposition_signature_compatibility=compatibility,
        measurement_compatibility=compatibility.measurement_compatibility.compatibility_state,
        result_semantic_compatibility=(
            compatibility.measurement_compatibility.result_semantic_level.compatibility_state
        ),
        intervention_causal_mode_compatibility={
            "intervention": compatibility.intervention_proposition.compatibility_state,
            "causal_mode": compatibility.causal_evidential_mode.compatibility_state,
        },
        contrast_compatibility=compatibility.experimental_contrast.compatibility_state,
        direction_result_relation=direction_relation,
        source_independence=source,
        provenance_completeness=provenance,
        diagnostic_conflict_opportunity_state=diagnostic_state,
        reasons=sorted(set(reasons)),
    )


def generate_bounded_diagnostic_pairs_v1(
    observations: Sequence[FulltextScientificObservationV1],
) -> tuple[
    list[ScientificPropositionBlockV1],
    list[DiagnosticFulltextPairV1],
    dict[str, str],
]:
    """Collapse exact copies and compare only pairs inside exact blocks."""
    unique, collapsed = collapse_duplicate_observations_v1(observations)
    by_id = {row.observation_id: row for row in unique}
    blocks = build_scientific_proposition_blocks_v1(unique)
    pairs = [
        evaluate_diagnostic_fulltext_pair_v1(
            proposition_block_id=block.proposition_block_id,
            observation_a=by_id[left],
            observation_b=by_id[right],
        )
        for block in blocks
        for left, right in combinations(block.observation_ids, 2)
    ]
    return blocks, pairs, collapsed


def diagnostic_pair_to_candidate_v2(
    pair: DiagnosticFulltextPairV1,
) -> ScientificConflictCandidateV2Candidate | None:
    state = pair.diagnostic_conflict_opportunity_state
    if state not in {"diagnostic_candidate_strong", "diagnostic_candidate_reviewable"}:
        return None
    compatibility = pair.proposition_signature_compatibility
    return ScientificConflictCandidateV2Candidate(
        candidate_id=layer_identity(
            "scientific_conflict_candidate",
            "scientific_conflict_candidate_v2_candidate_identity_v1",
            {"diagnostic_pair_id": pair.diagnostic_pair_id, "origin_lane": "diagnostic_fulltext"},
        ),
        observation_refs=[pair.observation_a, pair.observation_b],
        publication_refs=sorted({
            value for value in (pair.publication_a, pair.publication_b) if value is not None
        }),
        proposition_signature_refs=[
            compatibility.signature_a_identity,
            compatibility.signature_b_identity,
        ],
        alignment_state=compatibility.alignment_v3_candidate_state,
        contradiction_state=pair.direction_result_relation,
        entity_integrity_state="eligible",
        source_independence_state=pair.source_independence,
        provenance_state=pair.provenance_completeness,
        qualification_state=(
            "diagnostic_only_strong" if state == "diagnostic_candidate_strong"
            else "diagnostic_only_reviewable"
        ),
        origin_lane="diagnostic_fulltext",
    )


__all__ = [
    "ALIGNED_PROPOSITION_STATES_V1",
    "DiagnosticFulltextPairV1",
    "FulltextScientificObservationV1",
    "ScientificConflictCandidateV2Candidate",
    "ScientificPropositionBlockV1",
    "assess_source_independence_v1",
    "build_scientific_proposition_blocks_v1",
    "collapse_duplicate_observations_v1",
    "diagnostic_pair_to_candidate_v2",
    "evaluate_diagnostic_fulltext_pair_v1",
    "generate_bounded_diagnostic_pairs_v1",
    "scientific_proposition_block_components_v1",
    "scientific_proposition_block_id_v1",
    "scientific_proposition_signature_complete_v1",
]
