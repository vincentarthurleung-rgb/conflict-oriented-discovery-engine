"""Source snapshot constructors kept provider-independent."""
from __future__ import annotations

from .identities import sha256_bytes


def text_sha256(text: str) -> str:
    return sha256_bytes(text.encode("utf-8"))
