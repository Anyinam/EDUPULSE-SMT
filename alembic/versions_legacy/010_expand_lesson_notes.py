"""Expand lesson notes with structured fields and daily phases"""

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision = "010"
down_revision = "009"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("lesson_notes", sa.Column("class_name", sa.String(50), nullable=True))
    op.add_column(
        "lesson_notes", sa.Column("indicator_code", sa.String(50), nullable=True)
    )
    op.add_column(
        "lesson_notes", sa.Column("content_standard_code", sa.String(50), nullable=True)
    )
    op.add_column(
        "lesson_notes", sa.Column("performance_indicator", sa.Text(), nullable=True)
    )
    op.add_column(
        "lesson_notes", sa.Column("core_competencies", sa.Text(), nullable=True)
    )
    op.add_column("lesson_notes", sa.Column("key_words", sa.Text(), nullable=True))
    op.add_column(
        "lesson_notes",
        sa.Column("teaching_learning_resources", sa.Text(), nullable=True),
    )
    op.add_column("lesson_notes", sa.Column("references", sa.Text(), nullable=True))

    op.create_table(
        "daily_lesson_phases",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "lesson_note_id",
            sa.Integer(),
            sa.ForeignKey("lesson_notes.id"),
            nullable=False,
        ),
        sa.Column("day", sa.String(20), nullable=True),
        sa.Column("phase_1_starter", sa.Text(), nullable=True),
        sa.Column("phase_2_main", sa.Text(), nullable=True),
        sa.Column("phase_3_plenary", sa.Text(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(), server_default=sa.func.now(), nullable=True
        ),
    )


def downgrade():
    op.drop_table("daily_lesson_phases")
    op.drop_column("lesson_notes", "references")
    op.drop_column("lesson_notes", "teaching_learning_resources")
    op.drop_column("lesson_notes", "key_words")
    op.drop_column("lesson_notes", "core_competencies")
    op.drop_column("lesson_notes", "performance_indicator")
    op.drop_column("lesson_notes", "content_standard_code")
    op.drop_column("lesson_notes", "indicator_code")
    op.drop_column("lesson_notes", "class_name")
