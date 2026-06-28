"""Stable hashing helpers for artifacts and cache keys."""

import hashlib


def sha256_text(text: str) -> str:
    return hashlib.sha256(str(text).encode("utf-8")).hexdigest()

