"""Schemas and checks for Stage1 weighted payload audit."""

from __future__ import annotations

from typing import Any, Dict, List

from pydantic import BaseModel, Field


class PayloadAudit(BaseModel):
    """Structured Stage1 payload validation audit."""

    payload_dir: str
    total_payloads: int = 0
    warnings: List[Dict[str, Any]] = Field(default_factory=list)
    errors: List[Dict[str, Any]] = Field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.errors
