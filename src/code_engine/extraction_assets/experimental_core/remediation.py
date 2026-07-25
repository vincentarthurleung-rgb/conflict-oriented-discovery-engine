"""Offline-only remediation planning."""
from __future__ import annotations

from .identities import core_identity


def dedup_group(source_block_identity: str | None, minimal_source_scope: str) -> str:
    return core_identity("experimental_core_remediation_dedup_group_v1", {
        "source_block_identity": source_block_identity,
        "minimal_source_scope": minimal_source_scope,
    })


def authorization_fields() -> dict[str, bool]:
    return {
        "automatic_execution_authorized": False,
        "provider_call_authorized": False,
        "network_call_authorized": False,
        "budget_authorization_present": False,
    }

