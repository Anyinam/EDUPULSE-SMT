"""Add student status tracking for enrollment management

Revision ID: f9d2c8e3a4b5
Revises: af935fa0e071
Create Date: 2026-02-28 09:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'f9d2c8e3a4b5'
down_revision = 'af935fa0e071'
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    cols = {c["name"] for c in inspector.get_columns("students")}
    if "status" not in cols:
        op.add_column("students", sa.Column("status", sa.String(20), nullable=False, server_default="Active"))
    if "status_updated_at" not in cols:
        op.add_column("students", sa.Column("status_updated_at", sa.DateTime(), nullable=True))
    if "status_updated_by_user_id" not in cols:
        op.add_column("students", sa.Column("status_updated_by_user_id", sa.Integer(), nullable=True))
    if "status_reason" not in cols:
        op.add_column("students", sa.Column("status_reason", sa.String(255), nullable=True))

    fk_names = {fk.get("name") for fk in inspector.get_foreign_keys("students")}
    if "fk_students_status_updated_by_user" not in fk_names:
        with op.batch_alter_table("students", schema=None) as batch_op:
            batch_op.create_foreign_key(
                "fk_students_status_updated_by_user",
                "users",
                ["status_updated_by_user_id"],
                ["id"],
            )

    index_names = {idx.get("name") for idx in inspector.get_indexes("students")}
    if "ix_students_status" not in index_names:
        op.create_index("ix_students_status", "students", ["status"])


def downgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    index_names = {idx.get("name") for idx in inspector.get_indexes("students")}
    if "ix_students_status" in index_names:
        op.drop_index("ix_students_status", table_name="students")

    fk_names = {fk.get("name") for fk in inspector.get_foreign_keys("students")}
    if "fk_students_status_updated_by_user" in fk_names:
        with op.batch_alter_table("students", schema=None) as batch_op:
            batch_op.drop_constraint("fk_students_status_updated_by_user", type_="foreignkey")

    cols = {c["name"] for c in inspector.get_columns("students")}
    if "status_reason" in cols:
        op.drop_column("students", "status_reason")
    if "status_updated_by_user_id" in cols:
        op.drop_column("students", "status_updated_by_user_id")
    if "status_updated_at" in cols:
        op.drop_column("students", "status_updated_at")
    if "status" in cols:
        op.drop_column("students", "status")
