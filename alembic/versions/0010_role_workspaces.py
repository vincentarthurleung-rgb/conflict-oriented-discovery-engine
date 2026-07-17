"""Add researcher and adjudicator global roles without changing existing users."""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0010_role_workspaces"
down_revision = "0009_system_a_v2_metadata"
branch_labels = None
depends_on = None

OLD = "'owner', 'admin', 'developer', 'reviewer', 'pharma'"
NEW = "'owner', 'admin', 'developer', 'reviewer', 'adjudicator', 'researcher', 'pharma'"


def _sqlite_replace(before: str, after: str) -> None:
    connection = op.get_bind()
    schema_version = connection.exec_driver_sql("PRAGMA schema_version").scalar_one()
    connection.exec_driver_sql("PRAGMA writable_schema=ON")
    try:
        for table in ("users", "invites"):
            sql = connection.exec_driver_sql("SELECT sql FROM sqlite_master WHERE type='table' AND name=?", (table,)).scalar_one()
            if before not in sql:
                raise RuntimeError(f"expected role constraint not found in {table}")
            connection.exec_driver_sql("UPDATE sqlite_master SET sql=? WHERE type='table' AND name=?", (sql.replace(before, after), table))
    finally:
        connection.exec_driver_sql("PRAGMA writable_schema=OFF")
    connection.exec_driver_sql(f"PRAGMA schema_version={int(schema_version) + 1}")
    if connection.exec_driver_sql("PRAGMA integrity_check").scalar_one() != "ok":
        raise RuntimeError("SQLite integrity check failed after role constraint migration")


def upgrade() -> None:
    if op.get_bind().dialect.name == "sqlite":
        _sqlite_replace(OLD, NEW)
        return
    for table, name in (("users", "ck_users_role"), ("invites", "ck_invites_role")):
        op.drop_constraint(name, table, type_="check")
        op.create_check_constraint(name, table, f"role IN ({NEW})")


def downgrade() -> None:
    connection = op.get_bind()
    for table in ("users", "invites"):
        count = connection.execute(sa.text(f"SELECT count(*) FROM {table} WHERE role IN ('researcher','adjudicator')")).scalar_one()
        if count:
            raise RuntimeError(f"cannot downgrade while {table} contains researcher/adjudicator roles")
    if connection.dialect.name == "sqlite":
        _sqlite_replace(NEW, OLD)
        return
    for table, name in (("users", "ck_users_role"), ("invites", "ck_invites_role")):
        op.drop_constraint(name, table, type_="check")
        op.create_check_constraint(name, table, f"role IN ({OLD})")
