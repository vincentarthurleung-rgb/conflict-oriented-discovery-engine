"""Explicit, file-backed pilot profiles; never selected from query text."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def load_pilot_profile(name: str, repository_root: str | Path) -> dict[str, Any]:
    """Load a named pilot profile after validating its explicit identity."""

    profile_name = str(name or "").strip().casefold()
    if not profile_name or any(char not in "abcdefghijklmnopqrstuvwxyz0123456789_-" for char in profile_name):
        raise ValueError(f"Invalid pilot profile name: {name!r}")
    path = Path(repository_root) / "configs" / "pilots" / f"{profile_name}.json"
    if not path.is_file():
        raise FileNotFoundError(f"Pilot profile not found: {path}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if str(payload.get("pilot_profile") or "").casefold() != profile_name:
        raise ValueError(f"Pilot profile identity mismatch in {path}")
    payload["profile_path"] = str(path.resolve())
    return payload


__all__ = ["load_pilot_profile"]
