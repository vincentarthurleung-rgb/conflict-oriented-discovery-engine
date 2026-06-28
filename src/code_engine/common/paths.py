"""Central project-path helpers for CLI and compatibility entrypoints."""

from __future__ import annotations

from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[3]


def resolve_project_path(path: str | Path) -> Path:
    """Resolve a repository-relative path without changing process cwd."""

    candidate = Path(path)
    return candidate if candidate.is_absolute() else PROJECT_ROOT / candidate

