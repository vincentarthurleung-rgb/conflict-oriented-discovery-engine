"""Export renderer-neutral graph views as JSON."""

from dataclasses import asdict
from pathlib import Path

from code_engine.common.json_io import write_json
from code_engine.visualization.graph_models import GraphView


def export_graph_json(view: GraphView, path: str | Path) -> None:
    write_json(path, asdict(view))

