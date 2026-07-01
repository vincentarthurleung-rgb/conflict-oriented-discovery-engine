"""Runtime-only publication year filtering shared by acquisition and reasoning."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Iterable


@dataclass(frozen=True)
class PaperYearFilter:
    paper_year_from: int | None = None
    paper_year_to: int | None = None
    temporal_role: str = "unrestricted"
    source: str = "default"

    def __post_init__(self) -> None:
        if self.temporal_role not in {"discovery", "validation", "unrestricted"}:
            raise ValueError("temporal_role must be discovery, validation, or unrestricted")
        if self.paper_year_from is not None and self.paper_year_to is not None and self.paper_year_from > self.paper_year_to:
            raise ValueError("paper_year_from cannot be greater than paper_year_to")

    @property
    def enabled(self) -> bool:
        return self.paper_year_from is not None or self.paper_year_to is not None

    def includes(self, year: Any) -> bool:
        if not self.enabled:
            return True
        parsed = publication_year(year)
        if parsed is None:
            return False
        return ((self.paper_year_from is None or parsed >= self.paper_year_from) and
                (self.paper_year_to is None or parsed <= self.paper_year_to))

    def to_dict(self) -> dict[str, Any]:
        return {"enabled": self.enabled, **asdict(self), "hardcoded_cutoff_used": False}


def publication_year(paper_or_year: Any) -> int | None:
    value = paper_or_year
    if isinstance(value, dict):
        value = next((value.get(key) for key in ("publication_year", "year", "pub_year", "publication_date") if value.get(key) not in (None, "")), None)
    try:
        text = str(value).strip()
        return int(text[:4]) if len(text) >= 4 else int(text)
    except (TypeError, ValueError):
        return None


def filter_papers_by_year(papers: Iterable[dict[str, Any]], config: PaperYearFilter) -> tuple[list[dict[str, Any]], dict[str, int]]:
    values = list(papers)
    if not config.enabled:
        return values, {"papers_retrieved_before_year_filter": len(values), "papers_excluded_by_year_filter": 0,
                        "papers_missing_year_excluded": 0, "papers_after_year_filter": len(values)}
    kept, missing = [], 0
    for paper in values:
        year = publication_year(paper)
        if year is None:
            missing += 1
        elif config.includes(year):
            kept.append(paper)
    return kept, {"papers_retrieved_before_year_filter": len(values),
                  "papers_excluded_by_year_filter": len(values) - len(kept),
                  "papers_missing_year_excluded": missing, "papers_after_year_filter": len(kept)}


def paper_year_filter_from_dict(value: dict[str, Any] | PaperYearFilter | None) -> PaperYearFilter:
    if isinstance(value, PaperYearFilter):
        return value
    data = dict(value or {})
    return PaperYearFilter(paper_year_from=data.get("paper_year_from"), paper_year_to=data.get("paper_year_to"),
                           temporal_role=data.get("temporal_role", "unrestricted"),
                           source=data.get("source", "default"))


def pubmed_date_clause(config: PaperYearFilter) -> str:
    if not config.enabled:
        return ""
    lower = str(config.paper_year_from) if config.paper_year_from is not None else "1900"
    upper = str(config.paper_year_to) if config.paper_year_to is not None else "3000"
    return f'(\"{lower}\"[Date - Publication] : \"{upper}\"[Date - Publication])'


__all__ = ["PaperYearFilter", "filter_papers_by_year", "paper_year_filter_from_dict", "publication_year", "pubmed_date_clause"]
