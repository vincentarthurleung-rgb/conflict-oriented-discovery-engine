"""PubChem PUG REST client for compound entity resolution.

API: https://pubchem.ncbi.nlm.nih.gov/rest/pug
No API key required. Recommended ≤5 req/s.
"""

from __future__ import annotations

import time
from typing import Any

import requests

_BASE = "https://pubchem.ncbi.nlm.nih.gov/rest/pug"
_LAST_CALL: float = 0.0


class PubChemClient:
    """Search compound entities via PubChem PUG REST."""

    name = "pubchem"
    resource = "PubChem"
    network_call_cost = 2  # name→CID + CID→details (two HTTP calls per search)

    def search(self, surface: str, request: Any = None) -> list[dict[str, Any]]:
        global _LAST_CALL
        now = time.monotonic()
        since_last = now - _LAST_CALL
        if since_last < 0.25:
            time.sleep(0.25 - since_last)
        _LAST_CALL = time.monotonic()

        # Step 1: name → CID
        try:
            resp = requests.get(
                f"{_BASE}/compound/name/{requests.utils.quote(surface)}/cids/JSON",
                timeout=10,
            )
            if resp.status_code != 200:
                return []
            cid_data = resp.json()
        except Exception:
            return []

        cid_list = cid_data.get("IdentifierList", {}).get("CID", [])
        if not cid_list:
            return []
        cids = cid_list[:5]

        # Step 2: CID → details
        cid_str = ",".join(str(c) for c in cids)
        try:
            det_resp = requests.get(
                f"{_BASE}/compound/cid/{cid_str}/JSON",
                params={"record_type": "2d"},
                timeout=10,
            )
            det_resp.raise_for_status()
            det_data = det_resp.json()
        except Exception:
            return []

        results: list[dict[str, Any]] = []
        pc_comps = det_data.get("PC_Compounds", [])
        for comp in pc_comps:
            cid = comp.get("id", {}).get("id", {}).get("cid", "")
            if not cid:
                continue

            # Extract name
            name = ""
            synonyms = []
            props = comp.get("props", [])
            for p in props:
                urn_label = (p.get("urn", {}) or {}).get("label", "")
                if urn_label == "IUPAC Name":
                    name = (p.get("value", {}) or {}).get("sval", "")
                elif urn_label == "Molecular Formula":
                    if not name:
                        name = (p.get("value", {}) or {}).get("sval", "")

            results.append({
                "provider_record_id": str(cid),
                "canonical_id": f"PubChem:{cid}",
                "canonical_name": name or surface,
                "name": name or surface,
                "normalized_surface": surface.lower(),
                "entity_type": "compound",
                "aliases": synonyms,
                "external_ids": {"PubChem": str(cid)},
                "match_score": 0.8,
                "type_score": 0.85,
                "source_reliability": 0.9,
                "context_score": 0.5,
                "score": 0.8,
            })

        return results
