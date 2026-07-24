"""Standard orchestration boundary.

L4b comparability and divergence explanation are produced independently, then
joined only by the reference-only FactorAttributionBundle consumed at L4c.
"""

from .bundle import build_factor_attribution_bundle
from .decision.service import adjudicate_pair_staging

__all__ = ["build_factor_attribution_bundle", "adjudicate_pair_staging"]
