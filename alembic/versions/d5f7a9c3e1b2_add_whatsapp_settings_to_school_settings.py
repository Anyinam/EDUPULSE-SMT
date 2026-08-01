"""add whatsapp settings to school settings

Revision ID: d5f7a9c3e1b2
Revises: c4a1e2f9b7d3
Create Date: 2026-08-01 09:30:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "d5f7a9c3e1b2"
down_revision: Union[str, Sequence[str], None] = "c4a1e2f9b7d3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_column(table_name: str, column_name: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = [column["name"] for column in inspector.get_columns(table_name)]
    return column_name in columns


def upgrade() -> None:
    with op.batch_alter_table("school_settings", schema=None) as batch_op:
        if not _has_column("school_settings", "whatsapp_daily_limit"):
            batch_op.add_column(
                sa.Column("whatsapp_daily_limit", sa.Integer(), nullable=True, server_default="50")
            )
        if not _has_column("school_settings", "whatsapp_notifications_enabled"):
            batch_op.add_column(
                sa.Column(
                    "whatsapp_notifications_enabled",
                    sa.Boolean(),
                    nullable=True,
                    server_default=sa.true(),
                )
            )


def downgrade() -> None:
    with op.batch_alter_table("school_settings", schema=None) as batch_op:
        if _has_column("school_settings", "whatsapp_notifications_enabled"):
            batch_op.drop_column("whatsapp_notifications_enabled")
        if _has_column("school_settings", "whatsapp_daily_limit"):
            batch_op.drop_column("whatsapp_daily_limit")