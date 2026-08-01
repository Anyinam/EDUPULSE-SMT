"""add ledger audit features

Revision ID: 372cb324fac8
Revises: 24271819c34a
Create Date: 2026-02-24 09:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '372cb324fac8'
down_revision: Union[str, None] = '24271819c34a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())

    if "ledger_entries" not in tables:
        op.create_table(
            "ledger_entries",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("school_id", sa.String(length=20), nullable=False),
            sa.Column("tx_type", sa.String(length=30), nullable=False),
            sa.Column("tx_ref", sa.String(length=80), nullable=False),
            sa.Column("amount", sa.Float(), nullable=False),
            sa.Column("currency", sa.String(length=10), nullable=True),
            sa.Column("actor_id", sa.Integer(), nullable=True),
            sa.Column("student_id", sa.Integer(), nullable=True),
            sa.Column("source", sa.String(length=30), nullable=True),
            sa.Column("metadata", sa.JSON(), nullable=True),
            sa.Column("previous_hash", sa.String(length=64), nullable=True),
            sa.Column("hash", sa.String(length=64), nullable=False),
            sa.Column("is_verified", sa.Boolean(), nullable=True, server_default=sa.true()),
            sa.Column("created_at", sa.DateTime(), nullable=True),
            sa.ForeignKeyConstraint(["school_id"], ["schools.id"]),
            sa.ForeignKeyConstraint(["actor_id"], ["users.id"]),
            sa.ForeignKeyConstraint(["student_id"], ["students.id"]),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("tx_ref"),
        )
        return

    column_names = {c["name"] for c in inspector.get_columns("ledger_entries")}
    if "is_verified" not in column_names:
        op.add_column(
            "ledger_entries",
            sa.Column("is_verified", sa.Boolean(), default=True, nullable=True),
        )

    op.execute("UPDATE ledger_entries SET is_verified = true WHERE is_verified IS NULL")


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "ledger_entries" not in inspector.get_table_names():
        return

    column_names = {c["name"] for c in inspector.get_columns("ledger_entries")}
    if "is_verified" in column_names:
        op.drop_column("ledger_entries", "is_verified")
