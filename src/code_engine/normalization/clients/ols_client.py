"""EMBL-EBI OLS4 client for ontology-backed entity candidates.

Public API: https://www.ebi.ac.uk/ols4/api-docs
"""

from __future__ import annotations

import time
from typing import Any

from code_engine.normalization.clients.http import get_json

_BASE = "https://www.ebi.ac.uk/ols4/api/search"
_LAST_CALL: float = 0.0


class OLSClient:
    """Search ontology terms through EMBL-EBI OLS4."""

    name = "ols"
    resource = "OLS"
    network_call_cost = 1

    def search(self, surface: str, request: Any = None, *, ontologies: list[str] | None = None) -> list[dict[str, Any]]:
        global _LAST_CALL
        now = time.monotonic()
        since_last = now - _LAST_CALL
        if since_last < 0.2:
            time.sleep(0.2 - since_last)
        _LAST_CALL = time.monotonic()

        params: dict[str, Any] = {
            "q": surface,
            "rows": 10,
            "exact": "true",
        }
        if ontologies:
            params["ontology"] = ",".join(ontologies)
        status_code, data = get_json(_BASE, params=params)
        if status_code != 200:
            return []
        docs = ((data.get("response") or {}).get("docs") or [])
        return [item for item in docs if item.get("obo_id") and item.get("label")]
