"""remove exam papers feature tables

Revision ID: b91d5f7c2a11
Revises: 7a8b9c0d1e2f
Create Date: 2026-05-21 12:00:00.000000
"""

from alembic import op


# revision identifiers, used by Alembic.
revision = "b91d5f7c2a11"
down_revision = "7a8b9c0d1e2f"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("DROP INDEX IF EXISTS ix_exam_papers_subject_name")
    op.execute("DROP INDEX IF EXISTS ix_exam_papers_class_name")
    op.execute("DROP INDEX IF EXISTS ix_exam_papers_teacher_id")
    op.execute("DROP INDEX IF EXISTS ix_exam_papers_school_id")
    op.execute("DROP TABLE IF EXISTS exam_papers")


def downgrade():
    op.execute(
        """
    CREATE TABLE IF NOT EXISTS exam_papers (
        id INTEGER PRIMARY KEY,
        school_id VARCHAR(20) NOT NULL,
        teacher_id INTEGER NOT NULL,
        class_name VARCHAR(50) NOT NULL,
        subject_name VARCHAR(100) NOT NULL,
        academic_term VARCHAR(20),
        academic_year VARCHAR(20),
        exam_type VARCHAR(50),
        title VARCHAR(255) NOT NULL,
        instructions TEXT,
        total_marks INTEGER,
        duration_minutes INTEGER,
        questions JSON NOT NULL,
        status VARCHAR(20),
        created_at DATETIME NOT NULL,
        updated_at DATETIME,
        finalized_at DATETIME,
        FOREIGN KEY(school_id) REFERENCES schools(id),
        FOREIGN KEY(teacher_id) REFERENCES users(id)
    )
    """
    )
    op.execute("CREATE INDEX IF NOT EXISTS ix_exam_papers_school_id ON exam_papers (school_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_exam_papers_teacher_id ON exam_papers (teacher_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_exam_papers_class_name ON exam_papers (class_name)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_exam_papers_subject_name ON exam_papers (subject_name)")