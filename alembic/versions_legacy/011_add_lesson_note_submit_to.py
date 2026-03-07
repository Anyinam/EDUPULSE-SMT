"""add lesson note submit_to field

Revision ID: 011
Revises: 010
Create Date: 2026-02-21

"""

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision = "011"
down_revision = "010"
branch_labels = None
depends_on = None


def upgrade():
    # Add submit_to column to lesson_notes table
    op.add_column(
        "lesson_notes",
        sa.Column(
            "submit_to", sa.String(20), server_default="headmaster", nullable=True
        ),
    )


def downgrade():
    # Remove submit_to column from lesson_notes table
    op.drop_column("lesson_notes", "submit_to")
