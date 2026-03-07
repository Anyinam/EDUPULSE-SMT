"""Add school contact details for documents

Revision ID: 007
Revises: 006
Create Date: 2026-02-21

"""

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision = "007"
down_revision = "006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # For SQLite, we need to use batch_alter_table
    with op.batch_alter_table("schools", schema=None) as batch_op:
        batch_op.add_column(sa.Column("school_email", sa.String(100), nullable=True))
        batch_op.add_column(sa.Column("school_phone", sa.String(20), nullable=True))
        batch_op.add_column(sa.Column("school_address", sa.String(255), nullable=True))
        batch_op.add_column(sa.Column("school_website", sa.String(100), nullable=True))


def downgrade() -> None:
    # For SQLite, we need to use batch_alter_table
    with op.batch_alter_table("schools", schema=None) as batch_op:
        batch_op.drop_column("school_website")
        batch_op.drop_column("school_address")
        batch_op.drop_column("school_phone")
        batch_op.drop_column("school_email")
