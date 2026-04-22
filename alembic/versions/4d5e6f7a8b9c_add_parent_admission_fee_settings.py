"""add parent admission fee settings

Revision ID: 4d5e6f7a8b9c
Revises: 3c4d5e6f7a8b
Create Date: 2026-04-22 09:15:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "4d5e6f7a8b9c"
down_revision: Union[str, Sequence[str], None] = "3c4d5e6f7a8b"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("school_settings", schema=None) as batch_op:
        batch_op.add_column(sa.Column("admission_fee_enabled", sa.Boolean(), nullable=True, server_default=sa.false()))
        batch_op.add_column(sa.Column("admission_fee_amount", sa.Float(), nullable=True, server_default="0"))


def downgrade() -> None:
    with op.batch_alter_table("school_settings", schema=None) as batch_op:
        batch_op.drop_column("admission_fee_amount")
        batch_op.drop_column("admission_fee_enabled")