"""Deterministic Experimental Core repair contracts and fail-closed gates.

This module is runtime-safe: callers must supply candidates already grounded in
source evidence.  It does not load evaluation fixtures and never selects a
scientific answer from role metadata, candidate cardinality, or text similarity.
"""
from __future__ import annotations

import re
from enum import Enum
from typing import Any, Literal

from pydantic import Field, model_validator

from .identities import core_identity
from .models import CoreProvenance, StrictCoreAsset


def _identity(kind: str, payload: dict[str, Any]) -> str:
    basis = {key: value for key, value in payload.items() if key not in {"identity", "provenance"}}
    return core_identity(kind, basis)


def _normalized_token(value: str | None) -> str:
    return re.sub(r"[\s._-]+", " ", (value or "").strip().casefold()).strip()


class ResultValueState(str, Enum):
    SCIENTIFIC_RESULT_VALUE = "scientific_result_value"
    NOT_REPORTED = "not_reported"
    NOT_AVAILABLE = "not_available"
    UNKNOWN = "unknown"
    PARSER_PLACEHOLDER = "parser_placeholder"
    LEGACY_SENTINEL = "legacy_sentinel"


class ObservedResultStructuralIntegrityV2(StrictCoreAsset):
    source_result_identity: str
    result_value_state: ResultValueState
    observed_result_value: str | None = None
    eligibility: Literal["structurally_valid", "structurally_incomplete"]
    issue_codes: list[str] = Field(default_factory=list)
    repair_required: bool
    identity: str
    provenance: CoreProvenance
    schema_version: Literal["experimental_observed_result_structural_integrity_v2"] = (
        "experimental_observed_result_structural_integrity_v2"
    )


class ObservedResultRepairRevision(StrictCoreAsset):
    source_result_identity: str
    supersedes: str
    derived_from: list[str]
    result_value_state: ResultValueState
    observed_result_value: str | None = None
    eligibility: Literal["structurally_valid", "structurally_incomplete"]
    repair_reason: str
    repair_rule_identity: str
    immutable: Literal[True] = True
    identity: str
    provenance: CoreProvenance
    schema_version: Literal["experimental_observed_result_repair_revision_v1"] = (
        "experimental_observed_result_repair_revision_v1"
    )


_MISSINGNESS = {
    "not reported": ResultValueState.NOT_REPORTED,
    "none reported": ResultValueState.NOT_REPORTED,
    "not available": ResultValueState.NOT_AVAILABLE,
    "unavailable": ResultValueState.NOT_AVAILABLE,
    "unknown": ResultValueState.UNKNOWN,
    "n/a": ResultValueState.LEGACY_SENTINEL,
    "na": ResultValueState.LEGACY_SENTINEL,
}


def inspect_observed_result(
    *, source_result_identity: str, qualitative_result: str | None,
    quantitative_value: Any = None, parser_placeholder: bool = False,
    provenance: CoreProvenance,
) -> ObservedResultStructuralIntegrityV2:
    """Classify exact missingness tokens without deleting scientific sentences."""
    token = _normalized_token(qualitative_result)
    if parser_placeholder:
        state = ResultValueState.PARSER_PLACEHOLDER
    elif quantitative_value not in {None, ""}:
        state = ResultValueState.SCIENTIFIC_RESULT_VALUE
    else:
        state = _MISSINGNESS.get(token, ResultValueState.SCIENTIFIC_RESULT_VALUE)
    incomplete = state is not ResultValueState.SCIENTIFIC_RESULT_VALUE
    payload = {
        "source_result_identity": source_result_identity,
        "result_value_state": state,
        "observed_result_value": None if incomplete else qualitative_result,
        "eligibility": "structurally_incomplete" if incomplete else "structurally_valid",
        "issue_codes": ["missingness_not_scientific_result"] if incomplete else [],
        "repair_required": incomplete,
        "provenance": provenance,
    }
    payload["identity"] = _identity("experimental_observed_result_structural_integrity_v2", payload)
    return ObservedResultStructuralIntegrityV2.model_validate(payload)


class MeasurementKind(str, Enum):
    MOLECULAR_MEASUREMENT = "molecular_measurement"
    CLINICAL_OUTCOME = "clinical_outcome"
    PHENOTYPE = "phenotype"
    SURVIVAL_OUTCOME = "survival_outcome"
    ASSOCIATION_ENDPOINT = "association_endpoint"
    OTHER = "other"
    UNKNOWN = "unknown"


