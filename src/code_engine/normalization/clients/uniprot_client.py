"""UniProt REST API client for protein entity resolution.

API: https://rest.uniprot.org
No API key required. Recommended ≤5 req/s.
"""

from __future__ import annotations

import time
from typing import Any

import requests

_BASE = "https://rest.uniprot.org/uniprotkb"
_LAST_CALL: float = 0.0


class UniProtClient:
    """Search protein entities via UniProt REST API."""

    name = "uniprot"
    resource = "UniProt"

    def search(self, surface: str, request: Any = None) -> list[dict[str, Any]]:
        global _LAST_CALL
        now = time.monotonic()
        since_last = now - _LAST_CALL
        if since_last < 0.25:  # ~4 req/s
            time.sleep(0.25 - since_last)
        _LAST_CALL = time.monotonic()

        try:
            resp = requests.get(
                f"{_BASE}/search",
                params={
                    "query": surface,
                    "fields": "accession,id,protein_name,gene_names,organism_name",
                    "size": 10,
                },
                headers={"Accept": "application/json"},
                timeout=10,
            )
            resp.raise_for_status()
            data = resp.json()
        except Exception:
            return []

        results: list[dict[str, Any]] = []
        for hit in data.get("results", []):
            accession = hit.get("primaryAccession", "")
            if not accession:
                continue

            protein_id = hit.get("uniProtkbId", "")
            protein_name = ""
            protein_desc = hit.get("proteinDescription", {})
            if isinstance(protein_desc, dict):
                rec_name = protein_desc.get("recommendedName", {})
                if isinstance(rec_name, dict):
                    fs = rec_name.get("fullName", {})
                    if isinstance(fs, dict):
                        protein_name = fs.get("value", "")
                    elif isinstance(fs, str):
                        protein_name = fs

            genes = hit.get("genes", [])
            gene_names = []
            for g in genes:
                gn = g.get("geneName", {})
                if isinstance(gn, dict):
                    gene_names.append(gn.get("value", ""))

            aliases = list(gene_names)
            if protein_id:
                aliases.append(protein_id)

            results.append({
                "provider_record_id": accession,
                "canonical_id": f"UniProt:{accession}",
                "canonical_name": protein_id or protein_name or surface,
                "name": protein_name or surface,
                "normalized_surface": (protein_id or surface).lower(),
                "entity_type": "protein",
                "aliases": aliases,
                "external_ids": {"UniProt": accession},
                "match_score": 0.85,
                "type_score": 0.9,
                "source_reliability": 0.9,
                "context_score": 0.5,
                "score": 0.82,
            })

        return results
