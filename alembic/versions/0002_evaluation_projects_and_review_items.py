"""evaluation projects and review items"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0002_evaluation_projects_and_review_items"
down_revision = "0001_core_identity_and_auth"
branch_labels = None
depends_on = None


NAMESPACES = "'pilot', 'production', 'calibration', 'test'"
PROJECT_STATUSES = "'draft', 'active', 'frozen', 'archived'"


def upgrade() -> None:
    op.create_table(
        "evaluation_projects",
        sa.Column("project_id", sa.String(36), primary_key=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("namespace", sa.String(32), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("created_by_user_id", sa.String(36)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(f"namespace IN ({NAMESPACES})", name="ck_evaluation_projects_namespace"),
        sa.CheckConstraint(f"status IN ({PROJECT_STATUSES})", name="ck_evaluation_projects_status"),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.user_id"]),
    )
    op.create_index("ix_evaluation_projects_namespace", "evaluation_projects", ["namespace"])

    op.create_table(
        "evaluation_protocols",
        sa.Column("protocol_id", sa.String(36), primary_key=True),
        sa.Column("project_id", sa.String(36), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("protocol_json", sa.Text(), nullable=False),
        sa.Column("case_ids_sha256", sa.String(64), nullable=False),
        sa.Column("metric_registry_sha256", sa.String(64), nullable=False),
        sa.Column("annotation_schema_sha256", sa.String(64), nullable=False),
        sa.Column("dataset_split_sha256", sa.String(64), nullable=False),
        sa.Column("frozen", sa.Boolean(), nullable=False),
        sa.Column("created_by_user_id", sa.String(36)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("frozen_at", sa.DateTime(timezone=True)),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.user_id"]),
        sa.ForeignKeyConstraint(["project_id"], ["evaluation_projects.project_id"]),
        sa.UniqueConstraint("project_id", "version", name="uq_protocol_project_version"),
    )
    op.create_index("ix_evaluation_protocols_project_id", "evaluation_protocols", ["project_id"])

    op.create_table(
        "dataset_splits",
        sa.Column("split_id", sa.String(36), primary_key=True),
        sa.Column("project_id", sa.String(36), nullable=False),
        sa.Column("split_name", sa.String(80), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["evaluation_projects.project_id"]),
        sa.UniqueConstraint("project_id", "split_name", name="uq_dataset_split_project_name"),
    )
    op.create_index("ix_dataset_splits_project_id", "dataset_splits", ["project_id"])

    op.create_table(
        "dataset_split_cases",
        sa.Column("split_case_id", sa.String(36), primary_key=True),
        sa.Column("split_id", sa.String(36), nullable=False),
        sa.Column("case_id", sa.String(240), nullable=False),
        sa.ForeignKeyConstraint(["split_id"], ["dataset_splits.split_id"]),
        sa.UniqueConstraint("split_id", "case_id", name="uq_dataset_split_case"),
    )
    op.create_index("ix_dataset_split_cases_split_id", "dataset_split_cases", ["split_id"])
    op.create_index("ix_dataset_split_cases_case_id", "dataset_split_cases", ["case_id"])

    op.create_table(
        "review_items",
        sa.Column("review_item_id", sa.String(512), primary_key=True),
        sa.Column("case_id", sa.String(240), nullable=False),
        sa.Column("item_type", sa.String(120), nullable=False),
        sa.Column("source_scope", sa.String(120)),
        sa.Column("source_file", sa.Text()),
        sa.Column("source_line", sa.Integer()),
        sa.Column("payload_json", sa.Text(), nullable=False),
        sa.Column("source_hash", sa.String(64), nullable=False),
        sa.Column("import_run_id", sa.String(80), nullable=False),
        sa.Column("namespace", sa.String(32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(f"namespace IN ({NAMESPACES})", name="ck_review_items_namespace"),
        sa.UniqueConstraint("review_item_id", "source_hash", name="uq_review_item_source_hash"),
    )
    op.create_index("ix_review_items_case_id", "review_items", ["case_id"])
    op.create_index("ix_review_items_item_type", "review_items", ["item_type"])
    op.create_index("ix_review_items_source_hash", "review_items", ["source_hash"])
    op.create_index("ix_review_items_import_run_id", "review_items", ["import_run_id"])
    op.create_index("ix_review_items_namespace", "review_items", ["namespace"])


def downgrade() -> None:
    op.drop_index("ix_review_items_namespace", table_name="review_items")
    op.drop_index("ix_review_items_import_run_id", table_name="review_items")
    op.drop_index("ix_review_items_source_hash", table_name="review_items")
    op.drop_index("ix_review_items_item_type", table_name="review_items")
    op.drop_index("ix_review_items_case_id", table_name="review_items")
    op.drop_table("review_items")
    op.drop_index("ix_dataset_split_cases_case_id", table_name="dataset_split_cases")
    op.drop_index("ix_dataset_split_cases_split_id", table_name="dataset_split_cases")
    op.drop_table("dataset_split_cases")
    op.drop_index("ix_dataset_splits_project_id", table_name="dataset_splits")
    op.drop_table("dataset_splits")
    op.drop_index("ix_evaluation_protocols_project_id", table_name="evaluation_protocols")
    op.drop_table("evaluation_protocols")
    op.drop_index("ix_evaluation_projects_namespace", table_name="evaluation_projects")
    op.drop_table("evaluation_projects")