class MeasurementSemanticIntegrityV1(StrictCoreAsset):
    source_measurement_identity: str
    measurement_kind: MeasurementKind
    exposure_identity: str | None = None
    outcome_label: str | None = None
    association_explicit: bool = False
    status: Literal["valid", "invalid_merged_exposure_outcome", "unresolved"]
    issue_codes: list[str] = Field(default_factory=list)
    identity: str
    provenance: CoreProvenance
    schema_version: Literal["experimental_measurement_semantic_integrity_v1"] = (
        "experimental_measurement_semantic_integrity_v1"
    )


class MeasurementRepairRevision(StrictCoreAsset):
    source_measurement_identity: str
    supersedes: str
    derived_from: list[str]
    measurement_kind: MeasurementKind
    outcome_label: str
    exposure_factor_ref: str
    association_relation: Literal["factor_associated_with_measurement"] = "factor_associated_with_measurement"
    evidence_refs: list[str]
    repair_reason: str
    repair_rule_identity: str
    immutable: Literal[True] = True
    identity: str
    provenance: CoreProvenance
    schema_version: Literal["experimental_measurement_repair_revision_v1"] = (
        "experimental_measurement_repair_revision_v1"
    )


def classify_measurement_kind(endpoint: str | None, measured_entity: str | None = None) -> MeasurementKind:
    """Apply a small domain-neutral endpoint taxonomy; ambiguity stays unknown."""
    text = _normalized_token(endpoint)
    if not text:
        return MeasurementKind.UNKNOWN
    if any(token in text for token in ("survival", "mortality", "death")):
        return MeasurementKind.SURVIVAL_OUTCOME
    if any(token in text for token in ("tumor stage", "clinical stage", "disease stage")):
        return MeasurementKind.CLINICAL_OUTCOME
    if any(token in text for token in ("metastasis", "phenotype", "migration", "invasion")):
        return MeasurementKind.PHENOTYPE
    if any(token in text for token in ("association", "correlation", "risk", "outcome")):
        return MeasurementKind.ASSOCIATION_ENDPOINT
    entity = _normalized_token(measured_entity)
    if any(token in entity for token in ("expression", "abundance", "concentration", "level")):
        return MeasurementKind.MOLECULAR_MEASUREMENT
    return MeasurementKind.OTHER


def inspect_measurement_semantics(
    *, source_measurement_identity: str, measured_entity: str | None,
    endpoint: str | None, measurement_kind: MeasurementKind,
    exposure_identity: str | None, association_explicit: bool,
    provenance: CoreProvenance,
) -> MeasurementSemanticIntegrityV1:
    """Detect an exposure incorrectly reused as the entity of an outcome record."""
    merged = bool(
        exposure_identity and endpoint and measured_entity
        and measurement_kind in {
            MeasurementKind.CLINICAL_OUTCOME, MeasurementKind.PHENOTYPE,
            MeasurementKind.SURVIVAL_OUTCOME, MeasurementKind.ASSOCIATION_ENDPOINT,
        }
        and association_explicit
    )
    status = "invalid_merged_exposure_outcome" if merged else (
        "unresolved" if measurement_kind is MeasurementKind.UNKNOWN else "valid"
    )
    payload = {
        "source_measurement_identity": source_measurement_identity,
        "measurement_kind": measurement_kind,
        "exposure_identity": exposure_identity,
        "outcome_label": endpoint,
        "association_explicit": association_explicit,
        "status": status,
        "issue_codes": ["molecular_exposure_merged_with_outcome"] if merged else [],
        "provenance": provenance,
    }
    payload["identity"] = _identity("experimental_measurement_semantic_integrity_v1", payload)
    return MeasurementSemanticIntegrityV1.model_validate(payload)


ArmRole = Literal["experimental", "reference", "control", "baseline", "comparator", "unknown"]


class ExperimentalArmRecordV1(StrictCoreAsset):
    arm_id: str
    arm_label_raw: str
    factor_refs: list[str] = Field(default_factory=list)
    component_raw_values: list[str] = Field(default_factory=list)
    species: str | None = None
    model_system: str | None = None
    tissue: str | None = None
    genotype: str | None = None
    treatment: str | None = None
    timepoint: str | None = None
    cohort: str | None = None
    source_evidence_refs: list[str]
    group_definition_refs: list[str]
    role_candidate: ArmRole = "unknown"
    role_authority: Literal["candidate_only", "explicit_source", "unresolved"]
    validation_status: Literal["validated", "candidate", "blocked"]
    supersedes: str | None = None
    derived_from: list[str]
    repair_reason: str
    repair_rule_identity: str
    immutable: Literal[True] = True
    identity: str
    provenance: CoreProvenance
    schema_version: Literal["experimental_arm_record_v1"] = "experimental_arm_record_v1"

    @model_validator(mode="after")
    def validate_source_authority(self):
        if self.role_authority == "explicit_source" and not self.source_evidence_refs:
            raise ValueError("explicit source arm requires evidence")
        return self


