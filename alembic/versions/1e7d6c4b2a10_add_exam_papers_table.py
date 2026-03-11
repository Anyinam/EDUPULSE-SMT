"""Add exam papers table

Revision ID: 1e7d6c4b2a10
Revises: 9a1c2d3e4f55
Create Date: 2026-03-09 22:45:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "1e7d6c4b2a10"
down_revision: Union[str, Sequence[str], None] = "9a1c2d3e4f55"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if "exam_papers" not in inspector.get_table_names():
        op.create_table(
            "exam_papers",
            sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
            sa.Column("school_id", sa.String(length=20), nullable=False),
            sa.Column("teacher_id", sa.Integer(), nullable=False),
            sa.Column("class_name", sa.String(length=50), nullable=False),
            sa.Column("subject_name", sa.String(length=100), nullable=False),
            sa.Column("academic_term", sa.String(length=20), nullable=True),
            sa.Column("academic_year", sa.String(length=20), nullable=True),
            sa.Column("exam_type", sa.String(length=50), nullable=True),
            sa.Column("title", sa.String(length=255), nullable=False),
            sa.Column("instructions", sa.Text(), nullable=True),
            sa.Column("total_marks", sa.Integer(), nullable=True),
            sa.Column("duration_minutes", sa.Integer(), nullable=True),
            sa.Column("questions", sa.JSON(), nullable=False),
            sa.Column("status", sa.String(length=20), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=True),
            sa.Column("finalized_at", sa.DateTime(), nullable=True),
            sa.ForeignKeyConstraint(["school_id"], ["schools.id"]),
            sa.ForeignKeyConstraint(["teacher_id"], ["users.id"]),
        )

    op.execute("CREATE INDEX IF NOT EXISTS ix_exam_papers_school_id ON exam_papers (school_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_exam_papers_teacher_id ON exam_papers (teacher_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_exam_papers_class_name ON exam_papers (class_name)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_exam_papers_subject_name ON exam_papers (subject_name)")


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_exam_papers_subject_name")
    op.execute("DROP INDEX IF EXISTS ix_exam_papers_class_name")
    op.execute("DROP INDEX IF EXISTS ix_exam_papers_teacher_id")
    op.execute("DROP INDEX IF EXISTS ix_exam_papers_school_id")
    op.execute("DROP TABLE IF EXISTS exam_papers")
