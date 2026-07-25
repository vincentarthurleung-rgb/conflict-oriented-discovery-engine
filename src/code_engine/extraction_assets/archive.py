"""Byte-preserving, atomic archive. This module never invokes a parser."""
from __future__ import annotations

import os
import tempfile
from pathlib import Path

from .identities import sha256_bytes, stable_identity


class ImmutableAssetError(RuntimeError):
    pass


class RawResponseArchive:
    def __init__(self, root: Path | str):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def path_for(self, call_dedup_identity: str, digest: str) -> Path:
        safe = call_dedup_identity.rsplit(":", 1)[-1]
        return self.root / safe[:2] / f"{safe}.{digest}.raw"

    def persist(self, raw_bytes: bytes, call_dedup_identity: str) -> tuple[Path, str]:
        """Persist exact bytes using fsync + atomic rename, refusing overwrite."""
        if not isinstance(raw_bytes, bytes):
            raise TypeError("raw response must be bytes; parsed JSON is not a raw response")
        digest = sha256_bytes(raw_bytes)
        target = self.path_for(call_dedup_identity, digest)
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists():
            if target.read_bytes() != raw_bytes:
                raise ImmutableAssetError(f"immutable archive collision: {target}")
            return target, digest
        fd, tmp_name = tempfile.mkstemp(prefix=f".{target.name}.", dir=target.parent)
        try:
            with os.fdopen(fd, "wb") as handle:
                handle.write(raw_bytes)
                handle.flush()
                os.fsync(handle.fileno())
            # Link provides create-if-absent semantics. It cannot replace a file.
            try:
                os.link(tmp_name, target)
            except FileExistsError:
                if target.read_bytes() != raw_bytes:
                    raise ImmutableAssetError(f"immutable archive collision: {target}")
            os.chmod(target, 0o444)
        finally:
            Path(tmp_name).unlink(missing_ok=True)
        return target, digest

    @staticmethod
    def verify(path: Path | str, expected_sha256: str) -> bool:
        return sha256_bytes(Path(path).read_bytes()) == expected_sha256

    @staticmethod
    def response_identity(raw_sha256: str, attempt_identity: str) -> str:
        return stable_identity("raw_provider_response_v1", {
            "raw_response_sha256": raw_sha256,
            "provider_call_attempt_identity": attempt_identity,
        })