CompletenessStatus = Literal[
    "complete", "incomplete_reference_arm", "incomplete_factor",
    "candidate_set_invalid", "source_scope_insufficient", "unresolved",
]


class LinkageCandidateCompletenessV1(StrictCoreAsset):
    observation_identity: str
    status: CompletenessStatus
    candidate_ids: list[str]
    missing_components: list[str] = Field(default_factory=list)
    route: Literal["materializer", "structural_remediation", "source_recovery", "unresolved"]
    identity: str
    provenance: CoreProvenance
    schema_version: Literal["experimental_linkage_candidate_completeness_v1"] = (
        "experimental_linkage_candidate_completeness_v1"
    )


def candidate_completeness_gate(
    *, observation_identity: str, candidate_ids: list[str], source_scope_sufficient: bool,
    source_declares_reference_arm: bool, reference_arm_candidate_present: bool,
    factor_candidates_valid: bool, provenance: CoreProvenance,
) -> LinkageCandidateCompletenessV1:
    if not source_scope_sufficient:
        status, missing, route = "source_scope_insufficient", [], "source_recovery"
    elif source_declares_reference_arm and not reference_arm_candidate_present:
        status, missing, route = "incomplete_reference_arm", ["reference_arm"], "structural_remediation"
    elif not factor_candidates_valid or not candidate_ids:
        status, missing, route = "candidate_set_invalid", ["factor_candidate"], "structural_remediation"
    else:
        status, missing, route = "complete", [], "materializer"
    payload = {
        "observation_identity": observation_identity, "status": status,
        "candidate_ids": candidate_ids, "missing_components": missing, "route": route,
        "provenance": provenance,
    }
    payload["identity"] = _identity("experimental_linkage_candidate_completeness_v1", payload)
    return LinkageCandidateCompletenessV1.model_validate(payload)


MaterializationState = Literal[
    "candidate", "validated_source_grounded", "materializable",
    "materialized_sidecar", "blocked",
]


class SourceGroundedLinkageCandidateV1(StrictCoreAsset):
    observation_identity: str
    relation_type: Literal[
        "result_compared_against_reference_arm", "result_compared_against_factor",
        "factor_applies_to_measurement",
    ]
    source_ref: str
    target_ref: str
    source_identity: str
    evidence_refs: list[str]
    explicit_source_semantics: bool
    deterministic_grounding_version: str
    competing_candidate_refs: list[str] = Field(default_factory=list)
    candidate_completeness_status: CompletenessStatus
    structural_integrity_passed: bool
    authority_state: MaterializationState
    role_metadata_only: bool = False
    candidate_cardinality_only: bool = False
    identity: str
    provenance: CoreProvenance
    schema_version: Literal["source_grounded_experimental_linkage_candidate_v1"] = (
        "source_grounded_experimental_linkage_candidate_v1"
    )


class SourceGroundedMaterializedLinkageV1(StrictCoreAsset):
    linkage_id: str
    observation_identity: str
    relation_type: Literal[
        "result_compared_against_reference_arm", "result_compared_against_factor",
        "factor_applies_to_measurement",
    ]
    source_ref: str
    target_ref: str
    source_identity: str
    evidence_refs: list[str]
    derivation_method: Literal["validated_source_grounded_materialization"]
    authority_state: Literal["materialized_sidecar"]
    repair_rule_identity: str
    immutable: Literal[True] = True
    identity: str
    provenance: CoreProvenance
    schema_version: Literal["source_grounded_experimental_linkage_materialization_v1"] = (
        "source_grounded_experimental_linkage_materialization_v1"
    )


class MaterializationDecision(StrictCoreAsset):
    status: Literal["materialized", "rejected"]
    reason_codes: list[str]
    linkage: SourceGroundedMaterializedLinkageV1 | None = None


