"""add anniversary date to school settings

Revision ID: 24271819c34a
Revises: 0f3a2b9c6b1d
Create Date: 2026-02-24 08:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '24271819c34a'
down_revision: Union[str, None] = '0f3a2b9c6b1d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add anniversary_date column to school_settings table
    op.add_column('school_settings', sa.Column('anniversary_date', sa.Date(), nullable=True))


def downgrade() -> None:
    # Remove anniversary_date column from school_settings table
    op.drop_column('school_settings', 'anniversary_date')
