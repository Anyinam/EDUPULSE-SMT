"""add phone payment convenience fee setting

Revision ID: 5f8c1a9d2b6e
Revises: e4f1a2b3c4d5
Create Date: 2026-06-14 00:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "5f8c1a9d2b6e"
down_revision: Union[str, Sequence[str], None] = "e4f1a2b3c4d5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("school_settings", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(
                "phone_payment_convenience_fee_percent",
                sa.Float(),
                nullable=True,
                server_default="1.5",
            )
        )


def downgrade() -> None:
    with op.batch_alter_table("school_settings", schema=None) as batch_op:
        batch_op.drop_column("phone_payment_convenience_fee_percent")