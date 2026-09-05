"""add attendance last marked timestamp to school settings

Revision ID: c6e9f1a2b3d4
Revises: b5c6d7e8f901
Create Date: 2026-09-05 00:00:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "c6e9f1a2b3d4"
down_revision: Union[str, Sequence[str], None] = "b5c6d7e8f901"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


_TABLE_NAME = "school_settings"
_COLUMN_NAME = "attendance_last_marked_at"


def _has_column(column_name: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = {column["name"] for column in inspector.get_columns(_TABLE_NAME)}
    return column_name in columns


def upgrade() -> None:
    if _has_column(_COLUMN_NAME):
        return

    with op.batch_alter_table(_TABLE_NAME, schema=None) as batch_op:
        batch_op.add_column(sa.Column(_COLUMN_NAME, sa.DateTime(), nullable=True))


def downgrade() -> None:
    if not _has_column(_COLUMN_NAME):
        return

    with op.batch_alter_table(_TABLE_NAME, schema=None) as batch_op:
        batch_op.drop_column(_COLUMN_NAME)