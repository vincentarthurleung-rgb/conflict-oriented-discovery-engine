"""Preferred configuration API with audited legacy-path compatibility."""

from code_engine.config.loader import (
    DEFAULT_CONFIG_PATH,
    FALLBACK_AUDIT_PATH,
    ConfigValidationError,
    PipelineConfig,
    load_json_config,
    load_pipeline_config,
    resolve_config_path,
    write_fallback_audit,
)

__all__ = [
    "DEFAULT_CONFIG_PATH", "FALLBACK_AUDIT_PATH", "ConfigValidationError",
    "PipelineConfig", "load_json_config", "load_pipeline_config",
    "resolve_config_path", "write_fallback_audit",
]

