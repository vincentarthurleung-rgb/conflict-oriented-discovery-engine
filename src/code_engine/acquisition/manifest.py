"""Read-only scanner for paper-level processing state across local artifacts."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List

from pydantic import Field

from code_engine.schemas.models import CODEBaseModel
from code_engine.common.runtime import ensure_source_allowed, is_legacy_source


DEFAULT_INVENTORY_PATH = Path("data/index/artifact_inventory.json")
DEFAULT_AUDIT_PATH = Path("reports/artifact_inventory_audit.md")


def empty_artifact_inventory(status: str = "missing_empty_inventory") -> Dict[str, Any]:
    """Return an empty inventory without scanning or writing runtime paths."""

    return {
        "schema_version": "query_artifact_inventory_v1",
        "generated_at": None,
        "runtime_data_status": status,
        "using_legacy_data": False,
        "papers": [],
        "duplicate_groups": [],
        "warnings": ["Artifact inventory is unavailable; no runtime artifacts were assumed."],
    }


class CandidatePaperMatchReport(CODEBaseModel):
    intent_id: str
    candidate_papers: List[Dict[str, Any]] = Field(default_factory=list)
    already_downloaded: List[Dict[str, Any]] = Field(default_factory=list)
    already_in_manifest: List[Dict[str, Any]] = Field(default_factory=list)
    needs_download: List[Dict[str, Any]] = Field(default_factory=list)
    has_stage1_payload: List[Dict[str, Any]] = Field(default_factory=list)
    has_l1_output: List[Dict[str, Any]] = Field(default_factory=list)
    has_l1_5_output: List[Dict[str, Any]] = Field(default_factory=list)
    duplicate_by_pmid: List[Dict[str, Any]] = Field(default_factory=list)
    duplicate_by_pmcid: List[Dict[str, Any]] = Field(default_factory=list)
    duplicate_by_doi: List[Dict[str, Any]] = Field(default_factory=list)
    duplicate_by_title_hash: List[Dict[str, Any]] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)


def _read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def _paper_id_from_path(path: Path) -> str:
    for suffix in ("_payload", "_extracted", "_refined"):
        if path.stem.endswith(suffix):
            return path.stem[: -len(suffix)]
    return path.stem


def _first_existing(root: Path, candidates: Iterable[str]) -> Path | None:
    for candidate in candidates:
        path = root / candidate
        if path.exists():
            return path
    return None


def _files_by_paper(directory: Path | None) -> Dict[str, Path]:
    if directory is None or not directory.exists():
        return {}
    return {_paper_id_from_path(path): path for path in sorted(directory.glob("*.json"))}


def _chunk_count(payload: Dict[str, Any]) -> int:
    for key in ("chunks", "chunks_extracted", "paragraphs"):
        value = payload.get(key)
        if isinstance(value, list):
            return len(value)
    sections = payload.get("sections", [])
    if isinstance(sections, list):
        return sum(len(section.get("chunks", [])) for section in sections if isinstance(section, dict))
    return 0


def _dedup_keys(paper: Dict[str, Any]) -> List[str]:
    keys = []
    for field in ("pmid", "pmcid", "doi"):
        value = str(paper.get(field) or "").strip().lower()
        if value:
            keys.append(f"{field}:{value}")
    title = str(paper.get("title") or "").strip().lower()
    if title:
        keys.append(f"title_sha256:{hashlib.sha256(title.encode('utf-8')).hexdigest()}")
    return keys


def _write_audit(inventory: Dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    papers = inventory.get("papers", [])
    counts = {
        field: sum(bool(paper.get(field)) for paper in papers)
        for field in (
            "raw_available",
            "stage1_payload_available",
            "l1_extracted",
            "l1_5_refined",
            "l2_indexed",
            "l3_indexed",
            "l4_context_indexed",
            "l5_validated",
        )
    }
    lines = ["# Artifact Inventory Audit", "", f"Papers indexed: {len(papers)}", ""]
    lines.extend(f"- {key}: {value}" for key, value in counts.items())
    lines.extend(["", f"Duplicate groups: {len(inventory.get('duplicate_groups', []))}", ""])
    path.write_text("\n".join(lines), encoding="utf-8")


def build_artifact_inventory(
    repository_root: str | Path = ".",
    *,
    output_path: str | Path | None = None,
    audit_path: str | Path | None = None,
    allow_legacy_source: bool = False,
) -> Dict[str, Any]:
    """Build a local index without modifying source artifacts."""

    root = Path(repository_root)
    ensure_source_allowed(root, allow_legacy_source=allow_legacy_source)
    manifest_path = root / "data/metadata/global_manifest.json"
    manifest = _read_json(manifest_path)
    manifest_papers = manifest.get("papers", {}) if isinstance(manifest, dict) else {}

    raw_dir = _first_existing(root, ("data/raw/xml", "data/raw"))
    payload_dir = _first_existing(root, ("data/interim/weighted_payloads", "data/interim"))
    l1_dir = _first_existing(root, ("data/processed/l1",))
    l1_5_dir = _first_existing(root, ("data/processed/l1_5", "data/processed/l1_5_refined"))
    payload_files = _files_by_paper(payload_dir)
    l1_files = _files_by_paper(l1_dir)
    l1_5_files = _files_by_paper(l1_5_dir)

    paper_ids = set(manifest_papers) | set(payload_files) | set(l1_files) | set(l1_5_files)
    if raw_dir:
        paper_ids.update(path.stem for path in raw_dir.glob("*") if path.is_file())

    l2_available = (root / "data/processed/l2/entity_normalization_audit.json").exists()
    l3_payload = _read_json(root / "data/processed/l3/integrated_shannon_graph.json")
    l4_payload = _read_json(root / "data/processed/l4/context_mentions.json")
    l5_payload = _read_json(root / "data/processed/l5/validation_results.json")
    l3_ids = {
        trace.get("source_asset")
        for edge in l3_payload if isinstance(l3_payload, list)
        for trace in edge.get("whitebox_traceability", [])
    }
    l4_ids = {item.get("paper_id") for item in l4_payload.get("context_mentions", [])} if isinstance(l4_payload, dict) else set()
    l5_ids = {
        evidence.get("paper_id")
        for result in l5_payload.get("validation_results", [])
        for evidence in result.get("evidence", [])
        if isinstance(evidence, dict)
    } if isinstance(l5_payload, dict) else set()

    papers: List[Dict[str, Any]] = []
    for paper_id in sorted(str(item) for item in paper_ids if item):
        metadata = manifest_papers.get(paper_id, {}) if isinstance(manifest_papers, dict) else {}
        payload_path = payload_files.get(paper_id)
        l1_path = l1_files.get(paper_id)
        l1_5_path = l1_5_files.get(paper_id)
        detail = _read_json(l1_5_path or l1_path or payload_path) if (l1_5_path or l1_path or payload_path) else {}
        pmcid = metadata.get("pmcid") or detail.get("pmcid") or (paper_id if paper_id.upper().startswith("PMC") else None)
        pmid = metadata.get("pmid") or detail.get("pmid") or (paper_id if paper_id.isdigit() else None)
        raw_path = next(iter(sorted(raw_dir.glob(f"{paper_id}.*"))), None) if raw_dir else None
        paper = {
            "paper_id": paper_id,
            "pmid": pmid,
            "pmcid": pmcid,
            "doi": metadata.get("doi") or detail.get("doi"),
            "title": metadata.get("title") or metadata.get("article_title") or detail.get("article_title") or detail.get("title") or "",
            "year": metadata.get("year") or detail.get("year"),
            "in_manifest": paper_id in manifest_papers,
            "raw_path": str(raw_path.relative_to(root)) if raw_path else None,
            "payload_path": str(payload_path.relative_to(root)) if payload_path else None,
            "l1_path": str(l1_path.relative_to(root)) if l1_path else None,
            "l1_5_path": str(l1_5_path.relative_to(root)) if l1_5_path else None,
            "chunk_count": _chunk_count(_read_json(payload_path)) if payload_path else 0,
            "raw_available": raw_path is not None,
            "stage1_payload_available": payload_path is not None,
            "l1_extracted": l1_path is not None,
            "l1_5_refined": l1_5_path is not None,
            "l2_indexed": bool(l2_available and l1_5_path),
            "l3_indexed": paper_id in l3_ids,
            "l4_context_indexed": paper_id in l4_ids,
            "l5_validated": paper_id in l5_ids,
        }
        paper["dedup_keys"] = _dedup_keys(paper)
        papers.append(paper)

    dedup_map: Dict[str, List[str]] = {}
    for paper in papers:
        for key in paper["dedup_keys"]:
            dedup_map.setdefault(key, []).append(paper["paper_id"])
    duplicate_groups = [
        {"dedup_key": key, "paper_ids": ids}
        for key, ids in sorted(dedup_map.items())
        if len(ids) > 1
    ]
    inventory = {
        "schema_version": "query_artifact_inventory_v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "runtime_data_status": "runtime_artifacts_available" if any(
            paper.get("raw_available")
            or paper.get("stage1_payload_available")
            or paper.get("l1_extracted")
            or paper.get("l1_5_refined")
            or paper.get("l3_indexed")
            for paper in papers
        ) else "metadata_only_no_runtime_artifacts",
        "using_legacy_data": allow_legacy_source,
        "papers": papers,
        "duplicate_groups": duplicate_groups,
        "warnings": (["Explicit legacy artifact source is in use."] if allow_legacy_source else []),
    }
    target = Path(output_path) if output_path else root / DEFAULT_INVENTORY_PATH
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(inventory, ensure_ascii=False, indent=2), encoding="utf-8")
    _write_audit(inventory, Path(audit_path) if audit_path else root / DEFAULT_AUDIT_PATH)
    return inventory


def load_artifact_inventory(
    path: str | Path = DEFAULT_INVENTORY_PATH,
    *,
    build_if_missing: bool = False,
    repository_root: str | Path = ".",
    allow_legacy_source: bool = False,
) -> Dict[str, Any]:
    """Load an inventory, returning a non-writing empty state when missing."""

    inventory_path = Path(path)
    if not inventory_path.is_absolute():
        inventory_path = Path(repository_root) / inventory_path
    ensure_source_allowed(inventory_path, allow_legacy_source=allow_legacy_source)
    if not inventory_path.exists():
        if build_if_missing:
            return build_artifact_inventory(
                repository_root,
                output_path=inventory_path,
                allow_legacy_source=allow_legacy_source,
            )
        return empty_artifact_inventory()
    inventory = _read_json(inventory_path)
    if not isinstance(inventory, dict) or not inventory:
        return empty_artifact_inventory("invalid_empty_inventory")
    has_runtime_artifacts = any(
        paper.get("raw_available")
        or paper.get("stage1_payload_available")
        or paper.get("l1_extracted")
        or paper.get("l1_5_refined")
        or paper.get("l3_indexed")
        for paper in inventory.get("papers", [])
    )
    inventory.setdefault(
        "runtime_data_status",
        "runtime_artifacts_available" if has_runtime_artifacts else "metadata_only_no_runtime_artifacts",
    )
    inventory["using_legacy_data"] = is_legacy_source(inventory_path)
    inventory.setdefault("warnings", [])
    if inventory["using_legacy_data"]:
        inventory["warnings"].append("Explicit legacy artifact inventory source is in use.")
    return inventory


def find_papers_by_entity(entity: str, inventory: Dict[str, Any] | None = None) -> List[Dict[str, Any]]:
    """Match an entity against indexed paper metadata."""

    active = inventory if inventory is not None else load_artifact_inventory()
    needle = str(entity or "").casefold()
    return [
        paper for paper in active.get("papers", [])
        if needle and needle in " ".join(str(paper.get(key) or "") for key in ("title", "doi", "paper_id")).casefold()
    ]


def find_unprocessed_papers_for_query(query: Any, inventory: Dict[str, Any] | None = None) -> List[Dict[str, Any]]:
    """Return locally known relevant papers missing L1 or L1.5 processing."""

    active = inventory if inventory is not None else load_artifact_inventory()
    terms = [
        str(getattr(query, "normalized_subject", "") or "").casefold(),
        str(getattr(query, "normalized_object", "") or "").casefold(),
    ]
    candidates = []
    for paper in active.get("papers", []):
        haystack = " ".join(str(paper.get(key) or "") for key in ("title", "doi", "paper_id")).casefold()
        relevant = not any(terms) or any(term and term in haystack for term in terms)
        if relevant and (not paper.get("l1_extracted") or not paper.get("l1_5_refined")):
            candidates.append(paper)
    return candidates


def normalized_title_hash(title: str) -> str:
    normalized = " ".join("".join(character.lower() if character.isalnum() else " " for character in str(title)).split())
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest() if normalized else ""


def match_candidate_papers_to_inventory(
    search_plan: Any,
    inventory: Dict[str, Any],
    *,
    output_root: str | Path = ".",
    write_outputs: bool = False,
) -> CandidatePaperMatchReport:
    """Match fixture/mock candidates to local inventory without mutating manifest."""

    candidates = list(
        search_plan.get("candidate_papers", [])
        if isinstance(search_plan, dict)
        else getattr(search_plan, "candidate_papers", [])
    )
    papers = list(inventory.get("papers", []))
    fields = ("pmid", "pmcid", "doi")

    def key(record: Dict[str, Any], field: str) -> str:
        if field == "title_hash":
            return normalized_title_hash(record.get("title", ""))
        return str(record.get(field) or "").strip().casefold()

    indexes = {field: {} for field in (*fields, "title_hash")}
    for paper in papers:
        for field in indexes:
            value = key(paper, field)
            if value:
                indexes[field].setdefault(value, []).append(paper)

    matched_candidates = []
    buckets = {name: [] for name in ("already_downloaded", "already_in_manifest", "needs_download", "has_stage1_payload", "has_l1_output", "has_l1_5_output")}
    duplicates = {field: [] for field in (*fields, "title_hash")}
    candidate_seen = {field: {} for field in (*fields, "title_hash")}
    for candidate in candidates:
        candidate = dict(candidate)
        matches = []
        matched_by = []
        for field in indexes:
            value = key(candidate, field)
            if value:
                candidate_seen[field].setdefault(value, []).append(candidate)
                if indexes[field].get(value):
                    matches.extend(indexes[field][value])
                    matched_by.append(field)
        unique_matches = {str(item.get("paper_id")): item for item in matches}
        matched = next(iter(unique_matches.values()), None)
        enriched = {**candidate, "matched_inventory_paper": matched, "matched_by": matched_by}
        matched_candidates.append(enriched)
        if matched and matched.get("in_manifest", True):
            buckets["already_in_manifest"].append(enriched)
        if matched and matched.get("raw_available"):
            buckets["already_downloaded"].append(enriched)
        else:
            buckets["needs_download"].append(enriched)
        if matched and matched.get("stage1_payload_available"):
            buckets["has_stage1_payload"].append(enriched)
        if matched and matched.get("l1_extracted"):
            buckets["has_l1_output"].append(enriched)
        if matched and matched.get("l1_5_refined"):
            buckets["has_l1_5_output"].append(enriched)
    for field, values in candidate_seen.items():
        for value, records in values.items():
            if len(records) > 1 or len(indexes[field].get(value, [])) > 1:
                duplicates[field].append({"dedup_value": value, "candidates": records})
    warnings = [] if candidates else ["no_candidate_papers_provided_search_execution_not_performed"]
    report = CandidatePaperMatchReport(
        intent_id=str(search_plan.get("intent_id", "UNKNOWN") if isinstance(search_plan, dict) else search_plan.intent_id),
        candidate_papers=matched_candidates,
        duplicate_by_pmid=duplicates["pmid"],
        duplicate_by_pmcid=duplicates["pmcid"],
        duplicate_by_doi=duplicates["doi"],
        duplicate_by_title_hash=duplicates["title_hash"],
        warnings=warnings,
        **buckets,
    )
    if write_outputs:
        root = Path(output_root)
        data_path = root / f"data/query/candidate_match_{report.intent_id}.json"
        data_path.parent.mkdir(parents=True, exist_ok=True)
        data_path.write_text(report.model_dump_json(indent=2), encoding="utf-8")
        markdown = root / f"reports/candidate_match_{report.intent_id}.md"
        markdown.parent.mkdir(parents=True, exist_ok=True)
        markdown.write_text(
            "# Candidate Paper Match\n\n"
            f"- Candidates: {len(report.candidate_papers)}\n"
            f"- Already downloaded: {len(report.already_downloaded)}\n"
            f"- Need download: {len(report.needs_download)}\n",
            encoding="utf-8",
        )
    return report
