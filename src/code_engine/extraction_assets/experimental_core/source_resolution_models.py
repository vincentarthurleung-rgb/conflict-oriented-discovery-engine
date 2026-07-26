"""Strict, conflict-neutral models for source-grounded experimental resolution."""
from __future__ import annotations

from typing import Literal

from pydantic import Field, model_validator

from .models import CoreProvenance, StrictCoreAsset


SourceAuthority = Literal[
    "authoritative_current_fulltext", "authoritative_historical_snapshot",
    "structured_artifact_only", "incomplete_source", "unavailable",
]
HistoricalInputAuthority = Literal["authoritative", "incomplete", "unavailable"]
ScopeCompleteness = Literal[
    "complete_for_comparator_resolution",
    "complete_for_factor_application_resolution",
    "complete_for_method_resolution",
    "partial", "insufficient", "unavailable",
]


class SourceResolutionEnvelope(StrictCoreAsset):
    envelope_id: str
    task_type: Literal["comparator", "factor_application", "measurement_method"]
    observation_identity: str
    source_document_identity: str | None
    source_block_identity: str | None
    source_section_identity: str | None
    experiment_scope_identity: str | None
    result_identity: str | None
    measurement_identities: list[str]
    factor_identities: list[str]
    context_asset_identities: list[str]
    primary_result_sentence: str | None
    preceding_sentence_refs: list[str] = Field(default_factory=list)
    following_sentence_refs: list[str] = Field(default_factory=list)
    paragraph_text: str | None
    section_heading: str | None
    methods_text_refs: list[str] = Field(default_factory=list)
    figure_caption_refs: list[str] = Field(default_factory=list)
    table_caption_refs: list[str] = Field(default_factory=list)
    group_definition_refs: list[str] = Field(default_factory=list)
    evidence_chain_refs: list[str] = Field(default_factory=list)
    context_field_evidence_refs: list[str] = Field(default_factory=list)
    source_text_authority: SourceAuthority
    source_scope_completeness: ScopeCompleteness
    source_scope_policy_identity: str
    historical_provider_input_authority: HistoricalInputAuthority
    truncation_status: Literal["not_detected", "detected", "unknown"]
    ambiguity_status: Literal["none", "single_candidate", "multiple_candidates", "unknown"]
    identity: str
    provenance: CoreProvenance
    schema_version: Literal["source_grounded_experimental_resolution_envelope_v1"] = (
        "source_grounded_experimental_resolution_envelope_v1"
    )

    @model_validator(mode="after")
    def complete_scope_requires_more_than_claim(self):
        complete = self.source_scope_completeness.startswith("complete_for_")
        surrounding = (
            self.preceding_sentence_refs or self.following_sentence_refs
            or self.methods_text_refs or self.figure_caption_refs
            or self.table_caption_refs or self.group_definition_refs
        )
        if complete and (not self.primary_result_sentence or not surrounding):
            raise ValueError("a single claim sentence is not a complete source envelope")
        if (
            self.source_text_authority == "authoritative_current_fulltext"
            and self.historical_provider_input_authority == "authoritative"
        ):
            raise ValueError("current fulltext cannot establish historical provider-input authority")
        return self


class SourceScopeCompletenessAudit(StrictCoreAsset):
    envelope_identity: str
    task_type: Literal["comparator", "factor_application", "measurement_method"]
    completeness: ScopeCompleteness
    result_context_present: bool
    factors_present: bool
    measurements_present: bool
    comparison_context_present: bool
    group_definition_present: bool
    methods_present: bool
    caption_scope_checked: bool
    source_anchor_verified: bool
    truncation_detected: bool
    source_not_reported_authorized: bool
    missing_scope_components: list[str]
    identity: str
    provenance: CoreProvenance
    schema_version: Literal["source_resolution_scope_completeness_v1"] = (
        "source_resolution_scope_completeness_v1"
    )

    @model_validator(mode="after")
    def guard_not_reported(self):
        if self.source_not_reported_authorized and not self.completeness.startswith("complete_for_"):
            raise ValueError("source_not_reported requires task-complete source scope")
        return self


class ProviderCandidatePolicyAudit(StrictCoreAsset):
    target_identity: str
    source_text_exists: bool
    source_envelope_sufficient: bool
    information_likely_present: bool
    deterministic_resolution_failed: bool
    joint_prompt_suitable: bool
    annotation_cost_exceeds_batch_extraction: bool
    prompt_v2_expressible: bool
    paid_smoke_still_required: Literal[True] = True
    provider_candidate: bool
    provider_reextraction_required: Literal[False] = False
    automatic_execution_authorized: Literal[False] = False
    provider_call_authorized: Literal[False] = False
    network_call_authorized: Literal[False] = False
    budget_authorization_present: Literal[False] = False
    identity: str
    provenance: CoreProvenance
    schema_version: Literal["experimental_source_resolution_provider_candidate_policy_v1"] = (
        "experimental_source_resolution_provider_candidate_policy_v1"
    )

    @model_validator(mode="after")
    def candidate_requires_all_policy_gates(self):
        gates = (
            self.source_text_exists, self.source_envelope_sufficient,
            self.information_likely_present, self.deterministic_resolution_failed,
            self.joint_prompt_suitable, self.annotation_cost_exceeds_batch_extraction,
            self.prompt_v2_expressible,
        )
        if self.provider_candidate and not all(gates):
            raise ValueError("provider candidate requires every policy gate")
        return self
