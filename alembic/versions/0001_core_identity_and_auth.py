"""core identity and auth"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0001_core_identity_and_auth"
down_revision = None
branch_labels = None
depends_on = None


ROLES = "'owner', 'admin', 'developer', 'reviewer', 'pharma'"


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("user_id", sa.String(36), primary_key=True),
        sa.Column("username", sa.String(80), nullable=False),
        sa.Column("display_name", sa.String(160), nullable=False),
        sa.Column("password_hash", sa.Text(), nullable=False),
        sa.Column("role", sa.String(32), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_login_at", sa.DateTime(timezone=True)),
        sa.CheckConstraint(f"role IN ({ROLES})", name="ck_users_role"),
        sa.UniqueConstraint("username", name="uq_users_username"),
    )
    op.create_index("ix_users_username", "users", ["username"])
    op.create_index(
        "uq_users_single_enabled_owner",
        "users",
        ["role"],
        unique=True,
        sqlite_where=sa.text("role = 'owner' AND enabled = 1"),
    )

    op.create_table(
        "invites",
        sa.Column("invite_id", sa.String(36), primary_key=True),
        sa.Column("code_hash", sa.String(128), nullable=False),
        sa.Column("label", sa.String(160), nullable=False),
        sa.Column("role", sa.String(32), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True)),
        sa.Column("max_uses", sa.Integer(), nullable=False),
        sa.Column("uses", sa.Integer(), nullable=False),
        sa.Column("created_by_user_id", sa.String(36)),
        sa.CheckConstraint(f"role IN ({ROLES})", name="ck_invites_role"),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.user_id"]),
        sa.UniqueConstraint("code_hash", name="uq_invites_code_hash"),
    )

    op.create_table(
        "system_settings",
        sa.Column("key", sa.String(120), primary_key=True),
        sa.Column("value", sa.Text(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("system_settings")
    op.drop_table("invites")
    op.drop_index("uq_users_single_enabled_owner", table_name="users")
    op.drop_index("ix_users_username", table_name="users")
    op.drop_table("users")
