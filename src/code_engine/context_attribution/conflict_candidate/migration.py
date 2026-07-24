from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict

from ..claim_alignment.models import AlignedClaimGroup
from ..layer_identity import layer_identity
from .contradiction import ContradictionSignal
from .models import ConflictCandidate


class CandidateMigrationBinding(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal[
        "candidate_alignment_signal_migration_binding_v1"
    ] = "candidate_alignment_signal_migration_binding_v1"
    candidate_id: str
    legacy_candidate_identity: str
    claim_alignment_identity: str
    contradiction_signal_identity: str
    alignment_status: str
    contradiction_signal_status: str
    context_readiness: str
    historical_candidate_preserved: Literal[True] = True
    migration_binding_identity: str
    validation_status: Literal["validated", "rejected"]
    provenance: dict[str, Any]


def candidate_migration_binding_identity(payload: dict[str, Any]) -> str:
    return layer_identity(
        "candidate_migration_binding",
        "candidate_migration_binding_identity_v1",
        {
            key: payload[key]
            for key in (
                "candidate_id",
                "legacy_candidate_identity",
                "claim_alignment_identity",
                "contradiction_signal_identity",
                "alignment_status",
                "contradiction_signal_status",
                "context_readiness",
            )
        },
    )


def bind_historical_candidate(
    *,
    candidate: ConflictCandidate,
    alignment: AlignedClaimGroup,
    signal: ContradictionSignal,
) -> CandidateMigrationBinding:
    payload = {
        "schema_version": "candidate_alignment_signal_migration_binding_v1",
        "candidate_id": candidate.candidate_id,
        "legacy_candidate_identity": candidate.conflict_candidate_identity,
        "claim_alignment_identity": alignment.claim_alignment_identity,
        "contradiction_signal_identity": signal.contradiction_signal_identity,
        "alignment_status": alignment.alignment_status,
        "contradiction_signal_status": signal.signal_status,
        "context_readiness": candidate.context_readiness,
        "historical_candidate_preserved": True,
        "validation_status": "validated",
        "provenance": {
            "candidate_id_changed": False,
            "candidate_order_changed": False,
            "legacy_candidate_payload_modified": False,
            "future_candidate_generation_authorized": (
                alignment.alignment_status == "aligned"
                and signal.signal_status in {"candidate", "validated"}
            ),
        },
    }
    payload["migration_binding_identity"] = candidate_migration_binding_identity(
        payload
    )
    return CandidateMigrationBinding.model_validate(payload)
