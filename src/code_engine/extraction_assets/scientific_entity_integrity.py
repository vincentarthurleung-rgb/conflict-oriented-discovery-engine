"""Generic fail-closed entity-integrity gate for scientific consumers.

The gate consumes integrity state and proposition roles only.  Evaluation case
identities, task identities, entity spellings, and reference answers are not
part of this API.  Historical objects remain visible; the returned records are
eligibility sidecars rather than mutations of those objects.
"""
from __future__ import annotations

from typing import Iterable, Literal, Sequence

from pydantic import BaseModel, ConfigDict, Field, model_validator


EntityIntegrityStatus = Literal[
    "entity_integrity_valid",
    "entity_integrity_validated_normalization",
    "entity_integrity_unresolved",
    "entity_integrity_invalidated",
    "upstream_claim_integrity_blocked",
    "historical_integrity_warning_nonblocking",
]
ScientificRole = Literal[
    "subject",
    "object",
    "intervention_identity",
    "measurement_target_identity",
    "metadata",
    "auxiliary",
    "unknown",
]
ScientificConsumer = Literal[
    "claim_qualification",
    "contradiction_signal",
    "bridge_candidate",
    "claim_alignment",
    "candidate_qualification",
    "l4a_context_difference",
    "l4b_comparability",
    "divergence_explanatory_power",
    "formal_judgment",
]
EligibilityStatus = Literal[
    "eligible",
    "eligible_validated_normalization",
    "eligible_with_historical_warning",
    "blocked_upstream_entity_integrity",
    "blocked_upstream_claim_integrity",
    "blocked_upstream_scientific_integrity",
]

PROPOSITION_CRITICAL_ROLES = frozenset({
    "subject", "object", "intervention_identity", "measurement_target_identity",
})
BLOCKING_ENTITY_STATES = frozenset({
    "entity_integrity_unresolved", "entity_integrity_invalidated",
})
BLOCKING_ELIGIBILITY_STATES = frozenset({
    "blocked_upstream_entity_integrity",
    "blocked_upstream_claim_integrity",
    "blocked_upstream_scientific_integrity",
})


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ScientificEntityIntegrityStateV1(StrictModel):
    """One entity state attached to a scientific object without rewriting it."""

    schema_version: Literal[
        "scientific_entity_integrity_state_v1"
    ] = "scientific_entity_integrity_state_v1"
    object_id: str
    object_type: str
    entity_integrity_status: EntityIntegrityStatus
    affected_field: str
    scientific_role: ScientificRole
    source_refs: list[str] = Field(default_factory=list)
    historical_state_visible: bool = True
    historical_object_modified: bool = False

    @property
    def proposition_critical(self) -> bool:
        return self.scientific_role in PROPOSITION_CRITICAL_ROLES

    @model_validator(mode="after")
    def sidecar_is_non_mutating(self):
        if self.historical_object_modified:
            raise ValueError("entity_integrity_gate_cannot_modify_historical_object")
        return self


class ScientificEntityIntegrityGateResultV1(StrictModel):
    schema_version: Literal[
        "scientific_entity_integrity_gate_result_v1"
    ] = "scientific_entity_integrity_gate_result_v1"
    object_id: str
    object_type: str
    consumer: ScientificConsumer
    eligibility_status: EligibilityStatus
    authoritative_for_scientific_promotion: bool
    affected_fields: list[str]
    scientific_roles: list[ScientificRole]
    blocking_reasons: list[str]
    source_refs: list[str]
    historical_invalid_state_visible: bool = True
    historical_object_modified: bool = False


class ScientificEntityIntegrityBlocked(ValueError):
    """Raised before a consumer materializes output from blocked inputs."""


