"""add platform settings table

Revision ID: c4a1e2f9b7d3
Revises: 8c0f4c4a6f21
Create Date: 2026-08-01 09:20:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "c4a1e2f9b7d3"
down_revision: Union[str, Sequence[str], None] = "8c0f4c4a6f21"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "platform_settings" in inspector.get_table_names():
        return

    value_default = sa.text("'{}'::json")
    if bind.dialect.name == "sqlite":
        value_default = sa.text("'{}'")

    op.create_table(
        "platform_settings",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("setting_key", sa.String(length=120), nullable=False),
        sa.Column("setting_value", sa.JSON(), nullable=False, server_default=value_default),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("setting_key"),
    )
    op.create_index("ix_platform_settings_setting_key", "platform_settings", ["setting_key"], unique=True)


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "platform_settings" not in inspector.get_table_names():
        return

    op.drop_index("ix_platform_settings_setting_key", table_name="platform_settings")
    op.drop_table("platform_settings")