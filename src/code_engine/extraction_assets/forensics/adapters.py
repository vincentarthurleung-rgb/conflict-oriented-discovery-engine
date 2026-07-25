"""Pure adapters for legacy sidecars."""
from __future__ import annotations


def cache_key_from_attempt(row: dict) -> str | None:
    value = row.get("call_dedup_identity")
    prefix = "legacy_cache_key:"
    return value[len(prefix):] if isinstance(value, str) and value.startswith(prefix) else None


def cache_key_from_parsed(row: dict) -> str | None:
    value = row.get("provider_call_spec_identity")
    prefix = "legacy_cache_key:"
    return value[len(prefix):] if isinstance(value, str) and value.startswith(prefix) else None

