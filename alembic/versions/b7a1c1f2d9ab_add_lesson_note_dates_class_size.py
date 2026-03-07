"""add lesson note dates and class size

Revision ID: b7a1c1f2d9ab
Revises: 6e3c1dbe8b9b
Create Date: 2026-02-24 12:00:00.000000
"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "b7a1c1f2d9ab"
down_revision = "6e3c1dbe8b9b"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("lesson_notes", schema=None) as batch_op:
        batch_op.add_column(sa.Column("lesson_dates", sa.JSON(), nullable=True))
        batch_op.add_column(sa.Column("class_size", sa.Integer(), nullable=True))


def downgrade():
    with op.batch_alter_table("lesson_notes", schema=None) as batch_op:
        batch_op.drop_column("class_size")
        batch_op.drop_column("lesson_dates")
