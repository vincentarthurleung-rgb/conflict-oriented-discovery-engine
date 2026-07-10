"""assignments annotations and events"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0003_assignments_annotations_and_events"
down_revision = "0002_evaluation_projects_and_review_items"
branch_labels = None
depends_on = None


ASSIGNMENT_ROLES = "'primary', 'secondary', 'expert', 'adjudicator'"
ASSIGNMENT_STATUSES = "'assigned', 'in_progress', 'submitted', 'skipped', 'revisit', 'completed'"
ANNOTATION_DISPOSITIONS = "'submitted', 'skipped', 'revisit', 'draft'"
ANNOTATION_STATUSES = "'draft', 'submitted', 'superseded'"
NAMESPACES = "'pilot', 'production', 'calibration', 'test'"


def upgrade() -> None:
    op.create_table(
        "assignment_batches",
        sa.Column("batch_id", sa.String(36), primary_key=True),
        sa.Column("project_id", sa.String(36), nullable=False),
        sa.Column("reviewer_user_id", sa.String(36), nullable=False),
        sa.Column("batch_index", sa.Integer(), nullable=False),
        sa.Column("batch_size", sa.Integer(), nullable=False),
        sa.Column("filter_json", sa.Text(), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("assigned_by_user_id", sa.String(36)),
        sa.Column("assigned_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("due_at", sa.DateTime(timezone=True)),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.ForeignKeyConstraint(["assigned_by_user_id"], ["users.user_id"]),
        sa.ForeignKeyConstraint(["project_id"], ["evaluation_projects.project_id"]),
        sa.ForeignKeyConstraint(["reviewer_user_id"], ["users.user_id"]),
    )
    op.create_index("ix_assignment_batches_project_id", "assignment_batches", ["project_id"])
    op.create_index("ix_assignment_batches_reviewer_user_id", "assignment_batches", ["reviewer_user_id"])

    op.create_table(
        "assignments",
        sa.Column("assignment_id", sa.String(36), primary_key=True),
        sa.Column("project_id", sa.String(36), nullable=False),
        sa.Column("batch_id", sa.String(36)),
        sa.Column("review_item_id", sa.String(512), nullable=False),
        sa.Column("reviewer_user_id", sa.String(36), nullable=False),
        sa.Column("assignment_role", sa.String(32), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("assigned_by_user_id", sa.String(36)),
        sa.Column("assigned_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True)),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.CheckConstraint(f"assignment_role IN ({ASSIGNMENT_ROLES})", name="ck_assignments_role"),
        sa.CheckConstraint(f"status IN ({ASSIGNMENT_STATUSES})", name="ck_assignments_status"),
        sa.ForeignKeyConstraint(["assigned_by_user_id"], ["users.user_id"]),
        sa.ForeignKeyConstraint(["batch_id"], ["assignment_batches.batch_id"]),
        sa.ForeignKeyConstraint(["project_id"], ["evaluation_projects.project_id"]),
        sa.ForeignKeyConstraint(["review_item_id"], ["review_items.review_item_id"]),
        sa.ForeignKeyConstraint(["reviewer_user_id"], ["users.user_id"]),
        sa.UniqueConstraint("project_id", "review_item_id", "reviewer_user_id", "assignment_role", name="uq_assignment_role_per_user_item"),
    )
    op.create_index("ix_assignments_project_id", "assignments", ["project_id"])
    op.create_index("ix_assignments_batch_id", "assignments", ["batch_id"])
    op.create_index("ix_assignments_review_item_id", "assignments", ["review_item_id"])
    op.create_index("ix_assignments_reviewer_user_id", "assignments", ["reviewer_user_id"])

    op.create_table(
        "annotations",
        sa.Column("annotation_id", sa.String(36), primary_key=True),
        sa.Column("project_id", sa.String(36), nullable=False),
        sa.Column("review_item_id", sa.String(512), nullable=False),
        sa.Column("assignment_id", sa.String(36)),
        sa.Column("reviewer_user_id", sa.String(36), nullable=False),
        sa.Column("reviewer_username_snapshot", sa.String(80), nullable=False),
        sa.Column("reviewer_display_name_snapshot", sa.String(160), nullable=False),
        sa.Column("reviewer_role_snapshot", sa.String(32), nullable=False),
        sa.Column("namespace", sa.String(32), nullable=False),
        sa.Column("schema_version", sa.String(40), nullable=False),
        sa.Column("final_label", sa.String(80), nullable=False),
        sa.Column("structured_fields_json", sa.Text(), nullable=False),
        sa.Column("notes", sa.Text(), nullable=False),
        sa.Column("review_disposition", sa.String(32), nullable=False),
        sa.Column("uncertainty_reason", sa.String(120), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("client_submission_id", sa.String(120)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("submitted_at", sa.DateTime(timezone=True)),
        sa.CheckConstraint(f"namespace IN ({NAMESPACES})", name="ck_annotations_namespace"),
        sa.CheckConstraint(f"review_disposition IN ({ANNOTATION_DISPOSITIONS})", name="ck_annotations_disposition"),
        sa.CheckConstraint(f"status IN ({ANNOTATION_STATUSES})", name="ck_annotations_status"),
        sa.ForeignKeyConstraint(["assignment_id"], ["assignments.assignment_id"]),
        sa.ForeignKeyConstraint(["project_id"], ["evaluation_projects.project_id"]),
        sa.ForeignKeyConstraint(["review_item_id"], ["review_items.review_item_id"]),
        sa.ForeignKeyConstraint(["reviewer_user_id"], ["users.user_id"]),
        sa.UniqueConstraint("project_id", "review_item_id", "reviewer_user_id", "namespace", name="uq_current_annotation_per_user_item"),
        sa.UniqueConstraint("project_id", "reviewer_user_id", "client_submission_id", name="uq_annotation_client_submission"),
    )
    op.create_index("ix_annotations_project_id", "annotations", ["project_id"])
    op.create_index("ix_annotations_review_item_id", "annotations", ["review_item_id"])
    op.create_index("ix_annotations_reviewer_user_id", "annotations", ["reviewer_user_id"])
    op.create_index("ix_annotations_client_submission_id", "annotations", ["client_submission_id"])

    op.create_table(
        "annotation_events",
        sa.Column("event_id", sa.String(36), primary_key=True),
        sa.Column("annotation_id", sa.String(36), nullable=False),
        sa.Column("project_id", sa.String(36), nullable=False),
        sa.Column("review_item_id", sa.String(512), nullable=False),
        sa.Column("actor_user_id", sa.String(36)),
        sa.Column("actor_username_snapshot", sa.String(80), nullable=False),
        sa.Column("action", sa.String(80), nullable=False),
        sa.Column("previous_revision", sa.Integer()),
        sa.Column("new_revision", sa.Integer(), nullable=False),
        sa.Column("changed_fields_json", sa.Text(), nullable=False),
        sa.Column("full_snapshot_json", sa.Text(), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("request_id", sa.String(80)),
        sa.Column("ip_hash", sa.String(64)),
        sa.Column("session_hash", sa.String(64)),
        sa.ForeignKeyConstraint(["actor_user_id"], ["users.user_id"]),
        sa.ForeignKeyConstraint(["annotation_id"], ["annotations.annotation_id"]),
        sa.ForeignKeyConstraint(["project_id"], ["evaluation_projects.project_id"]),
        sa.ForeignKeyConstraint(["review_item_id"], ["review_items.review_item_id"]),
    )
    op.create_index("ix_annotation_events_annotation_id", "annotation_events", ["annotation_id"])
    op.create_index("ix_annotation_events_project_id", "annotation_events", ["project_id"])
    op.create_index("ix_annotation_events_review_item_id", "annotation_events", ["review_item_id"])
    op.create_index("ix_annotation_events_action", "annotation_events", ["action"])


def downgrade() -> None:
    op.drop_index("ix_annotation_events_action", table_name="annotation_events")
    op.drop_index("ix_annotation_events_review_item_id", table_name="annotation_events")
    op.drop_index("ix_annotation_events_project_id", table_name="annotation_events")
    op.drop_index("ix_annotation_events_annotation_id", table_name="annotation_events")
    op.drop_table("annotation_events")
    op.drop_index("ix_annotations_client_submission_id", table_name="annotations")
    op.drop_index("ix_annotations_reviewer_user_id", table_name="annotations")
    op.drop_index("ix_annotations_review_item_id", table_name="annotations")
    op.drop_index("ix_annotations_project_id", table_name="annotations")
    op.drop_table("annotations")
    op.drop_index("ix_assignments_reviewer_user_id", table_name="assignments")
    op.drop_index("ix_assignments_review_item_id", table_name="assignments")
    op.drop_index("ix_assignments_batch_id", table_name="assignments")
    op.drop_index("ix_assignments_project_id", table_name="assignments")
    op.drop_table("assignments")
    op.drop_index("ix_assignment_batches_reviewer_user_id", table_name="assignment_batches")
    op.drop_index("ix_assignment_batches_project_id", table_name="assignment_batches")
    op.drop_table("assignment_batches")
