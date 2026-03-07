"""add report card submit_to field

Revision ID: 012
Revises: 011
Create Date: 2026-02-21

"""

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision = "012"
down_revision = "011"
branch_labels = None
depends_on = None


def upgrade():
    # Add submit_to column to report_cards table
    op.add_column(
        "report_cards",
        sa.Column(
            "submit_to", sa.String(20), server_default="headmaster", nullable=True
        ),
    )


def downgrade():
    # Remove submit_to column from report_cards table
    op.drop_column("report_cards", "submit_to")
