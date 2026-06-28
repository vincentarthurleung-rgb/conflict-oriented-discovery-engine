"""MechanismGraph JSON persistence."""

from __future__ import annotations

import json
from pathlib import Path

from code_engine.mechanism.models import MechanismGraph


def save_mechanism_graph(graph: MechanismGraph, path: str | Path) -> Path:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_suffix(target.suffix + ".tmp")
    temporary.write_text(graph.model_dump_json(indent=2), encoding="utf-8")
    temporary.replace(target)
    return target


def load_mechanism_graph(path: str | Path) -> MechanismGraph:
    return MechanismGraph.model_validate(json.loads(Path(path).read_text(encoding="utf-8")))
