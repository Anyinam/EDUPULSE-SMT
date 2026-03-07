"""merge_migration_heads

Revision ID: dcf6a4b879a4
Revises: ps001_subaccounts, c2f820b101bd
Create Date: 2026-03-04 18:36:47.292360

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'dcf6a4b879a4'
down_revision: Union[str, Sequence[str], None] = ('ps001_subaccounts', 'c2f820b101bd')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
