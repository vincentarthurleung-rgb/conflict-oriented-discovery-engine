"""Candidate-only scientific entity equivalence authority.

This contract deliberately keeps within-corpus scientific identity separate
from externally canonical identifiers.  It never mutates historical entity
records and it permits no similarity or inferred alias mechanism.
"""
from __future__ import annotations

import unicodedata
from collections.abc import Iterable
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


ScientificEquivalenceStateV1 = Literal[
    "externally_canonical_verified",
    "local_verified_alias_equivalent",
    "local_exact_surface_equivalent",
    "local_safe_normalized_equivalent",
    "unresolved_entity_equivalence",
    "ambiguous_entity_equivalence",
    "invalid_entity_identity",
    "blocked_integrity_corruption",
]
ExternalCanonicalStateV1 = Literal[
    "external_id_verified",
    "verified_local_alias_to_external_id",
    "historical_alias_only",
    "local_identity_only",
    "external_id_unresolved",
    "identifier_conflict",
]


class StrictCandidateModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class EntityMentionEvidenceV1(StrictCandidateModel):
    """Minimum evidence used to decide one local mention's identity authority."""

    schema_version: Literal["entity_mention_evidence_v1"] = "entity_mention_evidence_v1"
    mention_ref: str
    observation_ref: str
    publication_ref: str
    experiment_ref: str
    proposition_role: str
    role_family: str
    source_surface: str | None
    validated_surface: str | None
    safe_surface: str | None
    entity_type: str | None
    canonical_ids: list[str] = Field(default_factory=list)
    alias_authority_refs: list[str] = Field(default_factory=list)
    raw_lineage_refs: list[str] = Field(default_factory=list)
    source_grounded: bool
    extracted_surface_validated: bool
    cleaner_integrity_state: Literal["clear", "warning", "blocked"]
    integrity_blocker: bool = False


class LocalEntityEquivalenceDecisionV1(StrictCandidateModel):
    schema_version: Literal[
        "local_entity_equivalence_decision_v1"
    ] = "local_entity_equivalence_decision_v1"
    local_identity_key: str | None
    scientific_equivalence_authority: ScientificEquivalenceStateV1
    external_canonical_authority: ExternalCanonicalStateV1
    eligible_for_local_equivalence: bool
    collision_state: Literal[
        "none", "type_conflict", "canonical_conflict", "alias_conflict"
    ] = "none"
    authority_refs: list[str] = Field(default_factory=list)
    basis: list[str]
    external_identity_asserted_from_local_authority: Literal[False] = False
    fuzzy_matching_used: Literal[False] = False
    llm_used: Literal[False] = False

    @model_validator(mode="after")
    def local_authority_does_not_claim_external_identity(self):
        if self.scientific_equivalence_authority.startswith("local_") and (
            self.external_canonical_authority
            not in {"local_identity_only", "external_id_unresolved", "historical_alias_only"}
        ):
            raise ValueError("local_equivalence_cannot_assert_external_verification")
        return self


def exact_surface_v1(value: object) -> str | None:
    """Case-sensitive NFKC + edge/whitespace normalization.

    This is an equality-preserving representation rule, not fuzzy matching.
    Case is intentionally preserved because it can be scientifically material.
    """
    if value is None:
        return None
    normalized = " ".join(unicodedata.normalize("NFKC", str(value)).split())
    return normalized or None


def local_identity_key_v1(surface: str, entity_type: str, role_family: str) -> str:
    return "|".join((exact_surface_v1(surface) or "", entity_type, role_family))