def materialize_linkage(candidate: SourceGroundedLinkageCandidateV1) -> MaterializationDecision:
    """Materialize only explicit, unambiguous, structurally valid source grounding."""
    reasons = []
    if candidate.authority_state not in {"validated_source_grounded", "materializable"}:
        reasons.append("authority_not_validated_source_grounded")
    if not candidate.source_ref or not candidate.target_ref:
        reasons.append("nonspecific_relation_endpoint")
    if not candidate.explicit_source_semantics:
        reasons.append("explicit_comparison_or_applicability_absent")
    if not candidate.evidence_refs or any(not ref.strip() for ref in candidate.evidence_refs):
        reasons.append("invalid_evidence_refs")
    if not candidate.deterministic_grounding_version:
        reasons.append("grounding_version_absent")
    if candidate.competing_candidate_refs:
        reasons.append("competing_candidate_unresolved")
    if candidate.candidate_completeness_status != "complete":
        reasons.append("candidate_completeness_gate_failed")
    if not candidate.structural_integrity_passed:
        reasons.append("structural_integrity_gate_failed")
    if candidate.role_metadata_only:
        reasons.append("role_metadata_not_authority")
    if candidate.candidate_cardinality_only:
        reasons.append("candidate_cardinality_not_authority")
    if reasons:
        return MaterializationDecision(status="rejected", reason_codes=reasons)
    payload = {
        "linkage_id": "", "observation_identity": candidate.observation_identity,
        "relation_type": candidate.relation_type, "source_ref": candidate.source_ref,
        "target_ref": candidate.target_ref, "source_identity": candidate.source_identity,
        "evidence_refs": candidate.evidence_refs,
        "derivation_method": "validated_source_grounded_materialization",
        "authority_state": "materialized_sidecar",
        "repair_rule_identity": candidate.deterministic_grounding_version,
        "immutable": True, "provenance": candidate.provenance,
    }
    payload["identity"] = _identity("source_grounded_experimental_linkage_materialization_v1", payload)
    payload["linkage_id"] = payload["identity"]
    return MaterializationDecision(
        status="materialized", reason_codes=[],
        linkage=SourceGroundedMaterializedLinkageV1.model_validate(payload),
    )


TaskValidityStatus = Literal[
    "already_deterministically_resolvable", "valid_for_annotation",
    "candidate_set_incomplete", "candidate_set_invalid",
    "observation_structure_invalid", "source_scope_insufficient",
    "structural_remediation_required", "unresolved",
]


class AnnotationTaskValidityGateV1(StrictCoreAsset):
    observation_identity: str
    status: TaskValidityStatus
    route: Literal[
        "linkage_materializer", "candidate_arm_repair", "structural_repair",
        "source_recovery", "human_annotation", "unresolved",
    ]
    reason_codes: list[str]
    identity: str
    provenance: CoreProvenance
    schema_version: Literal["annotation_task_validity_gate_v1"] = "annotation_task_validity_gate_v1"


def annotation_task_validity_gate(
    *, observation_identity: str, source_scope_sufficient: bool,
    candidate_status: CompletenessStatus, observation_structure_valid: bool,
    semantic_structure_valid: bool, deterministically_resolvable: bool,
    provenance: CoreProvenance,
) -> AnnotationTaskValidityGateV1:
    if not source_scope_sufficient:
        status, route, reasons = "source_scope_insufficient", "source_recovery", ["source_scope_insufficient"]
    elif not observation_structure_valid:
        status, route, reasons = "observation_structure_invalid", "structural_repair", ["result_structure_invalid"]
    elif not semantic_structure_valid:
        status, route, reasons = "structural_remediation_required", "structural_repair", ["measurement_semantics_invalid"]
    elif candidate_status in {"incomplete_reference_arm", "incomplete_factor"}:
        status, route, reasons = "candidate_set_incomplete", "candidate_arm_repair", [candidate_status]
    elif candidate_status == "candidate_set_invalid":
        status, route, reasons = "candidate_set_invalid", "candidate_arm_repair", [candidate_status]
    elif deterministically_resolvable:
        status, route, reasons = "already_deterministically_resolvable", "linkage_materializer", []
    elif candidate_status == "complete":
        status, route, reasons = "valid_for_annotation", "human_annotation", []
    else:
        status, route, reasons = "unresolved", "unresolved", [candidate_status]
    payload = {
        "observation_identity": observation_identity, "status": status,
        "route": route, "reason_codes": reasons, "provenance": provenance,
    }
    payload["identity"] = _identity("annotation_task_validity_gate_v1", payload)
    return AnnotationTaskValidityGateV1.model_validate(payload)


ReadinessV5Status = Literal[
    "machine_reusable_candidate", "machine_reusable_with_method_limitation",
    "machine_reusable_with_context_limitation", "machine_reusable_with_nonblocking_enrichment",
    "machine_reusable_with_core_annotation_pending", "structured_core_blocked_result_invalid",
    "structured_core_blocked_measurement_invalid", "structured_core_blocked_candidate_incomplete",
    "structured_core_blocked_reference_arm_missing", "structured_core_blocked_local_source_gap",
    "structured_core_blocked_external_source_gap", "structured_core_source_not_reported",
    "structured_core_linkage_unresolved", "non_experimental_claim", "unusable", "unassessed",
]


