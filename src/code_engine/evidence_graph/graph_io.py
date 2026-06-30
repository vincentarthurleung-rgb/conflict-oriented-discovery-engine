"""Local JSON/JSONL I/O for merged evidence graph artifacts."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterable


def load_artifact(path: Path) -> Any:
    if not path.exists():
        return []
    try:
        if path.suffix == ".jsonl":
            return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []


def records(value: Any) -> list[dict[str, Any]]:
    if isinstance(value, list):
        return [item for item in value if isinstance(item, dict)]
    if isinstance(value, dict):
        for key in ("observations", "records", "items", "evidence", "anchors", "results", "candidates"):
            if isinstance(value.get(key), list):
                return [item for item in value[key] if isinstance(item, dict)]
    return []


def write_json(path: Path, payload: Any) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return str(path)


def write_jsonl(path: Path, payload: Iterable[Any]) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    rows = (item.to_dict() if hasattr(item, "to_dict") else item for item in payload)
    path.write_text("".join(json.dumps(item, ensure_ascii=False) + "\n" for item in rows), encoding="utf-8")
    return str(path)
