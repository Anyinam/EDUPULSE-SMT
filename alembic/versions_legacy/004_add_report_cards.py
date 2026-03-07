"""Add ReportCard model for terminal report cards

Revision ID: 004
Revises: 003
Create Date: 2024-01-20

"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision = "004"
down_revision = "003"
branch_labels = None
depends_on = None


def upgrade():
    # Create report_cards table
    op.create_table(
        "report_cards",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "school_id", sa.String(20), sa.ForeignKey("schools.id"), nullable=False
        ),
        sa.Column(
            "student_id", sa.Integer(), sa.ForeignKey("students.id"), nullable=False
        ),
        sa.Column("academic_term", sa.String(20), nullable=False),
        sa.Column("academic_year", sa.String(20), nullable=False),
        sa.Column("class_name", sa.String(20), nullable=True),
        sa.Column("subject_grades", sa.JSON(), nullable=True),
        sa.Column("total_marks_obtained", sa.Float(), nullable=True),
        sa.Column("total_possible_marks", sa.Float(), nullable=True),
        sa.Column("term_average", sa.Float(), nullable=True),
        sa.Column("overall_position", sa.String(10), nullable=True),
        sa.Column("out_of_students", sa.Integer(), nullable=True),
        sa.Column("attendance_percentage", sa.Float(), nullable=True),
        sa.Column("total_attendance", sa.Integer(), nullable=True),
        sa.Column("homeroom_teacher_remarks", sa.Text(), nullable=True),
        sa.Column("headmaster_remarks", sa.Text(), nullable=True),
        sa.Column("proprietor_remarks", sa.Text(), nullable=True),
        sa.Column("ai_performance_analysis", sa.Text(), nullable=True),
        sa.Column("status", sa.String(20), default="Draft"),
        sa.Column("created_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("submitted_at", sa.DateTime(), nullable=True),
        sa.Column("headmaster_approved_at", sa.DateTime(), nullable=True),
        sa.Column(
            "headmaster_approved_by",
            sa.Integer(),
            sa.ForeignKey("users.id"),
            nullable=True,
        ),
        sa.Column("proprietor_approved_at", sa.DateTime(), nullable=True),
        sa.Column(
            "proprietor_approved_by",
            sa.Integer(),
            sa.ForeignKey("users.id"),
            nullable=True,
        ),
        sa.Column("printed_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
    )

    # Create index for faster lookups
    op.create_index(
        "ix_report_cards_student_term",
        "report_cards",
        ["student_id", "academic_term", "academic_year"],
        unique=True,
    )
    op.create_index("ix_report_cards_status", "report_cards", ["status"])


def downgrade():
    op.drop_index("ix_report_cards_status")
    op.drop_index("ix_report_cards_student_term")
    op.drop_table("report_cards")
