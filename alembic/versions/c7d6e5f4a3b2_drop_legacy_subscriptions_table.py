"""drop legacy subscriptions table

Revision ID: c7d6e5f4a3b2
Revises: a9b8c7d6e5f4
Create Date: 2026-08-01 18:10:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "c7d6e5f4a3b2"
down_revision: Union[str, Sequence[str], None] = "a9b8c7d6e5f4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_table(table_name: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return table_name in inspector.get_table_names()


def upgrade() -> None:
    if _has_table("subscriptions"):
        op.drop_table("subscriptions")


def downgrade() -> None:
    if _has_table("subscriptions"):
        return

    op.create_table(
        "subscriptions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("school_id", sa.String(length=20), nullable=False),
        sa.Column("plan", sa.String(length=20), nullable=False, server_default="free"),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="active"),
        sa.Column("start_date", sa.DateTime(), nullable=False),
        sa.Column("end_date", sa.DateTime(), nullable=True),
        sa.Column("trial_end_date", sa.DateTime(), nullable=True),
        sa.Column("last_payment_date", sa.DateTime(), nullable=True),
        sa.Column("next_billing_date", sa.DateTime(), nullable=True),
        sa.Column("auto_renew", sa.Boolean(), nullable=True, server_default=sa.true()),
        sa.Column("billing_email", sa.String(length=120), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["school_id"], ["schools.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("school_id"),
    )
