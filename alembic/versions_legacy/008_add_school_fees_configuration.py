"""Add school fee configuration fields

Revision ID: 008
Revises: 007
Create Date: 2026-02-21 10:00:00.000000

"""

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision = "008"
down_revision = "007"
branch_labels = None
depends_on = None


def upgrade():
    # Add fee configuration columns to school_settings table
    with op.batch_alter_table("school_settings", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("tuition_fee", sa.Float(), nullable=True, server_default="0.0")
        )
        batch_op.add_column(
            sa.Column("feeding_fee", sa.Float(), nullable=True, server_default="0.0")
        )
        batch_op.add_column(
            sa.Column("uniform_fee", sa.Float(), nullable=True, server_default="0.0")
        )
        batch_op.add_column(
            sa.Column("transport_fee", sa.Float(), nullable=True, server_default="0.0")
        )
        batch_op.add_column(
            sa.Column("other_fees", sa.JSON(), nullable=True, server_default="{}")
        )


def downgrade():
    # Remove fee configuration columns
    with op.batch_alter_table("school_settings", schema=None) as batch_op:
        batch_op.drop_column("other_fees")
        batch_op.drop_column("transport_fee")
        batch_op.drop_column("uniform_fee")
        batch_op.drop_column("feeding_fee")
        batch_op.drop_column("tuition_fee")
