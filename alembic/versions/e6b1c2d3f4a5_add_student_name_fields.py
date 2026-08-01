"""add student name fields

Revision ID: e6b1c2d3f4a5
Revises: d5f7a9c3e1b2
Create Date: 2026-08-01 11:45:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "e6b1c2d3f4a5"
down_revision: Union[str, Sequence[str], None] = "d5f7a9c3e1b2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_column(table_name: str, column_name: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = [column["name"] for column in inspector.get_columns(table_name)]
    return column_name in columns


def upgrade() -> None:
    with op.batch_alter_table("students", schema=None) as batch_op:
        if not _has_column("students", "first_name"):
            batch_op.add_column(sa.Column("first_name", sa.String(length=50), nullable=True))
        if not _has_column("students", "surname"):
            batch_op.add_column(sa.Column("surname", sa.String(length=50), nullable=True))
        if not _has_column("students", "gender"):
            batch_op.add_column(sa.Column("gender", sa.String(length=10), nullable=True))

    bind = op.get_bind()
    student_rows = bind.execute(
        sa.text(
            """
            SELECT id, name, first_name, surname
            FROM students
            WHERE first_name IS NULL OR surname IS NULL
            """
        )
    ).mappings()

    for row in student_rows:
        full_name = (row.get("name") or "Student").strip()
        name_parts = [part for part in full_name.split() if part]
        resolved_first_name = (row.get("first_name") or "").strip() or (name_parts[0] if name_parts else "Student")
        resolved_surname = (row.get("surname") or "").strip() or (" ".join(name_parts[1:]) if len(name_parts) > 1 else resolved_first_name)

        bind.execute(
            sa.text(
                """
                UPDATE students
                SET first_name = :first_name, surname = :surname
                WHERE id = :student_id
                """
            ),
            {
                "student_id": row["id"],
                "first_name": resolved_first_name,
                "surname": resolved_surname,
            },
        )

    with op.batch_alter_table("students", schema=None) as batch_op:
        batch_op.alter_column("first_name", existing_type=sa.String(length=50), nullable=False)
        batch_op.alter_column("surname", existing_type=sa.String(length=50), nullable=False)


def downgrade() -> None:
    with op.batch_alter_table("students", schema=None) as batch_op:
        if _has_column("students", "gender"):
            batch_op.drop_column("gender")
        if _has_column("students", "surname"):
            batch_op.drop_column("surname")
        if _has_column("students", "first_name"):
            batch_op.drop_column("first_name")