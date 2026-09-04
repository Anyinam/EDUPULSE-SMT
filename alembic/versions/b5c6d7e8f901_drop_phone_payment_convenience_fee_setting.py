"""drop phone payment convenience fee setting

Revision ID: b5c6d7e8f901
Revises: a4d9f3c2b1e0
Create Date: 2026-09-04 00:00:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision: str = "b5c6d7e8f901"
down_revision: Union[str, Sequence[str], None] = "a4d9f3c2b1e0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


_COLUMN_NAME = "phone_payment_convenience_fee_percent"
_TABLE_NAME = "school_settings"


def _has_column(column_name: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = {column["name"] for column in inspector.get_columns(_TABLE_NAME)}
    return column_name in columns


def upgrade() -> None:
    """Upgrade schema."""
    if not _has_column(_COLUMN_NAME):
        return

    with op.batch_alter_table(_TABLE_NAME, schema=None) as batch_op:
        batch_op.drop_column(_COLUMN_NAME)


def downgrade() -> None:
    """Downgrade schema."""
    if _has_column(_COLUMN_NAME):
        return

    with op.batch_alter_table(_TABLE_NAME, schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(
                _COLUMN_NAME,
                sa.Float(),
                nullable=True,
                server_default="1.5",
            )
        )
