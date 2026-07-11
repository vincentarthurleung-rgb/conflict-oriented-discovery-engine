"""Frontend-safe schema projection helpers."""
from __future__ import annotations

from .registry import AnnotationSchema


def form_projection(schema: AnnotationSchema | None) -> dict:
    if not schema:
        return {
            "configured": False,
            "message": "尚未配置正式标注 Schema",
            "fields": [],
        }
    value = schema.form_definition()
    value["configured"] = True
    return value
