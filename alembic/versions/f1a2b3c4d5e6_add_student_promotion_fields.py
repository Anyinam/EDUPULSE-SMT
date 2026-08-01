"""add student promotion fields

Revision ID: f1a2b3c4d5e6
Revises: e6b1c2d3f4a5
Create Date: 2026-08-01 11:55:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "f1a2b3c4d5e6"
down_revision: Union[str, Sequence[str], None] = "e6b1c2d3f4a5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_column(table_name: str, column_name: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = [column["name"] for column in inspector.get_columns(table_name)]
    return column_name in columns


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    fk_names = {fk.get("name") for fk in inspector.get_foreign_keys("students")}

    with op.batch_alter_table("students", schema=None) as batch_op:
        if not _has_column("students", "last_promoted_date"):
            batch_op.add_column(sa.Column("last_promoted_date", sa.DateTime(), nullable=True))
        if not _has_column("students", "last_promoted_by_user_id"):
            batch_op.add_column(sa.Column("last_promoted_by_user_id", sa.Integer(), nullable=True))

    if (
        _has_column("students", "last_promoted_by_user_id")
        and "fk_students_last_promoted_by_user" not in fk_names
    ):
        with op.batch_alter_table("students", schema=None) as batch_op:
            batch_op.create_foreign_key(
                "fk_students_last_promoted_by_user",
                "users",
                ["last_promoted_by_user_id"],
                ["id"],
            )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    fk_names = {fk.get("name") for fk in inspector.get_foreign_keys("students")}

    if "fk_students_last_promoted_by_user" in fk_names:
        with op.batch_alter_table("students", schema=None) as batch_op:
            batch_op.drop_constraint("fk_students_last_promoted_by_user", type_="foreignkey")

    with op.batch_alter_table("students", schema=None) as batch_op:
        if _has_column("students", "last_promoted_by_user_id"):
            batch_op.drop_column("last_promoted_by_user_id")
        if _has_column("students", "last_promoted_date"):
            batch_op.drop_column("last_promoted_date")