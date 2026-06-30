"""Conflict-gated full-text availability and acquisition."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable

from code_engine.corpus.io import atomic_write_json, atomic_write_jsonl


AvailabilityResolver = Callable[[dict[str, Any]], dict[str, Any]]


def build_fulltext_escalation_candidates(
    abstract_conflicts: list[dict[str, Any]], graph_conflicts: list[dict[str, Any]],
    relation_bundles: list[dict[str, Any]], papers: list[dict[str, Any]],
    *, triple_id: str = "", query_hash: str = "",
) -> list[dict[str, Any]]:
    paper_index: dict[str, dict[str, Any]] = {}
    for paper in papers:
        for key in (paper.get("paper_id"), paper.get("canonical_paper_id"), paper.get("pmid"), paper.get("pmcid")):
            if key:
                paper_index[str(key)] = paper
    selected: dict[str, dict[str, Any]] = {}

    def add(paper_key: Any, reason: str, conflict_id: str = "", bundle_id: str = "") -> None:
        paper = paper_index.get(str(paper_key), {})
        canonical = str(paper.get("canonical_paper_id") or paper.get("paper_id") or paper_key or "")
        if not canonical:
            return
        row = selected.setdefault(canonical, {
            "canonical_paper_id": canonical, "paper_id": paper.get("paper_id") or paper_key,
            "pmid": paper.get("pmid"), "pmcid": paper.get("pmcid"), "doi": paper.get("doi"),
            "title": paper.get("title"), "selected_for_fulltext": True,
            "selection_reasons": [], "linked_conflict_candidate_ids": [],
            "linked_relation_bundle_ids": [], "triple_id": triple_id, "query_hash": query_hash,
        })
        if reason not in row["selection_reasons"]:
            row["selection_reasons"].append(reason)
        if conflict_id and conflict_id not in row["linked_conflict_candidate_ids"]:
            row["linked_conflict_candidate_ids"].append(conflict_id)
        if bundle_id and bundle_id not in row["linked_relation_bundle_ids"]:
            row["linked_relation_bundle_ids"].append(bundle_id)

    for conflict in abstract_conflicts:
        cid = str(conflict.get("candidate_id") or "")
        for paper_id in conflict.get("paper_ids") or conflict.get("linked_paper_ids") or []:
            add(paper_id, "abstract_conflict_candidate", cid)
    for conflict in graph_conflicts:
        if conflict.get("status") != "graph_conflict_candidate":
            continue
        cid, bundle = str(conflict.get("graph_conflict_id") or ""), str(conflict.get("bundle_id") or "")
        for paper_id in [*(conflict.get("linked_paper_ids") or []), *(conflict.get("linked_canonical_paper_ids") or [])]:
            add(paper_id, "graph_conflict_candidate", cid, bundle)
    conflicting_bundles = {str(item.get("bundle_id")) for item in graph_conflicts if item.get("status") == "graph_conflict_candidate"}
    for bundle in relation_bundles:
        bundle_id = str(bundle.get("bundle_id") or "")
        if bundle_id not in conflicting_bundles:
            continue
        for paper_id in [*(bundle.get("paper_ids") or []), *(bundle.get("canonical_paper_ids") or [])]:
            add(paper_id, "relation_bundle_conflict", bundle_id=bundle_id)
    for row in selected.values():
        row["selection_reason"] = row["selection_reasons"][0]
    return list(selected.values())


def resolve_fulltext_availability(
    candidates: list[dict[str, Any]], *, resolver: AvailabilityResolver | Any | None = None,
) -> list[dict[str, Any]]:
    records = []
    for candidate in candidates:
        if resolver is not None:
            resolved = resolver(candidate) if callable(resolver) else resolver.resolve(candidate)
        elif candidate.get("full_text_path") or candidate.get("full_text"):
            resolved = {"fulltext_available": True, "open_access": True, "availability_source": "publisher", "fulltext_status": "available", "reason": "fulltext_already_present"}
        elif candidate.get("pmcid"):
            resolved = {"fulltext_available": True, "open_access": True, "availability_source": "pmc", "fulltext_status": "available", "reason": "pmcid_present"}
        else:
            resolved = {"fulltext_available": False, "open_access": False, "availability_source": "not_available", "fulltext_status": "not_available", "reason": "no_pmc_or_oa_resolution"}
        records.append({**candidate, **resolved})
    return records


def acquire_selected_fulltexts(
    availability_records: list[dict[str, Any]], *, repository_root: Path,
    execute: bool, network: bool, client: Any | None = None,
) -> tuple[list[dict[str, Any]], int]:
    output, calls = [], 0
    for item in availability_records:
        if not item.get("selected_for_fulltext") or not item.get("fulltext_available"):
            output.append({**item, "acquisition_status": "skipped", "acquisition_reason": item.get("reason") or "not_selected_or_unavailable"})
            continue
        existing = item.get("full_text_path")
        if existing:
            output.append({**item, "acquisition_status": "available", "full_text_path": existing})
            continue
        if not (execute and network and client is not None):
            output.append({**item, "acquisition_status": "planned", "acquisition_reason": "execute_network_client_required"})
            continue
        content = client.fetch(item, "pmc")
        calls += 1
        identity = str(item.get("pmcid") or item.get("canonical_paper_id")).replace("/", "_")
        path = Path(repository_root) / "data/raw/fulltext" / f"{identity}.xml"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        output.append({**item, "acquisition_status": "downloaded", "full_text_path": str(path), "full_text": content})
    return output, calls


__all__ = ["build_fulltext_escalation_candidates", "resolve_fulltext_availability", "acquire_selected_fulltexts"]
