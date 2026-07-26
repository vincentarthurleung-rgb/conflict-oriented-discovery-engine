"""Deterministic, stratified annotation pilot selection (selection only)."""
from __future__ import annotations

from collections import defaultdict
from typing import Any

from .identities import core_identity


def select_annotation_pilot(
    targets: list[dict[str, Any]], *, per_task_difficulty: int = 2
) -> dict[str, Any]:
    buckets: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for target in targets:
        buckets[(target["task_type"], target["expected_difficulty"])].append(target)
    selections = []
    used_documents: set[str] = set()
    for key in sorted(buckets):
        ranked = sorted(
            buckets[key],
            key=lambda row: (
                row["observation_identity"] in used_documents,
                row["observation_identity"], row["identity"],
            ),
        )
        for row in ranked[:per_task_difficulty]:
            used_documents.add(row["observation_identity"])
            selections.append({
                "annotation_target_identity": row["identity"],
                "task_type": row["task_type"],
                "difficulty": row["expected_difficulty"],
                "selection_reason": f"deterministic_{row['task_type']}_{row['expected_difficulty']}_coverage",
                "annotation_executed": False,
            })
    payload = {
        "selections": selections,
        "selection_rule": "task_then_difficulty_then_document_then_identity_v1",
        "per_task_difficulty_limit": per_task_difficulty,
        "human_annotations_executed": 0,
        "human_gold_created": False,
        "schema_version": "experimental_annotation_pilot_selection_v1",
    }
    payload["identity"] = core_identity("experimental_annotation_pilot_selection_v1", payload)
    return payload
