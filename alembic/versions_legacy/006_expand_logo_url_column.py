"""Expand logo_url column to TEXT for base64 images

Revision ID: 006
Revises: 005
Create Date: 2026-02-21

"""

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision = "006"
down_revision = "005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # For SQLite, we need to use batch_alter_table
    with op.batch_alter_table("schools", schema=None) as batch_op:
        batch_op.alter_column(
            "logo_url",
            existing_type=sa.String(255),
            type_=sa.Text(),
            existing_nullable=True,
        )


def downgrade() -> None:
    # For SQLite, we need to use batch_alter_table
    with op.batch_alter_table("schools", schema=None) as batch_op:
        batch_op.alter_column(
            "logo_url",
            existing_type=sa.Text(),
            type_=sa.String(255),
            existing_nullable=True,
        )
