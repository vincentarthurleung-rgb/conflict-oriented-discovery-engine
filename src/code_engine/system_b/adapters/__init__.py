"""Versioned read-only adapters for System A artifacts."""

from .fulltext_reentry_v5 import ADAPTER_VERSION, FulltextReentryV5Adapter

__all__ = ["ADAPTER_VERSION", "FulltextReentryV5Adapter"]
