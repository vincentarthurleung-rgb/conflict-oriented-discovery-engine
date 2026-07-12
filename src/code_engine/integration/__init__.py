"""Non-invasive integration contracts between System A and downstream consumers."""

from .atlas_handoff import HANDOFF_SCHEMA_VERSION, HandoffError, publish_atlas_handoff, validate_handoff

__all__ = ["HANDOFF_SCHEMA_VERSION", "HandoffError", "publish_atlas_handoff", "validate_handoff"]
