"""Provider attempt state machine and dedup ledger; contains no provider client."""
from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from typing import Iterable

from .models import AttemptStatus, ProviderCallAttempt

TRANSITIONS: dict[AttemptStatus, set[AttemptStatus]] = {
    AttemptStatus.prepared: {AttemptStatus.cache_hit, AttemptStatus.provider_in_flight, AttemptStatus.abandoned},
    AttemptStatus.provider_in_flight: {
        AttemptStatus.provider_transport_failed, AttemptStatus.provider_http_failed,
        AttemptStatus.raw_response_received,
    },
    AttemptStatus.raw_response_received: {
        AttemptStatus.raw_response_persisted, AttemptStatus.raw_response_persistence_failed,
    },
    AttemptStatus.raw_response_persistence_failed: {AttemptStatus.abandoned},
    AttemptStatus.raw_response_persisted: {AttemptStatus.parse_pending, AttemptStatus.completed},
    AttemptStatus.parse_pending: {AttemptStatus.parsed, AttemptStatus.parse_failed},
    AttemptStatus.parsed: {AttemptStatus.validation_pending, AttemptStatus.completed},
    AttemptStatus.parse_failed: {AttemptStatus.parse_pending, AttemptStatus.abandoned},
    AttemptStatus.validation_pending: {
        AttemptStatus.schema_validation_failed, AttemptStatus.scientific_validation_failed,
        AttemptStatus.completed,
    },
    AttemptStatus.schema_validation_failed: {AttemptStatus.validation_pending, AttemptStatus.abandoned},
    AttemptStatus.scientific_validation_failed: {AttemptStatus.validation_pending, AttemptStatus.abandoned},
    AttemptStatus.cache_hit: {AttemptStatus.parse_pending, AttemptStatus.completed},
    AttemptStatus.provider_transport_failed: {AttemptStatus.abandoned},
    AttemptStatus.provider_http_failed: {AttemptStatus.abandoned},
    AttemptStatus.completed: {AttemptStatus.superseded},
    AttemptStatus.abandoned: {AttemptStatus.superseded},
    AttemptStatus.superseded: set(),
}


def transition(attempt: ProviderCallAttempt, status: AttemptStatus, **updates: object) -> ProviderCallAttempt:
    if status not in TRANSITIONS[attempt.status]:
        raise ValueError(f"invalid attempt transition: {attempt.status.value} -> {status.value}")
    # Crucial billing rule: parse/schema/scientific failures never transition to in-flight.
    payload = attempt.model_dump()
    payload.update(updates)
    payload["status"] = status
    payload["state_history"] = [*attempt.state_history, status.value]
    return ProviderCallAttempt.model_validate(payload)


class CallLedger:
    def __init__(self, attempts: Iterable[ProviderCallAttempt] = ()):
        self._attempts = list(attempts)

    def reusable_raw_identity(self, call_dedup_identity: str) -> str | None:
        matches = [
            row.raw_response_identity for row in self._attempts
            if row.call_dedup_identity == call_dedup_identity
            and row.raw_response_identity
            and row.status in {
                AttemptStatus.raw_response_persisted, AttemptStatus.parse_pending,
                AttemptStatus.parsed, AttemptStatus.parse_failed,
                AttemptStatus.validation_pending, AttemptStatus.completed,
            }
        ]
        unique = set(matches)
        if len(unique) > 1:
            raise ValueError("duplicate paid-call identity claims multiple raw responses")
        return matches[0] if matches else None

    def should_call_provider(self, call_dedup_identity: str) -> bool:
        return self.reusable_raw_identity(call_dedup_identity) is None

    def add(self, attempt: ProviderCallAttempt) -> None:
        self._attempts.append(attempt)

    @property
    def real_api_calls(self) -> int:
        return sum(row.real_api_call for row in self._attempts if row.status != AttemptStatus.cache_hit)
