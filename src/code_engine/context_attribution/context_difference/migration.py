from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict

from ..claim_alignment.models import AlignedClaimGroup
from ..conflict_candidate.contradiction import ContradictionSignal
from ..conflict_candidate.migration import CandidateMigrationBinding
from ..layer_identity import layer_identity
from .models import ContextDifference


class ContextDifferenceMigrationBinding(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal[
        "context_difference_alignment_signal_binding_v1"
    ] = "context_difference_alignment_signal_binding_v1"
    context_difference_identity: str
    claim_alignment_identity: str
    contradiction_signal_identity: str
    conflict_candidate_identity: str
    candidate_migration_binding_identity: str
    observation_context_a_identity: str
    observation_context_b_identity: str
    migration_binding_identity: str
    validation_status: Literal["validated", "rejected"]
    provenance: dict[str, Any]


def context_difference_migration_binding_identity(payload: dict[str, Any]) -> str:
    return layer_identity(
        "context_difference_migration_binding",
        "context_difference_migration_binding_identity_v1",
        {
            key: payload[key]
            for key in (
                "context_difference_identity",
                "claim_alignment_identity",
                "contradiction_signal_identity",
                "conflict_candidate_identity",
                "candidate_migration_binding_identity",
                "observation_context_a_identity",
                "observation_context_b_identity",
            )
        },
    )


def bind_context_difference_migration(
    *,
    difference: ContextDifference,
    alignment: AlignedClaimGroup,
    signal: ContradictionSignal,
    candidate_binding: CandidateMigrationBinding,
) -> ContextDifferenceMigrationBinding:
    valid = (
        difference.validation_status == "validated"
        and difference.conflict_candidate_identity
        == candidate_binding.legacy_candidate_identity
        and candidate_binding.claim_alignment_identity
        == alignment.claim_alignment_identity
        and candidate_binding.contradiction_signal_identity
        == signal.contradiction_signal_identity
    )
    payload = {
        "schema_version": "context_difference_alignment_signal_binding_v1",
        "context_difference_identity": difference.context_difference_identity,
        "claim_alignment_identity": alignment.claim_alignment_identity,
        "contradiction_signal_identity": signal.contradiction_signal_identity,
        "conflict_candidate_identity": difference.conflict_candidate_identity,
        "candidate_migration_binding_identity": (
            candidate_binding.migration_binding_identity
        ),
        "observation_context_a_identity": (
            difference.observation_context_a_identity
        ),
        "observation_context_b_identity": (
            difference.observation_context_b_identity
        ),
        "validation_status": "validated" if valid else "rejected",
        "provenance": {
            "original_context_difference_modified": False,
            "status_value_anchor_modified": False,
            "binding_is_sidecar": True,
        },
    }
    payload["migration_binding_identity"] = (
        context_difference_migration_binding_identity(payload)
    )
    return ContextDifferenceMigrationBinding.model_validate(payload)
