#!/usr/bin/env python3
"""Inventory and clean regenerable runtime artifacts.

The default mode is a dry run. ``--apply`` removes known runtime artifacts;
``--apply --quarantine`` additionally moves uncertain legacy artifacts into a
timestamped quarantine directory. Source, configuration, fixtures, and
reproducibility metadata are outside the cleanup target set.
"""

from __future__ import annotations

import argparse
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


ROOT = Path(__file__).resolve().parents[2]
REPORT_DIR = ROOT / "cleanup_reports"
KNOWN_RUNTIME_DIRS = {
    Path("data/raw"): {"README.md"},
    Path("data/interim"): {"README.md"},
    Path("data/processed"): {"README.md"},
    Path("data/query"): {"README.md"},
    Path("data/index"): {"README.md"},
    Path("reports"): {".gitkeep", "README.md"},
    Path("runs"): {".gitkeep"},
    Path("logs"): {".gitkeep"},
}
CACHE_DIR_NAMES = {"__pycache__", ".pytest_cache", ".cache"}
PROTECTED_PATHS = {
    Path("src"), Path("scripts"), Path("config"), Path("configs"), Path("docs"),
    Path("tests/fixtures"), Path("data/demo"), Path("data/fixtures"),
    Path("data/metadata/global_manifest.json"),
    Path("data/metadata/literature_quality_audit.csv"),
    Path("README.md"), Path("requirements.txt"), Path("environment.yml"), Path(".gitignore"),
}
PLACEHOLDERS = {
    Path("data/raw/README.md"): "# Raw Literature Cache\n\nRaw files are not committed. Run the reviewed Stage0 acquisition scripts to regenerate them from `data/metadata/global_manifest.json`.\n",
    Path("data/interim/README.md"): "# Interim Runtime Data\n\nGenerated preprocessing payloads belong here temporarily and are not source code.\n",
    Path("data/processed/README.md"): "# Processed Runtime Data\n\nGenerated pipeline outputs are runtime artifacts. New experiments should write to `runs/<run_id>/`.\n",
    Path("data/query/README.md"): "# Query Runtime Data\n\nGenerated query indexes, coverage records, and answers are not committed.\n",
    Path("data/index/README.md"): "# Local Runtime Indexes\n\nKnowledge-store, artifact-inventory, and LLM-cache indexes are regenerated locally.\n",
    Path("reports/.gitkeep"): "",
    Path("reports/README.md"): "# Generated Reports\n\nRun-specific reports are generated artifacts and should be stored under `runs/<run_id>/` when possible.\n",
    Path("runs/.gitkeep"): "",
}


def _relative(path: Path) -> str:
    return str(path.relative_to(ROOT))


def _size(path: Path) -> int:
    if path.is_symlink() or path.is_file():
        try:
            return path.lstat().st_size
        except OSError:
            return 0
    return sum(_size(item) for item in path.rglob("*") if item.is_file() or item.is_symlink())


def _is_protected(path: Path) -> bool:
    relative = path.relative_to(ROOT)
    return relative in PROTECTED_PATHS


def _known_runtime_items() -> Iterable[Path]:
    for relative, preserved_names in KNOWN_RUNTIME_DIRS.items():
        directory = ROOT / relative
        if not directory.exists():
            continue
        for child in sorted(directory.iterdir()):
            if child.name not in preserved_names:
                yield child


def _cache_items() -> Iterable[Path]:
    seen: set[Path] = set()
    for directory_name in CACHE_DIR_NAMES:
        for path in ROOT.rglob(directory_name):
            if ".git" not in path.parts and path not in seen:
                seen.add(path)
                yield path
    for pattern in ("*.pyc", "*.pyo"):
        for path in ROOT.rglob(pattern):
            if ".git" not in path.parts and path not in seen:
                seen.add(path)
                yield path


def build_inventory(quarantine_uncertain: bool) -> dict[str, Any]:
    """Collect the full deletion/quarantine plan before changing the workspace."""

    discovered = sorted(
        set(_known_runtime_items()) | set(_cache_items()),
        key=lambda path: (len(path.parts), str(path)),
    )
    candidates: list[Path] = []
    for path in discovered:
        if not any(parent == path or parent in path.parents for parent in candidates):
            candidates.append(path)
    protected, planned, skipped, warnings = [], [], [], []
    for path in candidates:
        record = {"path": _relative(path), "bytes": _size(path)}
        if _is_protected(path):
            protected.append(record)
        else:
            planned.append(record)

    uncertain = ROOT / "artifacts/legacy"
    quarantined = []
    if uncertain.exists():
        record = {"path": _relative(uncertain), "bytes": _size(uncertain)}
        if quarantine_uncertain:
            quarantined.append(record)
        else:
            skipped.append(record)
            warnings.append("artifacts/legacy was not removed; use --apply --quarantine to isolate it.")

    for protected_path in sorted(PROTECTED_PATHS):
        absolute = ROOT / protected_path
        if absolute.exists():
            protected.append({"path": str(protected_path), "bytes": _size(absolute)})

    return {
        "protected_paths": sorted(protected, key=lambda item: item["path"]),
        "planned_deletions": planned,
        "deleted_paths": [],
        "planned_quarantine": quarantined,
        "quarantined_paths": [],
        "skipped_paths": skipped,
        "warnings": warnings,
    }


