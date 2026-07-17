"""System A v2 domain, capability and artifact adapter metadata."""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0009_system_a_v2_metadata"
down_revision = "0008_system_a_ingestion_ledger"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("source_ingestions") as batch:
        batch.add_column(sa.Column("projection_identity_hash", sa.String(64), nullable=False, server_default=""))
        batch.add_column(sa.Column("domain_snapshot_json", sa.Text(), nullable=False, server_default="{}"))
        batch.add_column(sa.Column("capability_summary_json", sa.Text(), nullable=False, server_default="{}"))
    with op.batch_alter_table("source_artifacts") as batch:
        batch.add_column(sa.Column("schema_version", sa.String(120), nullable=False, server_default=""))
        batch.add_column(sa.Column("adapter_status", sa.String(40), nullable=False, server_default="supported"))
        batch.add_column(sa.Column("usable_record_count", sa.Integer()))
        batch.add_column(sa.Column("coverage", sa.Float()))
        batch.add_column(sa.Column("error_reason", sa.Text(), nullable=False, server_default=""))
        batch.add_column(sa.Column("metadata_json", sa.Text(), nullable=False, server_default="{}"))


def downgrade() -> None:
    # SQLite 3.35+ supports direct DROP COLUMN.  Direct operations avoid a
    # batch table rebuild that would temporarily violate prediction/artifact
    # foreign keys on populated ledgers.
    for column in ("metadata_json", "error_reason", "coverage", "usable_record_count", "adapter_status", "schema_version"):
        op.drop_column("source_artifacts", column)
    for column in ("capability_summary_json", "domain_snapshot_json", "projection_identity_hash"):
        op.drop_column("source_ingestions", column)
