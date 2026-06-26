"""Configuration loading and section-level validation for C.O.D.E."""

from .loader import (
    DEFAULT_CONFIG_PATH,
    FALLBACK_AUDIT_PATH,
    ConfigValidationError,
    PipelineConfig,
    load_json_config,
    load_pipeline_config,
    write_fallback_audit,
)

__all__ = [
    "DEFAULT_CONFIG_PATH",
    "FALLBACK_AUDIT_PATH",
    "ConfigValidationError",
    "PipelineConfig",
    "load_json_config",
    "load_pipeline_config",
    "write_fallback_audit",
]
