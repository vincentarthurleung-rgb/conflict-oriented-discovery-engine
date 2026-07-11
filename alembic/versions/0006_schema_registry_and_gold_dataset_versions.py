"""schema registry and gold dataset versions"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0006_schema_registry_and_gold_dataset_versions"
down_revision = "0005_metrics_and_audit"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("gold_records") as batch:
        batch.drop_constraint("uq_gold_project_item_version", type_="unique")
        batch.drop_constraint("ck_gold_status", type_="check")
        batch.create_check_constraint("ck_gold_status", "status IN ('draft', 'candidate', 'adjudicated', 'frozen', 'superseded')")
    with op.batch_alter_table("metric_results") as batch:
        batch.drop_constraint("ck_metric_results_status", type_="check")
        batch.create_check_constraint("ck_metric_results_status", "status IN ('ready', 'partial', 'needs_annotation', 'needs_adjudication', 'not_applicable', 'insufficient_sample', 'configuration_mismatch', 'failed', 'not_implemented')")
    op.add_column("annotations", sa.Column("schema_id", sa.String(120), nullable=False, server_default="claim_review_v1"))
    op.add_column("annotations", sa.Column("schema_hash", sa.String(64), nullable=False, server_default=""))
    op.add_column("annotations", sa.Column("instructions_version", sa.String(120), nullable=False, server_default=""))
    op.add_column("annotations", sa.Column("instructions_hash", sa.String(160), nullable=False, server_default=""))

    op.add_column("adjudications", sa.Column("schema_id", sa.String(120), nullable=False, server_default="claim_review_v1"))
    op.add_column("adjudications", sa.Column("schema_hash", sa.String(64), nullable=False, server_default=""))

    op.add_column("gold_records", sa.Column("candidate_revision", sa.Integer(), nullable=False, server_default="1"))
    op.add_column("gold_records", sa.Column("gold_dataset_version", sa.Integer(), nullable=True))
    op.add_column("gold_records", sa.Column("schema_id", sa.String(120), nullable=False, server_default="claim_review_v1"))
    op.add_column("gold_records", sa.Column("schema_hash", sa.String(64), nullable=False, server_default=""))
    with op.batch_alter_table("gold_records") as batch:
        batch.create_unique_constraint("uq_gold_project_item_status_revision_dataset", ["project_id", "review_item_id", "status", "candidate_revision", "gold_dataset_version"])
    op.create_index("ix_gold_records_dataset_version", "gold_records", ["project_id", "gold_dataset_version"])

    bind = op.get_bind()
    rows = bind.execute(sa.text(
        "SELECT DISTINCT project_id FROM gold_records WHERE status IN ('frozen','superseded')"
    )).fetchall()
    for (project_id,) in rows:
        versions = bind.execute(sa.text(
            "SELECT DISTINCT gold_version FROM gold_records "
            "WHERE project_id=:project_id AND status IN ('frozen','superseded') "
            "ORDER BY gold_version"
        ), {"project_id": project_id}).fetchall()
        for dataset_version, (gold_version,) in enumerate(versions, start=1):
            bind.execute(sa.text(
                "UPDATE gold_records SET gold_dataset_version=:dataset_version, "
                "candidate_revision=gold_version WHERE project_id=:project_id "
                "AND gold_version=:gold_version AND status IN ('frozen','superseded')"
            ), {"dataset_version": dataset_version, "project_id": project_id, "gold_version": gold_version})
    bind.execute(sa.text(
        "UPDATE gold_records SET candidate_revision=gold_version "
        "WHERE status NOT IN ('frozen','superseded')"
    ))


def downgrade() -> None:
    op.drop_index("ix_gold_records_dataset_version", table_name="gold_records")
    with op.batch_alter_table("gold_records") as batch:
        batch.drop_constraint("uq_gold_project_item_status_revision_dataset", type_="unique")
    op.drop_column("gold_records", "schema_hash")
    op.drop_column("gold_records", "schema_id")
    op.drop_column("gold_records", "gold_dataset_version")
    op.drop_column("gold_records", "candidate_revision")
    op.drop_column("adjudications", "schema_hash")
    op.drop_column("adjudications", "schema_id")
    op.drop_column("annotations", "instructions_hash")
    op.drop_column("annotations", "instructions_version")
    op.drop_column("annotations", "schema_hash")
    op.drop_column("annotations", "schema_id")
    with op.batch_alter_table("metric_results") as batch:
        batch.drop_constraint("ck_metric_results_status", type_="check")
        batch.create_check_constraint("ck_metric_results_status", "status IN ('ready', 'partial', 'needs_annotation', 'needs_adjudication', 'not_applicable', 'insufficient_sample', 'configuration_mismatch', 'failed')")
    with op.batch_alter_table("gold_records") as batch:
        batch.drop_constraint("ck_gold_status", type_="check")
        batch.create_check_constraint("ck_gold_status", "status IN ('draft', 'adjudicated', 'frozen', 'superseded')")
        batch.create_unique_constraint("uq_gold_project_item_version", ["project_id", "review_item_id", "gold_version"])
