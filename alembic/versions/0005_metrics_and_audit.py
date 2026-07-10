"""metrics audit exports"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0005_metrics_and_audit"
down_revision = "0004_adjudication_and_gold"
branch_labels = None
depends_on = None


METRIC_STATUSES = (
    "'ready', 'partial', 'needs_annotation', 'needs_adjudication', "
    "'not_applicable', 'insufficient_sample', 'configuration_mismatch', 'failed'"
)


def upgrade() -> None:
    op.create_table(
        "metric_definitions",
        sa.Column("metric_id", sa.String(120), primary_key=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("metric_group", sa.String(120), nullable=False),
        sa.Column("formula_version", sa.String(80), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("unit", sa.String(80), nullable=False),
        sa.Column("aggregation", sa.String(80), nullable=False),
        sa.Column("higher_is_better", sa.Boolean(), nullable=False),
        sa.Column("required_inputs_json", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        "metric_runs",
        sa.Column("metric_run_id", sa.String(36), primary_key=True),
        sa.Column("project_id", sa.String(36), nullable=False),
        sa.Column("protocol_id", sa.String(36)),
        sa.Column("prediction_run_id", sa.String(160), nullable=False),
        sa.Column("gold_dataset_version", sa.String(80), nullable=False),
        sa.Column("git_commit", sa.String(80), nullable=False),
        sa.Column("config_json", sa.Text(), nullable=False),
        sa.Column("config_hash", sa.String(64), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("started_by_user_id", sa.String(36)),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True)),
        sa.Column("error_message", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["evaluation_projects.project_id"]),
        sa.ForeignKeyConstraint(["protocol_id"], ["evaluation_protocols.protocol_id"]),
        sa.ForeignKeyConstraint(["started_by_user_id"], ["users.user_id"]),
    )
    op.create_index("ix_metric_runs_project_id", "metric_runs", ["project_id"])

    op.create_table(
        "metric_results",
        sa.Column("metric_result_id", sa.String(36), primary_key=True),
        sa.Column("metric_run_id", sa.String(36), nullable=False),
        sa.Column("metric_id", sa.String(120), nullable=False),
        sa.Column("subgroup_type", sa.String(120), nullable=False),
        sa.Column("subgroup_value", sa.String(240), nullable=False),
        sa.Column("value", sa.Float()),
        sa.Column("ci_low", sa.Float()),
        sa.Column("ci_high", sa.Float()),
        sa.Column("sample_size_cases", sa.Integer()),
        sa.Column("sample_size_items", sa.Integer()),
        sa.Column("numerator", sa.Float()),
        sa.Column("denominator", sa.Float()),
        sa.Column("status", sa.String(40), nullable=False),
        sa.Column("missing_reason", sa.Text(), nullable=False),
        sa.Column("included_case_ids_json", sa.Text(), nullable=False),
        sa.Column("excluded_case_ids_json", sa.Text(), nullable=False),
        sa.Column("exclusion_reasons_json", sa.Text(), nullable=False),
        sa.Column("provenance_json", sa.Text(), nullable=False),
        sa.Column("computed_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(f"status IN ({METRIC_STATUSES})", name="ck_metric_results_status"),
        sa.ForeignKeyConstraint(["metric_id"], ["metric_definitions.metric_id"]),
        sa.ForeignKeyConstraint(["metric_run_id"], ["metric_runs.metric_run_id"]),
    )
    op.create_index("ix_metric_results_metric_run_id", "metric_results", ["metric_run_id"])
    op.create_index("ix_metric_results_metric_id", "metric_results", ["metric_id"])

    op.create_table(
        "audit_events",
        sa.Column("event_id", sa.String(36), primary_key=True),
        sa.Column("actor_user_id", sa.String(36)),
        sa.Column("actor_username_snapshot", sa.String(80), nullable=False),
        sa.Column("action", sa.String(120), nullable=False),
        sa.Column("object_type", sa.String(120), nullable=False),
        sa.Column("object_id", sa.String(240), nullable=False),
        sa.Column("project_id", sa.String(36)),
        sa.Column("case_id", sa.String(240), nullable=False),
        sa.Column("review_item_id", sa.String(512), nullable=False),
        sa.Column("metadata_json", sa.Text(), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("request_id", sa.String(80)),
        sa.Column("ip_hash", sa.String(64)),
        sa.Column("session_hash", sa.String(64)),
        sa.ForeignKeyConstraint(["actor_user_id"], ["users.user_id"]),
        sa.ForeignKeyConstraint(["project_id"], ["evaluation_projects.project_id"]),
    )
    op.create_index("ix_audit_events_action", "audit_events", ["action"])
    op.create_index("ix_audit_events_actor_time", "audit_events", ["actor_user_id", "occurred_at"])
    op.create_index("ix_audit_events_project_time", "audit_events", ["project_id", "occurred_at"])

    op.create_table(
        "export_events",
        sa.Column("export_event_id", sa.String(36), primary_key=True),
        sa.Column("actor_user_id", sa.String(36)),
        sa.Column("actor_username_snapshot", sa.String(80), nullable=False),
        sa.Column("export_type", sa.String(120), nullable=False),
        sa.Column("project_id", sa.String(36)),
        sa.Column("protocol_id", sa.String(36)),
        sa.Column("file_hash", sa.String(64), nullable=False),
        sa.Column("field_policy_json", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["actor_user_id"], ["users.user_id"]),
        sa.ForeignKeyConstraint(["project_id"], ["evaluation_projects.project_id"]),
        sa.ForeignKeyConstraint(["protocol_id"], ["evaluation_protocols.protocol_id"]),
    )


def downgrade() -> None:
    op.drop_table("export_events")
    op.drop_index("ix_audit_events_project_time", table_name="audit_events")
    op.drop_index("ix_audit_events_actor_time", table_name="audit_events")
    op.drop_index("ix_audit_events_action", table_name="audit_events")
    op.drop_table("audit_events")
    op.drop_index("ix_metric_results_metric_id", table_name="metric_results")
    op.drop_index("ix_metric_results_metric_run_id", table_name="metric_results")
    op.drop_table("metric_results")
    op.drop_index("ix_metric_runs_project_id", table_name="metric_runs")
    op.drop_table("metric_runs")
    op.drop_table("metric_definitions")
