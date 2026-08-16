"""Offline abstract entity-chain integrity and deterministic bridge filtering.

Abstract repairs are authorized only by the abstract source plus its extraction
lineage.  Fulltext evidence is intentionally absent from the integrity API so
that downstream evidence cannot circularly rewrite an upstream claim.
"""
from __future__ import annotations

import re
import unicodedata
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


IntegrityStatus = Literal[
    "consistent", "raw_extraction_entity_error", "normalization_entity_error",
    "claim_projection_entity_error", "signal_projection_entity_error",
    "source_binding_error", "scientifically_different_entities",
    "ambiguous_entity_mapping", "insufficient_evidence",
]
CandidateStatus = Literal[
    "excluded_deterministically", "scientifically_plausible_candidate", "insufficient_evidence",
]


def normalize_surface(value: Any) -> str:
    text = unicodedata.normalize("NFKC", str(value or "")).casefold()
    text = re.sub(r"\b(?:the|a|an)\b", " ", text)
    return " ".join(re.sub(r"[^a-z0-9]+", " ", text).split())


def entity_equivalent(left: Any, right: Any) -> bool:
    a, b = normalize_surface(left), normalize_surface(right)
    return bool(a and b and a == b)


def source_supports_entity(source_text: str, entity: Any) -> bool:
    source, target = normalize_surface(source_text), normalize_surface(entity)
    if not source or not target:
        return False
    # Token boundaries prevent AR1 from being treated as PAR1.
    return re.search(rf"(?:^| )({re.escape(target)})(?: |$)", source) is not None


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class AbstractClaimEntityIntegrityAuditV1(StrictModel):
    schema_version: Literal["abstract_claim_entity_integrity_audit_v1"] = "abstract_claim_entity_integrity_audit_v1"
    claim_id: str
    signal_id: str | None
    audited_entity_role: Literal["subject", "object"]
    source_text: str
    source_ref: str
    raw_extraction_payload_ref: str
    subject_raw: str | None
    object_raw: str | None
    normalized_subject: str | None
    normalized_object: str | None
    entity_resolution_authority: dict[str, Any]
    projected_proposition_core: dict[str, Any]
    contradiction_representation: dict[str, Any]
    signal_object_identity: str | None
    integrity_status: IntegrityStatus
    error_stage: Literal["none", "source_binding", "raw_extraction", "normalization", "claim_projection", "signal_projection", "scientific_comparison", "unknown"]
    abstract_source_is_repair_authority: bool = True
    fulltext_used_as_upstream_repair_authority: bool = False

    @model_validator(mode="after")
    def no_circular_repair(self):
        if self.fulltext_used_as_upstream_repair_authority:
            raise ValueError("fulltext_cannot_authorize_abstract_entity_repair")
        return self


class AbstractClaimIntegrityRevisionCandidateV1(StrictModel):
    schema_version: Literal["abstract_claim_integrity_revision_candidate_v1"] = "abstract_claim_integrity_revision_candidate_v1"
    historical_claim_id: str
    error_type: IntegrityStatus
    source_evidence: list[dict[str, Any]] = Field(min_length=1)
    candidate_corrected_entity: str
    repair_authority: Literal["abstract_source_plus_raw_extraction_lineage"] = "abstract_source_plus_raw_extraction_lineage"
    eligible_for_offline_replay: bool
    scientific_claim_revision_materialized: bool = False


class SignalIntegrityAuditV1(StrictModel):
    schema_version: Literal["signal_integrity_audit_v1"] = "signal_integrity_audit_v1"
    signal_id: str
    claim_id: str
    claim_integrity_status: IntegrityStatus
    signal_integrity_status: Literal[
        "eligible_pending_bridge_review", "blocked_upstream_claim_integrity",
        "blocked_signal_projection_integrity", "insufficient_evidence",
    ]
    historical_signal_modified: bool = False


class ExperimentCompatibilityFactsV1(StrictModel):
    experiment_scope_id: str
    observation_ids: list[str] = Field(min_length=1)
    entity_compatible: bool | None
    relation_compatible: bool | None
    measurement_compatible: bool | None
    result_compatible: bool | None
    evidence_family_compatible: bool | None
    deterministic_evidence_refs: list[str] = Field(default_factory=list)