def decide_local_equivalence_v1(
    mentions: Iterable[EntityMentionEvidenceV1],
    *,
    allow_safe_normalized: bool = False,
) -> LocalEntityEquivalenceDecisionV1:
    """Decide one pre-grouped class using only deterministic local authority."""
    rows = list(mentions)
    if not rows:
        raise ValueError("at_least_one_entity_mention_required")
    types = {row.entity_type for row in rows if row.entity_type}
    roles = {row.role_family for row in rows if row.role_family}
    canonical_ids = {value for row in rows for value in row.canonical_ids if value}
    safe = {exact_surface_v1(row.safe_surface) for row in rows if row.safe_surface}
    safe.discard(None)
    refs = sorted({ref for row in rows for ref in row.alias_authority_refs})

    external = (
        "identifier_conflict" if len(canonical_ids) > 1 else
        "external_id_verified" if len(canonical_ids) == 1 else
        "external_id_unresolved"
    )
    if any(row.integrity_blocker or row.cleaner_integrity_state == "blocked" for row in rows):
        return LocalEntityEquivalenceDecisionV1(
            local_identity_key=None,
            scientific_equivalence_authority="blocked_integrity_corruption",
            external_canonical_authority=external,
            eligible_for_local_equivalence=False,
            basis=["entity integrity or cleaner lineage is blocked"],
        )
    if len(types) > 1:
        return LocalEntityEquivalenceDecisionV1(
            local_identity_key=None,
            scientific_equivalence_authority="ambiguous_entity_equivalence",
            external_canonical_authority=external,
            eligible_for_local_equivalence=False,
            collision_state="type_conflict",
            basis=["validated entity types conflict"],
        )
    if not types:
        return LocalEntityEquivalenceDecisionV1(
            local_identity_key=None,
            scientific_equivalence_authority="unresolved_entity_equivalence",
            external_canonical_authority=external,
            eligible_for_local_equivalence=False,
            basis=["validated entity type is unavailable"],
        )
    if len(canonical_ids) > 1:
        return LocalEntityEquivalenceDecisionV1(
            local_identity_key=None,
            scientific_equivalence_authority="ambiguous_entity_equivalence",
            external_canonical_authority="identifier_conflict",
            eligible_for_local_equivalence=False,
            collision_state="canonical_conflict",
            basis=["one local surface maps to incompatible canonical identifiers"],
        )
    if len(roles) > 1:
        return LocalEntityEquivalenceDecisionV1(
            local_identity_key=None,
            scientific_equivalence_authority="ambiguous_entity_equivalence",
            external_canonical_authority=external,
            eligible_for_local_equivalence=False,
            basis=["proposition role families are incompatible"],
        )
    if not all(
        row.source_grounded
        and row.extracted_surface_validated
        and row.source_surface
        and row.safe_surface
        and row.raw_lineage_refs
        for row in rows
    ):
        return LocalEntityEquivalenceDecisionV1(
            local_identity_key=None,
            scientific_equivalence_authority="unresolved_entity_equivalence",
            external_canonical_authority=external,
            eligible_for_local_equivalence=False,
            basis=["required source, validated surface, or raw lineage authority is absent"],
        )
    alias_proven = bool(refs)
    exact_proven = len(safe) == 1
    if not exact_proven and not alias_proven:
        return LocalEntityEquivalenceDecisionV1(
            local_identity_key=None,
            scientific_equivalence_authority="unresolved_entity_equivalence",
            external_canonical_authority=external,
            eligible_for_local_equivalence=False,
            basis=["different surfaces have no existing deterministic alias authority"],
        )
    surface = sorted(safe)[0]
    entity_type = next(iter(types), "unknown")
    role = next(iter(roles), "unknown")
    state: ScientificEquivalenceStateV1
    if len(canonical_ids) == 1:
        state = "externally_canonical_verified"
    elif alias_proven:
        state = "local_verified_alias_equivalent"
        external = "local_identity_only"
    elif exact_proven:
        state = (
            "local_safe_normalized_equivalent"
            if allow_safe_normalized else "local_exact_surface_equivalent"
        )
        external = "local_identity_only"
    else:  # pragma: no cover - guarded above
        raise AssertionError("unreachable")
    return LocalEntityEquivalenceDecisionV1(
        local_identity_key=local_identity_key_v1(surface, entity_type, role),
        scientific_equivalence_authority=state,
        external_canonical_authority=external,
        eligible_for_local_equivalence=True,
        authority_refs=refs,
        basis=[
            "exact case-sensitive safe surface",
            "compatible validated entity type and proposition role",
            "no cleaner, canonical, or local collision",
        ],
    )
