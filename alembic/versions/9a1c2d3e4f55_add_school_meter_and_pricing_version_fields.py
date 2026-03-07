"""add school meter and pricing version fields

Revision ID: 9a1c2d3e4f55
Revises: 8b9d4f2c1a77
Create Date: 2026-03-07 18:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "9a1c2d3e4f55"
down_revision: Union[str, Sequence[str], None] = "8b9d4f2c1a77"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_column(table_name: str, column_name: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = [c["name"] for c in inspector.get_columns(table_name)]
    return column_name in columns


def upgrade() -> None:
    """Upgrade schema."""
    with op.batch_alter_table("schools", schema=None) as batch_op:
        if not _has_column("schools", "is_trial_active"):
            batch_op.add_column(sa.Column("is_trial_active", sa.Boolean(), nullable=True, server_default=sa.text("0")))
        if not _has_column("schools", "current_student_count"):
            batch_op.add_column(sa.Column("current_student_count", sa.Integer(), nullable=True, server_default=sa.text("0")))
        if not _has_column("schools", "last_metered_at"):
            batch_op.add_column(sa.Column("last_metered_at", sa.DateTime(), nullable=True))
        if not _has_column("schools", "plan_version"):
            batch_op.add_column(sa.Column("plan_version", sa.String(length=40), nullable=True))
        if not _has_column("schools", "pricing_locked_at"):
            batch_op.add_column(sa.Column("pricing_locked_at", sa.DateTime(), nullable=True))
        if not _has_column("schools", "custom_base_fee"):
            batch_op.add_column(sa.Column("custom_base_fee", sa.Float(), nullable=True))
        if not _has_column("schools", "custom_included_students"):
            batch_op.add_column(sa.Column("custom_included_students", sa.Integer(), nullable=True))
        if not _has_column("schools", "custom_overage_rate"):
            batch_op.add_column(sa.Column("custom_overage_rate", sa.Float(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table("schools", schema=None) as batch_op:
        if _has_column("schools", "custom_overage_rate"):
            batch_op.drop_column("custom_overage_rate")
        if _has_column("schools", "custom_included_students"):
            batch_op.drop_column("custom_included_students")
        if _has_column("schools", "custom_base_fee"):
            batch_op.drop_column("custom_base_fee")
        if _has_column("schools", "pricing_locked_at"):
            batch_op.drop_column("pricing_locked_at")
        if _has_column("schools", "plan_version"):
            batch_op.drop_column("plan_version")
        if _has_column("schools", "last_metered_at"):
            batch_op.drop_column("last_metered_at")
        if _has_column("schools", "current_student_count"):
            batch_op.drop_column("current_student_count")
        if _has_column("schools", "is_trial_active"):
            batch_op.drop_column("is_trial_active")
