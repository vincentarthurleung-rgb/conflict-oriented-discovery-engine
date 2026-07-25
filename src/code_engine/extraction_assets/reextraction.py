"""Read-only, block-deduplicated selective re-extraction planning."""
from __future__ import annotations

from collections import defaultdict
from typing import Any

from .identities import stable_identity


def deduplicate_by_block(needs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    groups: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for need in needs:
        groups[(str(need["source_snapshot_identity"]), str(need["block_id"]))].append(need)
    output: list[dict[str, Any]] = []
    for (snapshot, block), rows in sorted(groups.items()):
        observations = sorted({str(item) for row in rows for item in row.get("observation_candidate_ids", [])})
        fields = sorted({str(item) for row in rows for item in row.get("missing_capture_profile_fields", [])})
        dedup = stable_identity("selective_reextraction_group_v1", {
            "source_snapshot_identity": snapshot, "block_id": block,
        })
        output.append({
            "source_snapshot_identity": snapshot,
            "block_id": block,
            "observation_candidate_ids": observations,
            "missing_capture_profile_fields": fields,
            "dedup_group_identity": dedup,
            "minimal_block_set": [block],
            "estimated_call_count": 1,
            "automatic_execution_authorized": False,
            "provider_call_authorized": False,
            "network_call_authorized": False,
            "budget_authorization_present": False,
            "historical_payload_mutation_authorized": False,
        })
    return output
