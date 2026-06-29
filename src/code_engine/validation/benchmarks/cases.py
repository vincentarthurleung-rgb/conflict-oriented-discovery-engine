"""Benchmark case contracts and streaming loader."""

from pathlib import Path

from pydantic import Field

from code_engine.schemas.models import CODEBaseModel


class AggregatorBenchmarkCase(CODEBaseModel):
    case_id: str
    description: str
    anchor: dict
    signals_path: str
    expected_status: str
    expected_min_confidence: float | None = None
    expected_warnings_contains: list[str] = Field(default_factory=list)
    plan_status: str = "allowed"
    execution_mode: str = "local_index"


def load_benchmark_cases(path: str | Path) -> list[AggregatorBenchmarkCase]:
    source = Path(path)
    with source.open("r", encoding="utf-8") as handle:
        return [AggregatorBenchmarkCase.model_validate_json(line) for line in handle if line.strip()]


__all__ = ["AggregatorBenchmarkCase", "load_benchmark_cases"]
