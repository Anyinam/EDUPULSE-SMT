"""Add StudentAssignment, ClassGradingPolicy, and class_name to StudentGrade.

Revision ID: 003
Revises:
Create Date: 2026-02-13 17:00:00.000000

"""

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision = "003"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add class_name column to student_grade if it doesn't exist
    with op.batch_alter_table("student_grade", schema=None) as batch_op:
        batch_op.add_column(sa.Column("class_name", sa.String(20), nullable=True))

    # Create student_assignments table
    op.create_table(
        "student_assignment",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("student_id", sa.Integer(), nullable=False),
        sa.Column("school_id", sa.String(50), nullable=False),
        sa.Column("subject", sa.String(100), nullable=False),
        sa.Column("score", sa.Float(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["student_id"],
            ["student.id"],
        ),
        sa.ForeignKeyConstraint(
            ["school_id"],
            ["school.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    # Create class_grading_policies table
    op.create_table(
        "class_grading_policy",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("school_id", sa.String(50), nullable=False),
        sa.Column("class_name", sa.String(20), nullable=False),
        sa.Column(
            "assignment_weight", sa.Integer(), nullable=False, server_default="30"
        ),
        sa.Column("min_assignments", sa.Integer(), nullable=False, server_default="5"),
        sa.ForeignKeyConstraint(
            ["school_id"],
            ["school.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("school_id", "class_name"),
    )


def downgrade() -> None:
    # Drop class_grading_policies table
    op.drop_table("class_grading_policy")

    # Drop student_assignments table
    op.drop_table("student_assignment")

    # Remove class_name from student_grade
    with op.batch_alter_table("student_grade", schema=None) as batch_op:
        batch_op.drop_column("class_name")
