"""Pair- and consumer-level Context requirement activation contracts.

The presence of Context on an observation is not a requirement.  Requirements
must originate in a versioned consumer contract and are evaluated independently
for each pair and consumer.
"""
from __future__ import annotations

import hashlib
import json
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


ActivationStatus = Literal[
    "required_active", "conditionally_required_active", "optional_explicit",
    "not_required_explicit", "not_activated", "no_consumer_requirement_declared",
]
EvidenceState = Literal[
    "direct", "safe_inherited", "derived_authorized", "derived", "unresolved", "ambiguous",
    "not_reported_with_adequate_scope", "not_reported", "source_scope_insufficient",
]
PairSatisfaction = Literal[
    "satisfied", "partially_satisfied", "unsatisfied", "not_applicable",
]
PairReadiness = Literal[
    "ready_all_active_requirements_satisfied",
    "ready_with_nonblocking_context_gap",
    "reviewable_no_requirement_contract",
    "reviewable_partial_requirement_evidence",
    "blocked_required_context_missing",
    "blocked_required_context_ambiguous",
    "blocked_source_scope",
    "not_context_sensitive",
]


def stable(kind: str, payload: Any) -> str:
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return f"{kind}_{hashlib.sha256(raw.encode()).hexdigest()[:24]}"


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class PairContextRequirementProfileV1(StrictModel):
    schema_version: Literal["pair_context_requirement_profile_v1"] = "pair_context_requirement_profile_v1"
    pair_id: str
    consumer: str
    consumer_version: str
    validated_trigger_inputs: dict[str, Any]
    contract_ids: list[str]
    requirement_identity: str
    task_identity_read: bool = False
    reference_answer_read: bool = False

    @model_validator(mode="after")
    def no_evaluation_leakage(self):
        forbidden = {"task_id", "task_ids", "reference_answer", "human_adjudication", "reference_factor_id"}
        if forbidden.intersection(self.validated_trigger_inputs):
            raise ValueError("pair_requirement_trigger_contains_forbidden_evaluation_input")
        if self.task_identity_read or self.reference_answer_read:
            raise ValueError("pair_requirement_cannot_read_evaluation_identity_or_answer")
        return self


class PairContextRequirementActivationV1(StrictModel):
    schema_version: Literal["pair_context_requirement_activation_v1"] = "pair_context_requirement_activation_v1"
    pair_id: str
    consumer: str
    consumer_version: str
    dimension: str
    activation_status: ActivationStatus
    activation_class: ActivationStatus | None = None
    trigger_state: Literal["matched", "not_matched", "not_declared", "unconditional"]
    trigger_type: Literal[
        "proposition_scope", "experimental_contrast", "evidence_family_semantics",
        "measurement_result_semantics", "supported_pair_difference",
        "none_declared", "unconditional_explicit", "legacy_structured_condition",
    ] = "legacy_structured_condition"
    trigger_evidence: dict[str, Any]
    blocking_semantics: str
    source_contract_ref: str
    source_code_ref: str
    requirement_identity: str

    @model_validator(mode="after")
    def activation_names_are_consistent(self):
        if self.activation_class is not None and self.activation_class != self.activation_status:
            raise ValueError("activation_class_must_equal_activation_status")
        return self


class PairContextRequirementSatisfactionV1(StrictModel):
    schema_version: Literal["pair_context_requirement_satisfaction_v1"] = "pair_context_requirement_satisfaction_v1"
    pair_id: str
    consumer: str
    dimension: str
    requirement_identity: str
    activation_status: ActivationStatus
    side_a_evidence_state: EvidenceState
    side_b_evidence_state: EvidenceState
    satisfaction_status: PairSatisfaction
    evidence_refs: list[str] = Field(default_factory=list)


class PairContextReadinessV1Candidate(StrictModel):
    schema_version: Literal["pair_context_readiness_v1_candidate"] = "pair_context_readiness_v1_candidate"
    pair_id: str
    consumer: str
    consumer_version: str
    status: PairReadiness
    active_requirement_ids: list[str]
    candidate_only: bool = True
    historical_context_modified: bool = False


class PairContextReadinessV1(StrictModel):
    schema_version: Literal["pair_context_readiness_v1"] = "pair_context_readiness_v1"
    pair_id: str
    consumer: str
    consumer_version: str
    status: PairReadiness
    active_requirement_ids: list[str]
    historical_context_modified: bool = False


