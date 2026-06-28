"""Dependency-light utilities shared across package boundaries."""

from code_engine.common.paths import PROJECT_ROOT, resolve_project_path
from code_engine.common.runtime import ensure_source_allowed, is_legacy_source

__all__ = ["PROJECT_ROOT", "resolve_project_path", "ensure_source_allowed", "is_legacy_source"]
