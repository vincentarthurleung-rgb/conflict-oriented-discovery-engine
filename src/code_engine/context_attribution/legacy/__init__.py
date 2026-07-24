"""Read-only legacy artifact support; never a new runtime authority."""

from .pair_attribution_v3 import read_legacy_pair_attribution

__all__ = ["read_legacy_pair_attribution"]
