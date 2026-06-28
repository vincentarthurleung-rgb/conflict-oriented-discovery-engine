"""Streaming local-index adapters for resource-aware validation."""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterable, Iterator
from pathlib import Path
from typing import Any

from code_engine.schemas.validation import ValidationQueryPlan


IDENTITY_COLUMNS = (
    "canonical_id", "entity_id", "gene_symbol", "target_id", "target_gene",
    "target_name", "compound_id", "compound_name", "perturbagen_id",
    "perturbagen_name", "protein_id", "pathway_id", "disease_id",
)


def safe_json_dump(payload: Any) -> str:
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":"), default=str)


def stream_jsonl_records(path: str | Path, *, max_records: int | None = None) -> Iterator[dict[str, Any]]:
    source = Path(path)
    if not source.exists():
        return
    emitted = 0
    with source.open("r", encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            yield json.loads(line)
            emitted += 1
            if max_records is not None and emitted >= max_records:
                break


def write_jsonl_stream(records: Iterable[Any], path: str | Path) -> int:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    with target.open("w", encoding="utf-8") as handle:
        for item in records:
            if hasattr(item, "model_dump"):
                item = item.model_dump(mode="json")
            handle.write(safe_json_dump(item) + "\n")
            count += 1
    return count


def open_duckdb_readonly(path: str | Path):
    try:
        import duckdb
    except ImportError as exc:
        raise RuntimeError("DuckDB support is optional and not installed") from exc
    return duckdb.connect(str(path), read_only=True)


def query_parquet_with_duckdb(
    path: str | Path, query_plan: ValidationQueryPlan,
) -> Iterator[dict[str, Any]]:
    try:
        import duckdb
    except ImportError as exc:
        raise RuntimeError("DuckDB is required for indexed Parquet validation queries") from exc
    entities = _query_terms(query_plan)
    if not entities:
        raise ValueError("Broad Parquet scan is not allowed")
    connection = duckdb.connect(":memory:")
    try:
        columns = [row[0] for row in connection.execute("DESCRIBE SELECT * FROM read_parquet(?)", [str(path)]).fetchall()]
        filters = [column for column in IDENTITY_COLUMNS if column in columns]
        if not filters:
            raise ValueError("Parquet index has no supported identity columns")
        where = " OR ".join(f"lower(cast({column} as varchar)) = ?" for column in filters)
        params = [term.casefold() for _ in filters for term in entities]
        if len(entities) > 1:
            where = " OR ".join(f"lower(cast({column} as varchar)) IN ({','.join('?' for _ in entities)})" for column in filters)
        cursor = connection.execute(f"SELECT * FROM read_parquet(?) WHERE {where} LIMIT ?", [str(path), *params, query_plan.max_records])
        names = [item[0] for item in cursor.description]
        while True:
            rows = cursor.fetchmany(100)
            if not rows:
                break
            for row in rows:
                yield dict(zip(names, row))
    finally:
        connection.close()


def _query_terms(plan: ValidationQueryPlan) -> list[str]:
    return list(dict.fromkeys(
        str(value).strip()
        for entity in plan.query_entities
        for value in (entity.get("canonical_id"), entity.get("id"), entity.get("name"), entity.get("canonical_name"))
        if value
    ))


class ValidationLocalIndex:
    def __init__(self, name: str, validator_name: str, index_type: str, path: str | Path):
        self.name = name
        self.validator_name = validator_name
        self.index_type = index_type
        self.path = Path(path)

    def is_available(self) -> bool:
        return self.path.is_file()

    def estimate_query(self, query_plan: ValidationQueryPlan) -> dict:
        if not self.is_available():
            return {"status": "no_index", "estimated_records": 0, "estimated_memory_mb": 0.0}
        size_mb = self.path.stat().st_size / (1024 * 1024)
        return {
            "status": "estimated",
            "estimated_records": min(query_plan.max_records, max(1, int(size_mb * 100))),
            "estimated_memory_mb": min(size_mb, 64.0),
            "estimated_output_bytes": min(self.path.stat().st_size, query_plan.max_raw_payload_bytes),
            "estimated_query_seconds": min(30.0, 0.1 + size_mb / 100),
        }

    def stream_query(self, query_plan: ValidationQueryPlan) -> Iterator[dict[str, Any]]:
        if not self.is_available():
            return
        kind = self.index_type.casefold()
        if kind == "jsonl":
            terms = {item.casefold() for item in _query_terms(query_plan)}
            if not terms:
                raise ValueError("Broad JSONL scan is not allowed")
            emitted = 0
            for item in stream_jsonl_records(self.path):
                values = {str(item.get(column, "")).casefold() for column in IDENTITY_COLUMNS}
                if terms.intersection(values):
                    yield item
                    emitted += 1
                    if emitted >= query_plan.max_records:
                        break
        elif kind in {"sqlite", "db"}:
            yield from self._stream_sqlite(query_plan)
        elif kind == "parquet":
            yield from query_parquet_with_duckdb(self.path, query_plan)
        elif kind == "duckdb":
            yield from self._stream_duckdb(query_plan)
        else:
            raise ValueError(f"Unsupported validation index type: {self.index_type}")

    def _stream_sqlite(self, plan: ValidationQueryPlan) -> Iterator[dict[str, Any]]:
        terms = _query_terms(plan)
        if not terms:
            raise ValueError("Broad SQLite scan is not allowed")
        connection = sqlite3.connect(f"file:{self.path}?mode=ro", uri=True)
        connection.row_factory = sqlite3.Row
        try:
            table = str(plan.query_context.get("table") or "records")
            if not table.replace("_", "").isalnum():
                raise ValueError("Invalid SQLite table name")
            columns = [row[1] for row in connection.execute(f"PRAGMA table_info({table})")]
            filters = [item for item in IDENTITY_COLUMNS if item in columns]
            if not filters:
                raise ValueError("SQLite index has no supported identity columns")
            clauses = [f"lower(cast({column} as text)) IN ({','.join('?' for _ in terms)})" for column in filters]
            params = [term.casefold() for _ in filters for term in terms]
            cursor = connection.execute(f"SELECT * FROM {table} WHERE {' OR '.join(clauses)} LIMIT ?", [*params, plan.max_records])
            for row in cursor:
                yield dict(row)
        finally:
            connection.close()

    def _stream_duckdb(self, plan: ValidationQueryPlan) -> Iterator[dict[str, Any]]:
        connection = open_duckdb_readonly(self.path)
        try:
            table = str(plan.query_context.get("table") or "records")
            if not table.replace("_", "").isalnum():
                raise ValueError("Invalid DuckDB table name")
            terms = _query_terms(plan)
            if not terms:
                raise ValueError("Broad DuckDB scan is not allowed")
            columns = [row[0] for row in connection.execute(f"DESCRIBE {table}").fetchall()]
            filters = [item for item in IDENTITY_COLUMNS if item in columns]
            where = " OR ".join(f"lower(cast({column} as varchar)) IN ({','.join('?' for _ in terms)})" for column in filters)
            params = [term.casefold() for _ in filters for term in terms]
            cursor = connection.execute(f"SELECT * FROM {table} WHERE {where} LIMIT ?", [*params, plan.max_records])
            names = [item[0] for item in cursor.description]
            for row in cursor.fetchall():
                yield dict(zip(names, row))
        finally:
            connection.close()


__all__ = ["ValidationLocalIndex", "open_duckdb_readonly", "query_parquet_with_duckdb", "stream_jsonl_records", "write_jsonl_stream", "safe_json_dump"]
