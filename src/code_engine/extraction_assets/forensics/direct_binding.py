"""Direct evidence adapters."""
from __future__ import annotations


def direct_identity_evidence(left: dict, right: dict) -> list[dict[str, str]]:
    evidence = []
    for field, kind in (
        ("provider_request_id", "provider_request_id_exact"),
        ("provider_response_id", "provider_response_id_exact"),
        ("raw_response_sha256", "raw_sha256_reference_exact"),
        ("call_dedup_identity", "call_dedup_identity_exact"),
    ):
        if left.get(field) and left.get(field) == right.get(field):
            evidence.append({"type": kind, "field": field, "value": str(left[field])})
    return evidence

