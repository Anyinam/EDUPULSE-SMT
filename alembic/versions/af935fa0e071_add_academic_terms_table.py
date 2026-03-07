"""add_academic_terms_table

Revision ID: af935fa0e071
Revises: 372cb324fac8
Create Date: 2026-02-24 14:33:17.708787

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'af935fa0e071'
down_revision: Union[str, Sequence[str], None] = '372cb324fac8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema - Add academic_terms table for term management."""
    op.create_table(
        'academic_terms',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('school_id', sa.String(length=20), nullable=False),
        sa.Column('name', sa.String(length=50), nullable=False),
        sa.Column('academic_year', sa.String(length=20), nullable=False),
        sa.Column('start_date', sa.Date(), nullable=False),
        sa.Column('end_date', sa.Date(), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=True),
        sa.Column('billing_due_date', sa.Date(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('created_by', sa.Integer(), nullable=True),
        sa.CheckConstraint('end_date > start_date', name='ck_term_dates_valid'),
        sa.ForeignKeyConstraint(['created_by'], ['users.id'], ),
        sa.ForeignKeyConstraint(['school_id'], ['schools.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('school_id', 'academic_year', 'name', name='uq_school_term_year')
    )


def downgrade() -> None:
    """Downgrade schema - Remove academic_terms table."""
    op.drop_table('academic_terms')
