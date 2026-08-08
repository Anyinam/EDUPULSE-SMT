"""widen school bank fields for encryption

Revision ID: f2b4c6d8e0f1
Revises: e8d1f4a2c6b7
Create Date: 2026-08-08 08:05:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "f2b4c6d8e0f1"
down_revision: Union[str, Sequence[str], None] = "e8d1f4a2c6b7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    with op.batch_alter_table("schools", schema=None) as batch_op:
        batch_op.alter_column(
            "bank_name",
            existing_type=sa.String(length=100),
            type_=sa.Text(),
            existing_nullable=True,
        )
        batch_op.alter_column(
            "bank_account",
            existing_type=sa.String(length=50),
            type_=sa.Text(),
            existing_nullable=True,
        )
        batch_op.alter_column(
            "bank_account_name",
            existing_type=sa.String(length=100),
            type_=sa.Text(),
            existing_nullable=True,
        )
        batch_op.alter_column(
            "bank_branch",
            existing_type=sa.String(length=100),
            type_=sa.Text(),
            existing_nullable=True,
        )


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table("schools", schema=None) as batch_op:
        batch_op.alter_column(
            "bank_branch",
            existing_type=sa.Text(),
            type_=sa.String(length=100),
            existing_nullable=True,
        )
        batch_op.alter_column(
            "bank_account_name",
            existing_type=sa.Text(),
            type_=sa.String(length=100),
            existing_nullable=True,
        )
        batch_op.alter_column(
            "bank_account",
            existing_type=sa.Text(),
            type_=sa.String(length=50),
            existing_nullable=True,
        )
        batch_op.alter_column(
            "bank_name",
            existing_type=sa.Text(),
            type_=sa.String(length=100),
            existing_nullable=True,
        )