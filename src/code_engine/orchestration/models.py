"""Typed request/result models for one-command case orchestration."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

STAGES = ("base_run", "pmcid_repair", "fulltext_l1", "reentry", "handoff", "atlas_sync", "verification")


@dataclass(frozen=True)
class CaseToAtlasRequest:
    case_id: str
    case_profile_path: Path | None = None
    search_plan_path: Path | None = None
    runs_root: Path = Path("runs")
    system_b_output_root: Path = Path("system_b_outputs/system_a_sync")
    database_url: str = "sqlite:///data/code_atlas.db"
    external_data_root: Path = Path("data/external")
    network_enabled: bool = False
    api_enabled: bool = False
    resume: bool = True
    force_stages: frozenset[str] = frozenset()
    stop_after: str | None = None
    publish_handoff: bool = True
    atlas_sync: bool = True
    dry_run: bool = False

    def resolved(self) -> "CaseToAtlasRequest":
        package = Path("configs/generated_cases") / self.case_id
        return CaseToAtlasRequest(
            **{**asdict(self),
               "case_profile_path": Path(self.case_profile_path or package / "case_profile.json"),
               "search_plan_path": Path(self.search_plan_path or package / "search_plan.frozen.json"),
               "runs_root": Path(self.runs_root), "system_b_output_root": Path(self.system_b_output_root),
               "external_data_root": Path(self.external_data_root), "force_stages": frozenset(self.force_stages)}
        )

    def to_dict(self) -> dict[str, Any]:
        value = asdict(self)
        for key in ("case_profile_path", "search_plan_path", "runs_root", "system_b_output_root", "external_data_root"):
            value[key] = str(value[key]) if value[key] is not None else None
        value["force_stages"] = sorted(value["force_stages"])
        return value


@dataclass
class CaseToAtlasResult:
    orchestration_id: str
    status: str
    case_id: str
    base_run: str | None = None
    pmcid_repair_run: str | None = None
    fulltext_run: str | None = None
    reentry_run: str | None = None
    handoff_manifest: str | None = None
    handoff_status: str | None = None
    ingestion_id: str | None = None
    prediction_run_id: str | None = None
    projection_id: str | None = None
    current_case_count: int = 0
    claim_count: int = 0
    dossier_count: int = 0
    context_row_count: int = 0
    exploratory_triple_count: int = 0
    formal_conflict_count: int = 0
    api_calls: int = 0
    network_calls: int = 0
    cache_hits: int = 0
    reused_stages: list[str] = field(default_factory=list)
    sync_status: str | None = None
    warnings: list[str] = field(default_factory=list)
    verification: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