class CandidateExperimentFilteringV1(StrictModel):
    schema_version: Literal["candidate_experiment_filtering_v1"] = "candidate_experiment_filtering_v1"
    experiment_scope_id: str
    observation_ids: list[str]
    entity_compatible: bool | None
    relation_compatible: bool | None
    measurement_compatible: bool | None
    result_compatible: bool | None
    evidence_family_compatible: bool | None
    deterministic_exclusion_reasons: list[str]
    candidate_status: CandidateStatus
    evidence_refs: list[str]
    weak_similarity_used_for_exclusion: bool = False


class ManualScientificReviewResponseV1(StrictModel):
    schema_version: Literal["manual_scientific_review_response_v1"] = "manual_scientific_review_response_v1"
    selected_candidate_ids: list[str] = Field(default_factory=list)
    no_matching_experiment: bool = False
    multiple_matching_experiments: bool = False
    source_insufficient: bool = False
    cannot_determine: bool = False
    evidence_refs: list[str] = Field(default_factory=list)
    confidence: float | None = Field(default=None, ge=0, le=1)
    notes: str = ""


def classify_entity_chain(
    *, source_text: str, raw_entity: str | None, normalized_entity: str | None,
    projected_entity: str | None, signal_entity: str | None,
    source_binding_verified: bool,
) -> tuple[IntegrityStatus, str]:
    """Return a fail-closed stage classification without consulting fulltext."""
    if not source_binding_verified:
        return "source_binding_error", "source_binding"
    if not raw_entity or not source_text:
        return "insufficient_evidence", "unknown"
    if not source_supports_entity(source_text, raw_entity):
        return "raw_extraction_entity_error", "raw_extraction"
    if not normalized_entity:
        return "insufficient_evidence", "normalization"
    if not entity_equivalent(raw_entity, normalized_entity):
        return "normalization_entity_error", "normalization"
    if projected_entity and not entity_equivalent(normalized_entity, projected_entity):
        return "claim_projection_entity_error", "claim_projection"
    expected_signal_entity = projected_entity or normalized_entity
    if signal_entity and not entity_equivalent(expected_signal_entity, signal_entity):
        return "signal_projection_entity_error", "signal_projection"
    return "consistent", "none"


def signal_integrity_for(status: IntegrityStatus) -> str:
    if status == "consistent":
        return "eligible_pending_bridge_review"
    if status == "signal_projection_entity_error":
        return "blocked_signal_projection_integrity"
    if status == "insufficient_evidence":
        return "insufficient_evidence"
    return "blocked_upstream_claim_integrity"


def filter_experiment_candidate(facts: ExperimentCompatibilityFactsV1) -> CandidateExperimentFilteringV1:
    checks = {
        "entity_incompatible": facts.entity_compatible,
        "relation_incompatible": facts.relation_compatible,
        "measurement_incompatible": facts.measurement_compatible,
        "result_incompatible": facts.result_compatible,
        "evidence_family_incompatible": facts.evidence_family_compatible,
    }
    reasons = [name for name, value in checks.items() if value is False]
    if reasons:
        status: CandidateStatus = "excluded_deterministically"
    elif all(value is True for value in checks.values()):
        status = "scientifically_plausible_candidate"
    else:
        # Unknown compatibility is retained; absence of proof is not an
        # exclusion and text similarity is intentionally not an input.
        status = "insufficient_evidence"
    return CandidateExperimentFilteringV1(
        experiment_scope_id=facts.experiment_scope_id,
        observation_ids=facts.observation_ids,
        entity_compatible=facts.entity_compatible,
        relation_compatible=facts.relation_compatible,
        measurement_compatible=facts.measurement_compatible,
        result_compatible=facts.result_compatible,
        evidence_family_compatible=facts.evidence_family_compatible,
        deterministic_exclusion_reasons=reasons,
        candidate_status=status,
        evidence_refs=facts.deterministic_evidence_refs,
    )

