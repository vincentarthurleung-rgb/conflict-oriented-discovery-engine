"""SQLite cache for bounded external validation query results."""

from __future__ import annotations

import hashlib
import json
import sqlite3
from collections.abc import Iterable, Iterator
from pathlib import Path
from typing import Any

from code_engine.schemas.validation import ValidationQueryPlan


def build_validation_cache_key(
    validator_name: str, query_type: str, entities: list[dict],
    relation_family: str | None = None, polarity_type: str | None = None,
    direction: str | None = None, context: dict | None = None,
    config_fingerprint: str = "v1",
) -> str:
    canonical = sorted(str(item.get("canonical_id") or item.get("id") or item.get("name") or "") for item in entities)
    payload = {
        "validator_name": validator_name, "query_type": query_type,
        "entities": canonical, "relation_family": relation_family,
        "polarity_type": polarity_type, "direction": direction,
        "context": context or {}, "config_fingerprint": config_fingerprint,
    }
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


class ValidationQueryCache:
    def __init__(self, path: str | Path):
        self.path = Path(path)

    def is_available(self) -> bool:
        return self.path.is_file()

    def _connect(self) -> sqlite3.Connection:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self.path)
        connection.execute("CREATE TABLE IF NOT EXISTS validation_cache (cache_key TEXT NOT NULL, sequence INTEGER NOT NULL, payload TEXT NOT NULL, PRIMARY KEY(cache_key, sequence))")
        return connection

    def lookup(self, cache_key: str, max_records: int = 100) -> Iterator[dict[str, Any]]:
        if not self.path.exists():
            return
        connection = self._connect()
        try:
            cursor = connection.execute("SELECT payload FROM validation_cache WHERE cache_key=? ORDER BY sequence LIMIT ?", (cache_key, max_records))
            for row in cursor:
                yield json.loads(row[0])
        finally:
            connection.close()

    def store(self, cache_key: str, records: Iterable[Any]) -> int:
        connection = self._connect()
        count = 0
        try:
            connection.execute("DELETE FROM validation_cache WHERE cache_key=?", (cache_key,))
            for sequence, item in enumerate(records):
                if hasattr(item, "model_dump"):
                    item = item.model_dump(mode="json")
                connection.execute("INSERT INTO validation_cache(cache_key,sequence,payload) VALUES(?,?,?)", (cache_key, sequence, json.dumps(item, ensure_ascii=False, default=str)))
                count += 1
            connection.commit()
        finally:
            connection.close()
        return count

    def store_record(self, cache_key: str, sequence: int, record: Any, *, reset: bool = False) -> None:
        if hasattr(record, "model_dump"):
            record = record.model_dump(mode="json")
        connection = self._connect()
        try:
            if reset:
                connection.execute("DELETE FROM validation_cache WHERE cache_key=?", (cache_key,))
            connection.execute(
                "INSERT OR REPLACE INTO validation_cache(cache_key,sequence,payload) VALUES(?,?,?)",
                (cache_key, sequence, json.dumps(record, ensure_ascii=False, default=str)),
            )
            connection.commit()
        finally:
            connection.close()


def lookup_validation_cache(cache: ValidationQueryCache, query_plan: ValidationQueryPlan) -> Iterator[dict[str, Any]]:
    if not query_plan.cache_key:
        return iter(())
    return cache.lookup(query_plan.cache_key, query_plan.max_records)


def store_validation_cache_result(cache: ValidationQueryCache, query_plan: ValidationQueryPlan, records: Iterable[Any]) -> int:
    if not query_plan.cache_key:
        return 0
    return cache.store(query_plan.cache_key, records)


__all__ = ["ValidationQueryCache", "build_validation_cache_key", "lookup_validation_cache", "store_validation_cache_result"]
