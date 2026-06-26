"""Schemas and checks for the global manifest audit."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field


class ManifestPaperEntry(BaseModel):
    """Permissive wrapper for one global manifest paper entry."""

    model_config = ConfigDict(extra="allow")

    paper_id: str
    pmid: Optional[str] = None
    pmcid: Optional[str] = None
    doi: Optional[str] = None
    source: Optional[str] = None
    type: Optional[str] = None
    raw_path: Optional[str] = None
    payload_path: Optional[str] = None


class ManifestAudit(BaseModel):
    """Structured manifest validation audit."""

    manifest_path: str
    total_papers: int = 0
    warnings: List[Dict[str, Any]] = Field(default_factory=list)
    errors: List[Dict[str, Any]] = Field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.errors
