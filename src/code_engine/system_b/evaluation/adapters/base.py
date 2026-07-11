"""Shared deterministic evaluation adapter primitives."""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


def read_jsonl(path: Path) -> list[dict]:
    if not path.is_file():
        return []
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        try:
            value = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict):
            rows.append(value)
    return rows


@dataclass(frozen=True)
class AdapterStatus:
    status: str
    missing_reason: str = ""
    details: dict[str, Any] | None = None

    def to_dict(self) -> dict:
        return {"status": self.status, "missing_reason": self.missing_reason, "details": self.details or {}}


def first_existing(root: Path, names: tuple[str, ...]) -> Path | None:
    for name in names:
        path = root / name
        if path.is_file():
            return path
    return None