class PairContextTriggerFactV1(StrictModel):
    """Auditable structured fact capable of activating one pair requirement."""

    schema_version: Literal["pair_context_trigger_fact_v1"] = "pair_context_trigger_fact_v1"
    pair_id: str
    dimension: str
    trigger_type: Literal[
        "proposition_scope", "experimental_contrast", "evidence_family_semantics",
        "measurement_result_semantics", "supported_pair_difference",
    ]
    structurally_established: bool
    trigger_evidence: dict[str, Any]
    source_contract_ref: str
    source_code_ref: str


def conditional_activation_for(
    *, dimension: str, trigger_facts: list[PairContextTriggerFactV1],
) -> tuple[ActivationStatus, Literal["matched", "not_matched"], str | None]:
    """Activate only from a typed, structurally established matching fact."""
    matches = [
        fact for fact in trigger_facts
        if fact.dimension == dimension and fact.structurally_established
    ]
    if not matches:
        return "not_activated", "not_matched", None
    trigger_types = {fact.trigger_type for fact in matches}
    if len(trigger_types) != 1:
        raise ValueError("one_requirement_activation_requires_one_trigger_type")
    return "conditionally_required_active", "matched", next(iter(trigger_types))


def activation_for(
    *, requirement_class: str, trigger_condition: dict[str, Any],
    validated_trigger_inputs: dict[str, Any],
) -> tuple[ActivationStatus, Literal["matched", "not_matched", "not_declared", "unconditional"]]:
    if requirement_class == "no_requirement_declared":
        return "no_consumer_requirement_declared", "not_declared"
    if requirement_class == "required":
        return "required_active", "unconditional"
    if requirement_class == "optional_explicit":
        return "optional_explicit", "unconditional"
    if requirement_class == "not_required_explicit":
        return "not_required_explicit", "unconditional"
    if requirement_class != "conditionally_required":
        raise ValueError(f"unknown_requirement_class:{requirement_class}")
    field = trigger_condition.get("field")
    allowed = trigger_condition.get("in")
    matched = bool(field and isinstance(allowed, list) and validated_trigger_inputs.get(field) in allowed)
    return (
        ("conditionally_required_active", "matched")
        if matched else ("not_activated", "not_matched")
    )


def satisfaction_for_pair(
    activation_status: ActivationStatus, side_a: EvidenceState, side_b: EvidenceState,
) -> PairSatisfaction:
    if activation_status not in {
        "required_active", "conditionally_required_active", "optional_explicit"
    }:
        return "not_applicable"
    # ``derived`` is retained as a legacy evidence spelling but is not enough
    # to satisfy v1.  Only an explicitly authorized derivation can satisfy.
    satisfying = {"direct", "safe_inherited", "derived_authorized"}
    states = (side_a, side_b)
    resolved = sum(x in satisfying for x in states)
    if resolved == 2:
        return "satisfied"
    if resolved == 1:
        return "partially_satisfied"
    return "unsatisfied"


def readiness_for_pair(
    activations: list[PairContextRequirementActivationV1],
    satisfactions: list[PairContextRequirementSatisfactionV1],
) -> PairReadiness:
    if not activations or all(
        x.activation_status == "no_consumer_requirement_declared" for x in activations
    ):
        return "reviewable_no_requirement_contract"
    active_required = {
        x.requirement_identity for x in activations
        if x.activation_status in {"required_active", "conditionally_required_active"}
    }
    active_optional = {
        x.requirement_identity for x in activations if x.activation_status == "optional_explicit"
    }
    if not active_required and not active_optional:
        return "not_context_sensitive"
    required_rows = [x for x in satisfactions if x.requirement_identity in active_required]
    required_states = {
        state for row in required_rows
        for state in (row.side_a_evidence_state, row.side_b_evidence_state)
    }
    if "source_scope_insufficient" in required_states:
        return "blocked_source_scope"
    if "ambiguous" in required_states:
        return "blocked_required_context_ambiguous"
    if any(x.satisfaction_status == "unsatisfied" for x in required_rows):
        return "blocked_required_context_missing"
    if any(x.satisfaction_status == "partially_satisfied" for x in required_rows):
        return "reviewable_partial_requirement_evidence"
    optional_rows = [x for x in satisfactions if x.requirement_identity in active_optional]
    if any(x.satisfaction_status != "satisfied" for x in optional_rows):
        return "ready_with_nonblocking_context_gap"
    return "ready_all_active_requirements_satisfied"