class ScientificEntityIntegrityGateV1:
    """Evaluate generic entity and upstream eligibility state for one consumer."""

    schema_version = "scientific_entity_integrity_gate_v1"

    def evaluate(
        self,
        *,
        object_id: str,
        object_type: str,
        consumer: ScientificConsumer,
        entity_states: Iterable[ScientificEntityIntegrityStateV1] = (),
        upstream_results: Iterable[ScientificEntityIntegrityGateResultV1] = (),
    ) -> ScientificEntityIntegrityGateResultV1:
        states = list(entity_states)
        upstream = list(upstream_results)
        critical_blockers = [
            state for state in states
            if state.proposition_critical
            and state.entity_integrity_status in BLOCKING_ENTITY_STATES
        ]
        upstream_blockers = [
            result for result in upstream
            if result.eligibility_status in BLOCKING_ELIGIBILITY_STATES
            or not result.authoritative_for_scientific_promotion
        ]
        reasons: list[str] = []
        if critical_blockers:
            status: EligibilityStatus = "blocked_upstream_entity_integrity"
            reasons.extend(
                f"{state.entity_integrity_status}:{state.affected_field}:{state.scientific_role}"
                for state in critical_blockers
            )
        elif upstream_blockers:
            if consumer == "contradiction_signal":
                status = "blocked_upstream_claim_integrity"
            else:
                status = "blocked_upstream_scientific_integrity"
            reasons.extend(
                f"upstream:{result.object_type}:{result.object_id}:{result.eligibility_status}"
                for result in upstream_blockers
            )
        elif any(
            state.entity_integrity_status == "upstream_claim_integrity_blocked"
            for state in states
        ):
            status = (
                "blocked_upstream_claim_integrity"
                if consumer == "contradiction_signal"
                else "blocked_upstream_scientific_integrity"
            )
            reasons.append("upstream_claim_integrity_blocked")
        elif any(
            state.entity_integrity_status in BLOCKING_ENTITY_STATES
            or state.entity_integrity_status == "historical_integrity_warning_nonblocking"
            for state in states
        ):
            # An unresolved metadata or auxiliary entity remains auditable but
            # cannot block a proposition in which it does not participate.
            status = "eligible_with_historical_warning"
        elif any(
            state.entity_integrity_status == "entity_integrity_validated_normalization"
            for state in states
        ):
            status = "eligible_validated_normalization"
        else:
            status = "eligible"

        authorized = status not in BLOCKING_ELIGIBILITY_STATES
        return ScientificEntityIntegrityGateResultV1(
            object_id=object_id,
            object_type=object_type,
            consumer=consumer,
            eligibility_status=status,
            authoritative_for_scientific_promotion=authorized,
            affected_fields=sorted({state.affected_field for state in states}),
            scientific_roles=sorted({state.scientific_role for state in states}),
            blocking_reasons=sorted(set(reasons)),
            source_refs=sorted({ref for state in states for ref in state.source_refs}),
            historical_invalid_state_visible=all(
                state.historical_state_visible for state in states
            ),
        )


def require_scientific_entity_integrity(
    consumer: ScientificConsumer,
    decisions: Sequence[ScientificEntityIntegrityGateResultV1] | None,
) -> None:
    """Reject blocked sidecars before a production consumer materializes output.

    ``None`` retains compatibility for historical replay code that predates the
    sidecar contract.  Once sidecars are supplied, every supplied decision is
    enforced fail-closed.
    """
    if decisions is None:
        return
    blocked = [
        decision for decision in decisions
        if decision.eligibility_status in BLOCKING_ELIGIBILITY_STATES
        or not decision.authoritative_for_scientific_promotion
    ]
    if blocked:
        reasons = ",".join(
            f"{item.object_type}:{item.object_id}:{item.eligibility_status}"
            for item in blocked
        )
        raise ScientificEntityIntegrityBlocked(
            f"{consumer}_blocked_by_scientific_entity_integrity:{reasons}"
        )


SCIENTIFIC_ENTITY_INTEGRITY_CONSUMER_INVENTORY_V1 = (
    ("claim_qualification", "claim proposition/evidence qualification"),
    ("contradiction_signal", "contradiction signal construction"),
    ("bridge_candidate", "scientific bridge pair construction"),
    ("claim_alignment", "claim proposition alignment"),
    ("candidate_qualification", "candidate scientific qualification"),
    ("l4a_context_difference", "descriptive ContextDifference construction"),
    ("l4b_comparability", "factor comparability assessment"),
    ("divergence_explanatory_power", "divergence explanation assessment"),
    ("formal_judgment", "L4c/formal staging judgment"),
)

