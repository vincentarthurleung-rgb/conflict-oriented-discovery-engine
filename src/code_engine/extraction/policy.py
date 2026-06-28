"""Deterministic sampling policy for L1 extraction."""

from __future__ import annotations

from dataclasses import dataclass


DEFAULT_L1_TEMPERATURE = 0.0
DEFAULT_L1_TOP_P = 1.0
DEFAULT_L1_MAX_RETRIES = 2
DEFAULT_L1_SCHEMA_VERSION = "l1_v2_evidence_mechanism_schema"
DEFAULT_L1_POLICY_VERSION = "evidence_grounded_v2"
DEFAULT_L1_MODEL_NAME = "deepseek-v4-pro"
DEFAULT_L1_MODEL_FAMILY = "deepseek"


@dataclass(frozen=True)
class L1SamplingConfig:
    temperature: float = DEFAULT_L1_TEMPERATURE
    top_p: float = DEFAULT_L1_TOP_P
    max_retries: int = DEFAULT_L1_MAX_RETRIES
    experimental_temperature_schedule: bool = False


def get_l1_sampling_config(
    chunk_index: int = 0,
    *,
    experimental_temperature_schedule: bool = False,
) -> L1SamplingConfig:
    """Return fixed defaults unless the experimental schedule is explicit."""

    temperature = DEFAULT_L1_TEMPERATURE
    if experimental_temperature_schedule:
        temperature = round(min(1.0, 0.3 + max(0, int(chunk_index)) * 0.1), 2)
    return L1SamplingConfig(
        temperature=temperature,
        experimental_temperature_schedule=experimental_temperature_schedule,
    )
