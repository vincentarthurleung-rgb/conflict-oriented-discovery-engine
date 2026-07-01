"""Context annotations for guarded search queries; never an acquisition hard filter."""

from __future__ import annotations

import re
from typing import Any


CONTEXT_ALIAS_GROUPS = {
    "cancer": ("cancer", "tumor", "tumour", "neoplasm", "carcinoma", "oncology", "malignancy",
               "hcc", "hepatocellular carcinoma", "liver cancer", "cancer cell", "tumor cell"),
    "depression": ("depression", "depressive", "mdd", "major depressive disorder"),
    "hypoxia": ("hypoxia", "hypoxic"),
    "alzheimer": ("alzheimer", "alzheimer's", "ad dementia"),
}


def expand_context_terms(terms: list[str]) -> list[str]:
    expanded: list[str] = []
    for raw in terms:
        term = str(raw).strip()
        if not term:
            continue
        group = next((aliases for key, aliases in CONTEXT_ALIAS_GROUPS.items()
                      if key in term.casefold() or any(alias in term.casefold() for alias in aliases)), (term,))
        expanded.extend(group)
    return list(dict.fromkeys(expanded))


def annotate_query_context(item: dict[str, Any], *, context_terms: list[str]) -> dict[str, Any]:
    row = dict(item); query = str(row.get("query") or row.get("query_string") or "")
    aliases = expand_context_terms(context_terms)
    matched = [term for term in aliases if re.search(r"(?<!\w)" + re.escape(term.casefold()) + r"(?!\w)", query.casefold())]
    context_specific = bool(aliases)
    strict = bool(context_specific and matched)
    row.update({
        "passed_context_guard": strict if context_specific else True,
        "context_strict": strict,
        "allowed_for_context_specific_core": strict if context_specific else True,
        "context_terms_required": aliases,
        "context_terms_matched": matched,
        "context_guard_reason": "context_term_present" if strict else ("context_not_required" if not context_specific else "seed_mechanism_query_context_optional"),
        "query_scope": "context_specific" if strict else ("general" if not context_specific else "cross_context_mechanism"),
    })
    return row


__all__ = ["CONTEXT_ALIAS_GROUPS", "annotate_query_context", "expand_context_terms"]
