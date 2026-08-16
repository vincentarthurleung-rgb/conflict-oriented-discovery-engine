"""Fail-closed forensic classification for abstract-to-fulltext bridge candidates."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict


BridgeClassification = Literal[
    "local_bridge_recoverable",
    "local_fulltext_source_present_but_observation_binding_missing",
    "local_fulltext_reextraction_required",
    "source_present_but_target_experiment_not_extracted",
    "local_source_scope_insufficient",
    "fulltext_not_local",
    "ambiguous_multiple_fulltext_experiments",
    "scientifically_unmatchable_from_current_assets",
    "provenance_identity_mismatch",
    "unknown_forensic_state",
]


class BridgeForensicFactsV1(BaseModel):
    model_config = ConfigDict(extra="forbid")
    same_pmid: bool = False
    source_identity_consistent: bool = False
    local_fulltext_present: bool = False
    target_experiment_locatable: bool = False
    existing_validated_observation_count: int = 0
    exact_provenance_overlap: bool = False
    compatible_proposition: bool = False
    compatible_measurement_result: bool = False
    compatible_experiment_scope: bool = False
    competing_incompatible_observation_count: int = 0
    same_gene_only: bool = False
    same_polarity_only: bool = False
    wording_similarity_only: bool = False
    candidate_only_authority: bool = True


def classify_bridge(facts: BridgeForensicFactsV1) -> BridgeClassification:
    if not facts.source_identity_consistent:
        return "provenance_identity_mismatch"
    if not facts.local_fulltext_present:
        return "fulltext_not_local"
    if facts.competing_incompatible_observation_count > 0:
        return "ambiguous_multiple_fulltext_experiments"
    if (
        facts.existing_validated_observation_count == 1
        and facts.exact_provenance_overlap
        and facts.compatible_proposition
        and facts.compatible_measurement_result
        and facts.compatible_experiment_scope
        and not (facts.same_gene_only or facts.same_polarity_only or facts.wording_similarity_only)
    ):
        return "local_bridge_recoverable"
    if facts.target_experiment_locatable and facts.existing_validated_observation_count == 0:
        return "local_fulltext_reextraction_required"
    if facts.existing_validated_observation_count > 0 and not facts.exact_provenance_overlap:
        return "local_fulltext_source_present_but_observation_binding_missing"
    if not facts.target_experiment_locatable:
        return "local_source_scope_insufficient"
    return "unknown_forensic_state"


def bridge_may_create_scientific_link(
    *, classification: BridgeClassification, validated_by_scientific_authority: bool
) -> bool:
    """Forensics never promotes candidate-only evidence by itself."""
    return classification == "local_bridge_recoverable" and validated_by_scientific_authority
