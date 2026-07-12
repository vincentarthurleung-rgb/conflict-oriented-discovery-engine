"""System A handoff ingestion provenance ledger."""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0008_system_a_ingestion_ledger"
down_revision = "0007_owner_access_management"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "source_ingestions",
        sa.Column("ingestion_id", sa.String(36), primary_key=True),
        sa.Column("case_id", sa.String(240), nullable=False),
        sa.Column("source_run_id", sa.String(240), nullable=False),
        sa.Column("manifest_hash", sa.String(64), nullable=False),
        sa.Column("handoff_schema_version", sa.String(80), nullable=False),
        sa.Column("adapter_version", sa.String(80), nullable=False),
        sa.Column("prediction_version", sa.String(120), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("namespace", sa.String(32), nullable=False, server_default="system_a"),
        sa.Column("discovered_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True)),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.Column("error_code", sa.String(120), nullable=False, server_default=""),
        sa.Column("error_summary", sa.Text(), nullable=False, server_default=""),
        sa.Column("projection_root", sa.Text(), nullable=False, server_default=""),
        sa.Column("supersedes_ingestion_id", sa.String(36)),
        sa.Column("created_by_user_id", sa.String(36)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["supersedes_ingestion_id"], ["source_ingestions.ingestion_id"]),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.user_id"]),
        sa.UniqueConstraint("source_run_id", "manifest_hash", "adapter_version", name="uq_source_ingestion_idempotency"),
        sa.CheckConstraint("status IN ('discovered','validating','projecting','completed','failed','quarantined')", name="ck_source_ingestions_status"),
    )
    op.create_index("ix_source_ingestions_case_id", "source_ingestions", ["case_id"])
    op.create_index("ix_source_ingestions_source_run_id", "source_ingestions", ["source_run_id"])
    op.create_table(
        "prediction_runs",
        sa.Column("prediction_run_id", sa.String(64), primary_key=True),
        sa.Column("case_id", sa.String(240), nullable=False),
        sa.Column("source_ingestion_id", sa.String(36), nullable=False),
        sa.Column("prediction_version", sa.String(120), nullable=False),
        sa.Column("system_a_git_commit", sa.String(64), nullable=False, server_default=""),
        sa.Column("configuration_hash", sa.String(64), nullable=False, server_default=""),
        sa.Column("source_completed_at", sa.DateTime(timezone=True)),
        sa.Column("is_current", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["source_ingestion_id"], ["source_ingestions.ingestion_id"]),
        sa.UniqueConstraint("source_ingestion_id", name="uq_prediction_runs_source_ingestion_id"),
    )
    op.create_index("ix_prediction_runs_case_id", "prediction_runs", ["case_id"])
    op.create_table(
        "source_artifacts",
        sa.Column("source_artifact_id", sa.String(36), primary_key=True),
        sa.Column("source_ingestion_id", sa.String(36), nullable=False),
        sa.Column("logical_name", sa.String(160), nullable=False),
        sa.Column("relative_path", sa.Text(), nullable=False),
        sa.Column("sha256", sa.String(64), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("record_count", sa.Integer()),
        sa.Column("required", sa.Boolean(), nullable=False),
        sa.Column("validation_status", sa.String(32), nullable=False, server_default="valid"),
        sa.ForeignKeyConstraint(["source_ingestion_id"], ["source_ingestions.ingestion_id"]),
        sa.UniqueConstraint("source_ingestion_id", "logical_name", name="uq_source_artifact_logical_name"),
    )
    op.create_index("ix_source_artifacts_source_ingestion_id", "source_artifacts", ["source_ingestion_id"])


def downgrade() -> None:
    op.drop_index("ix_source_artifacts_source_ingestion_id", table_name="source_artifacts")
    op.drop_table("source_artifacts")
    op.drop_index("ix_prediction_runs_case_id", table_name="prediction_runs")
    op.drop_table("prediction_runs")
    op.drop_index("ix_source_ingestions_source_run_id", table_name="source_ingestions")
    op.drop_index("ix_source_ingestions_case_id", table_name="source_ingestions")
    op.drop_table("source_ingestions")
