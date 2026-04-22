"""add parent admission applications table

Revision ID: 3c4d5e6f7a8b
Revises: 1e7d6c4b2a10
Create Date: 2026-04-21 11:20:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "3c4d5e6f7a8b"
down_revision: Union[str, Sequence[str], None] = "1e7d6c4b2a10"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if "parent_admission_applications" not in inspector.get_table_names():
        op.create_table(
            "parent_admission_applications",
            sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
            sa.Column("school_id", sa.String(length=20), nullable=False),
            sa.Column("application_code", sa.String(length=40), nullable=False),
            sa.Column("status_token", sa.String(length=80), nullable=False),
            sa.Column("first_name", sa.String(length=50), nullable=False),
            sa.Column("surname", sa.String(length=50), nullable=False),
            sa.Column("gender", sa.String(length=10), nullable=True),
            sa.Column("date_of_birth", sa.Date(), nullable=True),
            sa.Column("preferred_class", sa.String(length=20), nullable=False),
            sa.Column("guardian_name", sa.Text(), nullable=True),
            sa.Column("parent_email", sa.Text(), nullable=True),
            sa.Column("parent_phone", sa.Text(), nullable=True),
            sa.Column("prior_school", sa.String(length=120), nullable=True),
            sa.Column("desired_test_mode", sa.String(length=20), nullable=True),
            sa.Column("internet_quality", sa.String(length=20), nullable=True),
            sa.Column("parent_notes", sa.Text(), nullable=True),
            sa.Column("document_manifest", sa.JSON(), nullable=True),
            sa.Column("ai_summary", sa.Text(), nullable=True),
            sa.Column("ai_recommendation", sa.String(length=40), nullable=True),
            sa.Column("ai_readiness_score", sa.Integer(), nullable=True),
            sa.Column("ai_flags", sa.JSON(), nullable=True),
            sa.Column("ai_missing_items", sa.JSON(), nullable=True),
            sa.Column("status", sa.String(length=30), nullable=True),
            sa.Column("submitted_at", sa.DateTime(), nullable=True),
            sa.Column("updated_at", sa.DateTime(), nullable=True),
            sa.Column("reviewed_at", sa.DateTime(), nullable=True),
            sa.Column("reviewed_by_user_id", sa.Integer(), nullable=True),
            sa.Column("reviewer_notes", sa.Text(), nullable=True),
            sa.Column("admitted_student_id", sa.Integer(), nullable=True),
            sa.ForeignKeyConstraint(["school_id"], ["schools.id"]),
            sa.ForeignKeyConstraint(["reviewed_by_user_id"], ["users.id"]),
            sa.ForeignKeyConstraint(["admitted_student_id"], ["students.id"]),
            sa.UniqueConstraint("application_code", name="uq_parent_admission_application_code"),
            sa.UniqueConstraint("status_token", name="uq_parent_admission_status_token"),
        )

    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_parent_admission_school_status "
        "ON parent_admission_applications (school_id, status)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_parent_admission_school_status")
    op.execute("DROP TABLE IF EXISTS parent_admission_applications")