"""add student scholarship fields

Revision ID: 8b9d4f2c1a77
Revises: 6fce9185f114
Create Date: 2026-03-04 20:25:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "8b9d4f2c1a77"
down_revision: Union[str, Sequence[str], None] = "6fce9185f114"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_column(table_name: str, column_name: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = [c["name"] for c in inspector.get_columns(table_name)]
    return column_name in columns


def upgrade() -> None:
    """Upgrade schema."""
    with op.batch_alter_table("students", schema=None) as batch_op:
        if not _has_column("students", "is_on_scholarship"):
            batch_op.add_column(sa.Column("is_on_scholarship", sa.Boolean(), nullable=True, server_default=sa.false()))
        if not _has_column("students", "scholarship_covers_tuition"):
            batch_op.add_column(sa.Column("scholarship_covers_tuition", sa.Boolean(), nullable=True, server_default=sa.false()))
        if not _has_column("students", "scholarship_covers_feeding"):
            batch_op.add_column(sa.Column("scholarship_covers_feeding", sa.Boolean(), nullable=True, server_default=sa.false()))
        if not _has_column("students", "scholarship_notes"):
            batch_op.add_column(sa.Column("scholarship_notes", sa.String(length=255), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table("students", schema=None) as batch_op:
        if _has_column("students", "scholarship_notes"):
            batch_op.drop_column("scholarship_notes")
        if _has_column("students", "scholarship_covers_feeding"):
            batch_op.drop_column("scholarship_covers_feeding")
        if _has_column("students", "scholarship_covers_tuition"):
            batch_op.drop_column("scholarship_covers_tuition")
        if _has_column("students", "is_on_scholarship"):
            batch_op.drop_column("is_on_scholarship")
