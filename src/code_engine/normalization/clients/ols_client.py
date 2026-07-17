"""EMBL-EBI OLS4 client for ontology-backed entity candidates.

Public API: https://www.ebi.ac.uk/ols4/api-docs
"""

from __future__ import annotations

import time
from typing import Any

import requests

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
        try:
            resp = requests.get(_BASE, params=params, timeout=12)
            resp.raise_for_status()
            data = resp.json()
        except Exception:
            return []
        docs = ((data.get("response") or {}).get("docs") or [])
        return [item for item in docs if item.get("obo_id") and item.get("label")]

