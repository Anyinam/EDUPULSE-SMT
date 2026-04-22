"""add parent admission pdf settings

Revision ID: 7a8b9c0d1e2f
Revises: 4d5e6f7a8b9c
Create Date: 2026-04-22 20:35:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "7a8b9c0d1e2f"
down_revision: Union[str, Sequence[str], None] = "4d5e6f7a8b9c"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("school_settings", schema=None) as batch_op:
        batch_op.add_column(sa.Column("approval_pdf_enabled", sa.Boolean(), nullable=True, server_default=sa.false()))
        batch_op.add_column(sa.Column("approval_pdf_delivery_mode", sa.String(length=30), nullable=True, server_default="email_link"))
        batch_op.add_column(sa.Column("approval_pdf_include_payment_summary", sa.Boolean(), nullable=True, server_default=sa.true()))
        batch_op.add_column(sa.Column("approval_pdf_include_required_items", sa.Boolean(), nullable=True, server_default=sa.true()))
        batch_op.add_column(sa.Column("approval_pdf_required_items", sa.Text(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("school_settings", schema=None) as batch_op:
        batch_op.drop_column("approval_pdf_required_items")
        batch_op.drop_column("approval_pdf_include_required_items")
        batch_op.drop_column("approval_pdf_include_payment_summary")
        batch_op.drop_column("approval_pdf_delivery_mode")
        batch_op.drop_column("approval_pdf_enabled")