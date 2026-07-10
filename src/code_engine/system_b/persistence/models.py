"""SQLAlchemy 2.x declarative models for Atlas formal evaluation state."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

from .enums import (
    ANNOTATION_DISPOSITIONS,
    ANNOTATION_STATUSES,
    ASSIGNMENT_ROLES,
    ASSIGNMENT_STATUSES,
    GOLD_STATUSES,
    METRIC_STATUSES,
    PROJECT_NAMESPACES,
    PROJECT_STATUSES,
    ROLES,
)


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def uuid_text() -> str:
    return str(uuid.uuid4())


def _check(name: str, column: str, values: tuple[str, ...]) -> CheckConstraint:
    quoted = ", ".join(f"'{x}'" for x in values)
    return CheckConstraint(f"{column} IN ({quoted})", name=name)


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"
    user_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_text)
    username: Mapped[str] = mapped_column(String(80), unique=True, index=True, nullable=False)
    display_name: Mapped[str] = mapped_column(String(160), nullable=False)
    password_hash: Mapped[str] = mapped_column(Text, nullable=False)
    role: Mapped[str] = mapped_column(String(32), nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    __table_args__ = (_check("ck_users_role", "role", ROLES),)
    # SQLite enforces the enabled-owner uniqueness through Alembic partial index.


class Invite(Base):
    __tablename__ = "invites"
    invite_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_text)
    code_hash: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    label: Mapped[str] = mapped_column(String(160), nullable=False)
    role: Mapped[str] = mapped_column(String(32), nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    max_uses: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    uses: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_by_user_id: Mapped[str | None] = mapped_column(ForeignKey("users.user_id"))
    __table_args__ = (_check("ck_invites_role", "role", ROLES),)


class SystemSetting(Base):
    __tablename__ = "system_settings"
    key: Mapped[str] = mapped_column(String(120), primary_key=True)
    value: Mapped[str] = mapped_column(Text, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)


class EvaluationProject(Base):
    __tablename__ = "evaluation_projects"
    project_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_text)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="", nullable=False)
    namespace: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="draft", nullable=False)
    created_by_user_id: Mapped[str | None] = mapped_column(ForeignKey("users.user_id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)
    __table_args__ = (
        _check("ck_evaluation_projects_namespace", "namespace", PROJECT_NAMESPACES),
        _check("ck_evaluation_projects_status", "status", PROJECT_STATUSES),
    )


class EvaluationProtocol(Base):
    __tablename__ = "evaluation_protocols"
    protocol_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_text)
    project_id: Mapped[str] = mapped_column(ForeignKey("evaluation_projects.project_id"), nullable=False, index=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    protocol_json: Mapped[str] = mapped_column(Text, nullable=False)
    case_ids_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    metric_registry_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    annotation_schema_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    dataset_split_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    frozen: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_by_user_id: Mapped[str | None] = mapped_column(ForeignKey("users.user_id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    frozen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    __table_args__ = (UniqueConstraint("project_id", "version", name="uq_protocol_project_version"),)


class DatasetSplit(Base):
    __tablename__ = "dataset_splits"
    split_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_text)
    project_id: Mapped[str] = mapped_column(ForeignKey("evaluation_projects.project_id"), nullable=False, index=True)
    split_name: Mapped[str] = mapped_column(String(80), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    __table_args__ = (UniqueConstraint("project_id", "split_name", name="uq_dataset_split_project_name"),)


class DatasetSplitCase(Base):
    __tablename__ = "dataset_split_cases"
    split_case_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_text)
    split_id: Mapped[str] = mapped_column(ForeignKey("dataset_splits.split_id"), nullable=False, index=True)
    case_id: Mapped[str] = mapped_column(String(240), nullable=False, index=True)
    __table_args__ = (UniqueConstraint("split_id", "case_id", name="uq_dataset_split_case"),)


class ReviewItem(Base):
    __tablename__ = "review_items"
    review_item_id: Mapped[str] = mapped_column(String(512), primary_key=True)
    case_id: Mapped[str] = mapped_column(String(240), nullable=False, index=True)
    item_type: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    source_scope: Mapped[str | None] = mapped_column(String(120))
    source_file: Mapped[str | None] = mapped_column(Text)
    source_line: Mapped[int | None] = mapped_column(Integer)
    payload_json: Mapped[str] = mapped_column(Text, nullable=False)
    source_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    import_run_id: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    namespace: Mapped[str] = mapped_column(String(32), nullable=False, default="test")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    __table_args__ = (
        UniqueConstraint("review_item_id", "source_hash", name="uq_review_item_source_hash"),
        _check("ck_review_items_namespace", "namespace", PROJECT_NAMESPACES),
    )


class AssignmentBatch(Base):
    __tablename__ = "assignment_batches"
    batch_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_text)
    project_id: Mapped[str] = mapped_column(ForeignKey("evaluation_projects.project_id"), nullable=False, index=True)
    reviewer_user_id: Mapped[str] = mapped_column(ForeignKey("users.user_id"), nullable=False, index=True)
    batch_index: Mapped[int] = mapped_column(Integer, nullable=False)
    batch_size: Mapped[int] = mapped_column(Integer, nullable=False)
    filter_json: Mapped[str] = mapped_column(Text, default="{}", nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="assigned", nullable=False)
    assigned_by_user_id: Mapped[str | None] = mapped_column(ForeignKey("users.user_id"))
    assigned_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Assignment(Base):
    __tablename__ = "assignments"
    assignment_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_text)
    project_id: Mapped[str] = mapped_column(ForeignKey("evaluation_projects.project_id"), nullable=False, index=True)
    batch_id: Mapped[str | None] = mapped_column(ForeignKey("assignment_batches.batch_id"), index=True)
    review_item_id: Mapped[str] = mapped_column(ForeignKey("review_items.review_item_id"), nullable=False, index=True)
    reviewer_user_id: Mapped[str] = mapped_column(ForeignKey("users.user_id"), nullable=False, index=True)
    assignment_role: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="assigned", nullable=False)
    assigned_by_user_id: Mapped[str | None] = mapped_column(ForeignKey("users.user_id"))
    assigned_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    __table_args__ = (
        UniqueConstraint("project_id", "review_item_id", "reviewer_user_id", "assignment_role", name="uq_assignment_role_per_user_item"),
        _check("ck_assignments_role", "assignment_role", ASSIGNMENT_ROLES),
        _check("ck_assignments_status", "status", ASSIGNMENT_STATUSES),
    )


class Annotation(Base):
    __tablename__ = "annotations"
    annotation_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_text)
    project_id: Mapped[str] = mapped_column(ForeignKey("evaluation_projects.project_id"), nullable=False, index=True)
    review_item_id: Mapped[str] = mapped_column(ForeignKey("review_items.review_item_id"), nullable=False, index=True)
    assignment_id: Mapped[str | None] = mapped_column(ForeignKey("assignments.assignment_id"))
    reviewer_user_id: Mapped[str] = mapped_column(ForeignKey("users.user_id"), nullable=False, index=True)
    reviewer_username_snapshot: Mapped[str] = mapped_column(String(80), nullable=False)
    reviewer_display_name_snapshot: Mapped[str] = mapped_column(String(160), nullable=False)
    reviewer_role_snapshot: Mapped[str] = mapped_column(String(32), nullable=False)
    namespace: Mapped[str] = mapped_column(String(32), nullable=False)
    schema_version: Mapped[str] = mapped_column(String(40), default="atlas_annotation_v1", nullable=False)
    final_label: Mapped[str] = mapped_column(String(80), default="", nullable=False)
    structured_fields_json: Mapped[str] = mapped_column(Text, default="{}", nullable=False)
    notes: Mapped[str] = mapped_column(Text, default="", nullable=False)
    review_disposition: Mapped[str] = mapped_column(String(32), default="draft", nullable=False)
    uncertainty_reason: Mapped[str] = mapped_column(String(120), default="", nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="draft", nullable=False)
    revision: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    client_submission_id: Mapped[str | None] = mapped_column(String(120), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    events: Mapped[list["AnnotationEvent"]] = relationship(back_populates="annotation")
    __table_args__ = (
        UniqueConstraint("project_id", "review_item_id", "reviewer_user_id", "namespace", name="uq_current_annotation_per_user_item"),
        UniqueConstraint("project_id", "reviewer_user_id", "client_submission_id", name="uq_annotation_client_submission"),
        _check("ck_annotations_namespace", "namespace", PROJECT_NAMESPACES),
        _check("ck_annotations_disposition", "review_disposition", ANNOTATION_DISPOSITIONS),
        _check("ck_annotations_status", "status", ANNOTATION_STATUSES),
    )


class AnnotationEvent(Base):
    __tablename__ = "annotation_events"
    event_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_text)
    annotation_id: Mapped[str] = mapped_column(ForeignKey("annotations.annotation_id"), nullable=False, index=True)
    project_id: Mapped[str] = mapped_column(ForeignKey("evaluation_projects.project_id"), nullable=False, index=True)
    review_item_id: Mapped[str] = mapped_column(ForeignKey("review_items.review_item_id"), nullable=False, index=True)
    actor_user_id: Mapped[str | None] = mapped_column(ForeignKey("users.user_id"))
    actor_username_snapshot: Mapped[str] = mapped_column(String(80), nullable=False)
    action: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    previous_revision: Mapped[int | None] = mapped_column(Integer)
    new_revision: Mapped[int] = mapped_column(Integer, nullable=False)
    changed_fields_json: Mapped[str] = mapped_column(Text, default="{}", nullable=False)
    full_snapshot_json: Mapped[str] = mapped_column(Text, nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    request_id: Mapped[str | None] = mapped_column(String(80))
    ip_hash: Mapped[str | None] = mapped_column(String(64))
    session_hash: Mapped[str | None] = mapped_column(String(64))
    annotation: Mapped[Annotation] = relationship(back_populates="events")


class Adjudication(Base):
    __tablename__ = "adjudications"
    adjudication_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_text)
    project_id: Mapped[str] = mapped_column(ForeignKey("evaluation_projects.project_id"), nullable=False, index=True)
    review_item_id: Mapped[str] = mapped_column(ForeignKey("review_items.review_item_id"), nullable=False, index=True)
    adjudicator_user_id: Mapped[str] = mapped_column(ForeignKey("users.user_id"), nullable=False)
    adjudicator_username_snapshot: Mapped[str] = mapped_column(String(80), nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="draft", nullable=False)
    final_label: Mapped[str] = mapped_column(String(80), default="", nullable=False)
    structured_gold_json: Mapped[str] = mapped_column(Text, default="{}", nullable=False)
    notes: Mapped[str] = mapped_column(Text, default="", nullable=False)
    schema_version: Mapped[str] = mapped_column(String(40), default="atlas_gold_v1", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revision: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    __table_args__ = (UniqueConstraint("project_id", "review_item_id", name="uq_adjudication_current_item"),)


class AdjudicationSource(Base):
    __tablename__ = "adjudication_sources"
    adjudication_source_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_text)
    adjudication_id: Mapped[str] = mapped_column(ForeignKey("adjudications.adjudication_id"), nullable=False)
    annotation_id: Mapped[str] = mapped_column(ForeignKey("annotations.annotation_id"), nullable=False)
    __table_args__ = (UniqueConstraint("adjudication_id", "annotation_id", name="uq_adjudication_source"),)


class GoldRecord(Base):
    __tablename__ = "gold_records"
    gold_record_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_text)
    project_id: Mapped[str] = mapped_column(ForeignKey("evaluation_projects.project_id"), nullable=False, index=True)
    protocol_id: Mapped[str] = mapped_column(ForeignKey("evaluation_protocols.protocol_id"), nullable=False, index=True)
    review_item_id: Mapped[str] = mapped_column(ForeignKey("review_items.review_item_id"), nullable=False, index=True)
    adjudication_id: Mapped[str | None] = mapped_column(ForeignKey("adjudications.adjudication_id"))
    final_gold_label: Mapped[str] = mapped_column(String(80), nullable=False)
    structured_gold_json: Mapped[str] = mapped_column(Text, default="{}", nullable=False)
    schema_version: Mapped[str] = mapped_column(String(40), default="atlas_gold_v1", nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="draft", nullable=False)
    frozen_by_user_id: Mapped[str | None] = mapped_column(ForeignKey("users.user_id"))
    frozen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    gold_version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    __table_args__ = (
        UniqueConstraint("project_id", "review_item_id", "gold_version", name="uq_gold_project_item_version"),
        _check("ck_gold_status", "status", GOLD_STATUSES),
    )


class MetricDefinition(Base):
    __tablename__ = "metric_definitions"
    metric_id: Mapped[str] = mapped_column(String(120), primary_key=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    metric_group: Mapped[str] = mapped_column(String(120), nullable=False)
    formula_version: Mapped[str] = mapped_column(String(80), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="", nullable=False)
    unit: Mapped[str] = mapped_column(String(80), default="", nullable=False)
    aggregation: Mapped[str] = mapped_column(String(80), default="", nullable=False)
    higher_is_better: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    required_inputs_json: Mapped[str] = mapped_column(Text, default="[]", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)


class MetricRun(Base):
    __tablename__ = "metric_runs"
    metric_run_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_text)
    project_id: Mapped[str] = mapped_column(ForeignKey("evaluation_projects.project_id"), nullable=False, index=True)
    protocol_id: Mapped[str | None] = mapped_column(ForeignKey("evaluation_protocols.protocol_id"))
    prediction_run_id: Mapped[str] = mapped_column(String(160), default="", nullable=False)
    gold_dataset_version: Mapped[str] = mapped_column(String(80), default="", nullable=False)
    git_commit: Mapped[str] = mapped_column(String(80), default="", nullable=False)
    config_json: Mapped[str] = mapped_column(Text, default="{}", nullable=False)
    config_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="ready", nullable=False)
    started_by_user_id: Mapped[str | None] = mapped_column(ForeignKey("users.user_id"))
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error_message: Mapped[str] = mapped_column(Text, default="", nullable=False)


class MetricResult(Base):
    __tablename__ = "metric_results"
    metric_result_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_text)
    metric_run_id: Mapped[str] = mapped_column(ForeignKey("metric_runs.metric_run_id"), nullable=False, index=True)
    metric_id: Mapped[str] = mapped_column(ForeignKey("metric_definitions.metric_id"), nullable=False, index=True)
    subgroup_type: Mapped[str] = mapped_column(String(120), default="", nullable=False)
    subgroup_value: Mapped[str] = mapped_column(String(240), default="", nullable=False)
    value: Mapped[float | None] = mapped_column(Float)
    ci_low: Mapped[float | None] = mapped_column(Float)
    ci_high: Mapped[float | None] = mapped_column(Float)
    sample_size_cases: Mapped[int | None] = mapped_column(Integer)
    sample_size_items: Mapped[int | None] = mapped_column(Integer)
    numerator: Mapped[float | None] = mapped_column(Float)
    denominator: Mapped[float | None] = mapped_column(Float)
    status: Mapped[str] = mapped_column(String(40), nullable=False)
    missing_reason: Mapped[str] = mapped_column(Text, default="", nullable=False)
    included_case_ids_json: Mapped[str] = mapped_column(Text, default="[]", nullable=False)
    excluded_case_ids_json: Mapped[str] = mapped_column(Text, default="[]", nullable=False)
    exclusion_reasons_json: Mapped[str] = mapped_column(Text, default="{}", nullable=False)
    provenance_json: Mapped[str] = mapped_column(Text, default="{}", nullable=False)
    computed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    __table_args__ = (_check("ck_metric_results_status", "status", METRIC_STATUSES),)


class AuditEvent(Base):
    __tablename__ = "audit_events"
    event_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_text)
    actor_user_id: Mapped[str | None] = mapped_column(ForeignKey("users.user_id"))
    actor_username_snapshot: Mapped[str] = mapped_column(String(80), default="", nullable=False)
    action: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    object_type: Mapped[str] = mapped_column(String(120), nullable=False)
    object_id: Mapped[str] = mapped_column(String(240), default="", nullable=False)
    project_id: Mapped[str | None] = mapped_column(ForeignKey("evaluation_projects.project_id"))
    case_id: Mapped[str] = mapped_column(String(240), default="", nullable=False)
    review_item_id: Mapped[str] = mapped_column(String(512), default="", nullable=False)
    metadata_json: Mapped[str] = mapped_column(Text, default="{}", nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    request_id: Mapped[str | None] = mapped_column(String(80))
    ip_hash: Mapped[str | None] = mapped_column(String(64))
    session_hash: Mapped[str | None] = mapped_column(String(64))


class ExportEvent(Base):
    __tablename__ = "export_events"
    export_event_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_text)
    actor_user_id: Mapped[str | None] = mapped_column(ForeignKey("users.user_id"))
    actor_username_snapshot: Mapped[str] = mapped_column(String(80), default="", nullable=False)
    export_type: Mapped[str] = mapped_column(String(120), nullable=False)
    project_id: Mapped[str | None] = mapped_column(ForeignKey("evaluation_projects.project_id"))
    protocol_id: Mapped[str | None] = mapped_column(ForeignKey("evaluation_protocols.protocol_id"))
    file_hash: Mapped[str] = mapped_column(String(64), default="", nullable=False)
    field_policy_json: Mapped[str] = mapped_column(Text, default="{}", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
