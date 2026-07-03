"""JSONL and SQLite persistence for derived KG records."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any, Iterable


class KGStore:
    def __init__(self, root: str | Path):
        self.root = Path(root)

    def write(self, nodes: Iterable[dict], edges: Iterable[dict], evidence: Iterable[dict], warnings: Iterable[dict]) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        nodes, edges, evidence, warnings = list(nodes), list(edges), list(evidence), list(warnings)
        self._jsonl("kg_nodes.jsonl", nodes)
        self._jsonl("kg_edges.jsonl", edges)
        self._jsonl("kg_evidence.jsonl", evidence)
        self._jsonl("kg_build_warnings.jsonl", warnings)
        database = self.root / "kg_index.sqlite"
        connection = sqlite3.connect(database)
        try:
            connection.executescript("DROP TABLE IF EXISTS nodes; DROP TABLE IF EXISTS edges; DROP TABLE IF EXISTS evidence; CREATE TABLE nodes (id TEXT PRIMARY KEY, type TEXT, label TEXT, data TEXT NOT NULL); CREATE TABLE edges (id TEXT PRIMARY KEY, source TEXT, target TEXT, predicate TEXT, case_id TEXT, data TEXT NOT NULL); CREATE TABLE evidence (id TEXT PRIMARY KEY, data TEXT NOT NULL); CREATE INDEX edge_source_idx ON edges(source); CREATE INDEX edge_target_idx ON edges(target); CREATE INDEX edge_case_idx ON edges(case_id);")
            connection.executemany("INSERT INTO nodes VALUES (?, ?, ?, ?)", ((item["id"], item["type"], item["label"], json.dumps(item, ensure_ascii=False)) for item in nodes))
            connection.executemany("INSERT INTO edges VALUES (?, ?, ?, ?, ?, ?)", ((item["id"], item["source"], item["target"], item["predicate"], item.get("case_id"), json.dumps(item, ensure_ascii=False)) for item in edges))
            connection.executemany("INSERT INTO evidence VALUES (?, ?)", ((item["id"], json.dumps(item, ensure_ascii=False)) for item in evidence))
            connection.commit()
        finally:
            connection.close()

    def load(self) -> tuple[list[dict], list[dict], list[dict]]:
        return tuple(self._read_jsonl(name) for name in ("kg_nodes.jsonl", "kg_edges.jsonl", "kg_evidence.jsonl"))  # type: ignore[return-value]

    def get_evidence(self, evidence_id: str) -> dict[str, Any] | None:
        database = self.root / "kg_index.sqlite"
        if database.is_file():
            connection = sqlite3.connect(database)
            try:
                row = connection.execute("SELECT data FROM evidence WHERE id = ?", (evidence_id,)).fetchone()
            finally:
                connection.close()
            return json.loads(row[0]) if row else None
        return next((item for item in self._read_jsonl("kg_evidence.jsonl") if item["id"] == evidence_id), None)

    def _jsonl(self, name: str, items: Iterable[dict]) -> None:
        text = "".join(json.dumps(item, ensure_ascii=False) + "\n" for item in items)
        (self.root / name).write_text(text, encoding="utf-8")

    def _read_jsonl(self, name: str) -> list[dict]:
        path = self.root / name
        if not path.is_file():
            return []
        return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
