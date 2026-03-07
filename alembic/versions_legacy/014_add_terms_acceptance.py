"""add terms acceptance tracking

Revision ID: 014_add_terms_acceptance
Revises: 013
Create Date: 2026-02-22 12:00:00.000000
"""

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision = "014_add_terms_acceptance"
down_revision = "013_add_security_models"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("users", sa.Column("terms_accepted_at", sa.DateTime(), nullable=True))
    op.add_column(
        "users", sa.Column("terms_version", sa.String(length=50), nullable=True)
    )
    op.add_column(
        "users", sa.Column("terms_accepted_ip", sa.String(length=64), nullable=True)
    )


def downgrade():
    op.drop_column("users", "terms_accepted_ip")
    op.drop_column("users", "terms_version")
    op.drop_column("users", "terms_accepted_at")
