"""add student grade diagnostic topics

Revision ID: a4d9f3c2b1e0
Revises: f2b4c6d8e0f1
Create Date: 2026-08-08 09:30:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "a4d9f3c2b1e0"
down_revision: Union[str, Sequence[str], None] = "f2b4c6d8e0f1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    with op.batch_alter_table("student_grades", schema=None) as batch_op:
        batch_op.add_column(sa.Column("diagnostic_topics", sa.JSON(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table("student_grades", schema=None) as batch_op:
        batch_op.drop_column("diagnostic_topics")