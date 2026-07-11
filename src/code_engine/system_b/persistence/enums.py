"""Shared persistence enum values.

Values are stored as strings to keep SQLite migrations simple and auditable.
"""
from __future__ import annotations

ROLES = ("owner", "admin", "developer", "reviewer", "pharma")
PROJECT_NAMESPACES = ("pilot", "production", "calibration", "test")
PROJECT_STATUSES = ("draft", "active", "frozen", "archived")
ASSIGNMENT_ROLES = ("primary", "secondary", "expert", "adjudicator")
ASSIGNMENT_STATUSES = ("assigned", "in_progress", "submitted", "skipped", "revisit", "completed")
ANNOTATION_DISPOSITIONS = ("submitted", "skipped", "revisit", "draft")
ANNOTATION_STATUSES = ("draft", "submitted", "superseded")
GOLD_STATUSES = ("draft", "candidate", "adjudicated", "frozen", "superseded")
METRIC_STATUSES = (
    "ready",
    "partial",
    "needs_annotation",
    "needs_adjudication",
    "not_applicable",
    "insufficient_sample",
    "configuration_mismatch",
    "failed",
    "not_implemented",
)
