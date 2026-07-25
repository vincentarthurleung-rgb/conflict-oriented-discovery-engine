"""Strict records for read-only historical extraction lineage forensics."""
from __future__ import annotations

from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class StrictForensicRecord(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class AuthorityLevel(str, Enum):
    exact_bound = "exact_bound"
    deterministically_reconstructed = "deterministically_reconstructed"
    probable_non_authoritative = "probable_non_authoritative"
    unbound = "unbound"
    rejected = "rejected"


class HistoricalLineageBinding(StrictForensicRecord):
    binding_id: str
    left_identity: str
    right_identity: str | None = None
    binding_authority_level: AuthorityLevel
    authoritative: bool
    formal_replay_use_allowed: bool
    direct_evidence: list[dict[str, Any]] = Field(default_factory=list)
    deterministic_evidence: list[dict[str, Any]] = Field(default_factory=list)
    weak_evidence: list[str] = Field(default_factory=list)
    conflict_reasons: list[str] = Field(default_factory=list)
    algorithm_version: str | None = None
    candidate_identities: list[str] = Field(default_factory=list)
    excluded_candidates: list[dict[str, str]] = Field(default_factory=list)
    uniqueness_proof: dict[str, Any] | None = None
    one_to_one_valid: bool
    schema_version: Literal["historical_lineage_binding_v1"] = "historical_lineage_binding_v1"
    identity: str

    @model_validator(mode="after")
    def authority_rules(self) -> "HistoricalLineageBinding":
        authoritative = self.binding_authority_level in {
            AuthorityLevel.exact_bound, AuthorityLevel.deterministically_reconstructed,
        }
        if self.authoritative != authoritative:
            raise ValueError("authoritative must follow authority level")
        if self.formal_replay_use_allowed != authoritative:
            raise ValueError("formal replay is allowed only for authoritative bindings")
        if authoritative and not self.one_to_one_valid:
            raise ValueError("authoritative binding requires one-to-one validity")
        if self.binding_authority_level == AuthorityLevel.exact_bound and not self.direct_evidence:
            raise ValueError("exact_bound requires direct evidence")
        if self.binding_authority_level == AuthorityLevel.deterministically_reconstructed:
            if not self.algorithm_version or not self.deterministic_evidence or not self.uniqueness_proof:
                raise ValueError("deterministic binding requires algorithm and uniqueness evidence")
        if self.binding_authority_level == AuthorityLevel.rejected and not self.conflict_reasons:
            raise ValueError("rejected binding requires conflict reasons")
        return self


class SourceRecoveryStatus(str, Enum):
    exact = "exact_request_snapshot_recovered"
    deterministic = "deterministic_request_snapshot_recovered"
    candidate = "reconstructed_candidate_non_authoritative"
    incomplete = "incomplete"
    rejected = "rejected"


class SourceSnapshotForensicRecovery(StrictForensicRecord):
    recovery_id: str
    source_snapshot_identity: str
    status: SourceRecoveryStatus
    authoritative: bool
    actual_request_text: str | None = None
    request_text_sha256: str | None = None
    source_text_sha256: str | None = None
    rendered_prompt_sha256: str | None = None
    encoding: str | None = None
    newline_policy: str | None = None
    template_identity: str | None = None
    evidence_refs: list[str] = Field(default_factory=list)
    candidate_alternatives: list[str] = Field(default_factory=list)
    reconstruction_algorithm_version: str | None = None
    rejection_reasons: list[str] = Field(default_factory=list)
    schema_version: Literal["source_snapshot_forensic_recovery_v1"] = "source_snapshot_forensic_recovery_v1"
    identity: str

    @model_validator(mode="after")
    def recovery_rules(self) -> "SourceSnapshotForensicRecovery":
        expected = self.status in {SourceRecoveryStatus.exact, SourceRecoveryStatus.deterministic}
        if self.authoritative != expected:
            raise ValueError("source recovery authority inconsistent with status")
        if expected and (self.actual_request_text is None or self.request_text_sha256 is None):
            raise ValueError("authoritative snapshot requires complete request text and hash")
        if self.status == SourceRecoveryStatus.deterministic and not self.reconstruction_algorithm_version:
            raise ValueError("deterministic recovery requires algorithm version")
        return self


class LineageCandidateEdge(StrictForensicRecord):
    edge_id: str
    left_identity: str
    right_identity: str
    direct_evidence_types: list[str] = Field(default_factory=list)
    replay_evidence_types: list[str] = Field(default_factory=list)
    hash_evidence: list[str] = Field(default_factory=list)
    request_response_id_evidence: list[str] = Field(default_factory=list)
    prompt_source_evidence: list[str] = Field(default_factory=list)
    parser_evidence: list[str] = Field(default_factory=list)
    timestamp_evidence: list[str] = Field(default_factory=list)
    filename_evidence: list[str] = Field(default_factory=list)
    negative_evidence: list[str] = Field(default_factory=list)
    conflict_evidence: list[str] = Field(default_factory=list)
    authority_candidate_level: AuthorityLevel
    deterministic_uniqueness: bool = False
    competing_edge_count: int = 0
    diagnostic_score: float = 0.0
    schema_version: Literal["lineage_candidate_edge_v1"] = "lineage_candidate_edge_v1"
    identity: str

    @model_validator(mode="after")
    def weak_signals_never_authorize(self) -> "LineageCandidateEdge":
        strong = bool(
            self.direct_evidence_types or self.replay_evidence_types or self.hash_evidence
            or self.request_response_id_evidence or self.prompt_source_evidence
        )
        if self.authority_candidate_level in {
            AuthorityLevel.exact_bound, AuthorityLevel.deterministically_reconstructed,
        } and not strong:
            raise ValueError("timestamp, filename, location, and score cannot authorize an edge")
        return self


class ReplayabilityStatusV2(str, Enum):
    fully_direct = "fully_replayable_zero_api_direct"
    fully_reconstructed = "fully_replayable_zero_api_reconstructed"
    raw_direct = "replayable_from_raw_response_direct"
    raw_reconstructed = "replayable_from_raw_response_reconstructed"
    parsed_only = "replayable_from_parsed_candidate_only"
    partial = "partially_replayable"
    reextract = "provider_reextraction_required"
    reingest = "source_reingestion_required"
    ambiguity = "blocked_lineage_ambiguity"
    invalid = "invalid"


class ResearchReadinessTier(str, Enum):
    tier_a = "tier_a_research_grade"
    tier_b = "tier_b_validated_with_limitations"
    tier_c = "tier_c_challenge_or_incomplete"
    unassessed = "unassessed"


class SelectiveReextractionRequirementV2(StrictForensicRecord):
    requirement_id: str
    pre_forensic_requirement_identity: str
    source_block_identity: str
    recovered_source_snapshot_identity: str | None = None
    recovered_raw_response_identity: str | None = None
    recovered_parsed_lineage: list[str] = Field(default_factory=list)
    offline_recovery_modes_available: list[str] = Field(default_factory=list)
    fields_recovered_without_api: list[str] = Field(default_factory=list)
    fields_still_missing: list[str] = Field(default_factory=list)
    post_forensic_reextraction_required: bool
    post_forensic_reason: str
    minimal_text_scope: str
    dedup_group_identity: str
    estimated_call_count: int
    provider_call_authorized: Literal[False] = False
    network_call_authorized: Literal[False] = False
    automatic_execution_authorized: Literal[False] = False
    budget_authorization_present: Literal[False] = False
    historical_payload_mutation_authorized: Literal[False] = False
    schema_version: Literal["selective_reextraction_requirement_v2"] = "selective_reextraction_requirement_v2"
    identity: str

