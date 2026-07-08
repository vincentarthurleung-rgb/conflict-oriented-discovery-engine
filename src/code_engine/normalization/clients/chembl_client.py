"""ChEMBL REST API client for compound/drug entity resolution.

API: https://www.ebi.ac.uk/chembl/api/data
No API key required.
"""

from __future__ import annotations

import time
from typing import Any

import requests

_BASE = "https://www.ebi.ac.uk/chembl/api/data"
_LAST_CALL: float = 0.0


class ChEMBLClient:
    """Search compound/drug entities via ChEMBL REST API."""

    name = "chembl"
    resource = "ChEMBL"
    network_call_cost = 1  # one HTTP query per search

    def search(self, surface: str, request: Any = None) -> list[dict[str, Any]]:
        global _LAST_CALL
        now = time.monotonic()
        since_last = now - _LAST_CALL
        if since_last < 0.25:
            time.sleep(0.25 - since_last)
        _LAST_CALL = time.monotonic()

        try:
            resp = requests.get(
                f"{_BASE}/molecule.json",
                params={
                    "q": surface,
                    "limit": 10,
                },
                headers={"Accept": "application/json"},
                timeout=10,
            )
            resp.raise_for_status()
            data = resp.json()
        except Exception:
            return []

        results: list[dict[str, Any]] = []
        for hit in data.get("molecules", []):
            chembl_id = hit.get("molecule_chembl_id", "")
            if not chembl_id:
                continue

            pref_name = hit.get("pref_name", "")
            synonyms_raw = hit.get("molecule_synonyms", [])
            aliases = [s.get("synonym", "") for s in synonyms_raw if isinstance(s, dict)]

            results.append({
                "provider_record_id": chembl_id,
                "canonical_id": f"ChEMBL:{chembl_id}",
                "canonical_name": pref_name or surface,
                "name": pref_name or surface,
                "normalized_surface": (pref_name or surface).lower(),
                "entity_type": "compound",
                "aliases": aliases,
                "external_ids": {"ChEMBL": chembl_id},
                "match_score": 0.8,
                "type_score": 0.85,
                "source_reliability": 0.85,
                "context_score": 0.5,
                "score": 0.78,
            })

        return results
