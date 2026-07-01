"""Conservative seed-alignment guard for discovery L1 acquisition queries."""

from __future__ import annotations

import re
from typing import Any


def _contains(query: str, aliases: list[str]) -> bool:
    text = query.casefold()
    return any(re.search(r"(?<!\w)" + re.escape(alias.casefold()) + r"(?!\w)", text) for alias in aliases if alias.strip())


def guard_search_queries(queries: list[dict[str, Any]], *, subject_aliases: list[str],
                         object_aliases: list[str]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    allowed, removed = [], []
    context_removed = broad_removed = off_seed = 0
    for item in queries:
        row = dict(item); query = str(row.get("query") or row.get("query_string") or "")
        group = str(row.get("query_group") or row.get("purpose") or "direct_relation")
        has_subject, has_object = _contains(query, subject_aliases), _contains(query, object_aliases)
        reason = None
        if group in {"context_only", "broad_recall", "validation_only"} or not row.get("allowed_for_l1_acquisition", False):
            reason = f"{group}_query_not_allowed_for_l1_acquisition"
            context_removed += int(group == "context_only"); broad_removed += int(group == "broad_recall")
        elif not has_subject:
            reason = "seed_subject_missing_or_object_only_query"
            off_seed += 1
        elif group == "direct_relation" and not has_object:
            reason = "seed_object_missing_from_direct_relation_query"
            off_seed += 1
        elif group == "mechanism" and not has_object:
            reason = "seed_object_or_mechanism_alias_missing"
            off_seed += 1
        row.update({"seed_subject_required": True, "seed_object_required": group in {"direct_relation", "mechanism"},
                    "passed_query_guard": reason is None})
        if reason:
            removed.append({"query": query, "query_group": group, "reason": reason})
        else:
            allowed.append(row)
    report = {"total_queries_before_guard": len(queries), "allowed_l1_acquisition_queries": len(allowed),
              "removed_queries": removed, "off_seed_queries_removed": off_seed,
              "context_only_queries_removed": context_removed, "broad_recall_queries_removed": broad_removed}
    return allowed, report


__all__ = ["guard_search_queries"]
