"""Minimal adapters from legacy records; never mutate the input artifact."""
from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any

from .archive import RawResponseArchive


def legacy_null_state(value: Any) -> str:
    return "legacy_null_unresolved" if value is None else "present"


def wrap_legacy_payload(payload: Any) -> Any:
    return deepcopy(payload)


def raw_response_sink(archive_root: Path | str, call_dedup_identity: str):
    """Return the minimal callback accepted by provider transport clients."""
    archive = RawResponseArchive(archive_root)

    def persist(raw_bytes: bytes) -> tuple[Path, str]:
        return archive.persist(raw_bytes, call_dedup_identity)

    return persist
