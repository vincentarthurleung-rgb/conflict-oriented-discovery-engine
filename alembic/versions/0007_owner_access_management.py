"""owner access management"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0007_owner_access_management"
down_revision = "0006_schema_registry_and_gold_dataset_versions"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("must_change_password", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column("users", sa.Column("session_version", sa.Integer(), nullable=False, server_default="1"))
    op.add_column("users", sa.Column("locked_until", sa.DateTime(timezone=True)))
    op.add_column("users", sa.Column("invite_source_id", sa.String(36)))
    op.create_index("ix_users_enabled_role", "users", ["enabled", "role"])

    op.add_column("invites", sa.Column("project_scope_json", sa.Text(), nullable=False, server_default="{}"))
    op.add_column("invites", sa.Column("notes", sa.Text(), nullable=False, server_default=""))
    op.add_column("invites", sa.Column("last_used_at", sa.DateTime(timezone=True)))

    op.create_table(
        "password_reset_tokens",
        sa.Column("reset_token_id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(36), nullable=False),
        sa.Column("token_hash", sa.String(128), nullable=False),
        sa.Column("created_by_user_id", sa.String(36)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True)),
        sa.Column("revoked_at", sa.DateTime(timezone=True)),
        sa.ForeignKeyConstraint(["user_id"], ["users.user_id"]),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.user_id"]),
        sa.UniqueConstraint("token_hash", name="uq_password_reset_token_hash"),
    )
    op.create_index("ix_password_reset_tokens_user", "password_reset_tokens", ["user_id"])

    op.create_table(
        "invite_usage_events",
        sa.Column("invite_usage_event_id", sa.String(36), primary_key=True),
        sa.Column("invite_id", sa.String(36), nullable=False),
        sa.Column("user_id", sa.String(36), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("request_id", sa.String(80)),
        sa.Column("ip_hash", sa.String(64)),
        sa.ForeignKeyConstraint(["invite_id"], ["invites.invite_id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.user_id"]),
    )
    op.create_index("ix_invite_usage_events_invite", "invite_usage_events", ["invite_id"])

    op.create_table(
        "user_onboarding_acknowledgements",
        sa.Column("ack_id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(36), nullable=False),
        sa.Column("project_id", sa.String(36), nullable=False),
        sa.Column("schema_id", sa.String(120), nullable=False),
        sa.Column("instructions_version", sa.String(120), nullable=False),
        sa.Column("instructions_hash", sa.String(160), nullable=False),
        sa.Column("acknowledged_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.user_id"]),
        sa.ForeignKeyConstraint(["project_id"], ["evaluation_projects.project_id"]),
        sa.UniqueConstraint("user_id", "project_id", "schema_id", "instructions_hash", name="uq_onboarding_ack_schema"),
    )
    op.create_index("ix_onboarding_ack_user", "user_onboarding_acknowledgements", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_onboarding_ack_user", table_name="user_onboarding_acknowledgements")
    op.drop_table("user_onboarding_acknowledgements")
    op.drop_index("ix_invite_usage_events_invite", table_name="invite_usage_events")
    op.drop_table("invite_usage_events")
    op.drop_index("ix_password_reset_tokens_user", table_name="password_reset_tokens")
    op.drop_table("password_reset_tokens")
    op.drop_column("invites", "last_used_at")
    op.drop_column("invites", "notes")
    op.drop_column("invites", "project_scope_json")
    op.drop_index("ix_users_enabled_role", table_name="users")
    op.drop_column("users", "invite_source_id")
    op.drop_column("users", "locked_until")
    op.drop_column("users", "session_version")
    op.drop_column("users", "must_change_password")
