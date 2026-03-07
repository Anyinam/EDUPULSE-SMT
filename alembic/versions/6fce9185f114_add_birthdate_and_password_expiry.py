"""add_birthdate_and_password_expiry

Revision ID: 6fce9185f114
Revises: dcf6a4b879a4
Create Date: 2026-03-04 18:36:53.745559

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '6fce9185f114'
down_revision: Union[str, Sequence[str], None] = 'dcf6a4b879a4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Add birthdate to students table
    with op.batch_alter_table('students', schema=None) as batch_op:
        batch_op.add_column(sa.Column('date_of_birth', sa.Date(), nullable=True))
    
    # Add temporary password fields to users table
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.add_column(sa.Column('is_temp_password', sa.Boolean(), default=False, server_default='0'))
        batch_op.add_column(sa.Column('temp_password_expires_at', sa.DateTime(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    # Remove birthdate from students
    with op.batch_alter_table('students', schema=None) as batch_op:
        batch_op.drop_column('date_of_birth')
    
    # Remove temporary password fields from users
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.drop_column('temp_password_expires_at')
        batch_op.drop_column('is_temp_password')
