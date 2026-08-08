"""add payment created by user

Revision ID: e8d1f4a2c6b7
Revises: c7d6e5f4a3b2
Create Date: 2026-08-08 15:05:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "e8d1f4a2c6b7"
down_revision: Union[str, Sequence[str], None] = "c7d6e5f4a3b2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_column(table_name: str, column_name: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = [c["name"] for c in inspector.get_columns(table_name)]
    return column_name in columns


def _has_foreign_key(table_name: str, constraint_name: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    foreign_keys = inspector.get_foreign_keys(table_name)
    return any((foreign_key.get("name") or "") == constraint_name for foreign_key in foreign_keys)


def upgrade() -> None:
    """Upgrade schema."""
    with op.batch_alter_table("payments", schema=None) as batch_op:
        if not _has_column("payments", "created_by_user_id"):
            batch_op.add_column(
                sa.Column(
                    "created_by_user_id",
                    sa.Integer(),
                    nullable=True,
                )
            )
        if not _has_foreign_key("payments", "fk_payments_created_by_user_id_users"):
            batch_op.create_foreign_key(
                "fk_payments_created_by_user_id_users",
                "users",
                ["created_by_user_id"],
                ["id"],
            )


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table("payments", schema=None) as batch_op:
        if _has_foreign_key("payments", "fk_payments_created_by_user_id_users"):
            batch_op.drop_constraint(
                "fk_payments_created_by_user_id_users",
                type_="foreignkey",
            )
        if _has_column("payments", "created_by_user_id"):
            batch_op.drop_column("created_by_user_id")