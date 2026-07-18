"""Versioned read-only adapters for System A artifacts."""

from .abstract_l2_projection import ADAPTER_VERSION as ABSTRACT_L2_ADAPTER_VERSION, AbstractL2ProjectionAdapter
from .fulltext_reentry_v5 import ADAPTER_VERSION, FulltextReentryV5Adapter

__all__ = ["ADAPTER_VERSION", "FulltextReentryV5Adapter", "ABSTRACT_L2_ADAPTER_VERSION", "AbstractL2ProjectionAdapter"]
