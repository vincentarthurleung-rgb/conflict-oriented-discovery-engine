"""adjudication and gold"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0004_adjudication_and_gold"
down_revision = "0003_assignments_annotations_and_events"
branch_labels = None
depends_on = None


GOLD_STATUSES = "'draft', 'adjudicated', 'frozen', 'superseded'"


def upgrade() -> None:
    op.create_table(
        "adjudications",
        sa.Column("adjudication_id", sa.String(36), primary_key=True),
        sa.Column("project_id", sa.String(36), nullable=False),
        sa.Column("review_item_id", sa.String(512), nullable=False),
        sa.Column("adjudicator_user_id", sa.String(36), nullable=False),
        sa.Column("adjudicator_username_snapshot", sa.String(80), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("final_label", sa.String(80), nullable=False),
        sa.Column("structured_gold_json", sa.Text(), nullable=False),
        sa.Column("notes", sa.Text(), nullable=False),
        sa.Column("schema_version", sa.String(40), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("submitted_at", sa.DateTime(timezone=True)),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["adjudicator_user_id"], ["users.user_id"]),
        sa.ForeignKeyConstraint(["project_id"], ["evaluation_projects.project_id"]),
        sa.ForeignKeyConstraint(["review_item_id"], ["review_items.review_item_id"]),
    )
    op.create_index("ix_adjudications_project_id", "adjudications", ["project_id"])
    op.create_index("ix_adjudications_review_item_id", "adjudications", ["review_item_id"])
    op.create_index("uq_adjudication_current_item", "adjudications", ["project_id", "review_item_id"], unique=True)

    op.create_table(
        "adjudication_sources",
        sa.Column("adjudication_source_id", sa.String(36), primary_key=True),
        sa.Column("adjudication_id", sa.String(36), nullable=False),
        sa.Column("annotation_id", sa.String(36), nullable=False),
        sa.ForeignKeyConstraint(["adjudication_id"], ["adjudications.adjudication_id"]),
        sa.ForeignKeyConstraint(["annotation_id"], ["annotations.annotation_id"]),
        sa.UniqueConstraint("adjudication_id", "annotation_id", name="uq_adjudication_source"),
    )

    op.create_table(
        "gold_records",
        sa.Column("gold_record_id", sa.String(36), primary_key=True),
        sa.Column("project_id", sa.String(36), nullable=False),
        sa.Column("protocol_id", sa.String(36), nullable=False),
        sa.Column("review_item_id", sa.String(512), nullable=False),
        sa.Column("adjudication_id", sa.String(36)),
        sa.Column("final_gold_label", sa.String(80), nullable=False),
        sa.Column("structured_gold_json", sa.Text(), nullable=False),
        sa.Column("schema_version", sa.String(40), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("frozen_by_user_id", sa.String(36)),
        sa.Column("frozen_at", sa.DateTime(timezone=True)),
        sa.Column("gold_version", sa.Integer(), nullable=False),
        sa.CheckConstraint(f"status IN ({GOLD_STATUSES})", name="ck_gold_status"),
        sa.ForeignKeyConstraint(["adjudication_id"], ["adjudications.adjudication_id"]),
        sa.ForeignKeyConstraint(["frozen_by_user_id"], ["users.user_id"]),
        sa.ForeignKeyConstraint(["project_id"], ["evaluation_projects.project_id"]),
        sa.ForeignKeyConstraint(["protocol_id"], ["evaluation_protocols.protocol_id"]),
        sa.ForeignKeyConstraint(["review_item_id"], ["review_items.review_item_id"]),
        sa.UniqueConstraint("project_id", "review_item_id", "gold_version", name="uq_gold_project_item_version"),
    )
    op.create_index("ix_gold_records_project_id", "gold_records", ["project_id"])
    op.create_index("ix_gold_records_protocol_id", "gold_records", ["protocol_id"])
    op.create_index("ix_gold_records_review_item_id", "gold_records", ["review_item_id"])
    op.create_index("ix_gold_records_status_version", "gold_records", ["status", "gold_version"])


def downgrade() -> None:
    op.drop_index("ix_gold_records_status_version", table_name="gold_records")
    op.drop_index("ix_gold_records_review_item_id", table_name="gold_records")
    op.drop_index("ix_gold_records_protocol_id", table_name="gold_records")
    op.drop_index("ix_gold_records_project_id", table_name="gold_records")
    op.drop_table("gold_records")
    op.drop_table("adjudication_sources")
    op.drop_index("uq_adjudication_current_item", table_name="adjudications")
    op.drop_index("ix_adjudications_review_item_id", table_name="adjudications")
    op.drop_index("ix_adjudications_project_id", table_name="adjudications")
    op.drop_table("adjudications")
