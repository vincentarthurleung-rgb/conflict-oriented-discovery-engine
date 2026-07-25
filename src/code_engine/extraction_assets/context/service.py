"""Offline orchestration facade for experimental context assets."""
from __future__ import annotations

from .consolidation import resolve_field
from .migration import migrated_semantic_authority
from .propagation import propagate


class ExperimentalContextAssetService:
    propagate = staticmethod(propagate)
    consolidate_field = staticmethod(resolve_field)
    migrated_semantic_authority = staticmethod(migrated_semantic_authority)
