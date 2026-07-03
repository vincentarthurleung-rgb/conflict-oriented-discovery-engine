"""Build case-independent inputs consumed by external validators."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Iterable


ENTITY_KEYS = ("entities", "entity_names", "mechanism_areas")
TYPE_FIELDS = {
    "gene": "genes", "protein": "genes", "drug": "drugs", "compound": "drugs",
    "disease": "diseases", "pathway": "pathways", "context": "contexts",
}


def _read(path: str | Path | None, default: Any) -> Any:
    if not path or not Path(path).is_file():
        return default
    value = Path(path).read_text(encoding="utf-8")
    if Path(path).suffix == ".jsonl":
        return [json.loads(line) for line in value.splitlines() if line.strip()]
    return json.loads(value)


def _values(value: Any) -> list[Any]:
    if value is None:
        return []
    return value if isinstance(value, list) else [value]


def _text(value: Any) -> str | None:
    if isinstance(value, str):
        return value.strip() or None
    if isinstance(value, dict):
        for key in ("canonical_name", "name", "label", "text", "title", "id"):
            if value.get(key):
                return str(value[key]).strip()
    return None


def _add(target: list[str], values: Iterable[Any]) -> None:
    known = {item.casefold() for item in target}
    for value in values:
        item = _text(value)
        if item and item.casefold() not in known:
            target.append(item)
            known.add(item.casefold())


def _year(profile: dict[str, Any], plan: dict[str, Any]) -> dict[str, int | None]:
    window = profile.get("time_window") or plan.get("time_window") or {}
    queries = plan.get("queries") or plan.get("query_groups") or []
    if isinstance(queries, dict):
        queries = [item for group in queries.values() for item in _values(group)]
    years_from = [int(item[k]) for item in queries if isinstance(item, dict) for k in ("year_from", "paper_year_from") if item.get(k)]
    years_to = [int(item[k]) for item in queries if isinstance(item, dict) for k in ("year_to", "paper_year_to") if item.get(k)]
    discovery_from = window.get("discovery_from") or (min(years_from) if years_from else None)
    discovery_to = window.get("discovery_to") or (max(years_to) if years_to else None)
    post = window.get("post_cutoff_from") or (int(discovery_to) + 1 if discovery_to is not None else None)
    return {"discovery_from": discovery_from, "discovery_to": discovery_to, "post_cutoff_from": post}


def build_validator_input(
    case_profile: dict[str, Any] | str | Path, *, search_plan: dict[str, Any] | str | Path | None = None,
    core_observations: list[dict[str, Any]] | str | Path | None = None,
    hypothesis_summary: dict[str, Any] | str | Path | None = None,
    kg_nodes: list[dict[str, Any]] | str | Path | None = None,
    mechanism_graph: dict[str, Any] | str | Path | None = None,
) -> dict[str, Any]:
    """Merge validator inputs in profile-to-derived-artifact priority order."""
    profile = _read(case_profile, {}) if not isinstance(case_profile, dict) else case_profile
    plan = _read(search_plan, {}) if not isinstance(search_plan, dict) else search_plan
    observations = _read(core_observations, []) if not isinstance(core_observations, list) else core_observations
    hypotheses_raw = _read(hypothesis_summary, {}) if not isinstance(hypothesis_summary, dict) else hypothesis_summary
    nodes = _read(kg_nodes, []) if not isinstance(kg_nodes, list) else kg_nodes
    graph = _read(mechanism_graph, {}) if not isinstance(mechanism_graph, dict) else mechanism_graph
    output: dict[str, Any] = {
        "case_id": profile.get("case_id") or plan.get("case_id"), "case_type": profile.get("case_type"),
        "domain_tags": list(profile.get("domain_tags") or []),
        "validation_needs": list(profile.get("validation_needs") or []),
        "entities": [], "genes": [], "drugs": [], "diseases": [], "pathways": [], "contexts": [],
        "hypotheses": [], "conflict_candidates": [], "search_terms": [],
        "time_window": _year(profile, plan),
    }
    for key in ENTITY_KEYS:
        _add(output["entities"], _values(profile.get(key)))
    for field, target in (("disease_areas", "diseases"), ("mechanism_areas", "pathways")):
        _add(output[target], _values(profile.get(field)))
    _add(output["search_terms"], [profile.get("query")])
    for query in _values(plan.get("queries")):
        if isinstance(query, dict):
            _add(output["search_terms"], [query.get("query_string") or query.get("query")])
    hypothesis_items = hypotheses_raw.get("hypotheses", hypotheses_raw.get("candidates", []))
    for item in _values(hypothesis_items):
        text = _text(item) or (item.get("hypothesis_text") if isinstance(item, dict) else None)
        _add(output["hypotheses"], [text])
        if isinstance(item, dict):
            _add(output["entities"], _values(item.get("entities")))
    for record in list(observations or []):
        if not isinstance(record, dict):
            continue
        for prefix in ("subject", "object"):
            name = record.get(f"{prefix}_canonical_name") or record.get(f"{prefix}_raw") or record.get(prefix)
            _add(output["entities"], [name])
            kind = str(record.get(f"{prefix}_entity_type") or "").lower()
            if kind in TYPE_FIELDS:
                _add(output[TYPE_FIELDS[kind]], [name])
        _add(output["contexts"], _values(record.get("contexts") or record.get("context")))
        if record.get("conflict_candidate") or record.get("conflict_status") in {"conflict", "near_conflict"}:
            output["conflict_candidates"].append(record)
    for node in list(nodes or []) + list(graph.get("nodes") or []):
        if not isinstance(node, dict):
            continue
        name = _text(node)
        kind = str(node.get("type") or node.get("node_type") or node.get("entity_type") or "").lower()
        _add(output["entities"], [name])
        if kind in TYPE_FIELDS:
            _add(output[TYPE_FIELDS[kind]], [name])
    # Explicit typed profile fields have the highest-confidence classification.
    for source, target in (("genes", "genes"), ("drugs", "drugs"), ("diseases", "diseases"), ("pathways", "pathways"), ("contexts", "contexts")):
        _add(output[target], _values(profile.get(source)))
    return output


def enrichr_input(value: dict[str, Any], minimum_gene_count: int = 2) -> dict[str, Any]:
    genes = list(value.get("genes") or [])
    if not genes:
        return {"status": "skipped_no_gene_set", "genes": []}
    if len(genes) < minimum_gene_count:
        return {"status": "gene_set_too_small", "genes": genes}
    return {"status": "ready", "genes": genes}


def reactome_input(value: dict[str, Any]) -> dict[str, Any]:
    terms = list(dict.fromkeys((value.get("pathways") or []) + (value.get("genes") or []) + (value.get("entities") or [])))
    return {"status": "ready" if terms else "skipped_no_entities", "terms": terms}


def pubmed_post_cutoff_input(value: dict[str, Any]) -> dict[str, Any]:
    terms = list(dict.fromkeys((value.get("search_terms") or []) + (value.get("entities") or []) + (value.get("hypotheses") or [])))
    cutoff = (value.get("time_window") or {}).get("post_cutoff_from")
    query = " OR ".join(f'"{re.sub(chr(34), "", term)}"' for term in terms if term)
    if cutoff:
        query = f"({query}) AND ({cutoff}:3000[dp])" if query else f"{cutoff}:3000[dp]"
    return {"status": "ready" if query else "skipped_no_search_terms", "query": query, "post_cutoff_from": cutoff}


__all__ = ["build_validator_input", "enrichr_input", "reactome_input", "pubmed_post_cutoff_input"]