def _remove(path: Path) -> None:
    if path.is_dir() and not path.is_symlink():
        shutil.rmtree(path)
    else:
        path.unlink(missing_ok=True)


def _write_placeholders() -> None:
    for relative, content in PLACEHOLDERS.items():
        path = ROOT / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        if not path.exists():
            path.write_text(content, encoding="utf-8")


def apply_inventory(audit: dict[str, Any], quarantine_root: Path) -> None:
    for record in audit["planned_deletions"]:
        path = ROOT / record["path"]
        if path.exists() or path.is_symlink():
            _remove(path)
            audit["deleted_paths"].append(record)
    for record in audit["planned_quarantine"]:
        source = ROOT / record["path"]
        if source.exists():
            destination = quarantine_root / record["path"]
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(source), str(destination))
            audit["quarantined_paths"].append({**record, "destination": _relative(destination)})
    _write_placeholders()


def _workspace_status() -> dict[str, Any]:
    remaining = sorted({
        _relative(path) for path in list(_known_runtime_items()) + list(_cache_items())
    })
    return {
        "clean": not remaining,
        "remaining_runtime_paths": remaining,
        "manifest_retained": (ROOT / "data/metadata/global_manifest.json").exists(),
        "fixtures_retained": (ROOT / "tests/fixtures").exists(),
    }


def write_audit(audit: dict[str, Any], timestamp: str) -> tuple[Path, Path]:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    json_path = REPORT_DIR / f"legacy_cleanup_{timestamp}.json"
    markdown_path = REPORT_DIR / f"legacy_cleanup_{timestamp}.md"
    json_path.write_text(json.dumps(audit, ensure_ascii=False, indent=2), encoding="utf-8")
    lines = [
        "# Legacy Runtime Cleanup Audit", "",
        f"- Mode: {audit['mode']}",
        f"- Status: {audit['status']}",
        f"- Planned deletions: {len(audit['planned_deletions'])}",
        f"- Deleted: {len(audit['deleted_paths'])}",
        f"- Quarantined: {len(audit['quarantined_paths'])}",
        f"- Workspace clean: {str(audit['current_clean_workspace_status']['clean']).lower()}",
        "", "## Warnings", "",
    ]
    lines.extend(f"- {warning}" for warning in audit["warnings"] or ["None"])
    lines.extend(["", "## Next Commands", ""])
    lines.extend(f"- `{command}`" for command in audit["next_commands"])
    markdown_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return json_path, markdown_path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--dry-run", action="store_true", help="inventory only (default)")
    mode.add_argument("--apply", action="store_true", help="apply known-safe cleanup")
    parser.add_argument("--quarantine", action="store_true", help="with --apply, isolate uncertain legacy artifacts")
    args = parser.parse_args()
    if args.quarantine and not args.apply:
        parser.error("--quarantine requires --apply")
    return args


def main() -> int:
    args = parse_args()
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    audit = build_inventory(quarantine_uncertain=args.quarantine)
    audit.update({
        "schema_version": "legacy_cleanup_audit_v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "mode": "apply_quarantine" if args.apply and args.quarantine else "apply" if args.apply else "dry_run",
        "status": "inventory_complete",
        "next_commands": [
            "python scripts/maintenance/cleanup_legacy_artifacts.py --dry-run",
            "python scripts/maintenance/cleanup_legacy_artifacts.py --apply",
            "python -m unittest discover -s tests",
        ],
    })
    audit["current_clean_workspace_status"] = _workspace_status()
    write_audit(audit, timestamp)

    if args.apply:
        quarantine_root = ROOT / "quarantine" / f"legacy_cleanup_{timestamp}"
        apply_inventory(audit, quarantine_root)
        audit["status"] = "cleanup_applied"
        audit["current_clean_workspace_status"] = _workspace_status()
    else:
        audit["status"] = "dry_run_complete"

    json_path, markdown_path = write_audit(audit, timestamp)
    print(f"{audit['mode']}: {audit['status']}")
    print(f"planned={len(audit['planned_deletions'])} deleted={len(audit['deleted_paths'])} quarantined={len(audit['quarantined_paths'])}")
    print(f"audit={json_path.relative_to(ROOT)}")
    print(f"summary={markdown_path.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
