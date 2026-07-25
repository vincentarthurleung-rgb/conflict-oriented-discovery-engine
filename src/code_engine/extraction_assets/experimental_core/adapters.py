"""Current-schema adapters; no Provider, network, or conflict imports."""
from __future__ import annotations

from typing import Any

from .factors import explicit_factor_candidates
from .measurements import explicit_measurement_candidates
from .results import explicit_result_candidates


def adapt_explicit_core(source: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    return {
        "factors": explicit_factor_candidates(source),
        "measurements": explicit_measurement_candidates(source),
        "results": explicit_result_candidates(source),
    }

