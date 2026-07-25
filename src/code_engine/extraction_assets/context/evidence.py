"""Evidence-anchor resolution for context fields."""
from __future__ import annotations

from ..field_evidence import reconstruct_exact_anchor


def resolve_exact_context_anchor(
    source_text: str, quote: str, *, authoritative_source_sha256: str,
) -> dict:
    return reconstruct_exact_anchor(
        source_text, quote, expected_source_sha256=authoritative_source_sha256,
    )


def provider_offsets_are_authoritative(_: list[tuple[int, int]]) -> bool:
    return False
