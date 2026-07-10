"""core identity and auth"""
from __future__ import annotations

from alembic import op
from code_engine.system_b.persistence.models import Base

revision = "0001_core_identity_and_auth"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    for table in Base.metadata.sorted_tables:
        columns = [column.copy() for column in table.columns]
        constraints = [constraint.copy() for constraint in list(table.constraints) if not constraint.__class__.__name__ == "PrimaryKeyConstraint"]
        op.create_table(table.name, *columns, *constraints)


def downgrade() -> None:
    for table in reversed(Base.metadata.sorted_tables):
        op.drop_table(table.name)
