"""Serializable graph-view model independent of a rendering library."""

from dataclasses import dataclass, field
from typing import Any


@dataclass
class GraphView:
    nodes: list[dict[str, Any]] = field(default_factory=list)
    edges: list[dict[str, Any]] = field(default_factory=list)

