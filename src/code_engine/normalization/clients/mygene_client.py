"""MyGene.info client for gene entity resolution.

API: https://mygene.info/v3/api
No API key required. Rate limit: ~1000 req/s.
"""

from __future__ import annotations

import time
from typing import Any

import requests

_BASE = "https://mygene.info/v3"
_LAST_CALL: float = 0.0


class MyGeneClient:
    """Search gene entities via MyGene.info (Entrez Gene)."""

    name = "mygene"
    resource = "EntrezGene"
    network_call_cost = 1  # one HTTP query per search

    def search(self, surface: str, request: Any = None) -> list[dict[str, Any]]:
        """Search for a gene term, return normalized candidate records."""
        global _LAST_CALL
        now = time.monotonic()
        since_last = now - _LAST_CALL
        if since_last < 0.3:  # ~3 req/s max (conservative for batch)
            time.sleep(0.3 - since_last)
        _LAST_CALL = time.monotonic()

        try:
            resp = requests.get(
                f"{_BASE}/query",
                params={
                    "q": surface,
                    "fields": "symbol,name,alias,entrezgene,uniprot,type_of_gene",
                    "species": "human",
                    "size": 10,
                },
                timeout=10,
            )
            resp.raise_for_status()
            data = resp.json()
        except Exception:
            return []

        results: list[dict[str, Any]] = []
        for hit in data.get("hits", []):
            gene_id = str(hit.get("entrezgene") or hit.get("_id", ""))
            if not gene_id:
                continue
            symbol = hit.get("symbol", "")
            name = hit.get("name", "")
            aliases = hit.get("alias", [])
            if isinstance(aliases, str):
                aliases = [aliases]

            uniprot = hit.get("uniprot", {})
            if isinstance(uniprot, dict):
                uniprot_id = uniprot.get("Swiss-Prot") or uniprot.get("TrEMBL")
            else:
                uniprot_id = None

            external_ids = {"EntrezGene": gene_id}
            if uniprot_id:
                external_ids["UniProt"] = uniprot_id

            results.append({
                "provider_record_id": gene_id,
                "canonical_id": f"EntrezGene:{gene_id}",
                "canonical_name": symbol or name,
                "name": name,
                "normalized_surface": symbol.lower() if symbol else surface.lower(),
                "entity_type": "gene",
                "aliases": aliases,
                "external_ids": external_ids,
                "match_score": 0.85,
                "type_score": 0.9,
                "source_reliability": 0.9,
                "context_score": 0.5,
                "score": 0.85,
            })

        return results
