from __future__ import annotations

import hashlib
import importlib.metadata
import platform
import subprocess
from pathlib import Path
from typing import Any

from .identities import canonical_sha256

CODE_PROVENANCE_VERSION = "context_attribution_code_provenance_v1"


def _run(root: Path, *args: str) -> str:
    result = subprocess.run(
        args, cwd=root, check=True, capture_output=True, text=True,
    )
    return result.stdout


def _file_hash(path: Path) -> str | None:
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None


def build_code_provenance(
    root: Path, *, execution_entrypoint: str,
) -> dict[str, Any]:
    root = root.resolve()
    tracked = [x for x in _run(root, "git", "ls-files").splitlines() if x]
    diff = _run(root, "git", "diff", "--binary", "--", *tracked)
    status = _run(root, "git", "status", "--porcelain=v1")
    # The requested provenance closure spans generated case inputs, reports,
    # tests, configuration, and runtime modules.  Hashing the complete tracked
    # repository is the least ambiguous stable superset and avoids a brittle
    # manually curated allowlist.  Include the new, not-yet-tracked v7 modules
    # as well so a dirty development execution remains reproducible.
    untracked_relevant = [
        path.relative_to(root).as_posix()
        for base in (
            root / "src/code_engine/context_attribution",
            root / "tests",
        )
        if base.is_dir()
        for path in base.rglob("*.py")
        if path.is_file()
    ]
    relevant = sorted(set(tracked) | set(untracked_relevant))
    hashes = {path: _file_hash(root / path) for path in sorted(relevant)}
    config_hashes = {
        path: value for path, value in hashes.items()
        if path.startswith("configs/")
    }
    packages = {}
    for name in ("pydantic", "pytest"):
        try:
            packages[name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            pass
    payload = {
        "schema_version": CODE_PROVENANCE_VERSION,
        "git_head": _run(root, "git", "rev-parse", "HEAD").strip(),
        "git_dirty": bool(status.strip()),
        "tracked_diff_sha256": hashlib.sha256(diff.encode()).hexdigest(),
        "relevant_module_hashes": hashes,
        "config_file_hashes": config_hashes,
        "execution_entrypoint": execution_entrypoint,
        "python_version": platform.python_version(),
        "package_versions": packages,
    }
    return {**payload, "identity_sha256": canonical_sha256(payload)}
