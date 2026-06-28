"""Runtime-source guards and empty-state helpers.

Legacy archives are never implicit inputs. Callers must explicitly opt in when
reading from quarantine or ``artifacts/legacy``.
"""

from __future__ import annotations

from pathlib import Path


LEGACY_PATH_PARTS = (("artifacts", "legacy"), ("quarantine",))


def is_legacy_source(path: str | Path) -> bool:
    """Return whether *path* points into a legacy or quarantined tree."""

    parts = tuple(part.casefold() for part in Path(path).parts)
    for marker in LEGACY_PATH_PARTS:
        if len(marker) == 1 and marker[0] in parts:
            return True
        if len(marker) == 2 and any(
            parts[index:index + 2] == marker for index in range(len(parts) - 1)
        ):
            return True
    return False


def ensure_source_allowed(path: str | Path, *, allow_legacy_source: bool = False) -> None:
    """Reject implicit reads from legacy storage."""

    if is_legacy_source(path) and not allow_legacy_source:
        raise ValueError(
            f"Legacy runtime source is disabled: {path}. "
            "Pass allow_legacy_source=True only for an explicit compatibility run."
        )
