"""Compatibility wrapper for the relocated config loader.

New code should import from `src.config.loader`. This module remains so older
pipeline imports continue to work.
"""

from src.config.loader import (  # noqa: F401
    DEFAULT_CONFIG_PATH,
    FALLBACK_AUDIT_PATH,
    ConfigValidationError,
    PipelineConfig,
    load_json_config,
    load_pipeline_config,
    write_fallback_audit,
)
