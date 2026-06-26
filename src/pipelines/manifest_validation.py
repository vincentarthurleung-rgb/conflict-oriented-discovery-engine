"""Audit validators for global_manifest.json and Stage1 weighted payloads.

These validators are intentionally non-invasive: by default they write audit
reports without blocking legacy Stage0/Stage1 flows. Passing --strict raises on
critical errors after writing the audit artifacts.
"""

from __future__ import annotations

import argparse
import json
import os
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, Iterable, List

from src.schemas import ManifestAudit, PayloadAudit


GLOBAL_MANIFEST_PATH = "data/metadata/global_manifest.json"
PAYLOAD_DIR = "data/interim/weighted_payloads"
MANIFEST_AUDIT_JSON = "data/metadata/manifest_validation_audit.json"
MANIFEST_AUDIT_MD = "reports/manifest_validation_audit.md"
PAYLOAD_AUDIT_JSON = "data/metadata/payload_validation_audit.json"
PAYLOAD_AUDIT_MD = "reports/payload_validation_audit.md"


def _append_issue(collection: List[Dict[str, Any]], code: str, message: str, **details: Any) -> None:
    collection.append({"code": code, "message": message, "details": details})


def _write_json(path: str, payload: Dict[str, Any]) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)


def _write_markdown(path: str, title: str, audit: Dict[str, Any]) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(f"# {title}\n\n")
        for key in ("manifest_path", "payload_dir", "total_papers", "total_payloads"):
            if key in audit:
                handle.write(f"- {key}: {audit[key]}\n")
        handle.write(f"- warnings: {len(audit.get('warnings', []))}\n")
        handle.write(f"- errors: {len(audit.get('errors', []))}\n")
        if audit.get("errors"):
            handle.write("\n## Errors\n")
            for issue in audit["errors"]:
                handle.write(f"- `{issue['code']}`: {issue['message']} {issue.get('details', {})}\n")
        if audit.get("warnings"):
            handle.write("\n## Warnings\n")
            for issue in audit["warnings"]:
                handle.write(f"- `{issue['code']}`: {issue['message']} {issue.get('details', {})}\n")


def _infer_manifest_paths(paper_id: str, entry: Dict[str, Any]) -> Dict[str, str]:
    source = entry.get("source", "")
    raw_path = entry.get("raw_path", "")
    payload_path = entry.get("payload_path", "")
    if not raw_path:
        if paper_id.startswith("PMC"):
            raw_path = f"data/raw/xml/{paper_id}.xml"
        elif paper_id.startswith("PMID"):
            raw_path = f"data/raw/abstracts/{paper_id}.json"
        elif source == "pubmed":
            raw_path = f"data/raw/abstracts/{paper_id}.json"
    if not payload_path:
        payload_path = f"data/interim/weighted_payloads/{paper_id}_payload.json"
    return {"raw_path": raw_path, "payload_path": payload_path}


def validate_manifest(manifest_path: str = GLOBAL_MANIFEST_PATH, strict: bool = False) -> ManifestAudit:
    """Validate global_manifest.json and write warnings/errors to an audit object."""

    errors: List[Dict[str, Any]] = []
    warnings: List[Dict[str, Any]] = []
    path = Path(manifest_path)
    if not path.exists():
        _append_issue(errors, "manifest_missing", "global manifest file is missing", path=manifest_path)
        audit = ManifestAudit(manifest_path=manifest_path, errors=errors)
        return audit

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        _append_issue(errors, "manifest_invalid_json", "global manifest is not valid JSON", error=str(exc))
        return ManifestAudit(manifest_path=manifest_path, errors=errors)

    papers = data.get("papers")
    if not isinstance(papers, dict):
        _append_issue(errors, "papers_missing", "manifest requires a `papers` object")
        papers = {}

    metadata = data.get("metadata", {})
    if isinstance(metadata, dict):
        has_old = "query" in metadata or "timestamp" in metadata
        has_new = "last_query" in metadata or "update_time" in metadata
        if has_old and has_new:
            _append_issue(warnings, "metadata_mixed_names", "metadata mixes query/timestamp and last_query/update_time")
        elif not has_old and not has_new:
            _append_issue(warnings, "metadata_unknown_names", "metadata does not use known query timestamp naming")

    seen = defaultdict(list)
    for paper_id, entry in papers.items():
        if not isinstance(entry, dict):
            _append_issue(errors, "paper_entry_not_object", "paper entry must be an object", paper_id=paper_id)
            continue

        stable_ids = {
            "pmid": entry.get("pmid") or (paper_id[4:] if str(paper_id).startswith("PMID") else None),
            "pmcid": entry.get("pmcid") or (paper_id if str(paper_id).startswith("PMC") else None),
            "doi": entry.get("doi"),
        }
        if not any(stable_ids.values()):
            _append_issue(warnings, "paper_missing_external_id", "paper has no pmid/pmcid/doi", paper_id=paper_id)
        for id_name, id_value in stable_ids.items():
            if id_value:
                seen[(id_name, str(id_value).lower())].append(paper_id)

        inferred = _infer_manifest_paths(str(paper_id), entry)
        for path_key in ("raw_path", "payload_path"):
            if not entry.get(path_key):
                _append_issue(warnings, f"{path_key}_missing", f"manifest entry lacks {path_key}", paper_id=paper_id, inferred=inferred[path_key])

    for (id_name, id_value), paper_ids in seen.items():
        if len(paper_ids) > 1:
            _append_issue(warnings, "duplicate_external_id", "duplicate external identifier", id_type=id_name, id_value=id_value, paper_ids=paper_ids)

    audit = ManifestAudit(manifest_path=manifest_path, total_papers=len(papers), warnings=warnings, errors=errors)
    if strict and audit.errors:
        raise ValueError(f"Manifest validation failed with {len(audit.errors)} errors")
    return audit


