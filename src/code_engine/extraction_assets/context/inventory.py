"""Read-only historical artifact inventory helpers."""
from __future__ import annotations

from pathlib import Path

from ..identities import sha256_bytes


def file_sha256(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def context_artifact_candidate(path: Path) -> bool:
    lowered = path.name.lower()
    return any(token in lowered for token in ("context", "extraction", "evidence", "readiness", "remediation"))
