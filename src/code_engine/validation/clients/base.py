"""Structured remote request planning contracts."""

from typing import Any

from pydantic import Field

from code_engine.schemas.models import CODEBaseModel


class RemoteRequestPlan(CODEBaseModel):
    client_name: str
    method: str = "GET"
    endpoint: str
    params: dict[str, Any] = Field(default_factory=dict)
    headers: dict[str, str] = Field(default_factory=dict)
    status: str = "planned"
    reason: str = "remote_execution_not_requested"


class RemoteRequestResult(CODEBaseModel):
    status: str
    records: list[dict[str, Any]] = Field(default_factory=list)
    raw_payload_path: str | None = None
    raw_payload_bytes_written: int = 0
    warnings: list[str] = Field(default_factory=list)
    error: str | None = None


__all__ = ["RemoteRequestPlan", "RemoteRequestResult"]