def _payload_has_text(payload: Dict[str, Any]) -> bool:
    if payload.get("abstract") or payload.get("full_text"):
        return True
    for key in ("sections", "chunks", "paragraphs"):
        value = payload.get(key)
        if isinstance(value, list) and value:
            return True
    return False


def validate_payload_file(path: Path) -> tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Validate one Stage1 payload file and return errors, warnings."""

    errors: List[Dict[str, Any]] = []
    warnings: List[Dict[str, Any]] = []
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        _append_issue(errors, "payload_invalid_json", "payload is not valid JSON", path=str(path), error=str(exc))
        return errors, warnings

    paper_id = payload.get("paper_id") or payload.get("pmcid") or payload.get("pmid") or payload.get("source_id")
    if not paper_id:
        _append_issue(errors, "payload_missing_paper_id", "payload lacks paper/source id", path=str(path))
    if not _payload_has_text(payload):
        _append_issue(errors, "payload_missing_text", "payload lacks abstract/full_text/sections/chunks/paragraphs", path=str(path), paper_id=paper_id)
    if "belief_weight" not in payload:
        _append_issue(warnings, "belief_weight_missing", "payload lacks belief_weight", path=str(path), paper_id=paper_id)
    elif not any(key in payload for key in ("journal", "jcr_tier", "impact_factor", "weight_source")):
        _append_issue(warnings, "belief_weight_source_unclear", "belief_weight is present but source metadata is unclear", path=str(path), paper_id=paper_id)
    return errors, warnings


def validate_payload_dir(payload_dir: str = PAYLOAD_DIR, strict: bool = False) -> PayloadAudit:
    """Validate all Stage1 payload JSON files in a directory."""

    errors: List[Dict[str, Any]] = []
    warnings: List[Dict[str, Any]] = []
    root = Path(payload_dir)
    if not root.exists():
        _append_issue(errors, "payload_dir_missing", "payload directory is missing", payload_dir=payload_dir)
        return PayloadAudit(payload_dir=payload_dir, errors=errors)

    payload_files = sorted(root.glob("*_payload.json"))
    for payload_path in payload_files:
        file_errors, file_warnings = validate_payload_file(payload_path)
        errors.extend(file_errors)
        warnings.extend(file_warnings)

    audit = PayloadAudit(payload_dir=payload_dir, total_payloads=len(payload_files), warnings=warnings, errors=errors)
    if strict and audit.errors:
        raise ValueError(f"Payload validation failed with {len(audit.errors)} errors")
    return audit


def write_validation_audits(manifest_audit: ManifestAudit, payload_audit: PayloadAudit) -> None:
    """Write JSON and markdown audit artifacts."""

    manifest_payload = manifest_audit.model_dump()
    payload_payload = payload_audit.model_dump()
    _write_json(MANIFEST_AUDIT_JSON, manifest_payload)
    _write_json(PAYLOAD_AUDIT_JSON, payload_payload)
    _write_markdown(MANIFEST_AUDIT_MD, "Manifest Validation Audit", manifest_payload)
    _write_markdown(PAYLOAD_AUDIT_MD, "Payload Validation Audit", payload_payload)


def main(argv: Iterable[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Audit global manifest and Stage1 payloads.")
    parser.add_argument("--manifest", default=GLOBAL_MANIFEST_PATH)
    parser.add_argument("--payload-dir", default=PAYLOAD_DIR)
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args(list(argv) if argv is not None else None)

    manifest_audit = validate_manifest(args.manifest, strict=args.strict)
    payload_audit = validate_payload_dir(args.payload_dir, strict=args.strict)
    write_validation_audits(manifest_audit, payload_audit)
    print(f"[Manifest Validation] warnings={len(manifest_audit.warnings)} errors={len(manifest_audit.errors)}")
    print(f"[Payload Validation] warnings={len(payload_audit.warnings)} errors={len(payload_audit.errors)}")
    if args.strict and (manifest_audit.errors or payload_audit.errors):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
