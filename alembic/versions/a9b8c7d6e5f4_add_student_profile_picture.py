"""add student profile picture

Revision ID: a9b8c7d6e5f4
Revises: f1a2b3c4d5e6
Create Date: 2026-08-01 14:45:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "a9b8c7d6e5f4"
down_revision: Union[str, Sequence[str], None] = "f1a2b3c4d5e6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_column(table_name: str, column_name: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = [column["name"] for column in inspector.get_columns(table_name)]
    return column_name in columns


def upgrade() -> None:
    with op.batch_alter_table("students", schema=None) as batch_op:
        if not _has_column("students", "profile_picture"):
            batch_op.add_column(sa.Column("profile_picture", sa.Text(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("students", schema=None) as batch_op:
        if _has_column("students", "profile_picture"):
            batch_op.drop_column("profile_picture")
