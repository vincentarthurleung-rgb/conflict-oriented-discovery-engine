"""Atomic orchestration state and append-only event persistence."""
from __future__ import annotations

import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def canonical_bytes(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode()


class OrchestrationStateStore:
    def __init__(self, runs_root: Path, orchestration_id: str):
        self.root = Path(runs_root) / "_orchestration" / orchestration_id
        self.request_path = self.root / "orchestration_request.json"
        self.state_path = self.root / "orchestration_state.json"
        self.events_path = self.root / "orchestration_events.jsonl"
        self.result_path = self.root / "final_result.json"

    def read_state(self) -> dict | None:
        try:
            value = json.loads(self.state_path.read_text(encoding="utf-8"))
            return value if isinstance(value, dict) else None
        except (OSError, json.JSONDecodeError):
            return None

    def write_request(self, value: dict) -> None:
        self._atomic(self.request_path, value)

    def write_state(self, value: dict) -> None:
        value["updated_at"] = utcnow()
        self._atomic(self.state_path, value)

    def write_result(self, value: dict) -> None:
        self._atomic(self.result_path, value)

    def append_event(self, event: str, **payload: Any) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        record = canonical_bytes({"event": event, "occurred_at": utcnow(), **payload})
        fd = os.open(self.events_path, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
        try:
            os.write(fd, record); os.fsync(fd)
        finally:
            os.close(fd)

    def _atomic(self, path: Path, value: Any) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        fd, temporary = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
        try:
            with os.fdopen(fd, "wb") as handle:
                handle.write(canonical_bytes(value)); handle.flush(); os.fsync(handle.fileno())
            os.replace(temporary, path)
        finally:
            try: os.unlink(temporary)
            except FileNotFoundError: pass
