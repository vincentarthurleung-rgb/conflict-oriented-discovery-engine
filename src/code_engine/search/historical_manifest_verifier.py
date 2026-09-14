"""Verify an immutable run using the file set frozen in its manifest."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


def _canonical_json(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verify_frozen_manifest(
    run_directory: str | Path,
    *,
    manifest_name: str = "implementation_manifest.json",
    root_field: str,
) -> dict[str, Any]:
    """Verify exactly the historical component set declared by a frozen manifest.

    Files added to the repository after the freeze are deliberately outside this
    verification boundary.  Each declared component must still be a physical
    regular file with the exact frozen digest.
    """
    run = Path(run_directory)
    manifest_path = run / manifest_name
    if not manifest_path.is_file() or manifest_path.is_symlink():
        raise ValueError(f"historical manifest is missing or not a physical file: {manifest_path}")
    manifest = json.loads(manifest_path.read_bytes())
    components = manifest.get("aggregate_components")
    if not isinstance(components, list) or not components:
        raise ValueError("historical manifest has no frozen aggregate_components")
    pairs: list[list[str]] = []
    verified: list[dict[str, str]] = []
    seen: set[str] = set()
    for component in components:
        relative = component.get("path")
        expected = component.get("sha256")
        if not isinstance(relative, str) or not relative or relative in seen:
            raise ValueError(f"invalid or duplicate historical component path: {relative!r}")
        seen.add(relative)
        path = run / relative
        if not path.is_file() or path.is_symlink():
            raise ValueError(f"historical protected file is missing or replaced: {relative}")
        actual = _sha256(path)
        if actual != expected:
            raise ValueError(f"historical protected file digest mismatch: {relative}")
        pairs.append([relative, actual])
        verified.append({"path": relative, "sha256": actual})
    aggregate = hashlib.sha256(_canonical_json(pairs)).hexdigest()
    declared = manifest.get(root_field)
    if aggregate != declared:
        raise ValueError(f"historical aggregate mismatch for {root_field}")
    return {
        "status": "PASS",
        "manifest_path": str(manifest_path),
        "protected_file_count": len(verified),
        "protected_files": verified,
        "aggregate_sha256": aggregate,
        "declared_aggregate_sha256": declared,
        "membership_source": "frozen_manifest_aggregate_components",
        "current_repository_membership_enumerated": False,
    }
