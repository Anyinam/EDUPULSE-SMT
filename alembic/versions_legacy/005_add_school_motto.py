"""Add school motto field

Revision ID: 005
Revises: 004
Create Date: 2026-02-17

"""

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision = "005"
down_revision = "004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("schools", sa.Column("motto", sa.String(255), nullable=True))


def downgrade() -> None:
    op.drop_column("schools", "motto")
