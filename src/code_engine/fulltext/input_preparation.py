"""Reusable, side-effect-free planning for cached and missing fulltext inputs."""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable


def _rows(path: Path) -> list[dict[str, Any]]:
    try:
        return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    except (OSError, json.JSONDecodeError):
        return []


def prepare_fulltext_inputs(*, candidates_path: str | Path, fulltext_root: str | Path,
                            retry_ledger_path: str | Path | None = None) -> dict[str, Any]:
    """Inspect local state only; this function never downloads or resolves identifiers."""
    root = Path(fulltext_root); candidates = _rows(Path(candidates_path)); seen: set[str] = set()
    ready = []; missing = []; invalid = []
    retry = _rows(Path(retry_ledger_path)) if retry_ledger_path else []
    retry_by_pmcid = {str(x.get("pmcid")): x for x in retry}
    for row in candidates:
        pmcid = str(row.get("pmcid") or "").upper().strip()
        if not pmcid:
            invalid.append({**row, "preparation_status": "missing_pmcid"}); continue
        if pmcid in seen: continue
        seen.add(pmcid); article = root / pmcid / "article_text.json"
        if article.is_file():
            source_hash = hashlib.sha256(article.read_bytes()).hexdigest()
            ready.append({**row, "pmcid": pmcid, "preparation_status": "cached_ready", "article_path": str(article), "source_fulltext_hash": source_hash, "download_required": False})
        else:
            prior = retry_by_pmcid.get(pmcid) or {}
            missing.append({**row, "pmcid": pmcid, "preparation_status": "missing_download_planned", "download_required": True, "retry_count": int(prior.get("retry_count") or 0), "last_error": prior.get("last_error"), "permanently_discarded": False})
    return {
        "schema_version": "fulltext_input_preparation_plan_v1", "created_at": datetime.now(timezone.utc).isoformat(),
        "candidate_count": len(candidates), "unique_pmcid_count": len(seen), "cached_ready_count": len(ready),
        "missing_count": len(missing), "invalid_count": len(invalid), "ready": ready, "missing_download_plan": missing,
        "invalid": invalid, "network_calls": 0, "download_calls": 0, "dry_run_safe": True,
    }


def execute_missing_only(plan: dict[str, Any], *, downloader: Callable[[dict[str, Any]], dict[str, Any]],
                         retry_ledger_path: str | Path) -> dict[str, Any]:
    """Execute only explicit missing rows through the caller's existing downloader adapter."""
    ledger_path = Path(retry_ledger_path); existing = _rows(ledger_path); by_id = {str(x.get("pmcid")): x for x in existing}
    results = []
    for row in plan.get("missing_download_plan") or []:
        result = downloader(row); results.append(result)
        pmcid = str(row.get("pmcid")); old = by_id.get(pmcid) or {}
        if result.get("full_text_status") != "available":
            by_id[pmcid] = {"pmcid": pmcid, "retry_count": int(old.get("retry_count") or 0) + 1, "last_error": result.get("error") or result.get("reason"), "retryable": True, "permanently_discarded": False, "updated_at": datetime.now(timezone.utc).isoformat()}
        else:
            by_id.pop(pmcid, None)
    ledger_path.parent.mkdir(parents=True, exist_ok=True)
    ledger_path.write_text("".join(json.dumps(x, ensure_ascii=False) + "\n" for x in by_id.values()), encoding="utf-8")
    return {"attempted": len(results), "results": results, "retry_ledger": str(ledger_path)}

