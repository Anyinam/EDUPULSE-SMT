"""encrypt pii fields

Revision ID: 6e3c1dbe8b9b
Revises: fd316f298b32
Create Date: 2026-02-22 15:10:00.000000
"""

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision = "6e3c1dbe8b9b"
down_revision = "fd316f298b32"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("users", schema=None) as batch_op:
        batch_op.alter_column(
            "email", existing_type=sa.String(length=100), type_=sa.Text()
        )

    with op.batch_alter_table("students", schema=None) as batch_op:
        batch_op.alter_column(
            "guardian_name", existing_type=sa.String(length=100), type_=sa.Text()
        )
        batch_op.alter_column(
            "parent_name", existing_type=sa.String(length=100), type_=sa.Text()
        )
        batch_op.alter_column(
            "parent_phone", existing_type=sa.String(length=20), type_=sa.Text()
        )
        batch_op.alter_column(
            "parent_email", existing_type=sa.String(length=100), type_=sa.Text()
        )


def downgrade():
    with op.batch_alter_table("students", schema=None) as batch_op:
        batch_op.alter_column(
            "parent_email", existing_type=sa.Text(), type_=sa.String(length=100)
        )
        batch_op.alter_column(
            "parent_phone", existing_type=sa.Text(), type_=sa.String(length=20)
        )
        batch_op.alter_column(
            "parent_name", existing_type=sa.Text(), type_=sa.String(length=100)
        )
        batch_op.alter_column(
            "guardian_name", existing_type=sa.Text(), type_=sa.String(length=100)
        )

    with op.batch_alter_table("users", schema=None) as batch_op:
        batch_op.alter_column(
            "email", existing_type=sa.Text(), type_=sa.String(length=100)
        )