class ObservationMachineReuseReadinessV5Candidate(StrictCoreAsset):
    observation_identity: str
    v4_readiness_identity: str
    status: ReadinessV5Status
    core_blockers: list[str] = Field(default_factory=list)
    nonblocking_limitations: list[str] = Field(default_factory=list)
    candidate_only: Literal[True] = True
    active_v4_replaced: Literal[False] = False
    human_gold: Literal[False] = False
    formal_authority: Literal[False] = False
    identity: str
    provenance: CoreProvenance
    schema_version: Literal["experimental_observation_machine_reuse_readiness_v5_candidate"] = (
        "experimental_observation_machine_reuse_readiness_v5_candidate"
    )


_BLOCKER_PRECEDENCE: tuple[tuple[str, ReadinessV5Status], ...] = (
    ("result_invalid", "structured_core_blocked_result_invalid"),
    ("measurement_invalid", "structured_core_blocked_measurement_invalid"),
    ("reference_arm_missing", "structured_core_blocked_reference_arm_missing"),
    ("candidate_incomplete", "structured_core_blocked_candidate_incomplete"),
    ("local_source_gap", "structured_core_blocked_local_source_gap"),
    ("external_source_gap", "structured_core_blocked_external_source_gap"),
    ("source_not_reported", "structured_core_source_not_reported"),
    ("linkage_unresolved", "structured_core_linkage_unresolved"),
)


def machine_reuse_readiness_v5(
    *, observation_identity: str, v4_readiness_identity: str,
    prior_status: str, core_blockers: list[str], nonblocking_limitations: list[str],
    provenance: CoreProvenance,
) -> ObservationMachineReuseReadinessV5Candidate:
    blockers = list(dict.fromkeys(core_blockers))
    status: ReadinessV5Status | None = next((value for key, value in _BLOCKER_PRECEDENCE if key in blockers), None)
    if status is None:
        if prior_status in {"non_experimental_claim", "unusable", "unassessed"}:
            status = prior_status  # type: ignore[assignment]
        elif "method" in nonblocking_limitations:
            status = "machine_reusable_with_method_limitation"
        elif "context" in nonblocking_limitations:
            status = "machine_reusable_with_context_limitation"
        elif nonblocking_limitations:
            status = "machine_reusable_with_nonblocking_enrichment"
        elif prior_status == "machine_reusable_with_core_annotation_pending":
            status = "machine_reusable_with_core_annotation_pending"
        else:
            status = "machine_reusable_candidate"
    payload = {
        "observation_identity": observation_identity,
        "v4_readiness_identity": v4_readiness_identity, "status": status,
        "core_blockers": blockers, "nonblocking_limitations": nonblocking_limitations,
        "candidate_only": True, "active_v4_replaced": False, "human_gold": False,
        "formal_authority": False, "provenance": provenance,
    }
    payload["identity"] = _identity("experimental_observation_machine_reuse_readiness_v5_candidate", payload)
    return ObservationMachineReuseReadinessV5Candidate.model_validate(payload)


CONTRACT_MODELS = {
    "experimental_observed_result_structural_integrity_v2": ObservedResultStructuralIntegrityV2,
    "experimental_measurement_semantic_integrity_v1": MeasurementSemanticIntegrityV1,
    "experimental_arm_record_v1": ExperimentalArmRecordV1,
    "experimental_linkage_candidate_completeness_v1": LinkageCandidateCompletenessV1,
    "source_grounded_experimental_linkage_materialization_v1": SourceGroundedMaterializedLinkageV1,
    "annotation_task_validity_gate_v1": AnnotationTaskValidityGateV1,
    "experimental_observation_machine_reuse_readiness_v5_candidate": ObservationMachineReuseReadinessV5Candidate,
}


def repair_contract_identity(name: str) -> dict[str, Any]:
    if name not in CONTRACT_MODELS:
        raise ValueError(f"unknown repair contract: {name}")
    payload = {
        "contract_name": name, "strict": True, "extra_forbid": True,
        "identity_algorithm": "sha256_canonical_json_v1", "immutable_revision_policy": True,
        "runtime_fixture_access": False, "scientific_inference_authorized": False,
    }
    digest = core_identity("experimental_core_repair_contract_identity_v1", payload)
    return {"schema_version": "experimental_core_repair_contract_identity_v1", **payload,
            "identity": digest, "identity_match": True}
