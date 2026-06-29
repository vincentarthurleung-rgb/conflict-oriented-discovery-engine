"""Fail-closed remote boundary with fake-response support for tests."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from code_engine.validation.clients.base import RemoteRequestPlan, RemoteRequestResult


class GuardedRemoteClient:
    name = "guarded_remote"
    endpoint = ""

    def can_execute(
        self, execute: bool, network_enabled: bool,
        external_validation_enabled: bool, auth_config: dict | None = None,
    ) -> tuple[bool, str]:
        if not execute:
            return False, "external_lookup_not_enabled"
        if not network_enabled:
            return False, "network_disabled"
        if not external_validation_enabled:
            return False, "external_validation_disabled"
        return True, "allowed"

    def build_request_plan(self, *, params: dict[str, Any] | None = None, endpoint: str | None = None) -> RemoteRequestPlan:
        return RemoteRequestPlan(client_name=self.name, endpoint=endpoint or self.endpoint, params=params or {})

    def execute_request(
        self, plan: RemoteRequestPlan, *, execute: bool = False,
        network_enabled: bool = False, external_validation_enabled: bool = False,
        auth_config: dict | None = None, fake_response: Any | None = None,
        raw_payload_path: str | Path | None = None, max_raw_payload_bytes: int = 5_000_000,
    ) -> RemoteRequestResult:
        allowed, reason = self.can_execute(execute, network_enabled, external_validation_enabled, auth_config)
        if fake_response is None and not allowed:
            return RemoteRequestResult(status=reason, warnings=["remote_request_not_executed"])
        if fake_response is None:
            return RemoteRequestResult(status="not_configured", warnings=["real_http_transport_not_configured"])
        payload = json.dumps(fake_response, ensure_ascii=False).encode("utf-8")
        truncated = len(payload) > max_raw_payload_bytes
        payload = payload[:max_raw_payload_bytes]
        destination = None
        if raw_payload_path:
            destination = Path(raw_payload_path)
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(payload)
        records = fake_response if isinstance(fake_response, list) else [fake_response]
        return RemoteRequestResult(
            status="completed", records=[item for item in records if isinstance(item, dict)],
            raw_payload_path=str(destination) if destination else None,
            raw_payload_bytes_written=len(payload),
            warnings=["raw_payload_truncated"] if truncated else [],
        )


__all__ = ["GuardedRemoteClient"]
