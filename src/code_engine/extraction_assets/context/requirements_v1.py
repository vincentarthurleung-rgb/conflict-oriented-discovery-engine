"""Consumer-driven context requirement and readiness v4 contracts."""
from __future__ import annotations

import hashlib
import json
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


RequirementClass = Literal[
    "required", "conditionally_required", "optional_explicit",
    "not_required_explicit", "no_requirement_declared",
]
SatisfactionStatus = Literal[
    "satisfied_direct", "satisfied_safe_inheritance", "satisfied_derived",
    "unsatisfied_unresolved", "unsatisfied_ambiguous", "unsatisfied_source_scope",
    "not_applicable",
]
ReadinessStatus = Literal[
    "ready_all_requirements_satisfied", "ready_with_safe_inheritance",
    "ready_with_nonblocking_optional_gap", "reviewable_no_requirement_contract",
    "reviewable_required_context_gap", "blocked_required_context_missing",
    "blocked_required_context_ambiguous", "blocked_source_scope",
    "not_context_sensitive",
]


def stable(kind: str, value: Any) -> str:
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return f"{kind}_{hashlib.sha256(raw.encode()).hexdigest()[:24]}"


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ContextRequirementContractV1(StrictModel):
    schema_version: Literal["downstream_context_requirement_contract_v1"] = "downstream_context_requirement_contract_v1"
    contract_id: str
    consumer: str
    consumer_version: str
    context_dimension: str
    field_or_dimension: Literal["dimension"] = "dimension"
    requirement_class: RequirementClass
    trigger_condition: dict[str, Any]
    blocking_semantics: str
    field_satisfaction_mapping: list[str] = Field(min_length=1)
    derived_satisfaction_allowed: bool = False
    source_contract_ref: str
    source_code_ref: str
    authority: Literal["production_source_contract", "versioned_config", "no_declaration_found"]

    @model_validator(mode="after")
    def declared_contract_requires_authority(self):
        if self.requirement_class != "no_requirement_declared" and self.authority == "no_declaration_found":
            raise ValueError("declared_requirement_requires_positive_consumer_authority")
        return self


class ContextRequirementActivationV1(StrictModel):
    schema_version: Literal["context_requirement_activation_v1"] = "context_requirement_activation_v1"
    activation_id: str
    observation_identity: str
    contract_id: str
    context_dimension: str
    requirement_class: RequirementClass
    trigger_evaluated: bool
    activated: bool
    structured_trigger_inputs: dict[str, Any]


class ContextRequirementSatisfactionV1(StrictModel):
    schema_version: Literal["context_requirement_satisfaction_v1"] = "context_requirement_satisfaction_v1"
    satisfaction_id: str
    activation_id: str
    observation_identity: str
    context_dimension: str
    requirement_class: RequirementClass
    status: SatisfactionStatus
    satisfying_field_ids: list[str] = Field(default_factory=list)
    provenance_refs: list[str] = Field(default_factory=list)


def evaluate_trigger(contract: ContextRequirementContractV1, structured: dict[str, Any]) -> bool:
    condition = contract.trigger_condition
    if contract.requirement_class != "conditionally_required":
        return contract.requirement_class in {"required", "optional_explicit"}
    field, allowed = condition.get("field"), condition.get("in")
    if not field or not isinstance(allowed, list):
        return False
    return structured.get(field) in allowed


def satisfaction_for(
    contract: ContextRequirementContractV1, *, value_authority: str | None,
    value_state: str | None, source_scope_sufficient: bool | None = True,
) -> SatisfactionStatus:
    if contract.requirement_class in {"no_requirement_declared", "not_required_explicit"}:
        return "not_applicable"
    if source_scope_sufficient is False:
        return "unsatisfied_source_scope"
    if value_state == "ambiguous":
        return "unsatisfied_ambiguous"
    if value_state != "present":
        return "unsatisfied_unresolved"
    if value_authority in {"direct_explicit", "direct_structured"}:
        return "satisfied_direct"
    if value_authority == "scope_inherited":
        return "satisfied_safe_inheritance"
    if value_authority == "deterministically_derived" and contract.derived_satisfaction_allowed:
        return "satisfied_derived"
    return "unsatisfied_unresolved"


def readiness_v4(satisfactions: list[ContextRequirementSatisfactionV1]) -> ReadinessStatus:
    if not satisfactions:
        return "reviewable_no_requirement_contract"
    declared = [x for x in satisfactions if x.requirement_class != "no_requirement_declared"]
    active_required = [x for x in declared if x.requirement_class in {"required", "conditionally_required"}]
    optional = [x for x in declared if x.requirement_class == "optional_explicit"]
    if not declared:
        return "reviewable_no_requirement_contract"
    if not active_required and not optional:
        return "not_context_sensitive"
    if any(x.status == "unsatisfied_source_scope" for x in active_required):
        return "blocked_source_scope"
    if any(x.status == "unsatisfied_ambiguous" for x in active_required):
        return "blocked_required_context_ambiguous"
    if any(x.status == "unsatisfied_unresolved" for x in active_required):
        return "blocked_required_context_missing"
    if optional and any(x.status.startswith("unsatisfied_") for x in optional):
        return "ready_with_nonblocking_optional_gap"
    if any(x.status == "satisfied_safe_inheritance" for x in active_required):
        return "ready_with_safe_inheritance"
    return "ready_all_requirements_satisfied"
