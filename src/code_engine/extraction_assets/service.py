"""Billing-safe orchestration: archive exact bytes before invoking a parser."""
from __future__ import annotations

from collections.abc import Callable
from typing import Any

from .archive import RawResponseArchive
from .call_ledger import transition
from .models import AttemptStatus, ProviderCallAttempt


class CrashAfterRawPersistence(RuntimeError):
    pass


class ExtractionAssetService:
    def __init__(self, archive: RawResponseArchive):
        self.archive = archive

    def persist_then_parse(
        self,
        attempt: ProviderCallAttempt,
        raw_bytes: bytes,
        parser: Callable[[bytes], Any],
        *,
        crash_after_persist: bool = False,
    ) -> tuple[ProviderCallAttempt, Any | None, Exception | None, str]:
        received = transition(attempt, AttemptStatus.raw_response_received)
        path, digest = self.archive.persist(raw_bytes, attempt.call_dedup_identity)
        raw_identity = self.archive.response_identity(digest, attempt.identity)
        persisted = transition(
            received, AttemptStatus.raw_response_persisted,
            raw_response_identity=raw_identity,
        )
        if crash_after_persist:
            raise CrashAfterRawPersistence(str(path))
        pending = transition(persisted, AttemptStatus.parse_pending)
        try:
            parsed = parser(path.read_bytes())
        except Exception as exc:  # audit outcome; never retries the provider
            return transition(pending, AttemptStatus.parse_failed, failure_kind="parser"), None, exc, raw_identity
        return transition(pending, AttemptStatus.parsed), parsed, None, raw_identity

    def resume_from_raw(
        self, attempt: ProviderCallAttempt, path: str, parser: Callable[[bytes], Any],
    ) -> tuple[ProviderCallAttempt, Any | None, Exception | None]:
        if attempt.status not in {AttemptStatus.raw_response_persisted, AttemptStatus.parse_failed}:
            raise ValueError("resume requires a persisted raw response")
        pending = transition(attempt, AttemptStatus.parse_pending)
        try:
            return transition(pending, AttemptStatus.parsed), parser(open(path, "rb").read()), None
        except Exception as exc:
            return transition(pending, AttemptStatus.parse_failed, failure_kind="parser"), None, exc
