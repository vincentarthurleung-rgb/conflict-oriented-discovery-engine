from __future__ import annotations

from typing import Any

from .identities import claim_alignment_identity
from .models import AlignedClaimGroup


def validate_claim_alignment(
    payload: AlignedClaimGroup | dict[str, Any],
) -> tuple[AlignedClaimGroup, list[str]]:
    value = (
        payload
        if isinstance(payload, AlignedClaimGroup)
        else AlignedClaimGroup.model_validate(payload)
    )
    errors: list[str] = []
    if len(set(value.member_observation_ids)) != 2:
        errors.append("alignment_requires_distinct_observations")
    if len(set(value.member_claim_identities)) != 2:
        errors.append("alignment_requires_distinct_claim_identities")
    if value.claim_alignment_identity != claim_alignment_identity(value.model_dump()):
        errors.append("claim_alignment_identity_mismatch")
    if set(value.context_readiness_by_member) != set(value.member_observation_ids):
        errors.append("alignment_context_readiness_members_mismatch")
    return value, errors
