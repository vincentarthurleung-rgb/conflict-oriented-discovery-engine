"""Append-only reviewed entity candidate cache."""

from __future__ import annotations

import json
from pathlib import Path

from code_engine.normalization.candidates import EntityCandidate, EntityResolutionResult


class EntityCache:
    def __init__(self, root: str | Path = "data/index/entity_cache", *, accepted_writes_enabled: bool = False):
        self.root = Path(root)
        self.candidates_path = self.root / "entity_candidates.jsonl"
        self.accepted_path = self.root / "accepted_mappings.jsonl"
        self.accepted_writes_enabled = accepted_writes_enabled

    @staticmethod
    def _read(path: Path) -> list[dict]:
        if not path.exists():
            return []
        records = []
        for line in path.read_text(encoding="utf-8").splitlines():
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError:
                continue
        return records

    def lookup(self, normalized_surface: str) -> list[dict]:
        needle = normalized_surface.casefold()
        return [item for item in self._read(self.accepted_path) if str(item.get("normalized_surface", "")).casefold() == needle]

    def record_candidates(self, candidates: list[EntityCandidate]) -> None:
        if not candidates:
            return
        self.root.mkdir(parents=True, exist_ok=True)
        with self.candidates_path.open("a", encoding="utf-8") as handle:
            for item in candidates:
                handle.write(item.model_dump_json() + "\n")

    def record_accepted(self, result: EntityResolutionResult) -> bool:
        if not self.accepted_writes_enabled or result.normalization_status not in {"resolved_curated", "resolved_external_grounded", "accepted_external_grounded"} or not result.selected_candidate:
            return False
        self.root.mkdir(parents=True, exist_ok=True)
        payload = {**result.selected_candidate.model_dump(), "normalization_status": result.normalization_status, "confidence": result.confidence}
        with self.accepted_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, ensure_ascii=False) + "\n")
        return True
